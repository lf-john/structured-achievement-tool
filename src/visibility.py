"""
Task Visibility — Query interface for SAT database.

Provides task status, active work, blocked stories, and daily summary generation.
Used by the dashboard and CLI tools.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List

from src.db.database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class TaskVisibility:
    """Query interface for task status and progress visibility."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def get_task_status(self, task_id: str) -> Dict:
        """Get detailed status for a specific task including stories and events."""
        task = self.db.get_task(task_id)
        if not task:
            return {"error": f"Task {task_id} not found"}

        stories = self.db.get_stories_for_task(task_id)
        recent_events = self.db.get_recent_events(task_id=task_id, limit=20)

        # Build phase history from events
        phase_history = [
            e for e in recent_events if e.get("event_type") == "phase_change"
        ]

        return {
            **task,
            "stories": stories,
            "recent_events": recent_events,
            "phase_history": phase_history,
        }

    def get_active_work(self) -> Dict:
        """Get all active tasks with their stories."""
        status = self.db.get_system_status()
        active_tasks = self.db.get_active_tasks()

        result = []
        for task in active_tasks:
            stories = self.db.get_stories_for_task(task["id"])
            result.append({
                **task,
                "stories": stories,
            })

        return {
            **status,
            "active_tasks": result,
        }

    def get_blocked_stories(self) -> List[Dict]:
        """Get all stories that are blocked on dependencies."""
        active_tasks = self.db.get_active_tasks()
        blocked = []

        for task in active_tasks:
            stories = self.db.get_stories_for_task(task["id"])
            for s in stories:
                if s["status"] == "blocked":
                    blocked.append(s)
                elif s["status"] == "pending" and s.get("depends_on"):
                    # Check if dependencies are complete
                    deps = s.get("depends_on", [])
                    dep_statuses = {
                        st["id"]: st["status"] for st in stories if st["id"] in deps
                    }
                    if any(v != "complete" for v in dep_statuses.values()):
                        blocked.append(s)

        return blocked

    def generate_daily_summary(self) -> str:
        """Generate a daily summary of task activity."""
        status = self.db.get_system_status()
        events = self.db.get_recent_events(limit=100)

        lines = []
        lines.append(f"SAT Daily Summary — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")
        lines.append("")
        lines.append(f"Active tasks: {status.get('active_tasks', 0)}")
        lines.append(f"Working stories: {status.get('working_stories', 0)}")
        lines.append(f"Failed stories: {status.get('failed_stories', 0)}")
        lines.append(f"Events (last hour): {status.get('events_last_hour', 0)}")
        lines.append("")

        # Count event types
        type_counts: Dict[str, int] = {}
        for e in events:
            t = e.get("event_type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        if type_counts:
            lines.append("Recent activity:")
            for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
                lines.append(f"  {t}: {c}")

        return "\n".join(lines)

    def format_task_report(self, task_id: str) -> str:
        """Format a task report as human-readable text."""
        data = self.get_task_status(task_id)
        if "error" in data:
            return data["error"]

        icons = {
            "complete": "+",
            "working": ">",
            "failed": "!",
            "pending": "-",
            "blocked": "x",
        }

        lines = []
        lines.append(f"Task: {data.get('title', task_id)}")
        lines.append(f"Status: {data.get('status', '?')}")
        lines.append("")

        for s in data.get("stories", []):
            icon = icons.get(s.get("status", ""), "?")
            lines.append(f"  [{icon}] {s.get('title', s.get('id', '?'))} ({s.get('status', '?')})")
            if s.get("phase"):
                lines.append(f"      Phase: {s['phase']}")

        return "\n".join(lines)


def main():
    """CLI entry point for visibility queries."""
    import argparse

    parser = argparse.ArgumentParser(description="SAT Task Visibility")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="System status overview")
    sub.add_parser("active", help="Active work")
    sub.add_parser("blocked", help="Blocked stories")
    sub.add_parser("summary", help="Daily summary")

    p_report = sub.add_parser("report", help="Task report")
    p_report.add_argument("task_id", help="Task ID")

    p_events = sub.add_parser("events", help="Recent events")
    p_events.add_argument("--task-id", help="Filter by task ID")
    p_events.add_argument("--limit", type=int, default=20, help="Number of events")

    args = parser.parse_args()

    db = DatabaseManager()
    vis = TaskVisibility(db)

    if args.command == "status":
        data = db.get_system_status()
        for k, v in data.items():
            print(f"{k}: {v}")
    elif args.command == "active":
        data = vis.get_active_work()
        print(json.dumps(data, indent=2))
    elif args.command == "blocked":
        blocked = vis.get_blocked_stories()
        print(json.dumps(blocked, indent=2))
    elif args.command == "summary":
        print(vis.generate_daily_summary())
    elif args.command == "report":
        print(vis.format_task_report(args.task_id))
    elif args.command == "events":
        events = db.get_recent_events(limit=args.limit, task_id=args.task_id)
        for e in events:
            ts = e.get("timestamp", "")
            print(f"[{ts}] {e.get('event_type', '?')}: {e.get('detail', '')}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
