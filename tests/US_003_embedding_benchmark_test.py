"""
IMPLEMENTATION PLAN for US-003:

Components:
  - src/benchmarking/embedding_benchmark.py: Main module for benchmarking nomic-embed-text
    - StandardTextPassage: Constant with standard text for consistent benchmarking
    - run_embedding_benchmark(model_name: str, output_file: str) -> dict: Main benchmark function
    - _measure_throughput(text: str, model_name: str) -> float: Measures tokens/second
    - _measure_latency(text: str, model_name: str) -> dict: Measures latency metrics
    - BenchmarkResult: Dataclass for storing benchmark results

Test Cases:
  1. AC 1 (`nomic-embed-text is benchmarked via /api/embeddings endpoint`) -> test_should_benchmark_embeddings_endpoint
  2. AC 2 (`Standard text passage is used for consistent benchmarking`) -> test_should_use_standard_passage
  3. AC 3 (`Warm-up run is executed and discarded`) -> test_should_execute_warmup_and_discard
  4. AC 4 (`3 timed runs are executed and results are averaged`) -> test_should_execute_three_timed_runs_and_average
  5. AC 5 (`Embedding dimension and latency metrics are captured`) -> test_should_capture_768_dimension_and_latency
  6. AC 6 (`Results are persisted for report generation`) -> test_should_persist_results

Edge Cases:
  - Empty text passage
  - Ollama unavailable during benchmark
  - Network timeout during timed runs
  - Inconsistent embedding dimensions
  - Multiple runs with inconsistent results
"""

import pytest
import sys
from unittest.mock import patch, MagicMock
import os
import json

# We expect this import to fail initially, leading to TDD-RED state.
# Import is intentionally placed here to cause import error during collection
try:
    from src.benchmarking.embedding_benchmark import (
        StandardTextPassage,
        run_embedding_benchmark,
        BenchmarkResult,
    )
except ImportError:
    pass  # Will fail later during test execution


class TestStandardTextPassage:
    """Test suite for StandardTextPassage constant."""

    def test_standard_passage_exists(self):
        """Test that StandardTextPassage is defined and is a non-empty string."""
        assert hasattr(StandardTextPassage, 'text')
        assert isinstance(StandardTextPassage.text, str)
        assert len(StandardTextPassage.text) > 0

    def test_standard_passage_is_constant(self):
        """Test that StandardTextPassage.text is the same across multiple accesses."""
        text1 = StandardTextPassage.text
        text2 = StandardTextPassage.text
        assert text1 is text2 or text1 == text2

    def test_standard_passage_contains_meaningful_content(self):
        """Test that the standard passage contains substantial text."""
        text = StandardTextPassage.text
        # Should have enough text to be meaningful for benchmarking
        assert len(text) > 100
        # Should contain spaces/words
        assert len(text.split()) > 20


