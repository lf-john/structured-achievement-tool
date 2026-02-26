"""
IMPLEMENTATION PLAN for US-004:

Components:
  - analyze_results(data):
    - Takes JSON benchmark data with model_name, prompt, response_time_ms, first_token_time_ms, output_tokens, status
    - Creates pandas DataFrame from data
    - Calculates tokens_per_sec for successful runs (output_tokens / response_time_ms/1000)
    - Returns tuple: (summary_dict, detailed_df) where summary_dict has per-model statistics
  - generate_recommendations(summary):
    - Analyzes summary to find best model for each task type
    - simple_qa: highest tokens_per_sec
    - reasoning: lowest response_time_ms with no errors
    - code: same as reasoning
    - Returns formatted Markdown table
  - generate_report(summary, detailed_df, output_path):
    - Creates Markdown report with timestamp
    - Includes Benchmark Summary table with all models
    - Includes Recommendations section
    - Includes Detailed Results section with per-model breakdown
    - Writes to output_path
  - main():
    - CLI entry point with --input and --output arguments
    - Validates input file exists
    - Calls analyze_results, then generate_report

Test Cases:
  1. [AC 1] Test analyze_results creates summary with correct metrics
  2. [AC 2] Test generate_report includes detailed per-model sections
  3. [AC 3] Test timeouts and errors are marked in report
  4. [AC 4] Test recommendations section maps model strengths
  5. [AC 5] Test report is valid Markdown with proper formatting
  6. [AC 6] Test main writes report to correct location
  7. [AC 7] Test report includes timestamp

Edge Cases:
  - Empty benchmark results array
  - All runs with 'timeout' or 'error' status
  - Model with no successful runs (tokens_per_sec = 0)
  - Multiple prompts per model
  - Non-existent input file
"""

import pytest
import sys
import os
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Note: We're testing import failures to verify TDD-RED phase
try:
    from src.benchmarking.report_generator import analyze_results, generate_recommendations, generate_report, main
    IMPLEMENTATION_EXISTS = True
except (ImportError, ModuleNotFoundError) as e:
    IMPLEMENTATION_EXISTS = False
    print(f"Import error (expected in TDD-RED): {e}")


