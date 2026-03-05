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

from src.workflows.base_workflow import (
    BaseWorkflow,
    parallel_analyze_node,
    parallel_gather_node,
    phase_node,
)
from src.workflows.state import StoryState

logger = logging.getLogger(__name__)


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


class ResearchWorkflow(BaseWorkflow):

    def build_graph(self) -> StateGraph:
        builder = StateGraph(StoryState)
        re = self.routing_engine

        # Parallel gather replaces single gather node
        builder.add_node("parallel_gather", partial(parallel_gather_node, routing_engine=re))
        # Parallel analyze splits topics and analyzes concurrently
        builder.add_node("parallel_analyze", partial(parallel_analyze_node, routing_engine=re))
        builder.add_node("synthesize", partial(phase_node, phase_name="SYNTHESIZE", agent_name="synthesizer", routing_engine=re))
        builder.add_node("persist", persist_research_node)

        builder.set_entry_point("parallel_gather")
        builder.add_edge("parallel_gather", "parallel_analyze")
        builder.add_edge("parallel_analyze", "synthesize")
        builder.add_edge("synthesize", "persist")
        builder.add_edge("persist", END)

        return builder
