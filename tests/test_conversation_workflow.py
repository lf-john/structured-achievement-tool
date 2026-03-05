"""Tests for src.workflows.conversation_workflow."""

import os
import pytest
from unittest.mock import MagicMock, patch, mock_open

from src.workflows.conversation_workflow import (
    ConversationWorkflow,
    persist_conversation_node,
    store_decision,
    _extract_content,
)


class TestStoreDecision:
    def test_store_true_returns_persist(self):
        state = {"story": {"store": True}}
        assert store_decision(state) == "persist"

    def test_store_false_returns_end(self):
        state = {"story": {"store": False}}
        assert store_decision(state) == "end"

    def test_store_missing_returns_end(self):
        state = {"story": {}}
        assert store_decision(state) == "end"

    def test_empty_story_returns_end(self):
        state = {}
        assert store_decision(state) == "end"


class TestExtractContent:
    def test_extracts_output_from_json(self):
        output = '{"output": "Hello world", "status": "complete"}'
        result = _extract_content(output, {"title": "Test", "id": "S1"})
        assert "Hello world" in result
        assert "# Test" in result
        assert "S1" in result

    def test_extracts_response_field_from_json(self):
        output = '{"response": "The answer is 42"}'
        result = _extract_content(output, {"title": "Q", "id": "S2"})
        assert "The answer is 42" in result

    def test_falls_back_to_raw_text(self):
        output = "Just plain text output"
        result = _extract_content(output, {"title": "T", "id": "S3"})
        assert "Just plain text output" in result

    def test_adds_header(self):
        result = _extract_content("content", {"title": "My Title", "id": "S4"})
        assert result.startswith("# My Title")
        assert "_Story: S4_" in result


class TestPersistConversationNode:
    def test_no_output_returns_early(self):
        state = {
            "story": {"id": "S1"},
            "working_directory": "/tmp/test",
            "phase_outputs": [],
        }
        result = persist_conversation_node(state)
        assert result is not None

    @patch("builtins.open", mock_open())
    @patch("os.makedirs")
    def test_writes_file_to_output_path(self, mock_makedirs):
        state = {
            "story": {"id": "S1", "output_path": "/tmp/test/out.md"},
            "working_directory": "/tmp/test",
            "phase_outputs": [{"output": "Hello", "phase": "EXECUTE"}],
        }
        persist_conversation_node(state)
        mock_makedirs.assert_called()

    @patch("builtins.open", mock_open())
    @patch("os.makedirs")
    def test_creates_default_output_path(self, mock_makedirs):
        state = {
            "story": {"id": "S1"},
            "working_directory": "/tmp/test",
            "phase_outputs": [{"output": "Hello"}],
        }
        persist_conversation_node(state)
        # Should create output/ directory
        mock_makedirs.assert_called()

    @patch("builtins.open", mock_open())
    @patch("os.makedirs")
    @patch("src.core.embedding_service.EmbeddingService", side_effect=Exception("no ollama"))
    def test_vector_store_failure_does_not_crash(self, mock_embed, mock_makedirs):
        """Vector memory failure should be caught and logged, not crash."""
        state = {
            "story": {"id": "S1", "output_path": "/tmp/out.md"},
            "working_directory": "/tmp/test",
            "phase_outputs": [{"output": "content"}],
        }
        result = persist_conversation_node(state)
        assert result is not None


class TestConversationWorkflowGraph:
    def test_has_all_nodes(self):
        workflow = ConversationWorkflow(routing_engine=MagicMock())
        graph = workflow.build_graph()
        node_names = set(graph.nodes.keys())
        assert node_names == {"execute", "persist"}

    def test_compiles_without_error(self):
        workflow = ConversationWorkflow(routing_engine=MagicMock())
        compiled = workflow.compile()
        assert compiled is not None

    def test_store_false_skips_persist(self):
        """Verify the conditional edge routes to END when store=false."""
        assert store_decision({"story": {"store": False}}) == "end"

    def test_store_true_routes_to_persist(self):
        """Verify the conditional edge routes to persist when store=true."""
        assert store_decision({"story": {"store": True}}) == "persist"
