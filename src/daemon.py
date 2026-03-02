import time, logging, os, asyncio, traceback, re, json, signal, atexit, sys, shutil
import argparse
from src.orchestrator_v2 import OrchestratorV2 as Orchestrator
from src.execution.stability_timeout import StabilityTimeout
from src.execution.slot_manager import SlotManager
from src.execution.rate_limit_handler import RateLimitHandler
from src.execution.audit_journal import AuditJournal
from src.execution.fuse_sentinel import FuseSentinel
from src.monitoring.metrics_exporter import start_metrics_server
from src.core.checkpoint_manager import init_db, resume_incomplete_workflows
from src.db.database_manager import DatabaseManager
from src.core.paths import (
    SAT_PROJECT_DIR, SAT_TASKS_DIR, MEMORY_DIR, CHECKPOINT_DB,
    SAT_DB, CONFIG_JSON, AUDIT_JOURNAL as AUDIT_JOURNAL_PATH,
    RATE_LIMIT_STATE,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Recently completed tasks: {file_path: completion_time} — prevents re-detection
# on slow FUSE mounts where tag writes may not propagate immediately
recently_completed = {}

# Per-task attempt counter: {file_path: int} — prevents infinite retry loops.
# If a task has been attempted MAX_TASK_ATTEMPTS times without success, it is
# marked <Failed> and skipped.  The monitor handles manual retries.
processing_attempts: dict[str, int] = {}
MAX_TASK_ATTEMPTS = 3

# --- PID file lock (Failure State 14) ---
PID_FILE = "/tmp/sat-daemon.pid"
CHECKPOINT_DB_PATH = str(CHECKPOINT_DB)


def _acquire_pid_lock():
    """Ensure only one daemon instance is running.  Exit if another is alive."""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                old_pid = int(f.read().strip())
            # Signal 0 checks existence without actually sending a signal
            os.kill(old_pid, 0)
            # If we reach here the process is still alive
            logging.error(
                "Another SAT daemon is already running (PID %d). Exiting.", old_pid
            )
            sys.exit(1)
        except (ValueError, ProcessLookupError, PermissionError):
            # Stale PID file — previous process is gone
            logging.info("Removing stale PID file (old PID no longer running)")
        except OSError:
            pass

    # Write our PID
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))
    logging.info("PID lock acquired: %s (PID %d)", PID_FILE, os.getpid())


def _release_pid_lock():
    """Remove the PID file on exit."""
    try:
        if os.path.exists(PID_FILE):
            with open(PID_FILE, "r") as f:
                stored_pid = int(f.read().strip())
            if stored_pid == os.getpid():
                os.remove(PID_FILE)
                logging.info("PID lock released: %s", PID_FILE)
    except Exception as e:
        logging.warning("Failed to release PID lock: %s", e)

def has_tag(file_path, tag):
    """Check if the file contains the specific tag on its own line."""
    if not os.path.exists(file_path):
        return False
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return bool(re.search(rf'^\s*{re.escape(tag)}\s*$', content, re.MULTILINE))
    except Exception as e:
        return False

def is_task_ready(file_path):
    """Check if the file is ready for processing (has <User> tag).

    This is an alias for has_tag(file_path, '<Pending>') for compatibility
    with test suite.
    """
    return has_tag(file_path, '<Pending>')

def get_latest_md_file(directory):
    """Find the latest .md file in a directory.

    Returns the alphabetically last .md file that doesn't start with underscore.
    Returns None if no suitable files are found.
    """
    if not os.path.exists(directory) or not os.path.isdir(directory):
        return None

    try:
        md_files = [
            f for f in os.listdir(directory)
            if f.endswith('.md') and not f.startswith('_') and os.path.isfile(os.path.join(directory, f))
        ]

        if not md_files:
            return None

        # Sort alphabetically and return the last one
        md_files.sort()
        return os.path.join(directory, md_files[-1])
    except Exception as e:
        logging.error(f"Error finding latest md file in {directory}: {e}")
        return None

def mark_file_status(file_path, old_tag, new_tag):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace the last occurrence of old_tag with new_tag
        parts = content.rsplit(old_tag, 1)
        if len(parts) == 2:
            new_content = new_tag.join(parts)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
                f.flush()
                os.fsync(f.fileno()) # Force write to disk/mount
            return True
        return False
    except Exception as e:
        logging.error(f"Error updating tags in {file_path}: {e}")
        return False

