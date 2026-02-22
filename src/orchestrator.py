import os, json, asyncio, requests
from typing import Dict, Optional
from src.core.story_agent import StoryAgent
from src.core.vector_store import VectorStore
from src.core.embedding_service import EmbeddingService

class Orchestrator:
    def __init__(self, project_path: str, vector_db_path: Optional[str] = None):
        self.project_path = project_path
        self.agent = StoryAgent(project_path=self.project_path)

        # Initialize vector store for RAG memory
        if vector_db_path is None:
            vector_db_path = os.path.join(project_path, ".memory", "vectors.db")

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(vector_db_path), exist_ok=True)

        # Initialize embedding service and vector store
        embedding_service = EmbeddingService(model_name="nomic-embed-text")
        self.vector_store = VectorStore(
            db_path=vector_db_path,
            embedding_service=embedding_service,
            dimension=768  # nomic-embed-text produces 768-dimensional vectors
        )

    def _send_notification(self, title: str, message: str, priority: str = "default", tags: str = ""):
        topic = os.environ.get("NTFY_TOPIC", "johnlane-claude-tasks")
        server = os.environ.get("NTFY_SERVER", "https://ntfy.sh")
        if not topic: return
        url = f"{server}/{topic}"
        headers = {"Title": title} if title else {}
        if priority != "default": headers["Priority"] = priority
        if tags: headers["Tags"] = tags
        try:
            requests.post(url, data=message.encode("utf-8"), headers=headers, timeout=5)
        except Exception as e: print(f"Failed to send notification: {e}")

    async def _write_response(self, task_dir: str, content: str, is_final=False):
        """Writes a response file, finding the next available number."""
        i = 2
        while True:
            filename = f"{i:03d}_response.md"
            filepath = os.path.join(task_dir, filename)
            if not os.path.exists(filepath):
                # We do NOT add <User> here automatically anymore since the user workflow relies on adding <User> to trigger.
                # Oh wait, the prompt says "the file always ends with `# <User>`". 
                # "Then when it creates a file, the file always ends with `# <User>`. This will not trigger processing. But I will edit the file and remove the `#`. This will trigger processing."
                safeguard = "\n\n# <User>" if not is_final else ""
                full_content = content + safeguard
                with open(filepath, "w") as f:
                    f.write(full_content)
                print(f"Response written to {filepath}")
                return
            i += 1

    async def process_task_file(self, file_path: str):
        print(f"Orchestrator processing: {file_path}")
        task_dir = os.path.dirname(file_path)
        with open(file_path, "r") as f:
            user_request = f.read()

        classification = self.agent.classify(user_request)
        task_type = classification.get("task_type", "development")

        task_name = os.path.splitext(os.path.basename(file_path))[0]

        # Search for similar tasks in vector memory for context
        similar_tasks_context = ""
        try:
            similar_tasks = self.vector_store.search(user_request, k=3)
            if similar_tasks:
                similar_tasks_context = "\n\n## Similar Past Tasks (for context)\n"
                for idx, task in enumerate(similar_tasks, 1):
                    similar_tasks_context += f"\n### Similar Task {idx} (similarity: {task.get('score', 0):.2f})\n"
                    similar_tasks_context += f"{task['text']}\n"
                    if task.get('metadata'):
                        similar_tasks_context += f"Metadata: {json.dumps(task['metadata'])}\n"
        except Exception as e:
            print(f"Warning: Failed to search vector store: {e}")

        # Use the name of the directory as the taskId to keep everything contained under one Ralph Pro project task.
        parent_dir_name = os.path.basename(os.path.dirname(file_path))

        ralph_task_dir = os.path.join(
            "/home/johnlane/ralph-pro/data/projects/structured-achievement-tool/tasks",
            parent_dir_name
        )
        os.makedirs(os.path.join(ralph_task_dir, "output"), exist_ok=True)

        existing_prd = None
        prd_path = os.path.join(ralph_task_dir, "prd.json")
        if os.path.exists(prd_path):
            try:
                with open(prd_path, "r") as f: existing_prd = json.load(f)
            except: pass

        existing_progress = None
        progress_path = os.path.join(ralph_task_dir, "progress.json")
        if os.path.exists(progress_path):
            try:
                with open(progress_path, "r") as f: existing_progress = json.load(f)
            except: pass

        print(f"Decomposing task '{parent_dir_name}' (file: {task_name})...")

        # Enrich the user request with similar task context
        enriched_request = user_request + similar_tasks_context
        prd = self.agent.decompose(enriched_request, task_type, existing_prd, existing_progress)
        
        with open(prd_path, "w") as f:
            json.dump(prd, f, indent=4)
        
        if not os.path.exists(os.path.join(ralph_task_dir, "task.json")):
            with open(os.path.join(ralph_task_dir, "task.json"), "w") as f:
                json.dump({"id": parent_dir_name, "name": f"Task from {parent_dir_name}"}, f, indent=4)
        
        if not os.path.exists(progress_path):
            with open(progress_path, "w") as f:
                json.dump({"taskId": parent_dir_name, "completedStories": []}, f, indent=4)

        self._send_notification(
            title=f"SAT: Task Decomposed ({parent_dir_name})",
            message=f"Decomposed into {len(prd.get('stories', []))} stories. Handing off to Ralph Pro.",
            tags="memo,robot"
        )

        await self._write_response(task_dir, f"Task '{task_name}' has been decomposed. Beginning implementation via TDD.")

        # Execute Ralph Pro
        print(f"Invoking Ralph Pro for task: {parent_dir_name}")
        cmd = f"cd /home/johnlane/ralph-pro/cli && node ralph-pro.js --project /home/johnlane/projects/structured-achievement-tool --task {parent_dir_name}"
        
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await process.communicate()
        except asyncio.CancelledError:
            print(f"Task cancelled. Terminating Ralph Pro process {process.pid}...")
            process.terminate()
            await process.wait()
            raise
        
        log_content = f"--- Ralph Pro Execution Log for {parent_dir_name} ---\n\n"
        log_content += f"Exit Code: {process.returncode}\n\n"
        log_content += "--- STDOUT ---\n"
        log_content += stdout.decode()
        log_content += "\n--- STDERR ---\n"
        log_content += stderr.decode()

        if process.returncode == 0:
            final_message = f"Task '{parent_dir_name}' completed successfully."
        else:
            final_message = f"Task '{parent_dir_name}' failed during execution. See logs for details."

        await self._write_response(task_dir, log_content)
        await self._write_response(task_dir, final_message, is_final=True)

        # Embed the completed task in vector memory for future context
        try:
            # Create a document combining request and response
            task_document = f"Request: {user_request}\n\nResponse: {log_content}\n\nResult: {final_message}"

            # Metadata about the task
            metadata = {
                "task_id": parent_dir_name,
                "task_name": task_name,
                "task_type": task_type,
                "file_path": file_path,
                "success": process.returncode == 0,
                "returncode": process.returncode
            }

            # Add to vector store
            self.vector_store.add_document(task_document, metadata)
            print(f"Task embedded in vector memory for future reference")
        except Exception as e:
            print(f"Warning: Failed to embed task in vector memory: {e}")

        return {"status": "complete", "returncode": process.returncode}
