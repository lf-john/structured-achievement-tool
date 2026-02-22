import time, logging, os, asyncio, traceback, re
from src.orchestrator import Orchestrator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
            return True
        return False
    except Exception as e:
        logging.error(f"Error updating tags in {file_path}: {e}")
        return False

async def monitor_cancellation(file_path, task):
    """Continuously check if <Cancel> is added to the file. If so, cancel the asyncio task."""
    while not task.done():
        if has_tag(file_path, '<Cancel>'):
            logging.info(f"Cancellation requested for {file_path}")
            task.cancel()
            break
        await asyncio.sleep(2)

async def process_task_wrapper(orchestrator, file_path):
    """Wraps the orchestrator call to handle cancellation and set the right tags."""
    # Instantly mark as working
    mark_file_status(file_path, '<User>', '<Working>')
    
    # We must run process_task_file in a task so we can monitor it concurrently
    orchestrator_task = asyncio.create_task(orchestrator.process_task_file(file_path))
    monitor_task = asyncio.create_task(monitor_cancellation(file_path, orchestrator_task))
    
    try:
        result = await orchestrator_task
        if result and result.get("status") == "complete" and result.get("returncode", 0) == 0:
            mark_file_status(file_path, '<Working>', '<Finished>')
        else:
            mark_file_status(file_path, '<Working>', '<Failed>')
    except asyncio.CancelledError:
        logging.info(f"Task for {file_path} was cancelled.")
        # Attempt to replace Cancel or Working with Finished (user requested reset to Finished on cancel)
        if not mark_file_status(file_path, '<Cancel>', '<Finished>'):
             mark_file_status(file_path, '<Working>', '<Finished>')
    except Exception as task_e:
        logging.error(f"Task failed for {file_path}: {task_e}")
        logging.error(traceback.format_exc())
        mark_file_status(file_path, '<Working>', '<Failed>')
    finally:
        monitor_task.cancel()

async def async_main():
    logging.info("Starting Structured Achievement Tool (SAT) Daemon...")
    try:
        project_path = os.path.expanduser("~/projects/structured-achievement-tool")
        watch_dir = os.path.expanduser("~/GoogleDrive/DriveSyncFiles/claude-tasks")
    except Exception as e:
        logging.error(f"Configuration error: {e}")
        return

    orchestrator = Orchestrator(project_path=project_path)
    logging.info(f"Monitoring: {watch_dir}")
    processed_files = set()

    while True:
        try:
            for task_dir_name in os.listdir(watch_dir):
                full_task_dir = os.path.join(watch_dir, task_dir_name)
                if os.path.isdir(full_task_dir) and not task_dir_name.startswith('_'):
                    for filename in os.listdir(full_task_dir):
                        if filename.endswith('.md') and not filename.startswith('_'):
                            file_path = os.path.join(full_task_dir, filename)
                            if has_tag(file_path, '<User>') and file_path not in processed_files:
                                logging.info(f"New ready task detected: {file_path}")
                                processed_files.add(file_path)
                                # We await the wrapper so tasks run sequentially but support cancellation
                                await process_task_wrapper(orchestrator, file_path)
                                # Remove from processed files once done so it can be re-triggered later
                                processed_files.remove(file_path)
        except Exception as e:
            logging.error(f"Main loop error: {e}")
            logging.error(traceback.format_exc())
        
        await asyncio.sleep(5)

def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    main()