async def monitor_cancellation(file_path, task):
    """Continuously check if <Cancel> is added to the file."""
    while not task.done():
        if has_tag(file_path, '<Cancel>'):
            logging.info(f"Cancellation requested for {file_path}")
            task.cancel()
            break
        await asyncio.sleep(2)

def detect_signal(file_path):
    """Detect the trigger signal in a file.

    Returns:
        'pending'  — normal task execution
        'plan'     — PRD Phase 1 (Discovery)
        'plan1'    — Single-phase PRD
        'phase2'   — PRD Phase 2 (Requirements) — user signals <1>
        'phase3'   — PRD Phase 3 (Architecture) — user signals <2> after Phase 2
        'phase4'   — PRD Phase 4 (Implementation) — user signals <2> after Phase 3
        'prd'      — Decompose approved PRD into executable stories
        None       — no recognized signal
    """
    if has_tag(file_path, '<Pending>'):
        return 'pending'
    if has_tag(file_path, '<PRD>'):
        return 'prd'
    if has_tag(file_path, '<Plan 1>'):
        return 'plan1'
    if has_tag(file_path, '<Plan>'):
        return 'plan'
    # Phase continuation signals: <1> advances to Phase 2, <2> advances based on current state
    if has_tag(file_path, '<1>'):
        return 'phase2'
    if has_tag(file_path, '<2>'):
        # Determine if this is Phase 3 or Phase 4 by checking which progress files exist
        task_dir = os.path.dirname(file_path)
        has_requirements = os.path.exists(os.path.join(task_dir, '_prd_requirements.md'))
        has_architecture = os.path.exists(os.path.join(task_dir, '_prd_architecture.md'))
        if has_architecture:
            return 'phase4'
        elif has_requirements:
            return 'phase3'
        else:
            return 'phase3'  # fallback
    return None



def parse_task_priority(file_path):
    """Parse priority metadata from the first 500 chars of a task file.

    Looks for an HTML comment like:  <!-- priority: high -->
    Valid values: high, normal, low.  Defaults to 'normal'.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            header = f.read(500)
        match = re.search(r'<!--\s*priority:\s*(high|normal|low)\s*-->', header, re.IGNORECASE)
        if match:
            return match.group(1).lower()
    except (OSError, UnicodeDecodeError):
        pass
    return 'normal'


def parse_task_project(file_path, passed_project=None):
    """Determine the project for a task file.

    Resolution order:
    1. Directory name — inferred from the task directory (most common)
    2. Passed variable — from PRD system, Debug workflow, etc.
    3. ``<!-- project: name -->`` metadata comment in the file (rare)

    Args:
        file_path: Path to the task file.
        passed_project: Optional project name passed programmatically
            (e.g., from PRD decomposition or Debug workflow).
    """
    # 1. Directory name (primary — most tasks live in project-specific dirs)
    task_dir = os.path.basename(os.path.dirname(file_path))
    PROJECT_DIR_MAP = {
        'sat-enhancements': 'structured-achievement-tool',
        'sat-test-run': 'structured-achievement-tool',
        'maintenance': 'structured-achievement-tool',
    }
    if task_dir in PROJECT_DIR_MAP:
        return PROJECT_DIR_MAP[task_dir]

    # 2. Passed variable (programmatic — PRD system, Debug workflow)
    if passed_project:
        return passed_project

    # 3. Metadata comment (rare — manual override)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            header = f.read(500)
        match = re.search(r'<!--\s*project:\s*(.+?)\s*-->', header, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    except (OSError, UnicodeDecodeError):
        pass

    # Fallback: use directory name as-is
    return task_dir


def parse_task_depends_on(file_path):
    """Parse depends_on metadata from the first 500 chars of a task file.

    Looks for:  <!-- depends_on: story1.md, story2.md -->
    Returns a list of dependency identifiers (basenames), or empty list.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            header = f.read(500)
        match = re.search(r'<!--\s*depends_on:\s*(.+?)\s*-->', header, re.IGNORECASE)
        if match:
            deps = [d.strip() for d in match.group(1).split(',') if d.strip()]
            return deps
    except (OSError, UnicodeDecodeError):
        pass
    return []


def _check_prerequisites_met(db_manager, depends_on):
    """Check if all prerequisites for a task are met.

    A prerequisite is met when the dependency task is in 'finished' or
    'cancelled' state, or when the dependency cannot be found in the
    task_states table (treat as met — the dependency may have been
    cleaned up).

    Args:
        db_manager: DatabaseManager instance.
        depends_on: List of dependency identifiers (basenames or paths).

    Returns:
        True if all prerequisites are met, False if any are still active.
    """
    if not depends_on:
        return True

    for dep in depends_on:
        # Look up by basename match — depends_on stores basenames
        dep_state = db_manager.find_task_state_by_name(dep)
        if dep_state and dep_state['status'] not in ('finished', 'cancelled'):
            return False
    return True


