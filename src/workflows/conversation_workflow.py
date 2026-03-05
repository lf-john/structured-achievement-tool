"""
Conversation Workflow — Lightweight single-phase execution with optional persistence.

EXECUTE → (PERSIST if store=true)

Used for:
- Simple questions and explanations
- Short documents that don't need full content verification
- Quick tasks where Conversation is the appropriate story type

The `store` flag on the story controls whether output is persisted:
- store=false: Execute only — output stays in workflow state
- store=true: Execute → Persist (write to file + vector memory)
"""

import logging
import os
from functools import partial

from langgraph.graph import END, StateGraph

from src.workflows.base_workflow import BaseWorkflow, phase_node
from src.workflows.state import StoryState

logger = logging.getLogger(__name__)


def persist_conversation_node(state: StoryState) -> StoryState:
    """Write conversation output to file and optionally vector memory.

    Reads the EXECUTE phase output and persists it.
    Only runs when story.store=true.
    """
    state = dict(state)
    story = state["story"]
    story_id = story.get("id", "unknown")
    working_dir = state["working_directory"]

    # Extract output from the last phase
    output_text = ""
    for po in reversed(state.get("phase_outputs", [])):
        if po.get("output"):
            output_text = po["output"]
            break

    if not output_text:
        logger.warning(f"Story {story_id}: No output to persist")
        return state

    # Determine output path
    output_path = story.get("output_path")
    if not output_path:
        output_dir = os.path.join(working_dir, "output")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{story_id}.md")

    if not os.path.isabs(output_path):
        output_path = os.path.join(working_dir, output_path)

    # Extract clean content from JSON output
    content = _extract_content(output_text, story)

    # 1. Write to file
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            f.write(content)
        logger.info(f"Story {story_id}: Conversation output written to {output_path}")
    except Exception as e:
        logger.error(f"Story {story_id}: Failed to write conversation file: {e}")

    # 2. Write to vector memory
    try:
        from src.core.embedding_service import EmbeddingService
        from src.core.vector_store import VectorStore

        db_path = os.path.join(working_dir, ".memory", "vectors.db")
        embedding_svc = EmbeddingService()
        vector_store = VectorStore(db_path, embedding_svc)

        embed_text = content[:7500] if len(content) > 7500 else content
        metadata = {
            "story_id": story_id,
            "type": "conversation",
            "title": story.get("title", ""),
        }
        vector_store.add_document(text=embed_text, metadata=metadata)
        logger.info(f"Story {story_id}: Conversation output stored in vector memory")
    except Exception as e:
        logger.warning(f"Story {story_id}: Failed to store in vector memory: {e}")

    return state


def _extract_content(output: str, story: dict) -> str:
    """Extract clean content from LLM output."""
    from src.llm.response_parser import extract_json

    title = story.get("title", "Conversation")
    story_id = story.get("id", "")

    content = output
    try:
        parsed = extract_json(output)
        if isinstance(parsed, dict):
            content = parsed.get("output", parsed.get("response", output))
    except (ValueError, Exception):
        pass

    header = f"# {title}\n\n_Story: {story_id}_\n\n---\n\n"
    return header + content


def store_decision(state: StoryState) -> str:
    """Route based on store flag: persist or end."""
    story = state.get("story", {})
    if story.get("store", False):
        return "persist"
    return "end"


class ConversationWorkflow(BaseWorkflow):

    def build_graph(self) -> StateGraph:
        builder = StateGraph(StoryState)
        re = self.routing_engine

        builder.add_node("execute", partial(
            phase_node, phase_name="EXECUTE", agent_name="executor", routing_engine=re))
        builder.add_node("persist", persist_conversation_node)

        builder.set_entry_point("execute")

        # Conditional: store=true → persist, store=false → end
        builder.add_conditional_edges(
            "execute",
            store_decision,
            {"persist": "persist", "end": END},
        )
        builder.add_edge("persist", END)

        return builder
