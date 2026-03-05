"""
Context Retriever for VectorStore Integration

This module provides functions for retrieving similar tasks from the VectorStore
and formatting them into readable context for prompt enrichment.
"""

from typing import Any

from src.core.vector_store import VectorStore


def retrieve_context(query: str, vector_store: VectorStore, k: int = 3) -> list[dict[str, Any]]:
    """
    Retrieve similar past tasks from the VectorStore.

    Args:
        query: The query text to search for similar tasks.
        vector_store: The VectorStore instance to search in.
        k: The number of similar tasks to retrieve (default: 3).

    Returns:
        A list of similar task results from the vector store.
        Returns empty list if vector_store is None or search fails.
    """
    if vector_store is None:
        return []

    try:
        results = vector_store.search(query, k=k)
        return results
    except Exception as e:
        # Log the error but don't crash - graceful degradation
        import logging
        logging.warning(f"VectorStore search failed: {e}")
        return []


def format_context(results: list[dict[str, Any]]) -> str:
    """
    Format similar task results into readable context text.

    Args:
        results: List of search results from VectorStore.

    Returns:
        A formatted string containing information about similar tasks.
        Returns empty string if no results.
    """
    if not results:
        return ""

    context_parts = ["Similar past tasks:"]

    for i, result in enumerate(results, 1):
        # Extract information from result
        text = result.get('text', 'N/A')
        score = result.get('score', 0.0)
        metadata = result.get('metadata', {})

        # Format the task information
        story_id = metadata.get('story_id', 'Unknown')

        # Build the formatted entry
        entry = f"\n{i}. [{story_id}] (similarity: {score:.2f})\n   {text}"

        # Add additional metadata if available
        status = metadata.get('status')
        if status:
            entry += f"\n   Status: {status}"

        phase_outputs = metadata.get('phase_outputs')
        if phase_outputs:
            entry += f"\n   Phases: {', '.join(phase_outputs)}"

        context_parts.append(entry)

    return "\n".join(context_parts)
