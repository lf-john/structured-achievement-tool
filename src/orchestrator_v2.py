"""
Orchestrator v2 — Native Python story execution via LangGraph workflows.

Replaces the Ralph Pro delegation with:
  classify → decompose → DAGExecutor → story_executor per story

Keeps: vector memory search, response writing, notifications, task embedding.
Removes: all Ralph Pro references (prd.json path, ralph-pro CLI, progress.json).
"""

import asyncio
import json
import logging
import os

from src.agents.classifier_agent import ClassifierAgent
from src.agents.spec_validator import validate_spec
from src.agents.story_agent import StoryAgent
from src.core.checkpoint_manager import init_db as init_checkpoint_db
from src.core.checkpoint_manager import read_checkpoint
from src.core.embedding_service import EmbeddingService
from src.core.rag_summarizer import RAGSummarizer
from src.core.vector_store import VectorStore
from src.db.database_manager import DatabaseManager
from src.execution.audit_journal import AuditJournal, AuditRecord
from src.execution.dag_executor import DAGExecutor
from src.execution.failure_monitor import FailureContext, FailureMonitor
from src.execution.story_executor import StoryResult, execute_story
from src.llm.cli_runner import invoke as cli_invoke
from src.llm.prompt_builder import TEMPLATE_DIR, substitute_placeholders
from src.llm.response_parser import extract_json
from src.llm.routing_engine import RoutingEngine
from src.notifications.notifier import Notifier

logger = logging.getLogger(__name__)


