"""
Capacities API integration.

Handles reading and writing daily notes in a Capacities space.
API docs: https://api.capacities.io/docs
"""

import logging
from datetime import date, timedelta
from typing import Optional

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.capacities.io"


class CapacitiesError(Exception):
    pass


class CapacitiesClient:
    def __init__(self, api_token: str, space_id: str):
        self.space_id = space_id
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    # ── Daily note helpers ─────────────────────────────────────────────────────

    def get_daily_note(self, target_date: date) -> Optional[dict]:
        """Return the daily note object for *target_date*, or None if it doesn't exist."""
        resp = self.session.get(
            f"{BASE_URL}/daily-note",
            params={"spaceId": self.space_id, "date": target_date.isoformat()},
        )
        if resp.status_code == 404:
            return None
        if not resp.ok:
            raise CapacitiesError(
                f"GET /daily-note failed [{resp.status_code}]: {resp.text}"
            )
        return resp.json()

    def get_daily_note_content(self, target_date: date) -> str:
        """Return the markdown content of the daily note, or '' if it doesn't exist."""
        note = self.get_daily_note(target_date)
        if note is None:
            return ""
        # Capacities stores note body under 'content' or 'mdText' depending on version
        return note.get("mdText") or note.get("content") or ""

    def append_to_daily_note(self, target_date: date, markdown: str) -> None:
        """
        Append *markdown* to the daily note for *target_date*.
        Creates the note if it doesn't exist yet.
        """
        resp = self.session.post(
            f"{BASE_URL}/daily-note/append",
            json={
                "spaceId": self.space_id,
                "date": target_date.isoformat(),
                "mdText": markdown,
            },
        )
        if not resp.ok:
            raise CapacitiesError(
                f"POST /daily-note/append failed [{resp.status_code}]: {resp.text}"
            )
        logger.debug("Appended %d chars to daily note %s", len(markdown), target_date)

    # ── Task extraction ────────────────────────────────────────────────────────

    @staticmethod
    def extract_incomplete_tasks(markdown: str) -> list[str]:
        """
        Parse *markdown* and return lines that represent incomplete checkbox tasks.

        Matches:
          - [ ] Task text
          - - [ ] Task text   (list item form)
        """
        tasks: list[str] = []
        for line in markdown.splitlines():
            stripped = line.strip()
            # Match bare "[ ] …" or list-item "- [ ] …"
            if stripped.startswith("[ ] ") or stripped.startswith("- [ ] "):
                # Normalise to list-item checkbox form
                if stripped.startswith("[ ] "):
                    task_text = stripped[4:].strip()
                else:
                    task_text = stripped[6:].strip()
                if task_text:
                    tasks.append(task_text)
        return tasks


def get_previous_weekday(today: date) -> date:
    """Return the most recent weekday before *today* (skips weekends)."""
    delta = 1
    if today.weekday() == 0:  # Monday → go back to Friday
        delta = 3
    elif today.weekday() == 6:  # Sunday → go back to Friday (shouldn't normally run)
        delta = 2
    return today - timedelta(days=delta)
