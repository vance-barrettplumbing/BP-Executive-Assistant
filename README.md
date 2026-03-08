# BP Executive Assistant

A digital executive assistant for Barrett Plumbing that runs a morning brief every weekday at 4 AM.

## What it does

Each weekday morning the assistant:

1. **Rolls over incomplete tasks** – reads the previous weekday's Capacities daily note, finds any unchecked `[ ]` tasks, and adds them to today's note.
2. **Pulls Todoist tasks** – fetches every Todoist task scheduled for today and adds it to today's Capacities daily note.
3. **Pulls Gmail action items** – searches your work Gmail inbox using a configurable query (default: starred + unread) and any Google Tasks due today, and adds them as to-do items in today's Capacities daily note.

---

## Requirements

- Python 3.10+
- A Linux server or always-on machine (runs via cron)
- Accounts: [Capacities](https://capacities.io), [Todoist](https://todoist.com), [Gmail / Google Workspace](https://workspace.google.com)

---

## Setup

### 1. Clone and run the setup script

```bash
git clone <repo-url> BP-Executive-Assistant
cd BP-Executive-Assistant
bash setup.sh
```

The script will:
- Create a Python virtual environment
- Install dependencies
- Copy `.env.example` → `.env`
- Offer to install the cron job automatically

---

### 2. Configure API credentials

Edit the `.env` file:

```bash
nano .env
```

#### Capacities

1. Open Capacities → **Settings → API**
2. Generate an API token and copy it → `CAPACITIES_API_TOKEN`
3. Find your Space ID in the URL (`/space/<id>/`) → `CAPACITIES_SPACE_ID`

#### Todoist

1. Open Todoist → **Settings → Integrations → Developer**
2. Copy your API token → `TODOIST_API_TOKEN`

#### Gmail / Google

See the next section.

---

### 3. Set up Google OAuth (Gmail + Google Tasks)

The Gmail and Google Tasks integration requires a one-time OAuth consent flow.

#### Create credentials in Google Cloud Console

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (e.g. **BP Executive Assistant**)
3. Enable these two APIs:
   - **Gmail API**
   - **Google Tasks API**
4. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**
5. Application type: **Desktop app**
6. Download the JSON file
7. Save it as `config/google_credentials.json` in this project

#### Run the one-time auth flow

```bash
source .venv/bin/activate
python src/integrations/gmail.py --auth
```

A browser window will open. Sign in with your work Google account and grant the requested permissions. The token is saved to `config/google_token.json` and all future runs are silent.

---

### 4. Configure the Gmail search query

The `GMAIL_DUE_TODAY_QUERY` variable in `.env` controls which emails are treated as action items. The default (`is:starred is:unread`) picks up starred, unread emails.

Other useful examples:

| Query | What it finds |
|---|---|
| `label:follow-up` | Emails you labelled "follow-up" |
| `label:action-required is:unread` | Emails with a custom "action-required" label |
| `is:starred is:unread newer_than:7d` | Starred unread emails from the last 7 days |

> **Tip:** Create a Gmail label called `Follow Up` and apply it to emails that need action. Set the query to `label:follow-up` for clean, intentional control.

---

### 5. Test the assistant

```bash
source .venv/bin/activate
python src/morning_brief.py
```

Check your Capacities daily note for today – you should see new sections appended.

---

### 6. Cron schedule

The setup script offers to install the cron job for you. To verify or add it manually:

```bash
crontab -e
```

Add this line (replacing `/path/to` with your actual path):

```
0 4 * * 1-5 cd /path/to/BP-Executive-Assistant && .venv/bin/python src/morning_brief.py >> logs/cron.log 2>&1
```

- Runs at **4:00 AM, Monday–Friday**
- Output is appended to `logs/cron.log`

---

## Project structure

```
BP-Executive-Assistant/
├── src/
│   ├── morning_brief.py          # Main orchestrator (entry point)
│   └── integrations/
│       ├── capacities.py         # Capacities API client
│       ├── todoist.py            # Todoist REST API client
│       └── gmail.py              # Gmail + Google Tasks client
├── config/
│   ├── google_credentials.json   # (you add this – gitignored)
│   └── google_token.json         # (auto-generated – gitignored)
├── logs/                         # Runtime logs (gitignored)
├── .env                          # Your secrets (gitignored)
├── .env.example                  # Template
├── requirements.txt
└── setup.sh
```

---

## What gets added to your Capacities daily note

Each morning brief appends a block like this:

```markdown
---
### Rolled Over from Yesterday

- [ ] Call back Mike re: water heater quote
- [ ] Order 3/4" copper fittings from supplier

### Todoist Tasks

- [ ] Invoice #1042 – follow up with Henderson property 🟠
- [ ] Schedule crew for Thursday job (Oak Street)

### Google Tasks

- [ ] Submit insurance renewal (Admin)

### Email Follow-ups

- [ ] **Re: Emergency repair – 42 Maple Ave**  *(from Sarah Henderson)*
  - Hi, just following up on the quote you sent last week…
  - [Open in Gmail](https://mail.google.com/...)
```

---

## Troubleshooting

**Nothing appears in my Capacities note**
- Check `logs/cron.log` or run manually and read the output
- Verify your `CAPACITIES_API_TOKEN` and `CAPACITIES_SPACE_ID` are correct

**Gmail auth fails**
- Delete `config/google_token.json` and re-run `python src/integrations/gmail.py --auth`

**Cron job not running**
- Confirm cron is active: `systemctl status cron`
- Check `/var/log/syslog` for cron execution entries
- Make sure the path in your crontab line is absolute
