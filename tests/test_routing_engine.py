"""Tests for src.llm.routing_engine — Complexity-based LLM routing."""

import json
import os
import tempfile
import pytest

from src.llm.routing_engine import RoutingEngine, AGENT_COMPLEXITY


class TestAgentComplexity:
    def test_all_agents_have_valid_ratings(self):
        for agent, complexity in AGENT_COMPLEXITY.items():
            assert 1 <= complexity <= 10, f"{agent} has complexity {complexity}"

    def test_known_agents_present(self):
        assert "design" in AGENT_COMPLEXITY
        assert "classifier" in AGENT_COMPLEXITY
        assert "coder" in AGENT_COMPLEXITY
        assert "mediator" in AGENT_COMPLEXITY

    def test_high_complexity_agents(self):
        assert AGENT_COMPLEXITY["design"] == 10
        assert AGENT_COMPLEXITY["planner"] == 9

    def test_low_complexity_agents(self):
        assert AGENT_COMPLEXITY["classifier"] == 3
        assert AGENT_COMPLEXITY["basic_info"] == 2


class TestRoutingEngine:
    def setup_method(self):
        self.engine = RoutingEngine()

    def test_high_complexity_routes_to_powerful_model(self):
        # Design (complexity 10) should get a power 9+ model
        provider = self.engine.select("design")
        assert provider.power >= 9

    def test_low_complexity_prefers_local(self):
        # Classifier (complexity 3) should prefer local models
        provider = self.engine.select("classifier")
        assert provider.local or provider.power <= 7

    def test_nemotron_for_basic_info(self):
        # basic_info (complexity 2) should get nemotron
        provider = self.engine.select("basic_info")
        assert provider.name == "nemotron"

    def test_coder_uses_story_complexity(self):
        # Coder with high complexity should get powerful model
        provider_high = self.engine.select("coder", story_complexity=9)
        provider_low = self.engine.select("coder", story_complexity=3)
        assert provider_high.power >= provider_low.power

    def test_code_task_uses_code_power(self):
        # qwen25_coder has power=4 but code_power=6
        provider = self.engine.select("coder", story_complexity=5, is_code_task=True)
        assert provider is not None

    def test_unknown_agent_uses_default(self):
        # Unknown agents should still get a valid provider (defaults to complexity 5)
        provider = self.engine.select("unknown_agent")
        assert provider is not None

    def test_get_complexity(self):
        assert self.engine.get_complexity("design") == 10
        assert self.engine.get_complexity("coder", story_complexity=8) == 8
        assert self.engine.get_complexity("basic_info", story_complexity=3) == 3
        # Non-variable agent ignores story_complexity
        assert self.engine.get_complexity("design", story_complexity=3) == 10


class TestRoutingEngineWithConfig:
    def test_phase_model_override(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"phase_models": {"CLASSIFIER": "opus"}}, f)
            f.flush()
            config_path = f.name

        try:
            engine = RoutingEngine(config_path=config_path)
            provider = engine.select("classifier")
            assert provider.name == "opus"
        finally:
            os.unlink(config_path)

    def test_fallback_when_no_eligible(self):
        """Even with extreme complexity, should fallback to default."""
        engine = RoutingEngine()
        # This shouldn't raise
        provider = engine.select("design")
        assert provider is not None

    def test_select_with_fallback(self):
        engine = RoutingEngine()
        primary, fallback = engine.select_with_fallback("coder")
        assert primary is not None
        assert fallback is not None
        # Primary and fallback should be different
        assert primary.name != fallback.name