def _detect_circular_deps(db_manager, task_path, depends_on):
    """Detect circular dependencies using topological sort (Kahn's algorithm).

    Reuses the same approach as DAGExecutor.detect_circular_dependencies()
    but operates on task_states rather than story graphs.

    If a cycle is detected, clears the depends_on for this task to break
    the cycle (same approach as story_agent.py line 141).

    Returns:
        The (possibly cleared) depends_on list.
    """
    if not depends_on:
        return depends_on

    from src.execution.dag_executor import DAGExecutor, CircularDependencyError

    # Build a mini dependency graph from task_states
    # Include the candidate task and all its transitive dependencies
    visited = set()
    to_visit = [task_path] + list(depends_on)
    graph_stories = []

    while to_visit:
        name = to_visit.pop(0)
        if name in visited:
            continue
        visited.add(name)

        state = db_manager.find_task_state_by_name(name)
        deps = []
        if state:
            try:
                deps = json.loads(state.get('depends_on', '[]') or '[]')
            except (json.JSONDecodeError, TypeError):
                deps = []
            for d in deps:
                if d not in visited:
                    to_visit.append(d)

        # Use the task_path or name as the story ID
        task_name = os.path.basename(state['task_path']) if state else name
        graph_stories.append({
            "id": task_name,
            "dependsOn": deps,
        })

    # Add the candidate task itself with its proposed dependencies
    candidate_name = os.path.basename(task_path)
    # Remove any existing entry for candidate (we'll add it with the proposed deps)
    graph_stories = [s for s in graph_stories if s["id"] != candidate_name]
    graph_stories.append({
        "id": candidate_name,
        "dependsOn": list(depends_on),
    })

    executor = DAGExecutor(graph_stories)
    if executor.detect_circular_dependencies():
        logging.warning(
            "Circular dependency detected involving %s — clearing depends_on to break cycle",
            task_path,
        )
        return []

    return depends_on


# Map signal types to the tag that triggered them
SIGNAL_TAGS = {
    'pending': '<Pending>',
    'plan': '<Plan>',
    'plan1': '<Plan 1>',
    'phase2': '<1>',
    'phase3': '<2>',
    'phase4': '<2>',
    'prd': '<PRD>',
}

# PRD signals don't get <Finished>/<Failed> — the orchestrator writes
# phase output + continuation tags directly to the file
PRD_SIGNALS = {'plan', 'plan1', 'phase2', 'phase3', 'phase4'}


