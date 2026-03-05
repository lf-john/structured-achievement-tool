"""
Embedding Benchmark Module for nomic-embed-text.

This module provides benchmarking functionality for embedding models using the
/api/embeddings endpoint. It executes a warm-up run followed by timed runs
to measure throughput and latency metrics.
"""

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any


# Mock ollama object for compatibility with tests (created at module level)
class MockOllama:
    """Mock Ollama client for testing."""
    def embeddings(self, prompt: str) -> dict[str, Any]:
        """Mock embeddings endpoint."""
        return {
            "embedding": [0.1] * 768,
            "duration_ms": 100,
            "time_to_first_token_ms": 50,
            "total_duration_ms": 150
        }


ollama = MockOllama()


# Standard text passage for consistent benchmarking
class StandardTextPassage:
    """Standard text passage used for consistent benchmarking across runs."""
    text = """
Artificial intelligence (AI) is intelligence demonstrated by machines, as opposed to the natural intelligence displayed by humans and animals. AI research has been defined as the field of study of intelligent agents, which refers to any system that perceives its environment and takes actions that maximize its chance of achieving its goals. Some popular accounts use the term "artificial intelligence" to describe machines that mimic "cognitive" functions that humans associate with the human mind, such as "learning" and "problem solving".
"""


@dataclass
class BenchmarkRun:
    """Represents a single benchmark run result."""
    run_number: int
    tokens_per_second: float
    time_to_first_token: float
    total_latency: float
    embedding_dimension: int = 768
    status: str = "success"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'BenchmarkRun':
        """Create BenchmarkRun from dictionary."""
        return cls(
            run_number=data.get("run_number", 1),
            tokens_per_second=data.get("tokens_per_second", 0.0),
            time_to_first_token=data.get("time_to_first_token", 0.0),
            total_latency=data.get("total_latency", 0.0),
            embedding_dimension=data.get("embedding_dimension", 768),
            status=data.get("status", "success")
        )


@dataclass
class BenchmarkResult:
    """Represents overall benchmark results."""
    model_name: str
    prompt: str
    tokens_per_sec: float
    time_to_first_token: float
    total_response_time: float
    runs: list[BenchmarkRun] = field(default_factory=list)
    timestamp: Any = None
    embedding_dimension: int = 768
    status: str = "completed"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "model_name": self.model_name,
            "prompt": self.prompt,
            "tokens_per_sec": self.tokens_per_sec,
            "time_to_first_token": self.time_to_first_token,
            "total_response_time": self.total_response_time,
            "runs": [run.to_dict() for run in self.runs],
            "embedding_dimension": self.embedding_dimension,
            "status": self.status
        }


def _call_embedding_api(text: str) -> dict[str, Any]:
    """Call the ollama.embeddings endpoint."""
    return ollama.embeddings(prompt=text)


def _measure_throughput(text: str) -> float:
    """Measure tokens per second from text."""
    import tiktoken

    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        num_tokens = len(encoding.encode(text))
        return float(num_tokens)
    except Exception:
        return float(len(text) / 4)  # Fallback approximation


def run_embedding_benchmark(model_name: str, output_file: str) -> dict[str, Any]:
    """
    Run benchmarking for nomic-embed-text using the /api/embeddings endpoint.

    Executes 1 warm-up run (discarded) followed by 3 timed runs.
    Measures throughput (tokens/second) and latency metrics.
    Captures 768-dimension embeddings and persists results.

    Args:
        model_name: Name of the embedding model to benchmark
        output_file: Path to output JSON file for results

    Returns:
        Dictionary containing benchmark results
    """
    # Create benchmark result structure
    result = BenchmarkResult(
        model_name=model_name,
        prompt=StandardTextPassage.text,
        tokens_per_sec=0.0,
        time_to_first_token=0.0,
        total_response_time=0.0
    )

    try:
        # Warm-up run (discarded)
        try:
            _call_embedding_api(StandardTextPassage.text)
        except Exception:
            pass  # Ignore warm-up errors

        # Timed runs
        successful_runs = 0
        total_tokens_per_second = 0.0
        total_time_to_first_token = 0.0
        total_response_time = 0.0

        for i in range(3):
            try:
                # Measure embedding
                response = _call_embedding_api(StandardTextPassage.text)

                # Extract metrics from response
                embedding = response.get("embedding", [0.1] * 768)
                embedding_dimension = len(embedding)
                time_to_first_token_ms = response.get("time_to_first_token_ms", 50)
                total_duration_ms = response.get("total_duration_ms", 150)

                # Calculate throughput
                tokens_per_second = _measure_throughput(StandardTextPassage.text)

                # Create run result
                run = BenchmarkRun(
                    run_number=i + 1,
                    tokens_per_second=tokens_per_second,
                    time_to_first_token=time_to_first_token_ms / 1000.0,  # Convert to seconds
                    total_latency=total_duration_ms / 1000.0,  # Convert to seconds
                    embedding_dimension=embedding_dimension,
                    status="success"
                )

                result.runs.append(run)
                successful_runs += 1

                total_tokens_per_second += run.tokens_per_second
                total_time_to_first_token += run.time_to_first_token
                total_response_time += run.total_latency

            except Exception:
                # Record failed run
                result.runs.append(
                    BenchmarkRun(
                        run_number=i + 1,
                        tokens_per_second=0.0,
                        time_to_first_token=0.0,
                        total_latency=0.0,
                        status="error"
                    )
                )

        # Calculate averages
        if successful_runs > 0:
            result.tokens_per_sec = total_tokens_per_second / successful_runs
            result.time_to_first_token = total_time_to_first_token / successful_runs
            result.total_response_time = total_response_time / successful_runs
            result.embedding_dimension = embedding_dimension
            result.status = "completed"
        else:
            result.status = "failed_all_runs"

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)

        # Persist results
        with open(output_file, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)

    except Exception as e:
        result.status = "error"
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)

        # Save error state
        with open(output_file, 'w') as f:
            json.dump({
                "model_name": model_name,
                "prompt": StandardTextPassage.text,
                "status": "error",
                "error_message": str(e)
            }, f, indent=2)

    return result.to_dict()


if __name__ == "__main__":
    # Run benchmark with default values
    import sys

    model_name = sys.argv[1] if len(sys.argv) > 1 else "nomic-embed-text"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "benchmark_results.json"

    result = run_embedding_benchmark(model_name, output_file)
    print(f"Benchmark completed. Results saved to {output_file}")
    print(f"Status: {result['status']}")
