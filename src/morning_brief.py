"""
BP Executive Assistant – Morning Brief
=======================================
Runs every weekday morning at 4 AM and:

1. Rolls over any incomplete tasks ([ ] checkboxes) from the previous
   weekday's Obsidian daily note into today's note.
2. Pulls Todoist tasks due today and adds them to today's note.
3. Pulls Google Tasks due today and adds them to today's note.

Usage:
    python src/morning_brief.py

Environment variables are loaded from a .env file in the project root.
"""

import logging
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

# ── Bootstrap ──────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

_log_level = os.getenv("LOG_LEVEL", "INFO").upper()
_log_file = os.getenv("LOG_FILE", "")

handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
if _log_file:
    log_path = PROJECT_ROOT / _log_file
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handlers.append(logging.FileHandler(log_path))

logging.basicConfig(
    level=getattr(logging, _log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=handlers,
)
logger = logging.getLogger("morning_brief")

# ── Integrations ───────────────────────────────────────────────────────────────

from integrations.obsidian import (  # noqa: E402
    ObsidianClient,
    ObsidianError,
    get_previous_weekday,
)
from integrations.todoist import (  # noqa: E402
    TodoistClient,
    TodoistError,
    format_todoist_tasks_as_markdown,
)
from integrations.gmail import (  # noqa: E402
    GmailClient,
    GmailError,
    format_google_tasks_as_markdown,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        logger.error("Required environment variable %s is not set.", name)
        sys.exit(1)
    return value


def _build_rollover_section(incomplete_tasks: list[str]) -> str:
    if not incomplete_tasks:
        return ""
    lines = ["### Rolled Over from Yesterday", ""]
    for task in incomplete_tasks:
        lines.append(f"- [ ] {task}")
    lines.append("")
    return "\n".join(lines)


# ── Main ───────────────────────────────────────────────────────────────────────

def run() -> None:
    today = date.today()
    yesterday = get_previous_weekday(today)

    logger.info("=== Morning Brief: %s ===", today.isoformat())

    # ── Obsidian ───────────────────────────────────────────────────────────────
    vault_path = _require_env("OBSIDIAN_VAULT_PATH")
    daily_folder = os.getenv("OBSIDIAN_DAILY_FOLDER", "daily")

    try:
        obsidian = ObsidianClient(vault_path=vault_path, daily_notes_folder=daily_folder)
    except ObsidianError as exc:
        logger.error("Cannot open Obsidian vault: %s", exc)
        sys.exit(1)

    # 1. Roll over incomplete tasks from the previous weekday
    rollover_md = ""
    try:
        logger.info("Reading previous day's note (%s)…", yesterday.isoformat())
        yesterday_content = obsidian.get_daily_note_content(yesterday)
        if yesterday_content:
            incomplete = obsidian.extract_incomplete_tasks(yesterday_content)
            logger.info(
                "Found %d incomplete task(s) in %s note.",
                len(incomplete),
                yesterday.isoformat(),
            )
            rollover_md = _build_rollover_section(incomplete)
        else:
            logger.info("No note found for %s – nothing to roll over.", yesterday.isoformat())
    except Exception as exc:
        logger.error("Error reading yesterday's Obsidian note: %s", exc)

    # ── Todoist ────────────────────────────────────────────────────────────────
    todoist_md = ""
    todoist_token = os.getenv("TODOIST_API_TOKEN")
    if todoist_token:
        try:
            logger.info("Fetching Todoist tasks due on %s…", today.isoformat())
            todoist = TodoistClient(api_token=todoist_token)
            tasks = todoist.get_tasks_due_on(today)
            todoist_md = format_todoist_tasks_as_markdown(tasks)
        except TodoistError as exc:
            logger.error("Todoist error: %s", exc)
    else:
        logger.warning("TODOIST_API_TOKEN not set – skipping Todoist.")

    # ── Google Tasks ───────────────────────────────────────────────────────────
    google_tasks_md = ""
    credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "config/google_credentials.json")
    token_file = os.getenv("GOOGLE_TOKEN_FILE", "config/google_token.json")

    if not Path(credentials_file).is_absolute():
        credentials_file = str(PROJECT_ROOT / credentials_file)
    if not Path(token_file).is_absolute():
        token_file = str(PROJECT_ROOT / token_file)

    if Path(credentials_file).exists() or Path(token_file).exists():
        try:
            gclient = GmailClient(credentials_file=credentials_file, token_file=token_file)
            logger.info("Fetching Google Tasks due on %s…", today.isoformat())
            gtasks = gclient.get_google_tasks_due_on(today)
            google_tasks_md = format_google_tasks_as_markdown(gtasks)
        except GmailError as exc:
            logger.error("Google Tasks error: %s", exc)
    else:
        logger.warning(
            "Google credentials not found at %s – skipping Google Tasks.", credentials_file
        )

    # ── Build the append block ─────────────────────────────────────────────────
    sections = [s for s in [rollover_md, todoist_md, google_tasks_md] if s]

    if not sections:
        logger.info("Nothing to add to today's note. Exiting.")
        return

    divider = "---\n\n"
    append_block = divider + "\n".join(sections)

    # ── Write to Obsidian ──────────────────────────────────────────────────────
    try:
        logger.info("Appending %d section(s) to today's Obsidian note…", len(sections))
        obsidian.append_to_daily_note(today, append_block)
        logger.info(
            "Done. Note written to: %s",
            obsidian._note_path(today),
        )
    except ObsidianError as exc:
        logger.error("Failed to write Obsidian daily note: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    run()
