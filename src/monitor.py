import os, time, subprocess, logging, json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from src.core.paths import MONITOR_WATCH_DIRS, SAT_DB, RETRY_COUNTS as RETRY_COUNTS_PATH

# --- Task State Hub integration (Option D) ---
_db_manager = None

def _get_db_manager():
    """Lazy-initialize the DatabaseManager for state hub queries."""
    global _db_manager
    if _db_manager is None:
        try:
            from src.db.database_manager import DatabaseManager
            _db_manager = DatabaseManager(str(SAT_DB))
        except Exception as e:
            logging.warning(f"Could not initialize state hub: {e}")
    return _db_manager

WATCH_DIRS = [str(d) for d in MONITOR_WATCH_DIRS]

# How long a task can be in <Working> before we consider it stuck (seconds)
STUCK_TIMEOUT = 1800  # 30 minutes

# Maximum number of times a failed task will be retried before giving up
MAX_RETRIES = 10

# Persistent retry count file (survives service restarts)
RETRY_COUNT_FILE = str(RETRY_COUNTS_PATH)

# Track when we first saw a task stuck in <Working>
stuck_since = {}

# Track how many times each task has been retried
retry_counts = {}


def _load_retry_counts():
    """Load retry counts from persistent storage."""
    global retry_counts
    try:
        if os.path.exists(RETRY_COUNT_FILE):
            with open(RETRY_COUNT_FILE, 'r') as f:
                retry_counts = json.load(f)
    except Exception as e:
        logging.warning(f"Could not load retry counts: {e}")
        retry_counts = {}


def _save_retry_counts():
    """Save retry counts to persistent storage."""
    try:
        os.makedirs(os.path.dirname(RETRY_COUNT_FILE), exist_ok=True)
        with open(RETRY_COUNT_FILE, 'w') as f:
            json.dump(retry_counts, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
    except Exception as e:
        logging.warning(f"Could not save retry counts: {e}")

def is_task_file(filename):
    """Return True if this is an actual task file, not a response file.

    Task files have descriptive names like 001_health_check.md, 004_proactive_agency.md.
    Response files have names like 002_response.md, 003_response.md.
    """
    return filename.endswith('.md') and not filename.startswith('_') and '_response' not in filename

def is_service_active(service_name):
    try:
        res = subprocess.run(["systemctl", "--user", "is-active", service_name], capture_output=True, text=True)
        return res.stdout.strip() == "active"
    except:
        return False

PID_FILE = "/tmp/sat-daemon.pid"


def _daemon_pid_alive():
    """Check whether the daemon process identified by PID_FILE is actually running."""
    if not os.path.exists(PID_FILE):
        return False
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)  # signal 0 = existence check
        return True
    except (ValueError, ProcessLookupError, PermissionError, OSError):
        return False


def is_sat_busy():
    """Check if SAT is actively processing a task.

    Uses a two-pronged check (Failure State 7):
    1. Daemon PID must be alive.
    2. At least one task file is in <Working> state.
    If the daemon is dead but files say <Working>, the monitor treats SAT as
    NOT busy so stuck-task handling can kick in.
    """
    daemon_alive = _daemon_pid_alive()

    for d in WATCH_DIRS:
        if not os.path.exists(d):
            continue
        for f in os.listdir(d):
            if not is_task_file(f):
                continue
            path = os.path.join(d, f)
            try:
                with open(path, 'r') as file:
                    content = file.read()
                if "<Working>" in content:
                    if daemon_alive:
                        return True
                    else:
                        # Daemon is dead but file says <Working> — treat as stuck
                        logging.warning(
                            "Task %s is <Working> but daemon PID is gone — "
                            "treating as stuck, not busy", f,
                        )
                        return False
            except:
                pass
    return False