async def process_task_wrapper(orchestrator, file_path, signal='pending',
                               slot_manager=None, slot_id=None,
                               rate_limit_handler=None, db_manager=None):
    """Wraps the orchestrator call to handle cancellation and set the right tags."""

    # --- Per-task attempt guard (Failure State 1) ---
    processing_attempts[file_path] = processing_attempts.get(file_path, 0) + 1
    attempt = processing_attempts[file_path]

    if attempt > MAX_TASK_ATTEMPTS:
        logging.error(
            "Task %s has been attempted %d times (max %d). Marking <Failed> to break retry loop.",
            file_path, attempt, MAX_TASK_ATTEMPTS,
        )
        # Try to mark whatever current tag is present as <Failed>
        for tag in ('<Pending>', '<Working>'):
            if mark_file_status(file_path, tag, '<Failed>'):
                break
        recently_completed[file_path] = time.time()
        if slot_manager and slot_id is not None:
            slot_manager.release_slot(slot_id)
        return

    logging.info(f"Locking task: {file_path} (signal={signal}, slot={slot_id}, attempt={attempt}/{MAX_TASK_ATTEMPTS})")

    # Immediately mark as working
    trigger_tag = SIGNAL_TAGS.get(signal, '<Pending>')
    mark_file_status(file_path, trigger_tag, '<Working>')

    # Track whether the mark_status_callback already updated the tag
    # (only used for normal 'pending' tasks, not PRD signals)
    _status_already_set = False

    # Route to the appropriate orchestrator method
    if signal in PRD_SIGNALS:
        orchestrator_task = asyncio.create_task(
            orchestrator.process_prd_phase(file_path, signal)
        )
    elif signal == 'prd':
        orchestrator_task = asyncio.create_task(
            orchestrator.process_prd_to_decompose(file_path)
        )
    else:
        # Build a callback so the orchestrator can update the task file tag
        # BEFORE it writes the final response file.
        def _mark_status(success: bool):
            nonlocal _status_already_set
            tag = '<Finished>' if success else '<Failed>'
            mark_file_status(file_path, '<Working>', tag)
            _status_already_set = True

        orchestrator_task = asyncio.create_task(
            orchestrator.process_task_file(file_path, mark_status_callback=_mark_status)
        )
    monitor_task = asyncio.create_task(monitor_cancellation(file_path, orchestrator_task))

    try:
        result = await orchestrator_task

        if signal in PRD_SIGNALS:
            # PRD phases: orchestrator already wrote output + tags to the file
            # Don't overwrite with <Finished>/<Failed>
            logging.info(f"PRD phase complete for {file_path}")
            processing_attempts.pop(file_path, None)  # Clear on success
            if db_manager:
                db_manager.transition_task_state(file_path, "finished")
        elif result and result.get("returncode") == 0:
            # The mark_status_callback may have already set the tag inside
            # the orchestrator (before the response file was written).
            if not _status_already_set:
                tagged = mark_file_status(file_path, '<Working>', '<Finished>')
                logging.info(f"Marked {file_path} as <Finished>: {tagged}")
            else:
                logging.info(f"Tag already set to <Finished> via callback for {file_path}")
            processing_attempts.pop(file_path, None)  # Clear on success
            # Remove from rate limit retry queue on success
            if rate_limit_handler:
                rate_limit_handler.remove_from_queue(file_path)
            # Record success in state hub
            if db_manager:
                db_manager.transition_task_state(file_path, "finished")
        else:
            # Check if failure was due to rate limiting
            if rate_limit_handler and result and result.get("rate_limited"):
                rate_limit_handler.queue_retry(
                    task_file=file_path,
                    story_id=result.get("story_id", "unknown"),
                    reason="rate_limit",
                )
                # Revert to Pending so it can be retried
                mark_file_status(file_path, '<Working>', '<Pending>')
                logging.info(f"Rate-limited task queued for retry: {file_path}")
                if db_manager:
                    db_manager.transition_task_state(file_path, "pending")
            elif not _status_already_set:
                tagged = mark_file_status(file_path, '<Working>', '<Failed>')
                logging.info(f"Marked {file_path} as <Failed>: {tagged} (returncode={result.get('returncode') if result else 'None'})")
            else:
                logging.info(f"Tag already set to <Failed> via callback for {file_path}")
            # Record failure in state hub
            if db_manager and not (rate_limit_handler and result and result.get("rate_limited")):
                error_msg = result.get("error", "") if result else "Unknown error"
                db_manager.transition_task_state(
                    file_path, "failed",
                    error_summary=str(error_msg)[:500],
                )
    except asyncio.CancelledError:
        logging.info(f"Task for {file_path} was cancelled.")
        if not mark_file_status(file_path, '<Cancel>', '<Finished>'):
             mark_file_status(file_path, '<Working>', '<Finished>')
        if db_manager:
            db_manager.transition_task_state(file_path, "cancelled")
    except Exception as task_e:
        logging.error(f"Task failed for {file_path}: {task_e}")
        mark_file_status(file_path, '<Working>', '<Failed>')
        if db_manager:
            db_manager.transition_task_state(
                file_path, "failed",
                error_summary=str(task_e)[:500],
            )
    finally:
        monitor_task.cancel()
        recently_completed[file_path] = time.time()
        if slot_manager and slot_id is not None:
            slot_manager.release_slot(slot_id)
        logging.info(f"Unlocking task: {file_path}")