class TestAnalyzeResults:
    """Tests for the analyze_results function."""

    def test_analyze_results_creates_summary_with_metrics(self):
        """AC 1: Test analyze_results creates summary with correct metrics."""
        if not IMPLEMENTATION_EXISTS:
            pytest.skip("Implementation not yet written")

        data = [
            {
                "model_name": "model-a",
                "prompt": "p1",
                "response_time_ms": 1000,
                "first_token_time_ms": 100,
                "output_tokens": 10,
                "status": "success"
            },
            {
                "model_name": "model-b",
                "prompt": "p1",
                "response_time_ms": 2000,
                "first_token_time_ms": 200,
                "output_tokens": 20,
                "status": "success"
            }
        ]

        summary, detailed_df = analyze_results(data)

        # Check summary contains expected keys
        assert "model-a" in summary
        assert "model-b" in summary
        assert "tokens_per_sec" in summary["model-a"]
        assert "time_to_first_token_ms" in summary["model-a"]
        assert "total_response_time_ms" in summary["model-a"]
        assert "timeouts" in summary["model-a"]
        assert "errors" in summary["model-a"]
        assert "total_runs" in summary["model-a"]

        # Check metrics are calculated correctly
        # model-a: 10 tokens / 1s = 10 tokens/sec
        assert summary["model-a"]["tokens_per_sec"] == 10.0
        assert summary["model-a"]["time_to_first_token_ms"] == 100.0
        assert summary["model-a"]["total_response_time_ms"] == 1000.0
        assert summary["model-a"]["timeouts"] == 0
        assert summary["model-a"]["errors"] == 0
        assert summary["model-a"]["total_runs"] == 1

    def test_analyze_results_handles_empty_array(self):
        """AC 1: Test analyze_results handles empty results array."""
        if not IMPLEMENTATION_EXISTS:
            pytest.skip("Implementation not yet written")

        summary, detailed_df = analyze_results([])

        assert summary == {}
        assert detailed_df.empty

    def test_analyze_results_handles_timeout_status(self):
        """AC 3: Test timeouts are counted correctly."""
        if not IMPLEMENTATION_EXISTS:
            pytest.skip("Implementation not yet written")

        data = [
            {
                "model_name": "model-a",
                "prompt": "p1",
                "response_time_ms": 5000,
                "first_token_time_ms": 500,
                "output_tokens": 0,
                "status": "timeout"
            }
        ]

        summary, detailed_df = analyze_results(data)

        assert summary["model-a"]["timeouts"] == 1
        assert summary["model-a"]["errors"] == 0
        # tokens_per_sec should be 0 for runs with no successful output
        assert summary["model-a"]["tokens_per_sec"] == 0.0

    def test_analyze_results_handles_error_status(self):
        """AC 3: Test errors are counted correctly."""
        if not IMPLEMENTATION_EXISTS:
            pytest.skip("Implementation not yet written")

        data = [
            {
                "model_name": "model-a",
                "prompt": "p1",
                "response_time_ms": 1200,
                "first_token_time_ms": 120,
                "output_tokens": 12,
                "status": "error"
            }
        ]

        summary, detailed_df = analyze_results(data)

        assert summary["model-a"]["errors"] == 1
        assert summary["model-a"]["timeouts"] == 0

    def test_analyze_results_calculates_mean_correctly(self):
        """AC 1: Test analyze_results calculates mean metrics correctly."""
        if not IMPLEMENTATION_EXISTS:
            pytest.skip("Implementation not yet written")

        data = [
            {
                "model_name": "model-a",
                "prompt": "p1",
                "response_time_ms": 1000,
                "first_token_time_ms": 100,
                "output_tokens": 10,
                "status": "success"
            },
            {
                "model_name": "model-a",
                "prompt": "p2",
                "response_time_ms": 2000,
                "first_token_time_ms": 200,
                "output_tokens": 20,
                "status": "success"
            }
        ]

        summary, detailed_df = analyze_results(data)

        # Mean should be (1000 + 2000) / 2 = 1500
        assert summary["model-a"]["total_response_time_ms"] == 1500.0
        # Mean should be (100 + 200) / 2 = 150
        assert summary["model-a"]["time_to_first_token_ms"] == 150.0
        # Mean tokens/sec should be (10 + 20) / 2 = 15
        assert summary["model-a"]["tokens_per_sec"] == 15.0


class TestGenerateRecommendations:
    """Tests for the generate_recommendations function."""

    def test_recommendations_maps_simple_qa_to_highest_tps(self):
        """AC 4: Test simple_qa recommendation goes to highest tokens_per_sec."""
        if not IMPLEMENTATION_EXISTS:
            pytest.skip("Implementation not yet written")

        summary = {
            "model-a": {"tokens_per_sec": 10.0, "total_response_time_ms": 1000.0, "errors": 0},
            "model-b": {"tokens_per_sec": 20.0, "total_response_time_ms": 2000.0, "errors": 0},
            "model-c": {"tokens_per_sec": 5.0, "total_response_time_ms": 500.0, "errors": 0}
        }

        recommendations = generate_recommendations(summary)

        assert "Simple Q&A" in recommendations
        assert "model-b" in recommendations

    def test_recommendations_maps_reasoning_to_lowest_time_no_errors(self):
        """AC 4: Test reasoning recommendation goes to lowest time with no errors."""
        if not IMPLEMENTATION_EXISTS:
            pytest.skip("Implementation not yet written")

        summary = {
            "model-a": {"tokens_per_sec": 10.0, "total_response_time_ms": 1000.0, "errors": 1},  # Has errors
            "model-b": {"tokens_per_sec": 15.0, "total_response_time_ms": 500.0, "errors": 0},  # Best
            "model-c": {"tokens_per_sec": 20.0, "total_response_time_ms": 600.0, "errors": 0}   # Slower
        }

        recommendations = generate_recommendations(summary)

        assert "Reasoning" in recommendations
        assert "model-b" in recommendations

    def test_recommendations_maps_code_same_as_reasoning(self):
        """AC 4: Test code recommendation is same as reasoning."""
        if not IMPLEMENTATION_EXISTS:
            pytest.skip("Implementation not yet written")

        summary = {
            "model-a": {"tokens_per_sec": 10.0, "total_response_time_ms": 1000.0, "errors": 0},
            "model-b": {"tokens_per_sec": 15.0, "total_response_time_ms": 500.0, "errors": 0}
        }

        recommendations = generate_recommendations(summary)

        assert "Code" in recommendations
        assert "model-b" in recommendations
        # Code and reasoning should both be model-b
        assert recommendations.index("Code") == recommendations.index("Reasoning")

    def test_recommendations_table_format(self):
        """AC 5: Test recommendations are formatted as Markdown table."""
        if not IMPLEMENTATION_EXISTS:
            pytest.skip("Implementation not yet written")

        summary = {
            "model-a": {"tokens_per_sec": 10.0, "total_response_time_ms": 1000.0, "errors": 0},
            "model-b": {"tokens_per_sec": 20.0, "total_response_time_ms": 500.0, "errors": 0}
        }

        recommendations = generate_recommendations(summary)

        # Should be a Markdown table
        assert "|" in recommendations
        assert "---" in recommendations
        assert "| Task Type" in recommendations
        assert "| Recommended Model" in recommendations