def release_safety(file_path):
    """Remove # from '# <Pending>' to make the file ready for processing."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        if "# <Pending>" in content:
            new_content = content.replace("# <Pending>", "<Pending>")
            with open(file_path, 'w') as f:
                f.write(new_content)
                f.flush()
                os.fsync(f.fileno())
            logging.info(f"Released safety for {file_path}")
            return True
    except Exception as e:
        logging.error(f"Error releasing safety: {e}")
    return False

def handle_failed_task(file_path, content):
    """Handle a task file that is in <Failed> state.

    Strategy:
    1. Log the failure
    2. Check for error details in response files
    3. Reset to # <User> so it can be retried on next cycle
    """
    task_dir = os.path.dirname(file_path)
    task_name = os.path.basename(file_path)

    logging.warning(f"Failed task detected: {task_name}")

    # Check retry count
    count = retry_counts.get(file_path, 0)
    if count >= MAX_RETRIES:
        logging.error(
            f"Task {task_name} has failed {count} times — max retries ({MAX_RETRIES}) "
            f"exceeded. Leaving in <Failed> state."
        )
        # Annotate the file so the user knows why it stopped retrying
        if "<!-- MAX_RETRIES_EXCEEDED -->" not in content:
            try:
                annotation = (
                    f"\n\n<!-- MAX_RETRIES_EXCEEDED -->\n"
                    f"**Monitor: This task has failed {count} times and will not be "
                    f"retried automatically. Manual intervention required.**\n"
                )
                with open(file_path, 'a') as f:
                    f.write(annotation)
                    f.flush()
                    os.fsync(f.fileno())
            except Exception as e:
                logging.error(f"Could not annotate max-retry task: {e}")
        return

    # Look for error details in response files
    response_files = sorted([
        f for f in os.listdir(task_dir)
        if f.endswith('.md') and '_response' in f
    ])

    error_info = ""
    for rf in response_files[-3:]:  # Check last 3 response files
        try:
            with open(os.path.join(task_dir, rf), 'r') as f:
                rc = f.read()
            if "failed" in rc.lower() or "error" in rc.lower() or "Exit Code: 1" in rc:
                error_info += f"\n--- {rf} ---\n{rc[-500:]}"  # Last 500 chars
        except:
            pass

    if error_info:
        logging.info(f"Error details for {task_name}: {error_info[:200]}")

    # Increment retry count and persist
    retry_counts[file_path] = count + 1
    _save_retry_counts()

    # Also increment in state hub if available
    db = _get_db_manager()
    if db:
        db.increment_task_retry(file_path)
        db.transition_task_state(file_path, "pending")

    # Reset the task to queued state so it can be retried
    try:
        new_content = content.replace("<Failed>", "# <Pending>")
        with open(file_path, 'w') as f:
            f.write(new_content)
            f.flush()
            os.fsync(f.fileno())
        logging.info(f"Reset failed task {task_name} to queued state for retry (attempt {count + 1}/{MAX_RETRIES})")
    except Exception as e:
        logging.error(f"Could not reset failed task {task_name}: {e}")

def _is_waiting_for_human(file_path):
    """Check if a task's checkpoint status is 'waiting_for_human'.

    Looks up the task in the checkpoint database. If the status is
    'waiting_for_human', the task is legitimately waiting and should
    not be marked as stuck.
    """
    try:
        from src.core.checkpoint_manager import read_checkpoint, STATUS_WAITING_FOR_HUMAN
        db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".memory", "checkpoints.db"
        )
        if not os.path.exists(db_path):
            return False
        # Build task_id from file path (dir_name/filename_stem)
        dir_name = os.path.basename(os.path.dirname(file_path))
        file_stem = os.path.splitext(os.path.basename(file_path))[0]
        task_id = f"{dir_name}/{file_stem}"
        cp = read_checkpoint(db_path, task_id)
        if cp and cp.status == STATUS_WAITING_FOR_HUMAN:
            return True
    except Exception:
        pass
    return False


def handle_stuck_task(file_path, content):
    """Handle a task that's been in <Working> too long.

    Strategy:
    1. Check if the task is waiting for human response (skip if so)
    2. Track how long it's been stuck
    3. After STUCK_TIMEOUT, mark as <Failed> so it can be retried
    """
    # Don't mark tasks waiting for human input as stuck
    if _is_waiting_for_human(file_path):
        logging.info(
            f"Task in <Working> but waiting for human response — not stuck: "
            f"{os.path.basename(file_path)}"
        )
        return

    now = time.time()

    if file_path not in stuck_since:
        stuck_since[file_path] = now
        logging.warning(f"Task may be stuck in <Working>: {os.path.basename(file_path)}")
        return

    elapsed = now - stuck_since[file_path]
    if elapsed > STUCK_TIMEOUT:
        logging.error(f"Task stuck for {elapsed/60:.0f} min, marking as <Failed>: {os.path.basename(file_path)}")
        try:
            new_content = content.replace("<Working>", "<Failed>")
            with open(file_path, 'w') as f:
                f.write(new_content)
                f.flush()
                os.fsync(f.fileno())
            del stuck_since[file_path]
        except Exception as e:
            logging.error(f"Could not mark stuck task as failed: {e}")
    else:
        logging.info(f"Task in <Working> for {elapsed/60:.0f} min (timeout at {STUCK_TIMEOUT/60:.0f} min): {os.path.basename(file_path)}")

def ensure_sat_running():
    """Make sure the SAT daemon is running. Restart if needed."""
    if not is_service_active("sat.service"):
        logging.warning("SAT service is not active. Restarting...")
        subprocess.run(["systemctl", "--user", "restart", "sat.service"])
        time.sleep(3)
        if is_service_active("sat.service"):
            logging.info("SAT service restarted successfully")
        else:
            logging.error("SAT service failed to restart")
            return False
    return True

def check_queue():
    """Main monitoring cycle. Returns True if any action was taken."""
    # First ensure SAT is running
    if not ensure_sat_running():
        return False

    sat_busy = is_sat_busy()

    # Always check for stuck <Working> tasks, even when daemon is busy.
    # Without this, a daemon that's alive but idle creates a permanent
    # deadlock: is_sat_busy() returns True (PID alive + <Working> file),
    # but the daemon never processes the task, and the stuck-task handler
    # never fires.
    for d in WATCH_DIRS:
        if not os.path.exists(d):
            continue
        for f in sorted(os.listdir(d)):
            if not is_task_file(f):
                continue
            path = os.path.join(d, f)
            try:
                with open(path, 'r') as file:
                    content = file.read()
            except Exception:
                continue
            if "<Working>" in content:
                handle_stuck_task(path, content)

    # Clear stuck tracking for files that are no longer stuck
    for tracked_path in list(stuck_since.keys()):
        if not os.path.exists(tracked_path):
            del stuck_since[tracked_path]
        else:
            try:
                with open(tracked_path, 'r') as f:
                    c = f.read()
                if "<Working>" not in c:
                    del stuck_since[tracked_path]
            except:
                pass

    # If SAT is actively processing, don't release new tasks
    if sat_busy:
        logging.info("SAT is busy processing a task")
        return False

    # SAT is idle — scan for failed tasks and queued tasks
    for d in WATCH_DIRS:
        if not os.path.exists(d):
            continue

        files = sorted([f for f in os.listdir(d) if is_task_file(f)])

        for f in files:
            path = os.path.join(d, f)
            try:
                with open(path, 'r') as file:
                    content = file.read()
            except Exception as e:
                logging.error(f"Could not read {f}: {e}")
                continue

            # Skip <Working> tasks — already handled above
            if "<Working>" in content:
                continue

            # Handle failed tasks — reset them for retry
            if "<Failed>" in content:
                handle_failed_task(path, content)
                return True  # Action taken

            # Release next queued task
            if "# <Pending>" in content:
                logging.info(f"Releasing next task: {f}")
                release_safety(path)
                return True  # Action taken

    return False  # No action taken

def _cleanup_retry_counts():
    """Remove retry count entries for tasks that are no longer in <Failed> state."""
    changed = False
    for file_path in list(retry_counts.keys()):
        if not os.path.exists(file_path):
            del retry_counts[file_path]
            changed = True
            continue
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            # If task is <Finished> or no longer exists, clear the counter
            if "<Finished>" in content:
                del retry_counts[file_path]
                changed = True
        except Exception:
            pass
    if changed:
        _save_retry_counts()


BASE_INTERVAL = 120   # 2 minutes
MAX_INTERVAL = 900    # 15 minutes

# G-Eval scoring interval: only score every N idle cycles to avoid thrashing
GEVAL_SCORE_INTERVAL = 3  # Score every 3rd idle cycle


def _run_idle_scoring():
    """Run G-Eval idle-time scoring if available."""
    try:
        from src.evaluation.geval_scorer import score_pending_invocations
        scored = score_pending_invocations()
        if scored > 0:
            logging.info(f"G-Eval: scored {scored} invocations during idle")
    except ImportError:
        pass  # Module not available
    except Exception as e:
        logging.debug(f"G-Eval scoring error: {e}")


def main():
    logging.info("SAT Monitor Service started.")
    logging.info(f"Watching directories: {WATCH_DIRS}")
    logging.info(f"Stuck timeout: {STUCK_TIMEOUT}s")
    logging.info(f"Max retries: {MAX_RETRIES}")
    _load_retry_counts()
    cycle = 0
    idle_cycles = 0
    current_interval = BASE_INTERVAL
    while True:
        try:
            action_taken = check_queue()
            if action_taken:
                current_interval = BASE_INTERVAL
                idle_cycles = 0
                logging.debug(f"Action taken, reset interval to {BASE_INTERVAL}s")
            else:
                current_interval = min(current_interval * 2, MAX_INTERVAL)
                idle_cycles += 1
                logging.debug(f"Idle cycle {idle_cycles}, interval now {current_interval}s")
                # Run G-Eval scoring during idle time
                if idle_cycles % GEVAL_SCORE_INTERVAL == 0:
                    _run_idle_scoring()
            # Clean up retry counts every 15 cycles
            cycle += 1
            if cycle % 15 == 0:
                _cleanup_retry_counts()
        except Exception as e:
            logging.error(f"Monitor error: {e}")
            current_interval = BASE_INTERVAL  # Reset on error
        time.sleep(current_interval)

if __name__ == "__main__":
    main()
