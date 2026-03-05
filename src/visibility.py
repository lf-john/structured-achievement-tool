"""
Task Visibility — Query interface for SAT database.

Provides task status, active work, blocked stories, and daily summary generation.
Used by the dashboard and CLI tools.
"""

import json
import logging
from datetime import UTC, datetime

from src.db.database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class TaskVisibility:
    """Query interface for task status and progress visibility."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def get_task_status(self, task_id: str) -> dict:
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

    def get_active_work(self) -> dict:
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

    def get_blocked_stories(self) -> list[dict]:
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
        lines.append(f"SAT Daily Summary — {datetime.now(UTC).strftime('%Y-%m-%d')}")
        lines.append("")
        lines.append(f"Active tasks: {status.get('active_tasks', 0)}")
        lines.append(f"Working stories: {status.get('working_stories', 0)}")
        lines.append(f"Failed stories: {status.get('failed_stories', 0)}")
        lines.append(f"Events (last hour): {status.get('events_last_hour', 0)}")
        lines.append("")

        # Count event types
        type_counts: dict[str, int] = {}
        for e in events:
            t = e.get("event_type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        if type_counts:
            lines.append("Recent activity:")
            for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
                lines.append(f"  {t}: {c}")

        # Debug reproduction stats
        repro_events = [
            e for e in events
            if e.get("event_type") == "debug_reproduction"
        ]
        if repro_events:
            methods = {}
            for e in repro_events:
                m = e.get("data", {}).get("method", "unknown") if isinstance(e.get("data"), dict) else "unknown"
                methods[m] = methods.get(m, 0) + 1
            lines.append("")
            lines.append("Debug reproduction methods:")
            for m, c in sorted(methods.items(), key=lambda x: -x[1]):
                lines.append(f"  {m}: {c}")

        # G-Eval provider performance (Enhancement #11)
        try:
            from src.evaluation.geval_scorer import get_low_scoring_details, get_provider_performance
            perf = get_provider_performance()
            if perf:
                lines.append("")
                lines.append("Provider quality scores (G-Eval):")
                for provider, agents in sorted(perf.items()):
                    for agent_type, scores in sorted(agents.items()):
                        avg = scores["avg_score"]
                        count = scores["sample_count"]
                        low = scores["low_scores"]
                        flag = " *** LOW ***" if avg <= 2.0 else ""
                        lines.append(
                            f"  {provider}/{agent_type}: avg={avg}/5 "
                            f"(n={count}, low_scores={low}){flag}"
                        )
                        # Show per-score counts for providers with any score < 2
                        dist = scores.get("score_distribution")
                        if dist:
                            for dim in ("completeness", "correctness", "format_compliance"):
                                dim_counts = dist.get(dim, {})
                                if dim_counts:
                                    counts_str = " ".join(
                                        f"{s}:{c}" for s, c in sorted(dim_counts.items())
                                    )
                                    lines.append(f"    {dim}: {counts_str}")

            # Detailed low-score invocations (available via monitoring tool: `python -m src.visibility summary`)
            low_scores = get_low_scoring_details()
            if low_scores:
                lines.append("")
                lines.append(f"Low quality invocations (score <= 2): {len(low_scores)} total")
                lines.append("  (Run `python -m src.visibility summary` for full details)")
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"G-Eval digest failed: {e}")

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
    sub.add_parser("quality", help="G-Eval quality details (low-scoring invocations)")
    sub.add_parser("calibration", help="Agent self-assessment accuracy (confidence vs G-Eval)")
    sub.add_parser("enhancements", help="Enhancement suggestions logged by agents")

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
    elif args.command == "quality":
        try:
            from src.evaluation.geval_scorer import get_low_scoring_details, get_provider_performance
            perf = get_provider_performance()
            if perf:
                print("Provider Quality Scores (G-Eval)\n")
                for provider, agents in sorted(perf.items()):
                    for agent_type, scores in sorted(agents.items()):
                        print(f"  {provider}/{agent_type}: avg={scores['avg_score']}/5 (n={scores['sample_count']})")
                        dist = scores.get("score_distribution")
                        if dist:
                            for dim in ("completeness", "correctness", "format_compliance"):
                                dim_counts = dist.get(dim, {})
                                if dim_counts:
                                    counts_str = " ".join(f"{s}:{c}" for s, c in sorted(dim_counts.items()))
                                    print(f"    {dim}: {counts_str}")
            low = get_low_scoring_details()
            if low:
                print(f"\nLow Quality Invocations (score <= 2 on any dimension): {len(low)}\n")
                for ls in low:
                    print(
                        f"  [{ls['timestamp'][:16]}] {ls['provider']}/{ls['agent_type']}: "
                        f"complete={ls['completeness']} correct={ls['correctness']} "
                        f"format={ls['format_compliance']}"
                    )
                    if ls.get("notes"):
                        print(f"    Notes: {ls['notes']}")
            elif not perf:
                print("No G-Eval scores available yet.")
        except ImportError:
            print("G-Eval scorer module not available.")
    elif args.command == "calibration":
        try:
            from src.evaluation.geval_scorer import get_calibration_report
            report = get_calibration_report()
            if report:
                print("Agent Self-Assessment Calibration\n")
                print(f"{'Provider':<20} {'Agent Type':<15} {'Samples':>7} {'Confidence':>10} {'G-Eval':>7} {'Delta':>7}")
                print("-" * 70)
                for r in report:
                    delta_str = f"{r['avg_delta']:+.2f}"
                    flag = ""
                    if abs(r["avg_delta"]) >= 1.5:
                        flag = " *** MISCALIBRATED ***"
                    elif r["avg_delta"] >= 0.5:
                        flag = " (overconfident)"
                    elif r["avg_delta"] <= -0.5:
                        flag = " (underconfident)"
                    print(
                        f"{r['provider']:<20} {r['agent_type']:<15} "
                        f"{r['sample_count']:>7} {r['avg_confidence']:>10.1f} "
                        f"{r['avg_geval']:>7.1f} {delta_str:>7}{flag}"
                    )
                print("\nDelta = confidence - G-Eval avg. Positive = overconfident.")
            else:
                print("No calibration data yet. Agents need to report confidence scores.")
        except ImportError:
            print("G-Eval scorer module not available.")
    elif args.command == "enhancements":
        import os as _os
        enh_file = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
            ".memory", "enhancements.jsonl"
        )
        if _os.path.exists(enh_file):
            with open(enh_file) as f:
                entries = [json.loads(line) for line in f if line.strip()]
            if entries:
                print(f"Enhancement Suggestions ({len(entries)} total)\n")
                for e in entries[-50:]:  # Show last 50
                    print(f"  [{e.get('ts', '')[:16]}] {e.get('phase', '?')}/{e.get('story_id', '?')}")
                    print(f"    {e.get('enhancement', '')}")
            else:
                print("No enhancements logged yet.")
        else:
            print("No enhancements file found. Agents haven't logged any yet.")
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