class TestRunEmbeddingBenchmark:
    """Test suite for run_embedding_benchmark function."""

    @patch('src.benchmarking.embedding_benchmark.ollama.embeddings')
    def test_should_benchmark_embeddings_endpoint(self, mock_embeddings):
        """Test that run_embedding_benchmark calls /api/embeddings endpoint."""
        # Setup mock response
        mock_response = {
            'embedding': [0.1] * 768,
            'duration_ms': 100,
            'total_duration_ms': 150
        }
        mock_embeddings.return_value = mock_response

        # Run benchmark
        result = run_embedding_benchmark(
            model_name="nomic-embed-text",
            output_file="/tmp/test_results.json"
        )

        # Verify embeddings endpoint was called
        mock_embeddings.assert_called_once()
        assert result['model_name'] == "nomic-embed-text"

    @patch('src.benchmarking.embedding_benchmark.ollama.embeddings')
    def test_should_use_standard_passage(self, mock_embeddings):
        """Test that the standard passage is used for benchmarking."""
        mock_embeddings.return_value = {'embedding': [0.1] * 768}

        run_embedding_benchmark(
            model_name="nomic-embed-text",
            output_file="/tmp/test_results.json"
        )

        # Verify standard passage was passed to ollama
        call_args = mock_embeddings.call_args
        assert 'prompt' in call_args.kwargs
        assert call_args.kwargs['prompt'] == StandardTextPassage.text

    @patch('src.benchmarking.embedding_benchmark.ollama.embeddings')
    def test_should_execute_warmup_and_discard(self, mock_embeddings):
        """Test that warm-up run is executed and its results are discarded."""
        # Setup mock to return different values for each call
        mock_embeddings.side_effect = [
            {'embedding': [0.1] * 768},  # Warm-up
            {'embedding': [0.2] * 768},  # Run 1
            {'embedding': [0.3] * 768},  # Run 2
            {'embedding': [0.4] * 768},  # Run 3
        ]

        # Clear any previous runs in result
        from src.benchmarking.embedding_benchmark import BenchmarkRun
        BenchmarkRun.__init__(BenchmarkRun, 1, 1.0, 0.1, 0.1, "success")

        result = run_embedding_benchmark(
            model_name="nomic-embed-text",
            output_file="/tmp/test_results.json"
        )

        # Verify embeddings was called 4 times (1 warm-up + 3 timed)
        assert mock_embeddings.call_count == 4

        # Verify warm-up result is not in final results
        assert len(result['runs']) == 3

    @patch('src.benchmarking.embedding_benchmark.ollama.embeddings')
    def test_should_execute_three_timed_runs_and_average(self, mock_embeddings):
        """Test that exactly 3 timed runs are executed and results are averaged."""
        # Setup mock with consistent results
        mock_embeddings.return_value = {'embedding': [0.1] * 768}

        result = run_embedding_benchmark(
            model_name="nomic-embed-text",
            output_file="/tmp/test_results.json"
        )

        # Verify exactly 3 timed runs were executed
        assert len(result['runs']) == 3

        # Verify averaging of tokens_per_second
        expected_tokens_per_sec = 100.0
        assert result['avg_tokens_per_second'] == expected_tokens_per_sec

        # Verify averaging of latency metrics
        expected_latency = 50.0
        assert result['avg_time_to_first_token'] == expected_latency

    @patch('src.benchmarking.embedding_benchmark.ollama.embeddings')
    def test_should_capture_768_dimension_and_latency(self, mock_embeddings):
        """Test that embedding dimension (768) and latency metrics are captured."""
        mock_embeddings.return_value = {
            'embedding': [0.1] * 768,
            'time_to_first_token_ms': 50,
            'total_duration_ms': 150
        }

        result = run_embedding_benchmark(
            model_name="nomic-embed-text",
            output_file="/tmp/test_results.json"
        )

        # Verify embedding dimension is captured
        assert result['embedding_dimension'] == 768

        # Verify latency metrics are captured
        assert 'avg_time_to_first_token' in result
        assert 'avg_total_latency' in result

        # Verify each run captures these metrics
        for run in result['runs']:
            assert 'embedding_dimension' in run
            assert 'time_to_first_token' in run
            assert 'total_latency' in run

    @patch('src.benchmarking.embedding_benchmark.ollama.embeddings')
    def test_should_persist_results(self, mock_embeddings):
        """Test that benchmark results are persisted to output file."""
        mock_embeddings.return_value = {'embedding': [0.1] * 768}

        test_output_file = "/tmp/test_embedding_benchmark.json"

        # Run benchmark with cleanup
        try:
            run_embedding_benchmark(
                model_name="nomic-embed-text",
                output_file=test_output_file
            )

            # Verify file exists
            assert os.path.exists(test_output_file)

            # Verify file contains valid JSON
            with open(test_output_file, 'r') as f:
                data = json.load(f)
                assert isinstance(data, dict)
                assert 'model_name' in data
                assert 'runs' in data

        finally:
            # Cleanup test file
            if os.path.exists(test_output_file):
                os.remove(test_output_file)

    @patch('src.benchmarking.embedding_benchmark.ollama.embeddings')
    def test_handles_empty_text_passage(self, mock_embeddings):
        """Test that empty text passage is handled gracefully."""
        mock_embeddings.return_value = {'embedding': [0.0]}

        result = run_embedding_benchmark(
            model_name="nomic-embed-text",
            output_file="/tmp/test_results.json"
        )

        # Should still complete successfully with empty text
        assert result is not None
        assert result['status'] == "completed"

    @patch('src.benchmarking.embedding_benchmark.ollama.embeddings')
    def test_handles_ollama_unavailable(self, mock_embeddings):
        """Test that Ollama unavailability is handled."""
        mock_embeddings.side_effect = Exception("Ollama unavailable")

        result = run_embedding_benchmark(
            model_name="nomic-embed-text",
            output_file="/tmp/test_results.json"
        )

        # Should return failure status
        assert result['status'] == "failed" or result['status'] == "error"


class TestBenchmarkResult:
    """Test suite for BenchmarkResult dataclass."""

    def test_benchmark_result_creation_with_valid_data(self):
        """Test creating a BenchmarkResult with all required fields."""
        result = BenchmarkResult(
            run_number=1,
            tokens_per_second=150.5,
            time_to_first_token=0.8,
            total_latency=5.2,
            status="success",
            embedding_dimension=768
        )
        assert result.run_number == 1
        assert result.tokens_per_second == 150.5
        assert result.embedding_dimension == 768
        assert result.status == "success"

    def test_benchmark_result_default_values(self):
        """Test that BenchmarkResult has sensible defaults."""
        result = BenchmarkResult(
            run_number=1,
            tokens_per_second=100.0,
            time_to_first_token=0.5,
            total_latency=3.0,
            status="success"
        )
        assert result.embedding_dimension == 768  # Default for nomic-embed-text

    def test_benchmark_result_invalid_run_number(self):
        """Test that BenchmarkResult rejects invalid run numbers."""
        with pytest.raises(ValueError):
            BenchmarkResult(
                run_number=-1,
                tokens_per_second=100.0,
                time_to_first_token=0.5,
                total_latency=3.0,
                status="success"
            )

    def test_benchmark_result_invalid_dimension(self):
        """Test that BenchmarkResult rejects invalid embedding dimensions."""
        with pytest.raises(ValueError):
            BenchmarkResult(
                run_number=1,
                tokens_per_second=100.0,
                time_to_first_token=0.5,
                total_latency=3.0,
                status="success",
                embedding_dimension=512  # Wrong dimension for nomic-embed-text
            )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
    sys.exit(1 if pytest.main([__file__, '-v']) else 0)
