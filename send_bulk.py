#!/usr/bin/env python3
import csv
import os
import sys
import time
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Dict, List, Tuple

import markdown
from dotenv import load_dotenv

PLACEHOLDERS = ("company", "name", "email")


@dataclass(frozen=True)
class Config:
    smtp_host: str
    smtp_port: int
    use_starttls: bool
    username: str
    password: str
    from_name: str
    bcc_self: bool
    bcc_address: str
    dry_run: bool
    rate_limit_seconds: float
    max_emails: int  # 0 = no limit


def _env_bool(key: str, default: bool = False) -> bool:
    v = os.getenv(key, str(default)).strip().lower()
    return v in ("1", "true", "yes", "y", "on")


def _env_int(key: str, default: int) -> int:
    v = os.getenv(key, "").strip()
    return int(v) if v else default


def _env_float(key: str, default: float) -> float:
    v = os.getenv(key, "").strip()
    return float(v) if v else default


def load_config() -> Config:
    load_dotenv()  # loads .env if present
    host = os.getenv("SMTP_HOST", "mail.privateemail.com").strip()
    port = _env_int("SMTP_PORT", 587)
    use_starttls = _env_bool("SMTP_USE_STARTTLS", True)

    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    if not username or not password:
        raise ValueError("Missing SMTP_USERNAME or SMTP_PASSWORD. Set them in .env (see .env.example).")

    from_name = os.getenv("FROM_NAME", "").strip() or username

    bcc_self = _env_bool("BCC_SELF", False)
    bcc_address = os.getenv("BCC_ADDRESS", "").strip() or username

    dry_run = _env_bool("DRY_RUN", True)
    rate_limit_seconds = _env_float("RATE_LIMIT_SECONDS", 1.0)
    max_emails = _env_int("MAX_EMAILS", 0)

    return Config(
        smtp_host=host,
        smtp_port=port,
        use_starttls=use_starttls,
        username=username,
        password=password,
        from_name=from_name,
        bcc_self=bcc_self,
        bcc_address=bcc_address,
        dry_run=dry_run,
        rate_limit_seconds=rate_limit_seconds,
        max_emails=max_emails,
    )


def read_template(path: str) -> Tuple[str, str]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    lines = text.splitlines()
    if not lines or not lines[0].lower().startswith("subject:"):
        raise ValueError("Template first line must start with 'Subject:'.")
    subject = lines[0].split(":", 1)[1].strip()
    body = "\n".join(lines[1:]).lstrip("\n")
    return subject, body


def read_leads_csv(path: str) -> List[Dict[str, str]]:
    leads: List[Dict[str, str]] = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"company", "name", "email"}
        if not reader.fieldnames or not required.issubset({h.strip().lower() for h in reader.fieldnames}):
            raise ValueError("CSV must include headers: company,name,email")

        for row in reader:
            # Normalize keys
            norm = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
            if not norm.get("email"):
                continue
            leads.append(norm)
    return leads


def render(template: str, lead: Dict[str, str]) -> str:
    out = template
    for k in PLACEHOLDERS:
        out = out.replace("{{" + k + "}}", lead.get(k, ""))
    return out


def markdown_to_html(md_text: str) -> str:
    html_body = markdown.markdown(
        md_text,
        extensions=["extra", "sane_lists", "smarty"],
    )
    return f"""<!doctype html>
<html>
  <body>
    {html_body}
  </body>
</html>
"""


def build_message(cfg: Config, to_addr: str, subject: str, body: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = f"{cfg.from_name} <{cfg.username}>" if cfg.from_name and cfg.from_name != cfg.username else cfg.username
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Reply-To"] = cfg.username

    if cfg.bcc_self:
        msg["Bcc"] = cfg.bcc_address

    # Plain-text fallback (Markdown as-is)
    msg.set_content(body)

    # HTML version rendered from Markdown
    html = markdown_to_html(body)
    msg.add_alternative(html, subtype="html")

    return msg


def send_all(csv_path: str, template_path: str) -> int:
    cfg = load_config()
    subject_tmpl, body_tmpl = read_template(template_path)
    leads = read_leads_csv(csv_path)

    if cfg.max_emails > 0:
        leads = leads[: cfg.max_emails]

    print(
        f"Loaded {len(leads)} lead(s). DRY_RUN={cfg.dry_run} "
        f"BCC_SELF={cfg.bcc_self} RATE_LIMIT_SECONDS={cfg.rate_limit_seconds}"
    )

    sent = 0
    failed = 0

    server = None
    try:
        if not cfg.dry_run:
            server = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30)
            server.ehlo()
            if cfg.use_starttls:
                server.starttls()
                server.ehlo()
            server.login(cfg.username, cfg.password)

        for i, lead in enumerate(leads, start=1):
            to_addr = lead["email"]
            subject = render(subject_tmpl, lead)
            body = render(body_tmpl, lead)

            print(f"[{i}/{len(leads)}] Sending to {to_addr} ...", end=" ")

            try:
                msg = build_message(cfg, to_addr, subject, body)

                if cfg.dry_run:
                    print("DRY_RUN (not sent)")
                else:
                    server.send_message(msg)
                    print("OK")
                sent += 1
            except Exception as e:
                failed += 1
                print(f"FAILED: {e}")

            if cfg.rate_limit_seconds > 0 and i < len(leads):
                time.sleep(cfg.rate_limit_seconds)

    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass

    print(f"\nDone. Attempted={len(leads)} Sent={sent} Failed={failed}")
    return 0 if failed == 0 else 2


def main(argv: List[str]) -> int:
    if len(argv) != 3:
        print("Usage: python send_bulk.py /path/to/leads.csv /path/to/template.txt")
        return 1
    return send_all(argv[1], argv[2])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))