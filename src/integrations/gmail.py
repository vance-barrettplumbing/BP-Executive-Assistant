"""
Gmail API integration.

Finds emails that represent action items due today based on a configurable
Gmail search query. Also checks Google Tasks for tasks due today.

First-run OAuth flow:
  Run `python src/integrations/gmail.py --auth` to complete the OAuth consent
  screen and save the token file. Subsequent runs use the saved token silently.

OAuth scopes required:
  https://www.googleapis.com/auth/gmail.readonly
  https://www.googleapis.com/auth/tasks.readonly
"""

import argparse
import logging
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/tasks.readonly",
]

# Maximum emails to inspect per run (safety cap)
MAX_EMAILS = 50


class GmailError(Exception):
    pass


class GmailClient:
    def __init__(self, credentials_file: str, token_file: str):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self._gmail = None
        self._tasks = None

    # ── Auth ───────────────────────────────────────────────────────────────────

    def _get_credentials(self) -> Credentials:
        creds: Optional[Credentials] = None
        token_path = Path(self.token_file)

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not Path(self.credentials_file).exists():
                    raise GmailError(
                        f"Google credentials file not found: {self.credentials_file}\n"
                        "Download it from Google Cloud Console and set GOOGLE_CREDENTIALS_FILE."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES
                )
                creds = flow.run_local_server(port=0)

            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json())
            logger.info("Saved Google OAuth token to %s", self.token_file)

        return creds

    def _gmail_service(self):
        if self._gmail is None:
            creds = self._get_credentials()
            self._gmail = build("gmail", "v1", credentials=creds)
        return self._gmail

    def _tasks_service(self):
        if self._tasks is None:
            creds = self._get_credentials()
            self._tasks = build("tasks", "v1", credentials=creds)
        return self._tasks

    # ── Gmail emails ───────────────────────────────────────────────────────────

    def get_due_emails(self, query: str) -> list[dict]:
        """
        Search Gmail using *query* and return matching email summaries.

        Each dict has:
          - subject  : email subject
          - sender   : From address
          - snippet  : short preview text
          - date     : received date string
          - thread_url: link to thread in Gmail web
        """
        try:
            service = self._gmail_service()
            result = (
                service.users()
                .messages()
                .list(userId="me", q=query, maxResults=MAX_EMAILS)
                .execute()
            )
        except HttpError as exc:
            raise GmailError(f"Gmail search failed: {exc}") from exc

        messages = result.get("messages", [])
        if not messages:
            logger.info("No Gmail messages matched query: %s", query)
            return []

        emails = []
        for msg_ref in messages:
            try:
                msg = (
                    service.users()
                    .messages()
                    .get(userId="me", id=msg_ref["id"], format="metadata",
                         metadataHeaders=["Subject", "From", "Date"])
                    .execute()
                )
                headers = {
                    h["name"]: h["value"]
                    for h in msg.get("payload", {}).get("headers", [])
                }
                emails.append(
                    {
                        "subject": headers.get("Subject", "(no subject)"),
                        "sender": headers.get("From", ""),
                        "snippet": msg.get("snippet", ""),
                        "date": headers.get("Date", ""),
                        "thread_url": (
                            f"https://mail.google.com/mail/#inbox/{msg['threadId']}"
                        ),
                    }
                )
            except HttpError as exc:
                logger.warning("Could not fetch message %s: %s", msg_ref["id"], exc)

        logger.info("Found %d Gmail message(s) matching: %s", len(emails), query)
        return emails

    # ── Google Tasks ───────────────────────────────────────────────────────────

    def get_google_tasks_due_on(self, target_date: date) -> list[dict]:
        """
        Return Google Tasks (from all task lists) that are due on *target_date*.

        Each dict has:
          - title    : task title
          - notes    : additional notes (may be empty)
          - list_name: name of the task list it belongs to
          - due      : ISO date string
        """
        # Google Tasks API uses RFC 3339 for the due-date filter
        due_min = datetime(
            target_date.year, target_date.month, target_date.day,
            0, 0, 0, tzinfo=timezone.utc
        ).isoformat()
        due_max = datetime(
            target_date.year, target_date.month, target_date.day,
            23, 59, 59, tzinfo=timezone.utc
        ).isoformat()

        try:
            service = self._tasks_service()
            task_lists = service.tasklists().list().execute().get("items", [])
        except HttpError as exc:
            raise GmailError(f"Google Tasks API failed: {exc}") from exc

        results = []
        for tl in task_lists:
            try:
                tasks_resp = (
                    service.tasks()
                    .list(
                        tasklist=tl["id"],
                        dueMin=due_min,
                        dueMax=due_max,
                        showCompleted=False,
                        showHidden=False,
                    )
                    .execute()
                )
                for task in tasks_resp.get("items", []):
                    results.append(
                        {
                            "title": task.get("title", ""),
                            "notes": task.get("notes", ""),
                            "list_name": tl.get("title", ""),
                            "due": task.get("due", ""),
                        }
                    )
            except HttpError as exc:
                logger.warning("Could not fetch tasks from list %s: %s", tl["id"], exc)

        logger.info(
            "Found %d Google Task(s) due on %s", len(results), target_date.isoformat()
        )
        return results


# ── Markdown formatters ────────────────────────────────────────────────────────

def format_emails_as_markdown(emails: list[dict]) -> str:
    if not emails:
        return ""
    lines = ["### Email Follow-ups", ""]
    for email in emails:
        sender_short = _short_sender(email["sender"])
        lines.append(f"- [ ] **{email['subject']}**  *(from {sender_short})*")
        if email["snippet"]:
            lines.append(f"  - {email['snippet'][:120].strip()}…")
        lines.append(f"  - [Open in Gmail]({email['thread_url']})")
    lines.append("")
    return "\n".join(lines)


def format_google_tasks_as_markdown(tasks: list[dict]) -> str:
    if not tasks:
        return ""
    lines = ["### Google Tasks", ""]
    for task in tasks:
        list_tag = f" *({task['list_name']})*" if task["list_name"] else ""
        lines.append(f"- [ ] {task['title']}{list_tag}")
        if task["notes"]:
            lines.append(f"  - {task['notes']}")
    lines.append("")
    return "\n".join(lines)


def _short_sender(from_header: str) -> str:
    """Extract display name or email from a From: header value."""
    if "<" in from_header:
        name = from_header.split("<")[0].strip().strip('"')
        return name if name else from_header.split("<")[1].rstrip(">")
    return from_header


# ── CLI helper for first-run auth ──────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Authenticate with Google APIs")
    parser.add_argument("--auth", action="store_true", help="Run OAuth flow")
    args = parser.parse_args()

    if args.auth:
        from dotenv import load_dotenv
        load_dotenv()
        client = GmailClient(
            credentials_file=os.getenv("GOOGLE_CREDENTIALS_FILE", "config/google_credentials.json"),
            token_file=os.getenv("GOOGLE_TOKEN_FILE", "config/google_token.json"),
        )
        creds = client._get_credentials()
        print("Authentication successful. Token saved.")
