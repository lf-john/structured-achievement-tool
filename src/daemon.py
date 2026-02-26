import time, logging, os, asyncio, traceback, re, json
from src.orchestrator_v2 import OrchestratorV2 as Orchestrator
from src.execution.stability_timeout import StabilityTimeout
from src.execution.slot_manager import SlotManager
from src.execution.rate_limit_handler import RateLimitHandler
from src.execution.audit_journal import AuditJournal
from src.monitoring.metrics_exporter import start_metrics_server

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Recently completed tasks: {file_path: completion_time} — prevents re-detection
# on slow FUSE mounts where tag writes may not propagate immediately
recently_completed = {}

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
                               rate_limit_handler=None):
    """Wraps the orchestrator call to handle cancellation and set the right tags."""
    logging.info(f"Locking task: {file_path} (signal={signal}, slot={slot_id})")

    # Immediately mark as working
    trigger_tag = SIGNAL_TAGS.get(signal, '<Pending>')
    mark_file_status(file_path, trigger_tag, '<Working>')

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
        orchestrator_task = asyncio.create_task(
            orchestrator.process_task_file(file_path)
        )
    monitor_task = asyncio.create_task(monitor_cancellation(file_path, orchestrator_task))

    try:
        result = await orchestrator_task

        if signal in PRD_SIGNALS:
            # PRD phases: orchestrator already wrote output + tags to the file
            # Don't overwrite with <Finished>/<Failed>
            logging.info(f"PRD phase complete for {file_path}")
        elif result and result.get("returncode") == 0:
            tagged = mark_file_status(file_path, '<Working>', '<Finished>')
            logging.info(f"Marked {file_path} as <Finished>: {tagged}")
            # Remove from rate limit retry queue on success
            if rate_limit_handler:
                rate_limit_handler.remove_from_queue(file_path)
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
            else:
                tagged = mark_file_status(file_path, '<Working>', '<Failed>')
                logging.info(f"Marked {file_path} as <Failed>: {tagged} (returncode={result.get('returncode') if result else 'None'})")
    except asyncio.CancelledError:
        logging.info(f"Task for {file_path} was cancelled.")
        if not mark_file_status(file_path, '<Cancel>', '<Finished>'):
             mark_file_status(file_path, '<Working>', '<Finished>')
    except Exception as task_e:
        logging.error(f"Task failed for {file_path}: {task_e}")
        mark_file_status(file_path, '<Working>', '<Failed>')
    finally:
        monitor_task.cancel()
        recently_completed[file_path] = time.time()
        if slot_manager and slot_id is not None:
            slot_manager.release_slot(slot_id)
        logging.info(f"Unlocking task: {file_path}")

async def async_main():
    logging.info("Starting Structured Achievement Tool (SAT) Daemon...")
    try:
        project_path = os.path.expanduser("~/projects/structured-achievement-tool")
        watch_dir = os.path.expanduser("~/GoogleDrive/DriveSyncFiles/sat-tasks")
        if not os.path.isdir(watch_dir):
            raise ValueError(f"Watch directory not found: {watch_dir}")
    except Exception as e:
        logging.error(f"Configuration error: {e}")
        return

    orchestrator = Orchestrator(project_path=project_path)
    memory_dir = os.path.join(project_path, ".memory")

    # Metrics exporter (Prometheus endpoint for Grafana)
    config_path = os.path.join(project_path, "config.json")
    metrics_config = {}
    try:
        with open(config_path, "r") as f:
            metrics_config = json.load(f).get("metrics", {})
    except (OSError, json.JSONDecodeError):
        pass

    if metrics_config.get("enabled", False):
        audit_journal = AuditJournal(
            file_path=os.path.join(memory_dir, "audit_journal.jsonl")
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
        state_file=os.path.join(memory_dir, "rate_limit_state.json"),
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

            # --- Scan for new tasks ---
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

                            signal = detect_signal(file_path)
                            if signal:
                                slot_id = slot_manager.get_available_slot()
                                if slot_id is None:
                                    break  # No slots — stop scanning this dir
                                slot_manager.assign_task(slot_id, file_path)
                                logging.info(f"New ready task detected: {file_path} (signal={signal}, slot={slot_id})")
                                asyncio.create_task(process_task_wrapper(
                                    orchestrator, file_path, signal=signal,
                                    slot_manager=slot_manager, slot_id=slot_id,
                                    rate_limit_handler=rate_limit_handler,
                                ))
                            else:
                                # No direct signal — check stability timeout
                                # for files with '# <Pending>' (user hasn't acknowledged)
                                if stability_timeout.check_file(file_path):
                                    # Timeout triggered — convert to processable
                                    mark_file_status(file_path, '# <Pending>', '<Pending>')
                                    stability_timeout.reset(file_path)
                                    logging.info(f"Stability timeout: converted {file_path} for processing")
                                    # It will be picked up next poll cycle with <Pending>

            # Expire recently_completed entries after 60 seconds
            now = time.time()
            expired = [fp for fp, t in recently_completed.items() if now - t > 60]
            for fp in expired:
                del recently_completed[fp]
        except Exception as e:
            logging.error(f"Main loop error: {e}")

        await asyncio.sleep(5)

def main():
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
