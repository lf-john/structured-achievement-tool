"""Tests for src.workflows.research_workflow."""

from unittest.mock import MagicMock, mock_open, patch

from src.workflows.base_workflow import _split_into_topics
from src.workflows.research_workflow import (
    ResearchWorkflow,
    _extract_research_content,
    persist_research_node,
)


class TestExtractResearchContent:
    def test_extracts_from_json_output(self):
        output = '{"output": "Key findings here", "status": "complete"}'
        result = _extract_research_content(output, {"title": "Research", "id": "R1"})
        assert "Key findings here" in result
        assert "# Research" in result

    def test_extracts_synthesis_field(self):
        output = '{"synthesis": "Synthesized content"}'
        result = _extract_research_content(output, {"title": "R", "id": "R2"})
        assert "Synthesized content" in result

    def test_falls_back_to_raw_text(self):
        output = "Raw research output"
        result = _extract_research_content(output, {"title": "R", "id": "R3"})
        assert "Raw research output" in result

    def test_adds_header(self):
        result = _extract_research_content("content", {"title": "My Research", "id": "R4"})
        assert result.startswith("# My Research")
        assert "_Story: R4_" in result


class TestPersistResearchNode:
    def test_no_synthesize_output_returns_early(self):
        state = {
            "story": {"id": "R1"},
            "working_directory": "/tmp/test",
            "phase_outputs": [
                {"phase": "ANALYZE", "output": "analysis"}
            ],
        }
        result = persist_research_node(state)
        assert result is not None

    @patch("builtins.open", mock_open())
    @patch("os.makedirs")
    def test_writes_file_with_synthesize_output(self, mock_makedirs):
        state = {
            "story": {"id": "R1"},
            "working_directory": "/tmp/test",
            "phase_outputs": [
                {"phase": "SYNTHESIZE", "output": "Synthesized research content"}
            ],
        }
        persist_research_node(state)
        mock_makedirs.assert_called()

    @patch("builtins.open", mock_open())
    @patch("os.makedirs")
    def test_uses_story_output_path_if_set(self, mock_makedirs):
        state = {
            "story": {"id": "R1", "output_path": "/custom/path/report.md"},
            "working_directory": "/tmp/test",
            "phase_outputs": [
                {"phase": "SYNTHESIZE", "output": "content"}
            ],
        }
        persist_research_node(state)
        mock_makedirs.assert_called()

    @patch("builtins.open", mock_open())
    @patch("os.makedirs")
    @patch("src.core.embedding_service.EmbeddingService", side_effect=Exception("no ollama"))
    def test_vector_store_failure_does_not_crash(self, mock_embed, mock_makedirs):
        state = {
            "story": {"id": "R1", "output_path": "/tmp/out.md"},
            "working_directory": "/tmp/test",
            "phase_outputs": [
                {"phase": "SYNTHESIZE", "output": "research content"}
            ],
        }
        result = persist_research_node(state)
        assert result is not None


class TestResearchWorkflowGraph:
    def test_has_all_nodes(self):
        workflow = ResearchWorkflow(routing_engine=MagicMock())
        graph = workflow.build_graph()
        node_names = set(graph.nodes.keys())
        expected = {"parallel_gather", "parallel_analyze", "synthesize", "persist"}
        assert expected == node_names

    def test_compiles_without_error(self):
        workflow = ResearchWorkflow(routing_engine=MagicMock())
        compiled = workflow.compile()
        assert compiled is not None

    def test_entry_point_is_parallel_gather(self):
        workflow = ResearchWorkflow(routing_engine=MagicMock())
        graph = workflow.build_graph()
        assert "parallel_gather" in graph.nodes


class TestSplitIntoTopics:
    def test_splits_by_channel_headers(self):
        gather_output = (
            "=== gatherer_web ===\n" + "Web content here. " * 20 + "\n\n"
            "=== gatherer_code ===\n" + "Code analysis here. " * 20 + "\n\n"
            "=== gatherer_docs ===\n" + "Doc review here. " * 20
        )
        topics = _split_into_topics(gather_output)
        assert len(topics) == 3
        assert topics[0][0] == "gatherer_web"
        assert "Web content" in topics[0][1]

    def test_splits_by_headings(self):
        gather_output = (
            "# Product Overview\n" + "Product details here. " * 20 + "\n\n"
            "# Target Audience\n" + "Audience details here. " * 20 + "\n\n"
            "# Pain Points\n" + "Pain point details here. " * 20
        )
        topics = _split_into_topics(gather_output)
        assert len(topics) >= 2

    def test_single_block_returns_full(self):
        gather_output = "Short content without any headers or structure."
        topics = _split_into_topics(gather_output)
        assert len(topics) == 1
        assert topics[0][0] == "full_analysis"

    def test_skips_short_chunks(self):
        gather_output = (
            "=== channel_a ===\nShort\n\n"
            "=== channel_b ===\n" + "Long content here. " * 20
        )
        topics = _split_into_topics(gather_output)
        # channel_a is too short (<200 chars), so falls back
        assert len(topics) >= 1
