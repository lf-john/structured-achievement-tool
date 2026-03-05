"""
Telegram Bot — Mobile access for SAT task management.

Phase 6, item 6.4. Provides:
- /status — System health and active task summary
- /tasks — List pending/working/finished tasks
- /task <id> — Detailed task info
- /approve <story_id> — Approve a pending human story
- /reject <story_id> <reason> — Reject a pending human story
- /create <title> — Create a new task file
- /costs — LLM cost summary
- /help — Command reference

Requires:
- TELEGRAM_BOT_TOKEN env var (from BotFather)
- TELEGRAM_ALLOWED_USERS env var (comma-separated user IDs for auth)
- pip install python-telegram-bot
"""

import logging
import os
import sqlite3
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Lazy import — python-telegram-bot may not be installed
_telegram = None


def _get_telegram():
    global _telegram
    if _telegram is None:
        try:
            from telegram import BotCommand, Update
            from telegram.ext import (
                ApplicationBuilder,
                CommandHandler,
                ContextTypes,
                MessageHandler,
                filters,
            )
            _telegram = {
                "Update": Update,
                "BotCommand": BotCommand,
                "ApplicationBuilder": ApplicationBuilder,
                "CommandHandler": CommandHandler,
                "ContextTypes": ContextTypes,
                "MessageHandler": MessageHandler,
                "filters": filters,
            }
        except ImportError:
            raise ImportError(
                "python-telegram-bot not installed. Run: pip install python-telegram-bot"
            )
    return _telegram


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _get_config():
    """Load paths and settings."""
    try:
        from src.core.paths import SAT_PROJECT_DIR, SAT_TASKS_DIR
        project_dir = str(SAT_PROJECT_DIR)
        tasks_dir = str(SAT_TASKS_DIR)
    except ImportError:
        project_dir = os.path.expanduser("~/projects/structured-achievement-tool")
        tasks_dir = os.path.expanduser("~/GoogleDrive/DriveSyncFiles/sat-tasks")

    return {
        "project_dir": project_dir,
        "tasks_dir": tasks_dir,
        "memory_dir": os.path.join(project_dir, ".memory"),
        "approvals_dir": os.path.join(tasks_dir, "approvals"),
    }


def _get_allowed_users() -> set:
    """Return set of allowed Telegram user IDs."""
    raw = os.environ.get("TELEGRAM_ALLOWED_USERS", "")
    if not raw:
        return set()
    return {int(uid.strip()) for uid in raw.split(",") if uid.strip().isdigit()}


# ---------------------------------------------------------------------------
# Auth decorator
# ---------------------------------------------------------------------------

def authorized(func):
    """Decorator that restricts commands to allowed users."""
    async def wrapper(update, context):
        allowed = _get_allowed_users()
        if allowed and update.effective_user.id not in allowed:
            await update.message.reply_text("Unauthorized. Your user ID is not in TELEGRAM_ALLOWED_USERS.")
            logger.warning(f"Telegram: unauthorized access attempt from user {update.effective_user.id}")
            return
        return await func(update, context)
    return wrapper


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