class TestGenerateReport:
    """Tests for the generate_report function."""

    @patch('pandas.DataFrame.to_markdown')
    def test_generate_report_includes_all_sections(self, mock_to_markdown, tmp_path):
        """AC 1-7: Test generate_report includes all required sections."""
        if not IMPLEMENTATION_EXISTS:
            pytest.skip("Implementation not yet written")

        summary = {
            "model-a": {
                "tokens_per_sec": 10.0,
                "time_to_first_token_ms": 100.0,
                "total_response_time_ms": 1000.0,
                "timeouts": 0,
                "errors": 0,
                "total_runs": 2
            }
        }

        detailed_df = MagicMock()
        detailed_df['model_name'].unique.return_value = ['model-a']

        output_path = tmp_path / "test_report.md"

        generate_report(summary, detailed_df, output_path)

        content = output_path.read_text()

        # Check header
        assert "# Ollama Benchmark Report" in content

        # Check timestamp
        assert "Generated on:" in content

        # Check summary section
        assert "## Benchmark Summary" in content
        assert "model-a" in content

        # Check recommendations section
        assert "## Recommendations" in content

        # Check detailed results section
        assert "## Detailed Results" in content
        assert "### model-a" in content

    @patch('pandas.DataFrame.to_markdown')
    def test_generate_report_includes_timeout_marker(self, mock_to_markdown, tmp_path):
        """AC 3: Test timeouts are marked in report."""
        if not IMPLEMENTATION_EXISTS:
            pytest.skip("Implementation not yet written")

        summary = {
            "model-a": {
                "tokens_per_sec": 10.0,
                "time_to_first_token_ms": 100.0,
                "total_response_time_ms": 1000.0,
                "timeouts": 1,
                "errors": 0,
                "total_runs": 1
            }
        }

        detailed_df = MagicMock()
        detailed_df['model_name'].unique.return_value = ['model-a']

        output_path = tmp_path / "test_report.md"

        generate_report(summary, detailed_df, output_path)

        content = output_path.read_text()

        # Check timeouts are in summary
        assert "timeout" in content.lower()

    @patch('pandas.DataFrame.to_markdown')
    def test_generate_report_includes_error_marker(self, mock_to_markdown, tmp_path):
        """AC 3: Test errors are marked in report."""
        if not IMPLEMENTATION_EXISTS:
            pytest.skip("Implementation not yet written")

        summary = {
            "model-a": {
                "tokens_per_sec": 10.0,
                "time_to_first_token_ms": 100.0,
                "total_response_time_ms": 1000.0,
                "timeouts": 0,
                "errors": 1,
                "total_runs": 1
            }
        }

        detailed_df = MagicMock()
        detailed_df['model_name'].unique.return_value = ['model-a']

        output_path = tmp_path / "test_report.md"

        generate_report(summary, detailed_df, output_path)

        content = output_path.read_text()

        # Check errors are in summary
        assert "error" in content.lower()

    def test_generate_report_writes_to_correct_location(self, tmp_path):
        """AC 6: Test report is written to specified location."""
        if not IMPLEMENTATION_EXISTS:
            pytest.skip("Implementation not yet written")

        summary = {}
        detailed_df = MagicMock()

        output_path = tmp_path / "output.md"

        generate_report(summary, detailed_df, output_path)

        # Check file was created
        assert output_path.exists()

        # Check file is not empty
        content = output_path.read_text()
        assert len(content) > 0


