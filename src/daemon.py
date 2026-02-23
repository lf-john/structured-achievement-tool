import time, logging, os, asyncio, traceback, re
from src.orchestrator_v2 import OrchestratorV2 as Orchestrator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# In-memory lock to prevent concurrent processing of the same file
# This is critical for slow mounts like Google Drive
active_tasks = set()

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

async def process_task_wrapper(orchestrator, file_path):
    """Wraps the orchestrator call to handle cancellation and set the right tags."""
    if file_path in active_tasks:
        return
    
    active_tasks.add(file_path)
    logging.info(f"Locking task: {file_path}")
    
    # Immediately mark as working
    mark_file_status(file_path, '<Pending>', '<Working>')
    
    orchestrator_task = asyncio.create_task(orchestrator.process_task_file(file_path))
    monitor_task = asyncio.create_task(monitor_cancellation(file_path, orchestrator_task))
    
    try:
        result = await orchestrator_task
        if result and result.get("returncode") == 0:
            mark_file_status(file_path, '<Working>', '<Finished>')
        else:
            mark_file_status(file_path, '<Working>', '<Failed>')
    except asyncio.CancelledError:
        logging.info(f"Task for {file_path} was cancelled.")
        if not mark_file_status(file_path, '<Cancel>', '<Finished>'):
             mark_file_status(file_path, '<Working>', '<Finished>')
    except Exception as task_e:
        logging.error(f"Task failed for {file_path}: {task_e}")
        mark_file_status(file_path, '<Working>', '<Failed>')
    finally:
        monitor_task.cancel()
        active_tasks.remove(file_path)
        logging.info(f"Unlocking task: {file_path}")

async def async_main():
    logging.info("Starting Structured Achievement Tool (SAT) Daemon...")
    try:
        project_path = os.path.expanduser("~/projects/structured-achievement-tool")
        watch_dir = os.path.expanduser("~/GoogleDrive/DriveSyncFiles/claude-tasks")
        if not os.path.isdir(watch_dir):
            raise ValueError(f"Watch directory not found: {watch_dir}")
    except Exception as e:
        logging.error(f"Configuration error: {e}")
        return

    orchestrator = Orchestrator(project_path=project_path)
    logging.info(f"Monitoring: {watch_dir}")

    while True:
        try:
            for task_dir_name in os.listdir(watch_dir):
                full_task_dir = os.path.join(watch_dir, task_dir_name)
                if os.path.isdir(full_task_dir) and not task_dir_name.startswith('_') and not task_dir_name.startswith('tmp'):
                    for filename in os.listdir(full_task_dir):
                        if filename.endswith('.md') and not filename.startswith('_') and '_response' not in filename:
                            file_path = os.path.join(full_task_dir, filename)
                            if file_path not in active_tasks and has_tag(file_path, '<Pending>'):
                                logging.info(f"New ready task detected: {file_path}")
                                # Launch task in background so we can continue monitoring other directories
                                asyncio.create_task(process_task_wrapper(orchestrator, file_path))
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
