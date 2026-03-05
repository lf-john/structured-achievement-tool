"""Tests for src.orchestrator_v2 — Integration of classify → decompose → execute."""

import json
from unittest.mock import patch

import pytest

from src.orchestrator_v2 import OrchestratorV2


class TestOrchestratorInit:
    def test_init_with_config(self, tmp_path):
        config = {
            "routing_strategy": "complexity_based",
            "routing_rules_enabled": True,
            "execution": {
                "max_retries_per_story": 3,
                "enable_mediator": False,
            },
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config))

        with patch("src.orchestrator_v2.EmbeddingService", side_effect=Exception("no ollama")):
            orchestrator = OrchestratorV2(str(tmp_path))

        assert orchestrator.max_retries == 3
        assert not orchestrator.mediator_enabled

    def test_init_without_config(self, tmp_path):
        with patch("src.orchestrator_v2.EmbeddingService", side_effect=Exception("no ollama")):
            orchestrator = OrchestratorV2(str(tmp_path))

        assert orchestrator.max_retries == 5  # Default
        assert not orchestrator.mediator_enabled

    def test_vector_store_graceful_degradation(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text("{}")

        with patch("src.orchestrator_v2.EmbeddingService", side_effect=Exception("no ollama")):
            orchestrator = OrchestratorV2(str(tmp_path))

        assert orchestrator.vector_store is None  # Gracefully degraded


class TestWriteResponse:
    @pytest.mark.asyncio
    async def test_writes_sequential_responses(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text("{}")

        with patch("src.orchestrator_v2.EmbeddingService", side_effect=Exception("no ollama")):
            orchestrator = OrchestratorV2(str(tmp_path))

        # Write first response
        await orchestrator._write_response(str(tmp_path), "Response 1")
        assert (tmp_path / "002_response.md").exists()
        content = (tmp_path / "002_response.md").read_text()
        assert "Response 1" in content
        assert "<Pending>" in content  # Non-final has pending marker

        # Write second response
        await orchestrator._write_response(str(tmp_path), "Response 2", is_final=True)
        assert (tmp_path / "003_response.md").exists()
        content = (tmp_path / "003_response.md").read_text()
        assert "Response 2" in content
        assert "<Pending>" not in content  # Final has no pending marker