@authorized
async def cmd_status(update, context):
    """System health summary."""
    lines = ["*SAT System Status*\n"]

    # Service status
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", "sat.service"],
            capture_output=True, text=True, timeout=5,
        )
        sat_active = result.stdout.strip()
    except Exception:
        sat_active = "unknown"

    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", "sat-monitor.service"],
            capture_output=True, text=True, timeout=5,
        )
        monitor_active = result.stdout.strip()
    except Exception:
        monitor_active = "unknown"

    status_emoji = {"active": "\u2705", "inactive": "\u274c", "failed": "\u274c"}
    lines.append(f"{status_emoji.get(sat_active, '\u2753')} Daemon: {sat_active}")
    lines.append(f"{status_emoji.get(monitor_active, '\u2753')} Monitor: {monitor_active}")

    # Ollama status
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "ollama.service"],
            capture_output=True, text=True, timeout=5,
        )
        ollama_active = result.stdout.strip()
    except Exception:
        ollama_active = "unknown"
    lines.append(f"{status_emoji.get(ollama_active, '\u2753')} Ollama: {ollama_active}")

    # Task counts
    cfg = _get_config()
    counts = _count_tasks(cfg["tasks_dir"])
    lines.append("\n*Tasks:*")
    lines.append(f"  Pending: {counts.get('pending', 0)}")
    lines.append(f"  Working: {counts.get('working', 0)}")
    lines.append(f"  Finished: {counts.get('finished', 0)}")
    lines.append(f"  Failed: {counts.get('failed', 0)}")

    # Pending approvals
    approvals = _list_pending_approvals(cfg["approvals_dir"])
    if approvals:
        lines.append(f"\n\u26a0\ufe0f *{len(approvals)} pending approval(s)*")
        for a in approvals[:3]:
            lines.append(f"  \u2022 {a}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@authorized
async def cmd_tasks(update, context):
    """List tasks with status."""
    cfg = _get_config()
    tasks = _get_task_list(cfg["tasks_dir"])

    if not tasks:
        await update.message.reply_text("No tasks found.")
        return

    lines = ["*SAT Tasks*\n"]
    for task in tasks[:20]:  # Cap at 20 to avoid message limit
        status_emoji = {
            "Pending": "\u23f3",
            "Working": "\u2699\ufe0f",
            "Finished": "\u2705",
            "Failed": "\u274c",
        }
        emoji = status_emoji.get(task["status"], "\u2753")
        lines.append(f"{emoji} `{task['file']}` — {task['status']}")

    if len(tasks) > 20:
        lines.append(f"\n_...and {len(tasks) - 20} more_")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@authorized
async def cmd_task_detail(update, context):
    """Show detailed info for a specific task."""
    if not context.args:
        await update.message.reply_text("Usage: /task <filename or keyword>")
        return

    keyword = " ".join(context.args).lower()
    cfg = _get_config()
    tasks = _get_task_list(cfg["tasks_dir"])

    matches = [t for t in tasks if keyword in t["file"].lower() or keyword in t.get("dir", "").lower()]

    if not matches:
        await update.message.reply_text(f"No task matching '{keyword}'")
        return

    task = matches[0]
    lines = [
        f"*Task:* `{task['file']}`",
        f"*Directory:* {task.get('dir', 'unknown')}",
        f"*Status:* {task['status']}",
    ]

    # Read first 500 chars of the task file
    try:
        with open(task["path"]) as f:
            content = f.read(500)
        lines.append(f"\n```\n{content}\n```")
    except Exception:
        pass

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@authorized
async def cmd_approve(update, context):
    """Approve a pending human story."""
    if not context.args:
        await update.message.reply_text("Usage: /approve <story_id>")
        return

    story_id = context.args[0]
    response_text = " ".join(context.args[1:]) if len(context.args) > 1 else "Approved via Telegram"
    cfg = _get_config()

    signal_path = os.path.join(cfg["approvals_dir"], f"{story_id}_approval.md")
    if not os.path.exists(signal_path):
        await update.message.reply_text(f"No approval file found for {story_id}")
        return

    try:
        with open(signal_path) as f:
            content = f.read()

        # Replace '# <Pending>' with user response + '<Pending>'
        content = content.replace("# <Pending>", f"{response_text}\n\n<Pending>")

        with open(signal_path, "w") as f:
            f.write(content)

        # fsync for Google Drive FUSE
        fd = os.open(signal_path, os.O_RDONLY)
        os.fsync(fd)
        os.close(fd)

        await update.message.reply_text(f"\u2705 Approved {story_id}")
        logger.info(f"Telegram: approved {story_id} by user {update.effective_user.id}")
    except Exception as e:
        await update.message.reply_text(f"Error approving {story_id}: {e}")


@authorized
async def cmd_reject(update, context):
    """Reject a pending human story."""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: /reject <story_id> <reason>")
        return

    story_id = context.args[0]
    reason = " ".join(context.args[1:])
    cfg = _get_config()

    signal_path = os.path.join(cfg["approvals_dir"], f"{story_id}_approval.md")
    if not os.path.exists(signal_path):
        await update.message.reply_text(f"No approval file found for {story_id}")
        return

    try:
        with open(signal_path) as f:
            content = f.read()

        content = content.replace("# <Pending>", f"REJECTED: {reason}\n\n<Pending>")

        with open(signal_path, "w") as f:
            f.write(content)

        fd = os.open(signal_path, os.O_RDONLY)
        os.fsync(fd)
        os.close(fd)

        await update.message.reply_text(f"\u274c Rejected {story_id}: {reason}")
        logger.info(f"Telegram: rejected {story_id} by user {update.effective_user.id}: {reason}")
    except Exception as e:
        await update.message.reply_text(f"Error rejecting {story_id}: {e}")


@authorized
async def cmd_create(update, context):
    """Create a new task file."""
    if not context.args:
        await update.message.reply_text(
            "Usage: /create <directory> <title>\n"
            "Example: /create other fix-login-bug"
        )
        return

    if len(context.args) < 2:
        await update.message.reply_text("Need both directory and title. Example: /create other fix-login-bug")
        return

    directory = context.args[0]
    title = "-".join(context.args[1:])
    cfg = _get_config()

    task_dir = os.path.join(cfg["tasks_dir"], directory)
    if not os.path.isdir(task_dir):
        await update.message.reply_text(
            f"Directory '{directory}' not found.\n"
            f"Available: {', '.join(_list_task_dirs(cfg['tasks_dir']))}"
        )
        return

    # Find next number
    existing = sorted(Path(task_dir).glob("*.md"))
    next_num = 1
    for f in existing:
        try:
            num = int(f.stem.split("_")[0])
            next_num = max(next_num, num + 1)
        except (ValueError, IndexError):
            pass

    filename = f"{next_num:03d}_{title}.md"
    filepath = os.path.join(task_dir, filename)

    # Collect remaining message text as the task body
    # If user sent more text after the command args, use it
    body = f"# Task: {title.replace('-', ' ').title()}\n\n## Objective\n\n[Created via Telegram by user {update.effective_user.id}]\n\n## Acceptance Criteria\n\n- [ ] TBD\n\n<Pending>\n"

    try:
        with open(filepath, "w") as f:
            f.write(body)
        fd = os.open(filepath, os.O_RDONLY)
        os.fsync(fd)
        os.close(fd)

        await update.message.reply_text(
            f"\u2705 Created: `{directory}/{filename}`\n"
            f"Edit in Obsidian to add details before SAT picks it up.",
            parse_mode="Markdown",
        )
        logger.info(f"Telegram: created task {filepath} by user {update.effective_user.id}")
    except Exception as e:
        await update.message.reply_text(f"Error creating task: {e}")


@authorized
async def cmd_costs(update, context):
    """Show LLM cost summary."""
    cfg = _get_config()
    costs_db = os.path.join(cfg["memory_dir"], "llm_costs.db")

    if not os.path.exists(costs_db):
        await update.message.reply_text("No cost data available yet.")
        return

    try:
        conn = sqlite3.connect(costs_db)
        rows = conn.execute(
            "SELECT model, COUNT(*) as calls, SUM(prompt_tokens) as pt, "
            "SUM(completion_tokens) as ct, SUM(cost_usd) as cost "
            "FROM llm_costs GROUP BY model ORDER BY cost DESC"
        ).fetchall()
        conn.close()

        lines = ["*LLM Cost Summary*\n"]
        total_cost = 0.0
        for model, calls, _pt, _ct, cost in rows:
            cost = cost or 0.0
            total_cost += cost
            lines.append(f"`{model}`: {calls} calls, ${cost:.2f}")

        lines.append(f"\n*Total: ${total_cost:.2f}*")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Error reading costs: {e}")


@authorized
async def cmd_help(update, context):
    """Show available commands."""
    text = (
        "*SAT Telegram Bot*\n\n"
        "/status — System health summary\n"
        "/tasks — List all tasks with status\n"
        "/task <keyword> — Task details\n"
        "/approve <story\\_id> [message] — Approve a pending story\n"
        "/reject <story\\_id> <reason> — Reject a pending story\n"
        "/create <dir> <title> — Create a new task\n"
        "/costs — LLM cost summary\n"
        "/help — This message"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _count_tasks(tasks_dir: str) -> dict:
    """Count tasks by status across all subdirectories."""
    counts = {"pending": 0, "working": 0, "finished": 0, "failed": 0}
    tasks_path = Path(tasks_dir)
    if not tasks_path.exists():
        return counts

    for md_file in tasks_path.rglob("*.md"):
        if md_file.name.startswith("_") or "_response" in md_file.name:
            continue
        try:
            content = md_file.read_text(errors="replace")
            if "<Failed>" in content:
                counts["failed"] += 1
            elif "<Finished>" in content:
                counts["finished"] += 1
            elif "<Working>" in content:
                counts["working"] += 1
            elif "<Pending>" in content:
                counts["pending"] += 1
        except Exception:
            pass
    return counts


def _get_task_list(tasks_dir: str) -> list:
    """Get list of task files with status."""
    tasks = []
    tasks_path = Path(tasks_dir)
    if not tasks_path.exists():
        return tasks

    for md_file in sorted(tasks_path.rglob("*.md")):
        if md_file.name.startswith("_") or "_response" in md_file.name:
            continue
        try:
            content = md_file.read_text(errors="replace")
            status = "Unknown"
            if "<Failed>" in content:
                status = "Failed"
            elif "<Finished>" in content:
                status = "Finished"
            elif "<Working>" in content:
                status = "Working"
            elif "<Pending>" in content:
                status = "Pending"

            rel_dir = md_file.parent.name
            tasks.append({
                "file": md_file.name,
                "dir": rel_dir,
                "path": str(md_file),
                "status": status,
            })
        except Exception:
            pass
    return tasks


def _list_pending_approvals(approvals_dir: str) -> list:
    """List story IDs with pending approvals."""
    pending = []
    approvals_path = Path(approvals_dir)
    if not approvals_path.exists():
        return pending

    for md_file in approvals_path.glob("*_approval.md"):
        try:
            content = md_file.read_text(errors="replace")
            if "# <Pending>" in content:
                story_id = md_file.stem.replace("_approval", "")
                pending.append(story_id)
        except Exception:
            pass
    return pending


def _list_task_dirs(tasks_dir: str) -> list:
    """List available task subdirectories."""
    tasks_path = Path(tasks_dir)
    if not tasks_path.exists():
        return []
    return [d.name for d in tasks_path.iterdir() if d.is_dir() and not d.name.startswith(".")]


# ---------------------------------------------------------------------------
# Bot startup
# ---------------------------------------------------------------------------

def create_bot():
    """Create and configure the Telegram bot application.

    Requires TELEGRAM_BOT_TOKEN environment variable.
    Optionally set TELEGRAM_ALLOWED_USERS to restrict access.

    Returns the Application object (call .run_polling() to start).
    """
    tg = _get_telegram()

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")

    app = tg["ApplicationBuilder"]().token(token).build()

    # Register handlers
    app.add_handler(tg["CommandHandler"]("start", cmd_help))
    app.add_handler(tg["CommandHandler"]("help", cmd_help))
    app.add_handler(tg["CommandHandler"]("status", cmd_status))
    app.add_handler(tg["CommandHandler"]("tasks", cmd_tasks))
    app.add_handler(tg["CommandHandler"]("task", cmd_task_detail))
    app.add_handler(tg["CommandHandler"]("approve", cmd_approve))
    app.add_handler(tg["CommandHandler"]("reject", cmd_reject))
    app.add_handler(tg["CommandHandler"]("create", cmd_create))
    app.add_handler(tg["CommandHandler"]("costs", cmd_costs))

    return app


def run_bot():
    """Start the Telegram bot (blocking)."""
    app = create_bot()
    logger.info("Starting SAT Telegram bot...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_bot()
