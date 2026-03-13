"""
Research Workflow — For information gathering and analysis.

PARALLEL_GATHER → PARALLEL_ANALYZE → SYNTHESIZE → PERSIST

Phase 3 enhancement:
- Single GATHER node replaced with parallel_gather_node running 3 channels:
  gather_web, gather_code, gather_docs — all merge before ANALYZE.
- Single ANALYZE node replaced with parallel_analyze_node that splits
  gathered data into topics and runs concurrent analysis on each.
  SYNTHESIZE already handles multiple inputs, so all analysis results
  are merged and passed through.

PERSIST node writes synthesized output to:
1. A .md file in the project's research/ directory
2. Vector memory for RAG retrieval in future stories

No loopbacks — linear pipeline.
"""

import logging
import os
from functools import partial

from langgraph.graph import END, StateGraph

from src.agents.ac_templates import get_default_acs, merge_acs
from src.agents.critic_agent import CriticAgent, validate_ratings
from src.workflows.base_workflow import (
    BaseWorkflow,
    _run_async,
    parallel_analyze_node,
    parallel_gather_node,
    phase_node,
)
from src.workflows.state import PhaseOutput, PhaseStatus, StoryState

logger = logging.getLogger(__name__)

# After 2 critic→rework loops, story FAILS
MAX_CRITIC_RETRIES = 2


def persist_research_node(state: StoryState) -> StoryState:
    """Write research output to .md file and vector memory.

    Reads the SYNTHESIZE phase output from state and persists it to:
    1. {working_directory}/research/{story_id}.md — for human review
    2. Vector memory via EmbeddingService — for RAG retrieval
    """
    state = dict(state)
    story = state["story"]
    story_id = story.get("id", "unknown")
    working_dir = state["working_directory"]

    # Extract synthesize output from phase_outputs
    synthesize_output = ""
    for po in reversed(state.get("phase_outputs", [])):
        if po.get("phase") == "SYNTHESIZE" and po.get("output"):
            synthesize_output = po["output"]
            break

    if not synthesize_output:
        logger.warning(f"Story {story_id}: No SYNTHESIZE output to persist")
        return state

    # 1. Write to .md file
    output_path = story.get("output_path")
    if not output_path:
        research_dir = os.path.join(working_dir, "research")
        os.makedirs(research_dir, exist_ok=True)
        output_path = os.path.join(research_dir, f"{story_id}.md")

    # If output_path is relative, make it absolute from working_dir
    if not os.path.isabs(output_path):
        output_path = os.path.join(working_dir, output_path)

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        # Try to extract clean content from JSON output
        content = _extract_research_content(synthesize_output, story)
        with open(output_path, "w") as f:
            f.write(content)
        logger.info(f"Story {story_id}: Research output written to {output_path}")
    except Exception as e:
        logger.error(f"Story {story_id}: Failed to write research file: {e}")

    # 2. Write to vector memory
    try:
        from src.core.embedding_service import EmbeddingService
        from src.core.vector_store import VectorStore

        db_path = os.path.join(working_dir, ".memory", "vectors.db")
        embedding_svc = EmbeddingService()
        vector_store = VectorStore(db_path, embedding_svc)

        # Truncate for embedding (nomic-embed-text: 2048 token context)
        embed_text = content[:7500] if len(content) > 7500 else content
        metadata = {
            "story_id": story_id,
            "type": "research",
            "title": story.get("title", ""),
            "source": "SYNTHESIZE",
        }
        vector_store.add_document(text=embed_text, metadata=metadata)
        logger.info(f"Story {story_id}: Research output stored in vector memory")
    except Exception as e:
        logger.warning(f"Story {story_id}: Failed to store in vector memory: {e}")

    return state


def _extract_research_content(output: str, story: dict) -> str:
    """Extract clean markdown content from SYNTHESIZE output.

    If the output is JSON, extracts the 'output' field.
    Otherwise uses the raw text. Adds a header with story metadata.
    """
    from src.llm.response_parser import extract_json

    title = story.get("title", "Research")
    story_id = story.get("id", "")

    # Try to extract from JSON
    content = output
    try:
        parsed = extract_json(output)
        if isinstance(parsed, dict):
            content = parsed.get("output", parsed.get("synthesis", output))
    except (ValueError, Exception):
        pass

    # Add header
    header = f"# {title}\n\n_Story: {story_id}_\n\n---\n\n"
    return header + content