class OrchestratorV2:
    """Task orchestrator that executes stories natively via LangGraph workflows."""

    def __init__(self, project_path: str, vector_db_path: str | None = None):
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

        # RAG summary layer (3.6) — summarize RAG results before feeding to main LLM
        self.rag_summarizer = RAGSummarizer()

        # Failure monitoring (Layer 1) and audit journaling
        memory_dir = os.path.join(project_path, ".memory")
        self.failure_monitor = FailureMonitor(
            output_dir=os.path.expanduser("~/GoogleDrive/DriveSyncFiles/sat-tasks/debug"),
        )
        self.audit_journal = AuditJournal(
            file_path=os.path.join(memory_dir, "audit_journal.jsonl"),
        )

        # Load execution config
        self.config = {}
        if os.path.exists(config_path):
            with open(config_path) as f:
                self.config = json.load(f)

        exec_config = self.config.get("execution", {})
        self.max_retries = exec_config.get("max_retries_per_story", 5)
        self.mediator_enabled = exec_config.get("enable_mediator", False)

    @staticmethod
    def _sanitize_output(text: str) -> str:
        """Strip system-reminder and other injected XML blocks from LLM output.

        LLMs sometimes echo back system prompts or injected context blocks.
        These must never appear in user-facing response files.
        """
        import re

        # Remove <system-reminder>...</system-reminder> blocks (possibly multiline)
        text = re.sub(
            r"<system-reminder>.*?</system-reminder>",
            "",
            text,
            flags=re.DOTALL,
        )
        # Remove any stray opening/closing tags that weren't paired
        text = re.sub(r"</?system-reminder>", "", text)
        return text

    async def _write_response(self, task_dir: str, content: str, is_final: bool = False):
        """Write a response file, finding the next available number."""
        content = self._sanitize_output(content)
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

    def _resolve_project_working_directory(self, file_path: str) -> str:
        """Resolve the working directory for a task based on its project.

        If the task belongs to a project other than SAT itself, use
        ~/projects/{project_name}/ as the working directory. This ensures
        LLM subprocesses write files to the correct project, not to SAT.
        """
        from src.daemon import parse_task_project

        project_name = parse_task_project(file_path)

        # SAT's own tasks use SAT's project directory
        if project_name == "structured-achievement-tool":
            return self.project_path

        # Other projects: resolve to ~/projects/{project_name}/
        projects_root = os.path.dirname(self.project_path)
        target_dir = os.path.join(projects_root, project_name)

        if os.path.isdir(target_dir):
            logger.info(f"Using project working directory: {target_dir}")
            return target_dir

        # If directory doesn't exist, create it
        os.makedirs(target_dir, exist_ok=True)
        logger.info(f"Created project working directory: {target_dir}")
        return target_dir

    async def process_task_file(self, file_path: str, mark_status_callback=None):
        """Process a task file: classify, decompose, execute stories.

        Args:
            file_path: Path to the .md task file
            mark_status_callback: Optional callable(success: bool) to update the
                task file tag BEFORE writing the final response file.

        Returns:
            dict with status and returncode
        """
        logger.info(f"Orchestrator processing: {file_path}")
        task_dir = os.path.dirname(file_path)
        task_id = os.path.basename(task_dir)

        # Resolve the working directory for this task's project
        task_working_directory = self._resolve_project_working_directory(file_path)

        # Set task-level correlation ID for hierarchical logging
        try:
            from src.logging_config import set_correlation_id

            set_correlation_id(task_id=task_id)
        except Exception:
            pass

        with open(file_path) as f:
            user_request = f.read()

        # --- Validate spec ---
        db_manager = DatabaseManager()
        spec_result = validate_spec(user_request, db_manager=db_manager)

        if spec_result.errors:
            logger.error(f"Spec validation failed for {file_path}: {spec_result.errors}")
            # Annotate the task file with the problems
            annotation = "\n\n---\n## Spec Validation Errors\n"
            for err in spec_result.errors:
                annotation += f"- {err}\n"
            if spec_result.warnings:
                annotation += "\n## Spec Validation Warnings\n"
                for warn in spec_result.warnings:
                    annotation += f"- {warn}\n"
            with open(file_path, "a") as f:
                f.write(annotation)
                f.flush()
                os.fsync(f.fileno())
            # Mark as Failed so monitor doesn't reprocess after timeout
            if mark_status_callback:
                try:
                    mark_status_callback(False)
                except Exception as e:
                    logger.warning(f"mark_status_callback failed during spec validation: {e}")
            return {"status": "validation_failed", "returncode": 1, "errors": spec_result.errors}

        if spec_result.warnings:
            for warn in spec_result.warnings:
                logger.warning(f"Spec validation warning for {file_path}: {warn}")

        # Pass metadata downstream (especially has_existing_output)
        spec_metadata = spec_result.metadata

        # --- Task-level classify (hint for decomposer) ---
        classification = await self.classifier.classify(user_request, self.project_path)
        task_type = classification.task_type
        operation_mode = classification.operation_mode
        logger.info(
            f"Task classified as: {task_type} (confidence: {classification.confidence}, "
            f"operation_mode: {operation_mode})"
        )

        # --- Search vector memory for context ---
        rag_context = ""
        if self.vector_store:
            try:
                similar_tasks = self.vector_store.search(user_request, k=3)
                if similar_tasks:
                    # Use RAG summarizer to condense results (reduces token usage)
                    rag_context = self.rag_summarizer.summarize(similar_tasks, user_request)
                    if not rag_context:
                        # Fallback to raw results if summarizer fails
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
            working_directory=task_working_directory,
            rag_context=rag_context,
            spec_metadata=spec_metadata,
        )

        # --- Per-story classification ---
        # Each story is independently classified. The decomposer's suggested
        # type is passed as a hint but the classifier's result takes precedence.
        for story_schema in decompose_result.stories:
            try:
                story_classification = await self.classifier.classify_story(
                    story_id=story_schema.id,
                    story_title=story_schema.title,
                    story_description=story_schema.description,
                    acceptance_criteria=story_schema.acceptanceCriteria,
                    output_path=story_schema.output_path,
                    suggested_type=story_schema.type,
                    working_directory=task_working_directory,
                )
                if story_classification.task_type != story_schema.type:
                    logger.info(
                        f"Story {story_schema.id} reclassified: "
                        f"{story_schema.type} -> {story_classification.task_type} "
                        f"(confidence: {story_classification.confidence:.2f})"
                    )
                story_schema.type = story_classification.task_type

                # Apply operation_mode from classification
                story_op_mode = story_classification.operation_mode
                story_schema.operation_mode = story_op_mode

                # Edit operations are harder — bump complexity by 1
                # (capped at 10) to route to more capable models
                if story_op_mode == "edit":
                    old_complexity = story_schema.complexity
                    story_schema.complexity = min(old_complexity + 1, 10)
                    logger.info(
                        f"Story {story_schema.id} is edit operation: "
                        f"complexity {old_complexity} -> {story_schema.complexity}"
                    )
            except Exception as e:
                # Fallback: keep decomposer's suggested type
                logger.warning(
                    f"Story {story_schema.id} classification failed, keeping suggested type '{story_schema.type}': {e}"
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

        # Read checkpoint to skip already-completed stories on retry
        completed_stories: set[str] = set()
        try:
            checkpoint_db = os.path.join(self.project_path, ".memory", "checkpoints.db")
            os.makedirs(os.path.dirname(checkpoint_db), exist_ok=True)
            init_checkpoint_db(checkpoint_db)
            if os.path.exists(checkpoint_db):
                checkpoint = read_checkpoint(checkpoint_db, task_id)
                if checkpoint and checkpoint.completed_stories:
                    completed_stories = set(checkpoint.completed_stories)
                    logger.info(f"Checkpoint found: {len(completed_stories)} stories already completed")
        except Exception as e:
            logger.warning(f"Failed to read checkpoint for skip logic: {e}")

        results: list[StoryResult] = []
        cancellation_event = asyncio.Event()

        for level_idx, level in enumerate(execution_levels):
            logger.info(f"Executing level {level_idx + 1}/{len(execution_levels)}: {level}")

            # Execute stories in this level concurrently
            level_tasks = []
            for story_id in level:
                # Skip already-completed stories (partial results from prior run)
                if story_id in completed_stories:
                    logger.info(f"Skipping already-completed story {story_id}")
                    results.append(
                        StoryResult(
                            story_id=story_id,
                            success=True,
                            attempts=0,
                            reason="skipped (completed in prior run)",
                        )
                    )
                    continue

                story = next((s for s in stories if s["id"] == story_id), None)
                if not story:
                    continue

                level_tasks.append(
                    execute_story(
                        story=story,
                        task_id=task_id,
                        task_description=user_request,
                        working_directory=task_working_directory,
                        routing_engine=self.routing_engine,
                        notifier=self.notifier,
                        max_attempts=self.max_retries,
                        mediator_enabled=self.mediator_enabled,
                        cancellation_event=cancellation_event,
                        audit_journal=self.audit_journal,
                        task_file=file_path,
                    )
                )

            level_results = await asyncio.gather(*level_tasks, return_exceptions=True)

            for r in level_results:
                if isinstance(r, Exception):
                    logger.error(f"Story execution error: {r}")
                    results.append(
                        StoryResult(
                            story_id="unknown",
                            success=False,
                            reason=str(r),
                        )
                    )
                else:
                    results.append(r)

        # --- Results ---
        completed = sum(1 for r in results if r.success)
        total = story_count
        success = completed == total and total > 0

        # Log each story result to audit journal
        import time as _time

        for r in results:
            try:
                self.audit_journal.log(
                    AuditRecord(
                        timestamp=_time.strftime("%Y-%m-%dT%H:%M:%S"),
                        task_file=file_path,
                        story_id=r.story_id,
                        success=r.success,
                        duration_seconds=r.duration_seconds if hasattr(r, "duration_seconds") else 0.0,
                        exit_code=0 if r.success else 1,
                        error_summary=r.reason[:200] if r.reason else None,
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to log audit record: {e}")

            # Embed story-level LEARN summary in vector memory
            if self.vector_store and r.success:
                try:
                    learn_output = ""
                    for po in r.phase_outputs:
                        if po.get("phase") == "LEARN" and po.get("output"):
                            learn_output = po["output"]
                            break
                    if learn_output:
                        story_doc = f"Story: {r.story_id}\nTask: {task_id}\n\nLearning:\n{learn_output[:3000]}"
                        story_metadata = {
                            "task_id": task_id,
                            "story_id": r.story_id,
                            "task_type": task_type,
                            "doc_type": "story_learning",
                            "success": True,
                        }
                        self.vector_store.add_document(story_doc, story_metadata)
                        logger.info(f"Story learning embedded for {r.story_id}")
                except Exception as e:
                    logger.warning(f"Failed to embed story learning: {e}")

        # Create debug stories for failed tasks via failure monitor
        if not success:
            for r in results:
                if not r.success:
                    try:
                        log_tail = self.failure_monitor.capture_log_tail()
                        context = FailureContext(
                            task_file=file_path,
                            task_name=f"{task_id}_{r.story_id}",
                            exit_code=1,
                            stderr=r.reason or "",
                            stdout="",
                            log_tail=log_tail,
                        )
                        self.failure_monitor.create_debug_story(context)
                    except Exception as e:
                        logger.warning(f"Failed to create debug story: {e}")

        # Write execution log — include per-story failure details for user visibility
        log_parts = [f"## Execution Results for {task_id}\n"]
        for r in results:
            status_label = "OK" if r.success else "FAILED"
            log_parts.append(f"- **{r.story_id}**: {status_label} (attempts: {r.attempts})")
            if r.reason:
                log_parts.append(f"  Reason: {r.reason}")

        # Per-story failure details (Enhancement: incremental output)
        failed_stories = [r for r in results if not r.success and r.phase_outputs]
        if failed_stories:
            log_parts.append("\n---\n")
            log_parts.append("## Failed Story Details\n")
            for r in failed_stories:
                log_parts.append(f"### {r.story_id}\n")
                for po in r.phase_outputs:
                    phase = po.get("phase", "?")
                    po_status = po.get("status", "?")
                    provider = po.get("provider_used", "?")
                    duration = po.get("duration_seconds", 0)
                    log_parts.append(f"- **{phase}**: {po_status} (provider: {provider}, {duration:.1f}s)")
                    # Include failure context from the last failed phase
                    if po_status == "failed" and po.get("output"):
                        output_preview = po["output"][:500]
                        log_parts.append(f"  ```\n  {output_preview}\n  ```")
                log_parts.append("")

        log_content = "\n".join(log_parts)

        await self._write_response(task_dir, log_content)

        # Update task file tag BEFORE writing response file so the monitor
        # never sees a response appear while the task is still <Working>.
        if mark_status_callback:
            try:
                mark_status_callback(success)
            except Exception as e:
                logger.warning(f"mark_status_callback failed: {e}")

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

    # --- PRD Design Process (Interactive, One Phase Per Invocation) ---

    # Signal → (phase_number, template_key, phase_label, next_continuation_tag)
    PRD_SIGNAL_MAP = {
        "plan": (1, "discovery", "Discovery", "# <1>"),
        "plan1": (1, "single_phase", "Single-Phase PRD", "# <PRD>"),
        "phase2": (2, "requirements", "Requirements", "# <2>"),
        "phase3": (3, "architecture", "Architecture", "# <2>"),
        "phase4": (4, "implementation", "Implementation Plan", "# <PRD>"),
    }

    @staticmethod
    def _render_prd_json_to_markdown(phase_key: str, data: dict) -> str:
        """Convert structured PRD JSON into readable markdown for the user.

        The LLM outputs JSON for structured parsing. This renders it as
        natural markdown that the user reads in Obsidian.
        """
        lines = []

        if phase_key == "discovery":
            ps = data.get("problemStatement", {})
            lines.append("### Problem Statement\n")
            lines.append(ps.get("summary", ""))
            lines.append("")
            if ps.get("currentState"):
                lines.append(f"**Current State:** {ps['currentState']}\n")
            if ps.get("desiredState"):
                lines.append(f"**Desired State:** {ps['desiredState']}\n")
            if ps.get("costOfInaction"):
                lines.append(f"**Cost of Inaction:** {ps['costOfInaction']}\n")
            if ps.get("stakeholders"):
                lines.append("**Stakeholders:**")
                for s in ps["stakeholders"]:
                    lines.append(f"- {s}")
                lines.append("")

            dr = data.get("domainResearch", {})
            lines.append("### Domain Research\n")
            if dr.get("technologies"):
                lines.append("**Technologies & APIs:**")
                for t in dr["technologies"]:
                    lines.append(f"- {t}")
                lines.append("")
            if dr.get("bestPractices"):
                lines.append("**Best Practices:**")
                for bp in dr["bestPractices"]:
                    lines.append(f"- {bp}")
                lines.append("")
            if dr.get("constraints"):
                lines.append("**Constraints:**")
                for c in dr["constraints"]:
                    lines.append(f"- {c}")
                lines.append("")

            sa = data.get("scopeAssessment", {})
            lines.append("### Scope Assessment\n")
            if sa.get("inScope"):
                lines.append("**In Scope:**")
                for item in sa["inScope"]:
                    lines.append(f"- {item}")
                lines.append("")
            if sa.get("outOfScope"):
                lines.append("**Out of Scope:**")
                for item in sa["outOfScope"]:
                    lines.append(f"- {item}")
                lines.append("")
            if sa.get("externalDependencies"):
                lines.append("**External Dependencies:**")
                for item in sa["externalDependencies"]:
                    lines.append(f"- {item}")
                lines.append("")
            if sa.get("missingInformation"):
                lines.append("**Missing Information:**")
                for item in sa["missingInformation"]:
                    lines.append(f"- {item}")
                lines.append("")

            risks = data.get("risks", [])
            if risks:
                lines.append("### Risks\n")
                lines.append("| Risk | Severity | Mitigation |")
                lines.append("|------|----------|------------|")
                for r in risks:
                    lines.append(f"| {r.get('risk', '')} | {r.get('severity', '')} | {r.get('mitigation', '')} |")
                lines.append("")

        elif phase_key == "requirements":
            benefits = data.get("benefits", [])
            if benefits:
                lines.append("### Benefits & Outcomes\n")
                for b in benefits:
                    lines.append(
                        f"- **{b.get('id', '')}**: {b.get('description', '')} (Stakeholder: {b.get('stakeholder', '')}, Measured by: {b.get('measuredBy', '')})"
                    )
                lines.append("")

            frs = data.get("functionalRequirements", [])
            if frs:
                lines.append("### Functional Requirements\n")
                for fr in frs:
                    lines.append(
                        f"**{fr.get('id', '')}** — {fr.get('description', '')} [{fr.get('priority', '')}] (traces to {fr.get('tracesToBenefit', 'N/A')})"
                    )
                    for ac in fr.get("acceptanceCriteria", []):
                        lines.append(f"  - {ac}")
                    lines.append("")

            nfr = data.get("nonFunctionalRequirements", {})
            if nfr:
                lines.append("### Non-Functional Requirements\n")
                for category, items in nfr.items():
                    lines.append(f"**{category.title()}:**")
                    for item in items if isinstance(items, list) else [items]:
                        lines.append(f"- {item}")
                    lines.append("")

            stories = data.get("userStories", [])
            if stories:
                lines.append("### User Stories\n")
                for us in stories:
                    lines.append(
                        f"> As a **{us.get('role', '')}**, I want **{us.get('capability', '')}**, so that **{us.get('benefit', '')}**.\n"
                    )
                    for ac in us.get("acceptanceCriteria", []):
                        lines.append(f"- {ac}")
                    lines.append("")

            dr = data.get("dataRequirements", {})
            if dr:
                lines.append("### Data Requirements\n")
                for key_name in ("dataModels", "integrationFlows"):
                    items = dr.get(key_name, [])
                    if items:
                        lines.append(f"**{key_name}:**")
                        for item in items:
                            lines.append(f"- {item}")
                        lines.append("")

        elif phase_key == "architecture":
            approaches = data.get("solutionApproaches", [])
            if approaches:
                lines.append("### Solution Approaches\n")
                for a in approaches:
                    lines.append(f"**{a.get('name', '')}** ({a.get('complexity', '')} complexity)")
                    lines.append(f"- {a.get('description', '')}")
                    lines.append(f"- Optimizes for: {a.get('optimizesFor', '')}")
                    lines.append(f"- Sacrifices: {a.get('sacrifices', '')}")
                    lines.append("")

            rec = data.get("recommendedApproach")
            if rec:
                lines.append(f"**Recommended Approach:** {rec}")
                lines.append(f"**Rationale:** {data.get('recommendationRationale', '')}\n")

            sa = data.get("systemArchitecture", {})
            if sa:
                lines.append("### System Architecture\n")
                for c in sa.get("components", []):
                    lines.append(f"- **{c.get('name', '')}**: {c.get('purpose', '')} ({c.get('technology', '')})")
                lines.append("")
                if sa.get("integrationPoints"):
                    lines.append("**Integration Points:**")
                    for ip in sa["integrationPoints"]:
                        lines.append(f"- {ip}")
                    lines.append("")

            cd = data.get("componentDesign", [])
            if cd:
                lines.append("### Component Design\n")
                for c in cd:
                    lines.append(f"#### {c.get('name', '')}")
                    lines.append(f"**Purpose:** {c.get('purpose', '')}")
                    if c.get("inputs"):
                        lines.append(f"**Inputs:** {', '.join(c['inputs'])}")
                    if c.get("outputs"):
                        lines.append(f"**Outputs:** {', '.join(c['outputs'])}")
                    if c.get("interfaces"):
                        lines.append(f"**Interfaces:** {', '.join(c['interfaces'])}")
                    lines.append(f"**Technology:** {c.get('technology', '')}\n")

            da = data.get("dataArchitecture", {})
            if da:
                lines.append("### Data Architecture\n")
                for key_name in ("storage", "dataFlows", "schemas"):
                    items = da.get(key_name, [])
                    if items:
                        lines.append(f"**{key_name}:**")
                        for item in items:
                            lines.append(f"- {item}")
                        lines.append("")

            mvp = data.get("mvpBoundary", {})
            if mvp:
                lines.append("### MVP Boundary\n")
                if mvp.get("mvp"):
                    lines.append("**MVP (ships first):**")
                    for item in mvp["mvp"]:
                        lines.append(f"- {item}")
                    lines.append("")
                if mvp.get("postMvp"):
                    lines.append("**Post-MVP:**")
                    for item in mvp["postMvp"]:
                        lines.append(f"- {item}")
                    lines.append("")

            fc = data.get("feasibilityCheck", {})
            if fc and fc.get("concerns"):
                lines.append("### Feasibility Concerns\n")
                for item in fc["concerns"]:
                    lines.append(f"- {item}")
                lines.append("")

        elif phase_key in ("implementation", "single_phase"):
            # Traceability
            tm = data.get("traceabilityMatrix", [])
            if tm:
                lines.append("### Feature-to-Benefit Traceability\n")
                lines.append("| Story | Benefit | Priority |")
                lines.append("|-------|---------|----------|")
                for row in tm:
                    lines.append(f"| {row.get('story', '')} | {row.get('benefit', '')} | {row.get('priority', '')} |")
                lines.append("")

            # Stories
            stories = data.get("stories", [])
            if stories:
                lines.append("### Stories\n")
                for s in stories:
                    deps = ", ".join(s.get("dependsOn", [])) or "None"
                    lines.append(
                        f"#### {s.get('id', '')} — {s.get('title', '')} [{s.get('type', '')}] (complexity: {s.get('complexity', '')})"
                    )
                    lines.append(f"{s.get('description', '')}")
                    lines.append(f"**Depends on:** {deps}")
                    if s.get("techStack"):
                        lines.append(f"**Tech:** {', '.join(s['techStack'])}")
                    lines.append("**Acceptance Criteria:**")
                    for ac in s.get("acceptanceCriteria", []):
                        lines.append(f"- {ac}")
                    lines.append("")

            # Execution phases
            ep = data.get("executionPhases", [])
            if ep:
                lines.append("### Execution Phases\n")
                for p in ep:
                    story_list = ", ".join(p.get("stories", []))
                    lines.append(f"**Phase {p.get('phase', '')}: {p.get('name', '')}** — {p.get('description', '')}")
                    lines.append(f"  Stories: {story_list}\n")

            # Risk mitigation
            rm = data.get("riskMitigation", [])
            if rm:
                lines.append("### Risk Mitigation\n")
                for r in rm:
                    lines.append(
                        f"- **{r.get('risk', '')}** → Addressed by {r.get('addressedBy', '')} (Fallback: {r.get('fallback', '')})"
                    )
                lines.append("")

            # Single-phase extras
            if phase_key == "single_phase":
                benefits = data.get("benefits", [])
                if benefits:
                    lines.insert(0, "### Benefits & Outcomes\n")
                    idx = 1
                    for b in benefits:
                        lines.insert(
                            idx, f"- **{b.get('id', '')}**: {b.get('description', '')} ({b.get('stakeholder', '')})"
                        )
                        idx += 1
                    lines.insert(idx, "")

                ps = data.get("problemStatement", {})
                if ps:
                    insert_at = idx + 1
                    lines.insert(insert_at, "### Problem & Context\n")
                    insert_at += 1
                    lines.insert(insert_at, ps.get("summary", ""))
                    insert_at += 1
                    if ps.get("currentState"):
                        lines.insert(insert_at, f"**Current State:** {ps['currentState']}")
                        insert_at += 1
                    if ps.get("desiredState"):
                        lines.insert(insert_at, f"**Desired State:** {ps['desiredState']}")
                        insert_at += 1
                    lines.insert(insert_at, "")

                reqs = data.get("requirements", [])
                if reqs:
                    insert_at = len(lines) - len(stories) * 8 if stories else len(lines)
                    lines.insert(insert_at, "### Requirements\n")
                    insert_at += 1
                    for fr in reqs:
                        lines.insert(
                            insert_at,
                            f"**{fr.get('id', '')}** — {fr.get('description', '')} [{fr.get('priority', '')}] (traces to {fr.get('tracesToBenefit', 'N/A')})",
                        )
                        insert_at += 1
                        for ac in fr.get("acceptanceCriteria", []):
                            lines.insert(insert_at, f"  - {ac}")
                            insert_at += 1
                    lines.insert(insert_at, "")

        # Self-audit (common across all phases)
        sa = data.get("selfAudit", {})
        if sa:
            revisions = sa.get("revisions", [])
            if revisions:
                lines.append("### Self-Audit Revisions\n")
                for r in revisions:
                    lines.append(f"- {r}")
                lines.append("")
            orphans = sa.get("orphanStories", [])
            if orphans:
                lines.append("**Scope Creep Warning — Stories without benefit traceability:**")
                for o in orphans:
                    lines.append(f"- {o}")
                lines.append("")

        # Questions for user (common across all phases)
        questions = data.get("questionsForUser", [])
        if questions:
            lines.append("---\n")
            lines.append("## What I Need From You\n")
            lines.append("Please answer these questions (add `ME:` prefix to your responses):\n")
            for i, q in enumerate(questions, 1):
                lines.append(f"{i}. {q}\n")

        return "\n".join(lines)

    async def process_prd_phase(self, file_path: str, signal: str):
        """Run a single PRD phase, write output + questions to the task file, stop.

        The daemon calls this once per phase. After writing output, the file
        ends with continuation tags (# <Plan> and # <N>). The user reviews,
        answers questions, removes # from their choice, and the daemon picks
        it up again for the next phase.
        """
        import re

        phase_num, template_key, phase_label, next_tag = self.PRD_SIGNAL_MAP.get(
            signal, (1, "discovery", "Discovery", "# <1>")
        )

        logger.info(f"PRD Phase {phase_num}: {phase_label} starting ({file_path})")
        task_dir = os.path.dirname(file_path)
        task_id = os.path.basename(task_dir)

        # Read the full file content (includes user's original request + any annotations)
        with open(file_path) as f:
            full_content = f.read()

        # Strip signal/status tags from content passed to LLM
        clean_content = re.sub(
            r"^\s*<(?:Plan|Plan 1|Working|Pending|1|2|PRD)>\s*$", "", full_content, flags=re.MULTILINE
        ).strip()
        # Also strip the # <tag> options left from previous phase
        clean_content = re.sub(r"^#\s*<(?:Plan|Plan 1|1|2|PRD)>\s*$", "", clean_content, flags=re.MULTILINE).strip()

        # DB tracking
        db = DatabaseManager()
        session = db.get_active_prd_session(task_id)
        if session:
            session_id = session["id"]
            # Find associated task
            tasks = db.get_tasks_by_project(task_id)
            db_task_id = tasks[0]["id"] if tasks else None
        else:
            db_task_id = db.create_task(
                project=task_id,
                title=f"PRD: {task_id}",
                source_file=file_path,
            )
            db.update_task_status(db_task_id, "working")
            session_id = db.create_prd_session(project=task_id, file_path=file_path)

        db.update_prd_session(session_id, phase=phase_num)

        # Load prior phase outputs from progress files
        prior_outputs = {}
        for key in ("discovery", "requirements", "architecture"):
            progress_path = os.path.join(task_dir, f"_prd_{key}.md")
            if os.path.exists(progress_path):
                with open(progress_path) as f:
                    prior_outputs[key] = f.read()

        # RAG context (Phase 1 only)
        rag_context = ""
        if phase_num == 1 and self.vector_store:
            try:
                similar = self.vector_store.search(clean_content, k=3)
                if similar:
                    parts = ["\n## Similar Past Work\n"]
                    for idx, item in enumerate(similar, 1):
                        parts.append(f"### Similar {idx} (score: {item.get('score', 0):.2f})")
                        parts.append(item.get("text", ""))
                    rag_context = "\n".join(parts)
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")

        # Build prompt from template
        task_title = task_id.replace("-", " ").replace("_", " ").title()
        template_path = os.path.join(TEMPLATE_DIR, f"prd_{template_key}.md")

        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Missing template: prd_{template_key}.md")

        with open(template_path) as f:
            template = f.read()

        subs = {
            "TASK_TITLE": task_title,
            "USER_REQUEST": clean_content,
            "RAG_CONTEXT": rag_context,
            "DISCOVERY_OUTPUT": prior_outputs.get("discovery", ""),
            "REQUIREMENTS_OUTPUT": prior_outputs.get("requirements", ""),
            "ARCHITECTURE_OUTPUT": prior_outputs.get("architecture", ""),
        }

        prompt = substitute_placeholders(template, subs)

        # Invoke LLM
        provider = self.routing_engine.select("design")
        result = await cli_invoke(
            provider=provider,
            prompt=prompt,
            working_directory=self.project_path,
        )

        if result.exit_code != 0 and not result.stdout.strip():
            error_msg = f"PRD Phase {phase_label} failed: {result.stderr[:500]}"
            logger.error(error_msg)
            # Write error to file and mark failed
            with open(file_path) as f:
                content = f.read()
            content = content.replace("<Working>", f"<Failed>\n\nPRD Error: {error_msg}")
            with open(file_path, "w") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            return {"status": "failed", "returncode": 1}

        output_text = result.stdout.strip()

        # Parse JSON from LLM output for structured rendering
        parsed_json = None
        try:
            parsed_json = extract_json(output_text)
        except Exception as e:
            logger.warning(f"Could not parse JSON from PRD output: {e}")

        # Save raw JSON output to progress file (for machine use in subsequent phases)
        progress_file = os.path.join(task_dir, f"_prd_{template_key}.md")
        with open(progress_file, "w") as f:
            f.write(f"## PRD Phase {phase_num}: {phase_label}\n\n")
            f.write(output_text)
            f.flush()
            os.fsync(f.fileno())

        logger.info(f"PRD Phase {phase_label} output saved to {progress_file}")

        # Render JSON to readable markdown for the user
        if parsed_json and isinstance(parsed_json, dict):
            rendered_markdown = self._render_prd_json_to_markdown(template_key, parsed_json)
        else:
            # Fallback: use raw output if JSON parsing failed
            rendered_markdown = output_text
            logger.warning("Using raw LLM output (JSON parsing failed)")

        # Log event
        if db_task_id:
            db.log_event(
                event_type="prd_phase_complete",
                task_id=db_task_id,
                phase=f"PRD_{template_key.upper()}",
                provider=provider.name,
                detail=f"Phase {phase_num} ({phase_label}) complete",
            )

        # Write phase output to a NEW numbered file (NNN_PHASE_X.md)
        # Find the next available file number in the task directory
        existing_nums = []
        for fn in os.listdir(task_dir):
            if fn.endswith(".md") and not fn.startswith("_"):
                try:
                    existing_nums.append(int(fn[:3]))
                except ValueError:
                    pass
        next_num = max(existing_nums) + 1 if existing_nums else 2

        phase_filename = f"{next_num:03d}_PHASE_{phase_num}.md"
        phase_filepath = os.path.join(task_dir, phase_filename)

        phase_file_content = (
            f"# Phase {phase_num}: {phase_label}\n\n{rendered_markdown}\n\n---\n\n# <Plan>\n{next_tag}\n"
        )

        with open(phase_filepath, "w") as f:
            f.write(phase_file_content)
            f.flush()
            os.fsync(f.fileno())

        logger.info(f"PRD Phase {phase_num} written to {phase_filepath}")

        # Mark the triggering file as <Finished>
        with open(file_path) as f:
            content = f.read()
        content = content.replace("<Working>", "<Finished>")
        with open(file_path, "w") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        self.notifier.send_ntfy(
            title=f"PRD Phase {phase_num} Complete",
            message=f"{phase_label} done for {task_id}. Review and continue.",
            tags="memo",
        )

        return {"status": "phase_complete", "returncode": 0}

    async def process_prd_to_decompose(self, file_path: str):
        """Handle <PRD> signal: user approved the PRD, now decompose into stories.

        Reads all _prd_*.md progress files, combines them into the final PRD,
        then runs the normal classify → decompose → execute pipeline.
        """
        import re

        logger.info(f"PRD approved, starting decomposition: {file_path}")
        task_dir = os.path.dirname(file_path)
        task_id = os.path.basename(task_dir)

        # Combine all PRD phase outputs
        prd_parts = []
        for key, _label in [
            ("discovery", "Discovery"),
            ("requirements", "Requirements"),
            ("architecture", "Architecture"),
            ("implementation", "Implementation Plan"),
        ]:
            path = os.path.join(task_dir, f"_prd_{key}.md")
            if os.path.exists(path):
                with open(path) as f:
                    prd_parts.append(f.read())

        if not prd_parts:
            logger.error("No PRD phase outputs found for decomposition")
            return {"status": "failed", "returncode": 1}

        # Update DB
        db = DatabaseManager()
        session = db.get_active_prd_session(task_id)
        if session:
            db.update_prd_session(session["id"], status="complete", prd_content="\n\n".join(prd_parts))

        # Embed PRD in vector memory
        if self.vector_store:
            try:
                with open(file_path) as f:
                    user_request = f.read()
                user_request = re.sub(
                    r"^\s*<(?:Plan|Working|Pending|PRD|1|2)>\s*$", "", user_request, flags=re.MULTILINE
                ).strip()[:2000]
                doc = f"PRD for {task_id}: {user_request}\n\n{prd_parts[-1][:1000]}"
                self.vector_store.add_document(
                    doc,
                    {
                        "task_id": task_id,
                        "task_type": "prd",
                        "success": True,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to embed PRD: {e}")

        # Now run normal task processing with the PRD as context
        return await self.process_task_file(file_path)
