import os, time, subprocess, logging, re, json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

WATCH_DIRS = [
    "/home/johnlane/GoogleDrive/DriveSyncFiles/claude-tasks/sat-enhancements",
    "/home/johnlane/GoogleDrive/DriveSyncFiles/claude-tasks/marketing-automation"
]

# How long a task can be in <Working> before we consider it stuck (seconds)
STUCK_TIMEOUT = 1800  # 30 minutes

# Track when we first saw a task stuck in <Working>
stuck_since = {}

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

def is_sat_busy():
    """Check if SAT is actively processing a task."""
    # Check for ralph-pro processes
    res = subprocess.run(["pgrep", "-f", "ralph-pro.js"], capture_output=True)
    if res.returncode == 0:
        return True
    # Check for any file in <Working> state
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
                    return True
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

    # Reset the task to queued state so it can be retried
    try:
        new_content = content.replace("<Failed>", "# <Pending>")
        with open(file_path, 'w') as f:
            f.write(new_content)
            f.flush()
            os.fsync(f.fileno())
        logging.info(f"Reset failed task {task_name} to queued state for retry")
    except Exception as e:
        logging.error(f"Could not reset failed task {task_name}: {e}")

def handle_stuck_task(file_path, content):
    """Handle a task that's been in <Working> too long.

    Strategy:
    1. Track how long it's been stuck
    2. After STUCK_TIMEOUT, mark as <Failed> so it can be retried
    """
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
    """Main monitoring cycle."""
    # First ensure SAT is running
    if not ensure_sat_running():
        return

    # If SAT is actively processing, just check for stuck tasks
    if is_sat_busy():
        logging.info("SAT is busy processing a task")
        return

    # SAT is idle — scan for tasks to process
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

            # Handle stuck tasks
            if "<Working>" in content:
                handle_stuck_task(path, content)
                return  # Don't release more tasks while one is (maybe) working

            # Handle failed tasks — reset them for retry
            if "<Failed>" in content:
                handle_failed_task(path, content)
                return  # One action per cycle

            # Release next queued task
            if "# <Pending>" in content:
                logging.info(f"Releasing next task: {f}")
                release_safety(path)
                return  # One release per cycle

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

def main():
    logging.info("SAT Monitor Service started.")
    logging.info(f"Watching directories: {WATCH_DIRS}")
    logging.info(f"Stuck timeout: {STUCK_TIMEOUT}s")
    while True:
        try:
            check_queue()
        except Exception as e:
            logging.error(f"Monitor error: {e}")
        time.sleep(120)  # Check every 2 minutes

if __name__ == "__main__":
    main()
