# Cxplus Bulk Mailer (minimal)

Terminal-only CLI to send templated emails to a list of leads **via Namecheap PrivateEmail SMTP**.

- **No UI**
- **No database**
- Takes **exactly 2 arguments**: (1) CSV path (2) template txt path
- Uses SMTP **STARTTLS** (port 587)
- Optional safety knobs via `.env` (dry-run, rate limit, max emails, BCC self)

## 1) Setup

### Requirements
- Python 3.10+ (3.8+ likely OK)

### Install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configure SMTP (do NOT commit secrets)
Copy `.env.example` to `.env` and fill in values:

```bash
cp .env.example .env
```

Then edit `.env`:
- `SMTP_USERNAME` should be `bishwajit@cxplus.ai`
- `SMTP_PASSWORD` should be your **PrivateEmail app password**
- `SMTP_HOST` is `mail.privateemail.com`
- `SMTP_PORT` is `587`
- `SMTP_USE_STARTTLS` should be `true`

Tip: Keep `BCC_SELF=true` initially so every message is also delivered to your own mailbox (useful if Sent doesn't show SMTP submissions).

## 2) Input files

### Leads CSV (argument #1)
`examples/leads.csv`:
```csv
company,name,email
Acme Inc,Jane Doe,jane@example.com
Beta Ltd,John Smith,john@example.com
```

### Email template (argument #2)
`examples/email_template.txt`:

First line must start with `Subject:`. Everything after is the body.

Supported placeholders:
- `{{company}}`
- `{{name}}`
- `{{email}}`

Example:
```
Subject: Quick question about {{company}}'s customer feedback workflow

Hi {{name}},

I'm Bish from Cxplus.ai...
```

## 3) Run

### Dry run (recommended first)
Set in `.env`:
```
DRY_RUN=true
```

Then:
```bash
python send_bulk.py examples/leads.csv examples/email_template.txt
```

### Actually send
Set:
```
DRY_RUN=false
```

Then run the same command.

## 4) Notes / Safety

- Use `RATE_LIMIT_SECONDS=1` (or higher) to avoid provider throttling.
- Use `MAX_EMAILS` as a guardrail while testing.
- This tool prints a per-recipient status line and a final summary.
- If you want the email to reliably appear in your mailbox, keep `BCC_SELF=true`.

## 5) Troubleshooting

- Auth error: verify app password, username (full email), and STARTTLS (587).
- Connection error: verify `mail.privateemail.com:587` is reachable.
- Template error: ensure first line starts with `Subject:`.

---

**Disclaimer:** Ensure you comply with applicable anti-spam laws and only email leads you have a lawful basis to contact.
