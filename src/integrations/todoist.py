"""
Todoist API integration.

Fetches tasks that are due on a given date using the Todoist Sync API v9.
API docs: https://developer.todoist.com/sync/v9/
"""

import logging
from datetime import date

import requests

logger = logging.getLogger(__name__)

_SYNC_URL = "https://api.todoist.com/sync/v9/sync"


class TodoistError(Exception):
    pass


class TodoistClient:
    def __init__(self, api_token: str):
        self._token = api_token
        self._headers = {"Authorization": f"Bearer {api_token}"}

    def _sync(self, resource_types: list[str]) -> dict:
        resp = requests.post(
            _SYNC_URL,
            headers=self._headers,
            json={"sync_token": "*", "resource_types": resource_types},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

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
            data = self._sync(["items", "projects"])
        except Exception as exc:
            raise TodoistError(f"Failed to fetch Todoist tasks: {exc}") from exc

        projects = {p["id"]: p["name"] for p in data.get("projects", [])}

        results = []
        for item in data.get("items", []):
            if item.get("checked") or item.get("is_deleted"):
                continue
            due = item.get("due")
            if due and due.get("date", "").startswith(date_str):
                results.append(
                    {
                        "id": item["id"],
                        "content": item["content"],
                        "description": item.get("description") or "",
                        "priority": item.get("priority", 1),
                        "project": projects.get(item.get("project_id"), ""),
                        "url": f"https://todoist.com/app/task/{item['id']}",
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
