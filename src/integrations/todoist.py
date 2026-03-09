"""
Todoist API integration.

Fetches tasks that are due on a given date using the Todoist API v1.
API docs: https://developer.todoist.com/api/v1/
"""

import logging
from datetime import date

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.todoist.com/api/v1"


class TodoistError(Exception):
    pass


class TodoistClient:
    def __init__(self, api_token: str):
        self._headers = {"Authorization": f"Bearer {api_token}"}

    def _get_paginated(self, path: str, params: dict) -> list[dict]:
        """Fetch all pages from a cursor-paginated endpoint."""
        results = []
        cursor = None
        while True:
            if cursor:
                params = {**params, "cursor": cursor}
            resp = requests.get(
                f"{_BASE_URL}{path}",
                headers=self._headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            results.extend(data.get("results", []))
            cursor = data.get("next_cursor")
            if not cursor:
                break
        return results

    def get_tasks_due_on(self, target_date: date) -> list[dict]:
        """
        Return all active Todoist tasks whose due date matches *target_date*.

        Each returned dict has keys:
          - id        : Todoist task ID
          - content   : task title
          - description: longer description (may be empty)
          - priority  : 1 (normal) – 4 (urgent)
          - project   : project name (resolved from project_id)
          - url       : deep-link URL into Todoist
        """
        date_str = target_date.isoformat()
        try:
            tasks = self._get_paginated(
                "/tasks/filter", {"query": f"due: {date_str}"}
            )
        except Exception as exc:
            raise TodoistError(f"Failed to fetch Todoist tasks: {exc}") from exc

        # Build project id → name map for display
        try:
            projects_resp = self._get_paginated("/projects", {})
            projects = {p["id"]: p["name"] for p in projects_resp}
        except Exception:
            projects = {}

        results = []
        for task in tasks:
            results.append(
                {
                    "id": task["id"],
                    "content": task["content"],
                    "description": task.get("description") or "",
                    "priority": task.get("priority", 1),
                    "project": projects.get(task.get("project_id"), ""),
                    "url": task.get("url", f"https://todoist.com/app/task/{task['id']}"),
                }
            )

        logger.info("Found %d Todoist task(s) due on %s", len(results), date_str)
        return results


def format_todoist_tasks_as_markdown(tasks: list[dict]) -> str:
    if not tasks:
        return ""
    lines = ["### Todoist Tasks", ""]
    for task in tasks:
        project_tag = f" *({task['project']})*" if task["project"] else ""
        priority_marker = _priority_label(task["priority"])
        lines.append(f"- [ ] {task['content']}{project_tag}{priority_marker}")
        if task["description"]:
            lines.append(f"  - {task['description']}")
    lines.append("")
    return "\n".join(lines)


def _priority_label(priority: int) -> str:
    # Todoist priority: 4 = urgent (p1), 3 = high (p2), 2 = medium (p3), 1 = normal (p4)
    return {4: " 🔴", 3: " 🟠", 2: " 🟡"}.get(priority, "")
