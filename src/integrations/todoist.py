"""
Todoist API integration.

Fetches tasks that are due on a given date using the Todoist REST API v2.
API docs: https://developer.todoist.com/rest/v2/
"""

import logging
from datetime import date

from todoist_api_python.api import TodoistAPI

logger = logging.getLogger(__name__)


class TodoistError(Exception):
    pass


class TodoistClient:
    def __init__(self, api_token: str):
        self.api = TodoistAPI(api_token)

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
            all_tasks = self.api.get_tasks(filter=f"due: {date_str}")
        except Exception as exc:
            raise TodoistError(f"Failed to fetch Todoist tasks: {exc}") from exc

        # Build project id → name map for display
        try:
            projects = {p.id: p.name for p in self.api.get_projects()}
        except Exception:
            projects = {}

        results = []
        for task in all_tasks:
            results.append(
                {
                    "id": task.id,
                    "content": task.content,
                    "description": task.description or "",
                    "priority": task.priority,
                    "project": projects.get(task.project_id, ""),
                    "url": task.url,
                }
            )

        logger.info("Found %d Todoist task(s) due on %s", len(results), date_str)
        return results


def format_todoist_tasks_as_markdown(tasks: list[dict]) -> str:
    """Convert a list of Todoist task dicts to Capacities-compatible markdown."""
    if not tasks:
        return ""
    lines = ["### Todoist Tasks", ""]
    for task in tasks:
        project_tag = f" *({task['project']})*" if task["project"] else ""
        priority_marker = _priority_label(task["priority"])
        lines.append(f"- [ ] {task['content']}{project_tag}{priority_marker}")
        if task["description"]:
            # Indent description as a sub-item so it's visually grouped
            lines.append(f"  - {task['description']}")
    lines.append("")
    return "\n".join(lines)


def _priority_label(priority: int) -> str:
    # Todoist priority: 4 = urgent (p1), 3 = high (p2), 2 = medium (p3), 1 = normal (p4)
    return {4: " 🔴", 3: " 🟠", 2: " 🟡"}.get(priority, "")
