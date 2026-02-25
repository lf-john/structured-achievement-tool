"""
Orchestrator v2 — Native Python story execution via LangGraph workflows.

Replaces the Ralph Pro delegation with:
  classify → decompose → DAGExecutor → story_executor per story

Keeps: vector memory search, response writing, notifications, task embedding.
Removes: all Ralph Pro references (prd.json path, ralph-pro CLI, progress.json).
"""

import os
import json
import asyncio
import logging
from typing import Dict, Optional

from src.agents.classifier_agent import ClassifierAgent
from src.agents.story_agent import StoryAgent
from src.llm.routing_engine import RoutingEngine
from src.execution.dag_executor import DAGExecutor
from src.execution.story_executor import execute_story, StoryResult
from src.notifications.notifier import Notifier
from src.core.vector_store import VectorStore
from src.core.embedding_service import EmbeddingService
from src.agents.base_agent import BaseAgent
from src.llm.prompt_builder import load_template, substitute_placeholders, TEMPLATE_DIR
from src.llm.response_parser import extract_json
from src.llm.cli_runner import invoke as cli_invoke
from src.db.database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class OrchestratorV2:
    """Task orchestrator that executes stories natively via LangGraph workflows."""

    def __init__(self, project_path: str, vector_db_path: Optional[str] = None):
        self.project_path = project_path
        config_path = os.path.join(project_path, "config.json")

        # LLM routing engine
        self.routing_engine = RoutingEngine(config_path=config_path)

        # Agents
        self.classifier = ClassifierAgent(routing_engine=self.routing_engine)
        self.story_agent = StoryAgent(routing_engine=self.routing_engine)

        # Notifications
        self.notifier = Notifier()

        # Vector memory (optional, graceful degradation)
        self.vector_store = None
        try:
            if vector_db_path is None:
                vector_db_path = os.path.join(project_path, ".memory", "vectors.db")
            os.makedirs(os.path.dirname(vector_db_path), exist_ok=True)
            embedding_service = EmbeddingService(model_name="nomic-embed-text")
            self.vector_store = VectorStore(
                db_path=vector_db_path,
                embedding_service=embedding_service,
                dimension=768,
            )
        except Exception as e:
            logger.warning(f"Vector store initialization failed: {e}")

        # Load execution config
        self.config = {}
        if os.path.exists(config_path):
            with open(config_path) as f:
                self.config = json.load(f)

        exec_config = self.config.get("execution", {})
        self.max_retries = exec_config.get("max_retries_per_story", 5)
        self.mediator_enabled = exec_config.get("enable_mediator", False)

    async def _write_response(self, task_dir: str, content: str, is_final: bool = False):
        """Write a response file, finding the next available number."""
        i = 2
        while True:
            filename = f"{i:03d}_response.md"
            filepath = os.path.join(task_dir, filename)
            if not os.path.exists(filepath):
                safeguard = "\n\n# <Pending>" if not is_final else ""
                full_content = content + safeguard
                with open(filepath, "w") as f:
                    f.write(full_content)
                    f.flush()
                    os.fsync(f.fileno())
                logger.info(f"Response written to {filepath}")
                return
            i += 1

    async def process_task_file(self, file_path: str):
        """Process a task file: classify, decompose, execute stories.

        Args:
            file_path: Path to the .md task file

        Returns:
            dict with status and returncode
        """
        logger.info(f"Orchestrator processing: {file_path}")
        task_dir = os.path.dirname(file_path)
        task_id = os.path.basename(task_dir)

        with open(file_path, "r") as f:
            user_request = f.read()

        # --- Classify ---
        classification = await self.classifier.classify(user_request, self.project_path)
        task_type = classification.task_type
        logger.info(f"Task classified as: {task_type} (confidence: {classification.confidence})")

        # --- Search vector memory for context ---
        rag_context = ""
        if self.vector_store:
            try:
                similar_tasks = self.vector_store.search(user_request, k=3)
                if similar_tasks:
                    parts = ["\n## Similar Past Tasks (for context)\n"]
                    for idx, task in enumerate(similar_tasks, 1):
                        parts.append(f"\n### Similar Task {idx} (similarity: {task.get('score', 0):.2f})")
                        parts.append(task.get("text", ""))
                    rag_context = "\n".join(parts)
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")

        # --- Decompose ---
        logger.info(f"Decomposing task '{task_id}'...")
        decompose_result = await self.story_agent.decompose(
            user_request=user_request,
            task_type=task_type,
            working_directory=self.project_path,
            rag_context=rag_context,
        )

        stories = [s.model_dump() for s in decompose_result.stories]
        story_count = len(stories)
        logger.info(f"Decomposed into {story_count} stories")

        # Notify
        self.notifier.notify_task_start(task_id, story_count)
        await self._write_response(
            task_dir,
            f"Task '{task_id}' decomposed into {story_count} stories. Beginning execution.",
        )

        # --- Execute via DAG ---
        dag = DAGExecutor(stories)
        execution_levels = dag.get_execution_levels()
        logger.info(f"Execution plan: {len(execution_levels)} levels")

        results: list[StoryResult] = []
        cancellation_event = asyncio.Event()

        for level_idx, level in enumerate(execution_levels):
            logger.info(f"Executing level {level_idx + 1}/{len(execution_levels)}: {level}")

            # Execute stories in this level concurrently
            level_tasks = []
            for story_id in level:
                story = next((s for s in stories if s["id"] == story_id), None)
                if not story:
                    continue

                level_tasks.append(
                    execute_story(
                        story=story,
                        task_id=task_id,
                        task_description=user_request,
                        working_directory=self.project_path,
                        routing_engine=self.routing_engine,
                        notifier=self.notifier,
                        max_attempts=self.max_retries,
                        mediator_enabled=self.mediator_enabled,
                        cancellation_event=cancellation_event,
                    )
                )

            level_results = await asyncio.gather(*level_tasks, return_exceptions=True)

            for r in level_results:
                if isinstance(r, Exception):
                    logger.error(f"Story execution error: {r}")
                    results.append(StoryResult(
                        story_id="unknown",
                        success=False,
                        reason=str(r),
                    ))
                else:
                    results.append(r)

        # --- Results ---
        completed = sum(1 for r in results if r.success)
        total = story_count
        success = completed == total and total > 0

        # Write execution log
        log_parts = [f"## Execution Results for {task_id}\n"]
        for r in results:
            status = "OK" if r.success else "FAILED"
            log_parts.append(f"- **{r.story_id}**: {status} (attempts: {r.attempts})")
            if r.reason:
                log_parts.append(f"  Reason: {r.reason}")
        log_content = "\n".join(log_parts)

        await self._write_response(task_dir, log_content)

        # Write final status
        if success:
            final = f"Task '{task_id}' completed successfully. {completed}/{total} stories done."
        elif completed > 0:
            final = f"Task '{task_id}' partially completed. {completed}/{total} stories done."
        else:
            final = f"Task '{task_id}' failed. 0/{total} stories completed."

        await self._write_response(task_dir, final, is_final=True)

        # Notify completion
        self.notifier.notify_task_complete(task_id, completed, total, success)

        # Embed in vector memory
        if self.vector_store:
            try:
                doc = f"Request: {user_request[:2000]}\n\nResult: {final}"
                metadata = {
                    "task_id": task_id,
                    "task_type": task_type,
                    "file_path": file_path,
                    "success": success,
                    "stories_completed": completed,
                    "stories_total": total,
                }
                self.vector_store.add_document(doc, metadata)
                logger.info("Task embedded in vector memory")
            except Exception as e:
                logger.warning(f"Failed to embed task: {e}")

        return {"status": "complete", "returncode": 0 if success else 1}