async def async_main(no_resume: bool = False):
    _acquire_pid_lock()
    atexit.register(_release_pid_lock)
    logging.info("Starting Structured Achievement Tool (SAT) Daemon...")
    try:
        project_path = str(SAT_PROJECT_DIR)
        watch_dir = str(SAT_TASKS_DIR)
        if not os.path.isdir(watch_dir):
            raise ValueError(f"Watch directory not found: {watch_dir}")

        # Initialize checkpoint database (non-fatal)
        try:
            init_db(CHECKPOINT_DB_PATH)
        except Exception as e:
            logging.warning(f"Checkpoint DB init failed (non-fatal): {e}")

        # --- Config.json validation + backup ---
        config_path = str(CONFIG_JSON)
        config_bak_path = config_path + ".bak"
        REQUIRED_CONFIG_KEYS = {"routing_strategy", "execution", "metrics"}

        config_valid = False
        try:
            with open(config_path, "r") as f:
                config_data = json.load(f)
            missing = REQUIRED_CONFIG_KEYS - set(config_data.keys())
            if missing:
                raise ValueError(f"Missing required config keys: {missing}")
            config_valid = True
        except (OSError, json.JSONDecodeError, ValueError) as e:
            logging.error(f"Config validation failed: {e}")
            if os.path.exists(config_bak_path):
                logging.info("Restoring config.json from backup...")
                shutil.copy2(config_bak_path, config_path)
                logging.info("Config restored from config.json.bak")
            else:
                logging.error("No config.json.bak available to restore from")

        if config_valid:
            shutil.copy2(config_path, config_bak_path)
            logging.info("Config validated OK — backup saved to config.json.bak")

        # Resume incomplete workflows (unless --no-resume flag is set)
        if not no_resume:
            logging.info("Attempting to resume incomplete workflows...")
            try:
                resume_incomplete_workflows(CHECKPOINT_DB_PATH)
            except Exception as e:
                logging.error(f"Failed to resume workflows (will continue): {e}")
        else:
            logging.info("Skipping workflow resumption due to --no-resume flag")
    except Exception as e:
        logging.error(f"Configuration error: {e}")
        return

    orchestrator = Orchestrator(project_path=project_path)
    memory_dir = str(MEMORY_DIR)

    # --- Task State Hub (Option D) ---
    db_manager = DatabaseManager(str(SAT_DB))
    logging.info("Task state hub initialized (SQLite)")

    # --- FUSE Sentinel (Option A) ---
    fuse_sentinel = FuseSentinel()
    logging.info("FUSE sentinel initialized: %s", fuse_sentinel.sentinel_path)

    # Metrics exporter (Prometheus endpoint for Grafana)
    config_path = str(CONFIG_JSON)
    metrics_config = {}
    try:
        with open(config_path, "r") as f:
            metrics_config = json.load(f).get("metrics", {})
    except (OSError, json.JSONDecodeError):
        pass

    if metrics_config.get("enabled", False):
        audit_journal = AuditJournal(
            file_path=str(AUDIT_JOURNAL_PATH)
        )
        metrics_port = metrics_config.get("exporter_port", 9101)
        start_metrics_server(
            audit_journal=audit_journal,
            port=metrics_port,
            queue_dir=watch_dir,
        )
        logging.info(f"Metrics server started on port {metrics_port}")

    # Phase 2 components
    stability_timeout = StabilityTimeout(timeout_seconds=300)
    slot_manager = SlotManager(
        max_slots=2,
        lock_dir=os.path.join(memory_dir, "locks"),
    )
    rate_limit_handler = RateLimitHandler(
        state_file=str(RATE_LIMIT_STATE),
    )

    logging.info(f"Monitoring: {watch_dir} (slots={slot_manager.max_slots})")

    while True:
        try:
            # --- Check rate limit retry queue for ready tasks ---
            if not rate_limit_handler.is_token_exhausted():
                ready_retries = rate_limit_handler.get_ready_tasks()
                for entry in ready_retries:
                    if slot_manager.is_task_running(entry.task_file):
                        continue
                    slot_id = slot_manager.get_available_slot()
                    if slot_id is None:
                        break  # No slots available
                    if entry.task_file not in recently_completed:
                        slot_manager.assign_task(slot_id, entry.task_file)
                        logging.info(f"Retrying rate-limited task: {entry.task_file} (attempt {entry.attempt})")
                        asyncio.create_task(process_task_wrapper(
                            orchestrator, entry.task_file, signal='pending',
                            slot_manager=slot_manager, slot_id=slot_id,
                            rate_limit_handler=rate_limit_handler,
                        ))

            # --- FUSE Sentinel Check (Option A) ---
            fuse_healthy = fuse_sentinel.is_healthy()
            if not fuse_healthy:
                logging.warning(
                    "FUSE mount unhealthy (sentinel check failed, %d consecutive). "
                    "Skipping FUSE scan this cycle.",
                    fuse_sentinel.consecutive_failures,
                )
                # Skip the FUSE scan but don't skip rate-limit retries (they use the hub)
                await asyncio.sleep(5)
                continue

            # --- Scan for new tasks ---
            # Collect all candidate tasks first, then sort by priority
            _PRIORITY_ORDER = {'high': 0, 'normal': 1, 'low': 2}
            candidate_tasks = []  # [(priority, file_path, signal)]

            for task_dir_name in os.listdir(watch_dir):
                full_task_dir = os.path.join(watch_dir, task_dir_name)
                if os.path.isdir(full_task_dir) and not task_dir_name.startswith('_') and not task_dir_name.startswith('tmp'):
                    for filename in os.listdir(full_task_dir):
                        if filename.endswith('.md') and not filename.startswith('_') and '_response' not in filename:
                            file_path = os.path.join(full_task_dir, filename)
                            # Skip response files written by Claude
                            try:
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    header = f.read(200)
                                if '<!-- CLAUDE-RESPONSE -->' in header:
                                    continue
                            except (OSError, UnicodeDecodeError):
                                continue

                            if slot_manager.is_task_running(file_path) or file_path in recently_completed:
                                continue

                            sig = detect_signal(file_path)
                            if sig:
                                priority = parse_task_priority(file_path)
                                project = parse_task_project(file_path)
                                depends_on = parse_task_depends_on(file_path)
                                candidate_tasks.append((priority, file_path, sig, project, depends_on))
                            else:
                                # No direct signal — check stability timeout
                                # for files with '# <Pending>' (user hasn't acknowledged)
                                if stability_timeout.check_file(file_path):
                                    # Timeout triggered — convert to processable
                                    mark_file_status(file_path, '# <Pending>', '<Pending>')
                                    stability_timeout.reset(file_path)
                                    logging.info(f"Stability timeout: converted {file_path} for processing")
                                    # It will be picked up next poll cycle with <Pending>

            # Sort candidates: high priority first, then normal, then low
            candidate_tasks.sort(key=lambda t: _PRIORITY_ORDER.get(t[0], 1))

            for priority, file_path, sig, project, depends_on in candidate_tasks:
                # Record in state hub before processing
                db_manager.upsert_task_state(
                    file_path, "pending", signal=sig, priority=priority,
                    project=project, depends_on=depends_on if depends_on else None,
                )

                # --- Prerequisite enforcement ---
                # Merge depends_on from file metadata AND from DB
                task_state = db_manager.get_task_state(file_path)
                db_depends_on = []
                if task_state:
                    try:
                        db_depends_on = json.loads(task_state.get('depends_on', '[]') or '[]')
                    except (json.JSONDecodeError, TypeError):
                        pass

                all_deps = list(set(depends_on + db_depends_on))

                # Circular dependency detection (reuses DAG executor's topological sort)
                all_deps = _detect_circular_deps(db_manager, file_path, all_deps)

                if all_deps and not _check_prerequisites_met(db_manager, all_deps):
                    logging.info(f"Task blocked by prerequisites: {file_path} (depends_on={all_deps})")
                    continue

                slot_id = slot_manager.get_available_slot()
                if slot_id is None:
                    break  # No slots available
                slot_manager.assign_task(slot_id, file_path)

                # Transition to working in the hub
                db_manager.transition_task_state(
                    file_path, "working", signal=sig,
                    last_worker=f"slot-{slot_id}",
                )

                logging.info(f"New ready task detected: {file_path} (priority={priority}, project={project}, signal={sig}, slot={slot_id})")
                asyncio.create_task(process_task_wrapper(
                    orchestrator, file_path, signal=sig,
                    slot_manager=slot_manager, slot_id=slot_id,
                    rate_limit_handler=rate_limit_handler,
                    db_manager=db_manager,
                ))

            # Expire recently_completed entries after 60 seconds
            now = time.time()
            expired = [fp for fp, t in recently_completed.items() if now - t > 60]
            for fp in expired:
                del recently_completed[fp]
        except Exception as e:
            logging.error(f"Main loop error: {e}")

        await asyncio.sleep(5)

def main():
    """Main entry point for the daemon.

    Parses command-line arguments and starts the daemon with optional
    --no-resume flag to skip workflow resumption on startup.
    """
    parser = argparse.ArgumentParser(
        description="Structured Achievement Tool (SAT) Daemon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                     # Start daemon with resume enabled (default)
  %(prog)s --no-resume         # Start daemon without resuming workflows
  %(prog)s --help              # Show this help message
        """
    )
    parser.add_argument(
        '--no-resume',
        action='store_true',
        help='Skip workflow resumption on daemon startup (useful for debugging)'
    )

    args = parser.parse_args()

    try:
        asyncio.run(async_main(no_resume=args.no_resume))
    except KeyboardInterrupt:
        pass
    finally:
        _release_pid_lock()

if __name__ == "__main__":
    main()
