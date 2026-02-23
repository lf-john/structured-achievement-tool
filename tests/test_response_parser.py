"""Tests for src.llm.response_parser — JSON extraction + Pydantic validation."""

import pytest
from pydantic import ValidationError

from src.llm.response_parser import (
    extract_json,
    validate_response,
    parse_and_validate,
    AgentResponse,
    AgentStatus,
    ClassifyResponse,
    DecomposeResponse,
    StorySchema,
    VerifyResponse,
    MediatorResponse,
    MediatorDecision,
)


class TestExtractJson:
    def test_raw_json(self):
        result = extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_with_whitespace(self):
        result = extract_json('  \n {"key": "value"} \n ')
        assert result == {"key": "value"}

    def test_json_in_markdown_fence(self):
        text = 'Here is the response:\n```json\n{"key": "value"}\n```\nDone.'
        result = extract_json(text)
        assert result == {"key": "value"}

    def test_json_in_plain_fence(self):
        text = '```\n{"key": "value"}\n```'
        result = extract_json(text)
        assert result == {"key": "value"}

    def test_json_embedded_in_text(self):
        text = 'Some preamble text here. {"key": "value"} And trailing text.'
        result = extract_json(text)
        assert result == {"key": "value"}

    def test_nested_json(self):
        text = '{"outer": {"inner": "value"}, "list": [1, 2]}'
        result = extract_json(text)
        assert result == {"outer": {"inner": "value"}, "list": [1, 2]}

    def test_empty_input_raises(self):
        with pytest.raises(ValueError, match="Empty response"):
            extract_json("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="Empty response"):
            extract_json("   \n  ")

    def test_no_json_raises(self):
        with pytest.raises(ValueError, match="No valid JSON found"):
            extract_json("This has no JSON at all.")

    def test_invalid_json_in_fence_raises(self):
        text = '```json\n{bad json here}\n```'
        with pytest.raises(ValueError, match="No valid JSON found"):
            extract_json(text)

    def test_multiple_fences_uses_first_valid(self):
        text = '```json\n{invalid\n```\n```json\n{"key": "value"}\n```'
        result = extract_json(text)
        assert result == {"key": "value"}


class TestValidateResponse:
    def test_valid_classify_response(self):
        data = {"task_type": "development", "confidence": 0.9, "reasoning": "test"}
        result = validate_response(data, ClassifyResponse)
        assert result.task_type == "development"
        assert result.confidence == 0.9

    def test_classify_confidence_bounds(self):
        with pytest.raises(ValidationError):
            validate_response({"task_type": "x", "confidence": 1.5}, ClassifyResponse)

        with pytest.raises(ValidationError):
            validate_response({"task_type": "x", "confidence": -0.1}, ClassifyResponse)

    def test_valid_agent_response(self):
        data = {"status": "complete", "output": "done", "thinking": "thought"}
        result = validate_response(data, AgentResponse)
        assert result.status == AgentStatus.COMPLETE
        assert result.output == "done"

    def test_agent_response_invalid_status(self):
        with pytest.raises(ValidationError):
            validate_response({"status": "invalid", "output": "x"}, AgentResponse)

    def test_decompose_response_with_stories(self):
        data = {
            "stories": [
                {
                    "id": "US-001",
                    "title": "Test Story",
                    "description": "A test story",
                    "type": "development",
                    "complexity": 5,
                    "dependsOn": [],
                    "acceptanceCriteria": ["It works"],
                }
            ]
        }
        result = validate_response(data, DecomposeResponse)
        assert len(result.stories) == 1
        assert result.stories[0].id == "US-001"
        assert result.stories[0].complexity == 5

    def test_story_schema_complexity_bounds(self):
        with pytest.raises(ValidationError):
            StorySchema(id="x", title="x", description="x", complexity=0)
        with pytest.raises(ValidationError):
            StorySchema(id="x", title="x", description="x", complexity=11)

    def test_mediator_response_valid(self):
        data = {
            "decision": "ACCEPT",
            "confidence": 0.9,
            "reasoning": "Looks good",
            "actions": [],
        }
        result = validate_response(data, MediatorResponse)
        assert result.decision == MediatorDecision.ACCEPT

    def test_mediator_invalid_decision(self):
        with pytest.raises(ValidationError):
            validate_response({"decision": "INVALID", "reasoning": "x"}, MediatorResponse)


class TestParseAndValidate:
    def test_end_to_end(self):
        text = '```json\n{"task_type": "debug", "confidence": 0.8}\n```'
        result = parse_and_validate(text, ClassifyResponse)
        assert result.task_type == "debug"
        assert result.confidence == 0.8

    def test_invalid_json_then_validation(self):
        with pytest.raises(ValueError):
            parse_and_validate("not json", ClassifyResponse)

    def test_valid_json_invalid_model(self):
        with pytest.raises(ValidationError):
            parse_and_validate('{"wrong_field": "x"}', ClassifyResponse)