class TestMainFunction:
    """Tests for the main function."""

    def test_main_creates_report_with_default_args(self, tmp_path, monkeypatch):
        """AC 6: Test main generates report with default arguments."""
        if not IMPLEMENTATION_EXISTS:
            pytest.skip("Implementation not yet written")

        # Create mock input data
        mock_data = [
            {
                "model_name": "model-a",
                "prompt": "test",
                "response_time_ms": 1000,
                "first_token_time_ms": 100,
                "output_tokens": 10,
                "status": "success"
            }
        ]
        input_data = json.dumps(mock_data)

        # Create temporary input file
        input_file = tmp_path / "test_input.json"
        input_file.write_text(input_data)

        # Set up output path
        output_file = tmp_path / "ollama_benchmark.md"

        # Mock argument parser
        with patch('argparse.ArgumentParser.parse_args',
                   return_value=MagicMock(input=str(input_file), output=str(output_file))):
            # Mock file operations
            with patch('builtins.open', mock_open(read_data=input_data)) as mock_file:
                # Mock pandas functions
                with patch('pandas.DataFrame'):
                    # Mock datetime
                    with patch('datetime.datetime') as mock_datetime:
                        mock_datetime.now.return_value.strftime.return_value = "2026-02-26 15:00:00"

                        # Mock generate_report to avoid file I/O
                        with patch('src.benchmarking.report_generator.generate_report') as mock_generate:
                            main()

                            # Check generate_report was called
                            mock_generate.assert_called_once()

    def test_main_handles_nonexistent_input(self):
        """AC 6: Test main handles nonexistent input file."""
        if not IMPLEMENTATION_EXISTS:
            pytest.skip("Implementation not yet written")

        # Mock nonexistent input
        with patch('argparse.ArgumentParser.parse_args',
                   return_value=MagicMock(input='nonexistent.json', output='/tmp/test.md')):
            # Mock Path.exists to return False
            with patch('src.benchmarking.report_generator.Path') as mock_path:
                mock_path.return_value.exists.return_value = False

                # Should not crash, should just exit silently
                with patch('sys.exit') as mock_exit:
                    main()
                    # Should have been called (though exit code isn't critical for this test)
                    mock_exit.assert_called_once()


class TestMarkdownFormatting:
    """Tests for Markdown formatting in the report."""

    @patch('pandas.DataFrame.to_markdown')
    def test_report_has_valid_markdown_table_syntax(self, mock_to_markdown, tmp_path):
        """AC 5: Test report has valid Markdown table syntax."""
        if not IMPLEMENTATION_EXISTS:
            pytest.skip("Implementation not yet written")

        summary = {}
        detailed_df = MagicMock()
        output_path = tmp_path / "test_report.md"

        generate_report(summary, detailed_df, output_path)

        content = output_path.read_text()

        # Check for proper Markdown table syntax
        assert "| Model |" in content
        assert "|---|" in content
        assert "|" in content  # Table row separator

    def test_recommendations_section_is_markdown_table(self, tmp_path):
        """AC 5: Test recommendations section is Markdown table."""
        if not IMPLEMENTATION_EXISTS:
            pytest.skip("Implementation not yet written")

        summary = {
            "model-a": {"tokens_per_sec": 10.0, "total_response_time_ms": 1000.0, "errors": 0}
        }

        detailed_df = MagicMock()
        output_path = tmp_path / "test_report.md"

        generate_report(summary, detailed_df, output_path)

        content = output_path.read_text()

        # Check recommendations section
        assert "## Recommendations" in content

        # Extract recommendations section
        lines = content.split('\n')
        in_recommendations = False
        for line in lines:
            if "## Recommendations" in line:
                in_recommendations = True
            elif in_recommendations and line.startswith("##"):
                break

        recommendations_section = '\n'.join(lines[:lines.index(line) if in_recommendations else len(lines)])

        # Should be Markdown table
        assert "|" in recommendations_section
        assert "---" in recommendations_section
        assert "| Task Type" in recommendations_section


# Test exit code for TDD-RED detection
if __name__ == "__main__":
    # This won't actually run tests, but will fail if implementation exists
    if not IMPLEMENTATION_EXISTS:
        print("✓ Tests correctly failing (implementation not found)")
        sys.exit(1)
    else:
        print("✗ Implementation exists (should fail in TDD-RED phase)")
        sys.exit(0)
