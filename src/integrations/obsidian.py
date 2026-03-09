"""
Obsidian integration.

Reads and writes daily notes in a local Obsidian vault.
Daily notes are stored as plain markdown files at:
  <vault_path>/<daily_notes_folder>/YYYY-MM-DD.md

No API or network access required – everything is direct file I/O.
"""

import logging
from datetime import date, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class ObsidianError(Exception):
    pass


class ObsidianClient:
    def __init__(self, vault_path: str, daily_notes_folder: str = "daily"):
        self.vault = Path(vault_path).expanduser().resolve()
        self.daily_folder = self.vault / daily_notes_folder

        if not self.vault.exists():
            raise ObsidianError(f"Obsidian vault not found: {self.vault}")

    # ── Path helpers ───────────────────────────────────────────────────────────

    def _note_path(self, target_date: date) -> Path:
        return self.daily_folder / f"{target_date.isoformat()}.md"

    # ── Read / write ───────────────────────────────────────────────────────────

    def get_daily_note_content(self, target_date: date) -> str:
        """Return the full markdown content of the daily note, or '' if it doesn't exist."""
        path = self._note_path(target_date)
        if not path.exists():
            logger.debug("Daily note not found: %s", path)
            return ""
        content = path.read_text(encoding="utf-8")
        logger.debug("Read %d chars from %s", len(content), path)
        return content

    def append_to_daily_note(self, target_date: date, markdown: str) -> None:
        """
        Append *markdown* to the daily note for *target_date*.
        Creates the note (and any missing parent directories) if it doesn't exist.
        """
        path = self._note_path(target_date)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Ensure there is a blank line before the appended block
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            separator = "\n" if existing.endswith("\n") else "\n\n"
        else:
            # Brand-new note – add a simple date heading first
            path.write_text(
                f"# {target_date.strftime('%A, %B %-d %Y')}\n\n",
                encoding="utf-8",
            )
            separator = ""

        with path.open("a", encoding="utf-8") as f:
            f.write(separator + markdown)

        logger.debug("Appended %d chars to %s", len(markdown), path)

    # ── Task extraction ────────────────────────────────────────────────────────

    @staticmethod
    def extract_incomplete_tasks(markdown: str) -> list[str]:
        """
        Parse *markdown* and return text of all unchecked checkbox lines.

        Matches both:
          [ ] Task text
          - [ ] Task text
        """
        tasks: list[str] = []
        for line in markdown.splitlines():
            stripped = line.strip()
            if stripped.startswith("- [ ] "):
                tasks.append(stripped[6:].strip())
            elif stripped.startswith("[ ] "):
                tasks.append(stripped[4:].strip())
        return [t for t in tasks if t]


def get_previous_weekday(today: date) -> date:
    """Return the most recent weekday before *today* (skips weekends)."""
    delta = 3 if today.weekday() == 0 else 1  # Monday → Friday
    return today - timedelta(days=delta)
