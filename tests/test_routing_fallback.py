"""Tests for routing_engine fallback with DeepSeek backup."""


from src.llm.routing_engine import RoutingEngine


class TestSelectWithFallback:
    def test_reasoning_backup_is_deepseek(self):
        engine = RoutingEngine()
        engine.config = {
            "routing_preferences": {
                "reasoning_backup": "deepseek_r1",
            },
            "default_backup": "deepseek_r1",
        }
        _, fallback = engine.select_with_fallback("design")  # complexity 10
        assert fallback.name == "deepseek_r1"

    def test_code_backup_is_qwen_coder(self):
        engine = RoutingEngine()
        engine.config = {
            "routing_preferences": {
                "code_backup": "qwen25_coder",
            },
            "default_backup": "deepseek_r1",
        }
        _, fallback = engine.select_with_fallback("coder", is_code_task=True)
        assert fallback.name == "qwen25_coder"

    def test_classification_backup_is_nemotron(self):
        engine = RoutingEngine()
        engine.config = {
            "routing_preferences": {
                "classification_backup": "nemotron",
            },
            "default_backup": "deepseek_r1",
        }
        _, fallback = engine.select_with_fallback("classifier")  # complexity 3
        assert fallback.name == "nemotron"

    def test_fallback_different_from_primary(self):
        engine = RoutingEngine()
        engine.config = {
            "default_primary": "sonnet",
            "default_backup": "deepseek_r1",
            "routing_preferences": {},
        }
        primary, fallback = engine.select_with_fallback("learner")  # complexity 4
        assert primary.name != fallback.name
