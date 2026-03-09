# BP Executive Assistant

A digital executive assistant for Barrett Plumbing that runs a morning brief every weekday at 4 AM.

## What it does

Each weekday morning the assistant:

1. **Rolls over incomplete tasks** – reads the previous weekday's Obsidian daily note, finds any unchecked `[ ]` tasks, and appends them to today's note. On Mondays it automatically looks back to Friday.
2. **Pulls Todoist tasks** – fetches every Todoist task scheduled for today and adds it to today's Obsidian daily note.
3. **Pulls Gmail action items** – searches your work Gmail inbox using a configurable query (default: starred + unread) and any Google Tasks due today, and adds them as to-do items in today's note.

---

## Requirements

- Python 3.10+
- A Linux server or always-on machine (runs via cron)
- Obsidian vault accessible as a local folder on the server
- Accounts: [Todoist](https://todoist.com), [Gmail / Google Workspace](https://workspace.google.com)

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

### 2. Configure environment variables

Edit `.env`:

```bash
nano .env
```

#### Obsidian

Set the path to your vault and the daily notes folder:

```env
OBSIDIAN_VAULT_PATH=/home/youruser/obsidian-vault
OBSIDIAN_DAILY_FOLDER=daily
```

The script reads and writes files at `<vault>/<daily_folder>/YYYY-MM-DD.md`.

> **Tip:** If your vault lives on another machine (laptop, NAS), sync it to the server first using [Syncthing](https://syncthing.net), [rclone](https://rclone.org), or git. The script just needs the folder to be present on disk.

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

A browser window opens. Sign in with your work Google account and grant permissions. The token saves to `config/google_token.json` – all future runs are silent.

---

### 4. Configure the Gmail search query

The `GMAIL_DUE_TODAY_QUERY` variable controls which emails are pulled as action items:

| Query | What it finds |
|---|---|
| `is:starred is:unread` | Starred unread emails *(default)* |
| `label:follow-up` | Emails with a "follow-up" label |
| `label:action-required is:unread` | Emails with a custom "action-required" label |
| `is:starred is:unread newer_than:7d` | Starred unread emails from the last 7 days |

> **Tip:** Create a Gmail label called `Follow Up` and apply it to emails that need action, then set `GMAIL_DUE_TODAY_QUERY=label:follow-up`.

---

### 5. Test the assistant

```bash
source .venv/bin/activate
python src/morning_brief.py
```

Check your Obsidian vault – today's daily note should have new sections appended.

---

### 6. Cron schedule

The setup script offers to install the cron job. To verify or add it manually:

```bash
crontab -e
```

Add this line (replace `/path/to` with your actual path):

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
│       ├── obsidian.py           # Reads/writes local Obsidian vault files
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

## What gets added to your Obsidian daily note

Each morning brief appends a block like this to `daily/YYYY-MM-DD.md`:

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

**Nothing appears in my daily note**
- Run manually and check the output: `source .venv/bin/activate && python src/morning_brief.py`
- Confirm `OBSIDIAN_VAULT_PATH` points to the correct directory
- Confirm `OBSIDIAN_DAILY_FOLDER` matches the folder name in your vault

**Gmail auth fails**
- Delete `config/google_token.json` and re-run `python src/integrations/gmail.py --auth`

**Cron job not running**
- Confirm cron is active: `systemctl status cron`
- Check `/var/log/syslog` for cron execution entries
- Make sure the path in your crontab is absolute