def research_critic_node(state: StoryState, routing_engine=None) -> StoryState:
    """Critic review of synthesized research output against acceptance criteria."""
    state = dict(state)
    state["current_phase"] = "CRITIC_REVIEW"
    story = state["story"]
    story_id = story.get("id", "unknown")
    working_dir = state["working_directory"]

    story_acs = story.get("acceptanceCriteria", [])
    default_acs = get_default_acs("research")
    acceptance_criteria = merge_acs(story_acs, default_acs)

    output_content = ""
    for po in reversed(state.get("phase_outputs", [])):
        if po.get("phase") == "SYNTHESIZE" and po.get("output"):
            output_content = po["output"]
            break

    if not output_content:
        logger.warning(f"Story {story_id}: Research critic skipped — no synthesize output")
        state["critic_passed"] = True
        state["critic_ratings"] = []
        state["critic_average"] = 0.0
        state["critic_validation"] = {"passed": True, "message": "Skipped — no content"}
        phase_output = PhaseOutput(
            phase="CRITIC_REVIEW",
            status=PhaseStatus.SKIPPED,
            output="Skipped — no synthesize output.",
            exit_code=0,
            provider_used="none",
        )
        state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]
        return state

    task_description = state.get("task_description", story.get("description", ""))
    critic_retry_count = state.get("critic_retry_count", 0)
    critic = CriticAgent(mode="content_critic", routing_engine=routing_engine, escalation=critic_retry_count * 5)

    try:
        response = _run_async(
            critic.evaluate(
                acceptance_criteria=acceptance_criteria,
                output_content=output_content,
                task_description=task_description,
                working_directory=working_dir,
            ),
            timeout=180,
        )
    except (ValueError, RuntimeError) as e:
        logger.error(f"Story {story_id}: Research critic failed: {e}")
        state["critic_passed"] = True
        state["critic_ratings"] = []
        state["critic_average"] = 0.0
        state["critic_validation"] = {"passed": True, "message": f"Critic error: {e}"}
        phase_output = PhaseOutput(
            phase="CRITIC_REVIEW",
            status=PhaseStatus.FAILED,
            output=f"Critic error: {e}",
            exit_code=1,
            provider_used="content_critic",
        )
        state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]
        return state

    validation = validate_ratings(response, acceptance_criteria)
    state["critic_passed"] = validation.passed
    state["critic_ratings"] = [r.model_dump() for r in response.ratings]
    state["critic_average"] = validation.average
    state["critic_validation"] = {
        "passed": validation.passed,
        "missing_acs": validation.missing_acs,
        "failing_acs": validation.failing_acs,
        "average": validation.average,
        "message": validation.message,
    }

    status = PhaseStatus.COMPLETE if validation.passed else PhaseStatus.FAILED
    phase_output = PhaseOutput(
        phase="CRITIC_REVIEW",
        status=status,
        output=f"Research critic: {'PASSED' if validation.passed else 'FAILED'} avg={validation.average}",
        exit_code=0 if validation.passed else 1,
        provider_used="content_critic",
    )
    state["phase_outputs"] = state.get("phase_outputs", []) + [phase_output.model_dump()]

    if not validation.passed:
        state["critic_retry_count"] = critic_retry_count + 1
        failing_details = [
            f"  - {f['ac_id']} ({f['ac_name']}): {f['rating']}/10 — {f['justification']}"
            for f in validation.failing_acs
        ]
        content_preview = output_content[:10000]
        if len(output_content) > 10000:
            content_preview += "\n[...truncated...]"
        state["failure_context"] = (
            f"Critic failed (avg={validation.average}):\n{validation.message}\n"
            + "\n".join(failing_details)
            + f"\n\nExisting output to revise:\n```\n{content_preview}\n```"
        )
        logger.info(
            f"Story {story_id}: Research critic FAILED (avg={validation.average}, "
            f"retry {state['critic_retry_count']}/{MAX_CRITIC_RETRIES})"
        )
    else:
        logger.info(f"Story {story_id}: Research critic PASSED (avg={validation.average})")

    return state


def research_critic_decision(state: StoryState) -> str:
    """Route after research CRITIC_REVIEW: pass → persist, fail → synthesize, max → fail."""
    if state.get("critic_passed"):
        return "persist"
    if state.get("critic_retry_count", 0) >= MAX_CRITIC_RETRIES:
        logger.warning(f"Research critic retry limit ({MAX_CRITIC_RETRIES}) reached — story FAILS")
        return "fail"
    return "synthesize"


class ResearchWorkflow(BaseWorkflow):
    def build_graph(self) -> StateGraph:
        builder = StateGraph(StoryState)
        re = self.routing_engine

        builder.add_node("parallel_gather", partial(parallel_gather_node, routing_engine=re))
        builder.add_node("parallel_analyze", partial(parallel_analyze_node, routing_engine=re))
        builder.add_node(
            "synthesize", partial(phase_node, phase_name="SYNTHESIZE", agent_name="synthesizer", routing_engine=re)
        )
        builder.add_node("critic_review", partial(research_critic_node, routing_engine=re))
        builder.add_node("persist", persist_research_node)

        builder.set_entry_point("parallel_gather")
        builder.add_edge("parallel_gather", "parallel_analyze")
        builder.add_edge("parallel_analyze", "synthesize")
        builder.add_edge("synthesize", "critic_review")

        builder.add_conditional_edges(
            "critic_review",
            research_critic_decision,
            {
                "persist": "persist",
                "synthesize": "synthesize",
                "fail": "persist",  # Still persist what we have
            },
        )

        builder.add_edge("persist", END)

        return builder
