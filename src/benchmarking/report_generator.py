"""
Report Generator for Ollama Benchmark Results.

This module generates comprehensive Markdown reports from benchmark data,
including summary tables, detailed results, and model recommendations for SAT routing.
"""

import json
import os
import sys
from datetime import datetime
from typing import Any

import pandas as pd


def analyze_results(data: list[dict[str, Any]]) -> tuple:
    """
    Analyze benchmark results and create summary statistics.

    Args:
        data: List of benchmark result dictionaries with model_name, prompt, response_time_ms, etc.

    Returns:
        Tuple of (summary_dict, detailed_dataframe)
    """
    summary = {}
    detailed_rows = []

    for item in data:
        model = item["model_name"]
        prompt = item["prompt"]
        status = item.get("status", "unknown")

        # Initialize model entry in summary
        if model not in summary:
            summary[model] = {
                "tokens_per_sec": 0.0,
                "time_to_first_token_ms": 0.0,
                "total_response_time_ms": 0.0,
                "timeouts": 0,
                "errors": 0,
                "total_runs": 0,
                "successful_runs": 0
            }

        # Track metrics based on status
        if status == "success":
            # Calculate tokens_per_sec if not provided directly
            tokens_per_sec = item.get("tokens_per_sec")
            if tokens_per_sec is None:
                output_tokens = item.get("output_tokens", 0)
                response_time_ms = item.get("total_response_time_ms", item.get("response_time_ms", 1))
                tokens_per_sec = output_tokens / response_time_ms * 1000

            # Get time to first token - try both key names
            time_to_first = item.get("time_to_first_token_ms") or item.get("first_token_time_ms", 0)

            summary[model]["tokens_per_sec"] += tokens_per_sec
            summary[model]["time_to_first_token_ms"] += time_to_first
            summary[model]["total_response_time_ms"] += item.get("total_response_time_ms", 0)
            summary[model]["successful_runs"] += 1
            summary[model]["total_runs"] += 1

            # Add to detailed dataframe
            detailed_rows.append({
                "model_name": model,
                "prompt": prompt,
                "tokens_per_sec": tokens_per_sec,
                "time_to_first_token_ms": time_to_first,
                "total_response_time_ms": item.get("total_response_time_ms", 0),
                "status": status
            })
        elif status == "timeout":
            summary[model]["timeouts"] += 1
            summary[model]["total_runs"] += 1
            detailed_rows.append({
                "model_name": model,
                "prompt": prompt,
                "tokens_per_sec": 0,
                "time_to_first_token_ms": 0,
                "total_response_time_ms": item.get("total_response_time_ms", 0),
                "status": "TIMEOUT"
            })
        else:  # error
            summary[model]["errors"] += 1
            summary[model]["total_runs"] += 1
            detailed_rows.append({
                "model_name": model,
                "prompt": prompt,
                "tokens_per_sec": 0,
                "time_to_first_token_ms": 0,
                "total_response_time_ms": item.get("total_response_time_ms", 0),
                "status": "ERROR"
            })

    # Calculate averages
    for model in summary:
        if summary[model]["successful_runs"] > 0:
            summary[model]["tokens_per_sec"] = (
                summary[model]["tokens_per_sec"] / summary[model]["successful_runs"]
            )
            summary[model]["time_to_first_token_ms"] = (
                summary[model]["time_to_first_token_ms"] / summary[model]["successful_runs"]
            )
            summary[model]["total_response_time_ms"] = (
                summary[model]["total_response_time_ms"] / summary[model]["successful_runs"]
            )

    detailed_df = pd.DataFrame(detailed_rows) if detailed_rows else pd.DataFrame()

    return summary, detailed_df


def generate_recommendations(summary: dict[str, dict[str, Any]]) -> str:
    """
    Generate model recommendations for SAT routing.

    Args:
        summary: Dictionary of model statistics

    Returns:
        Markdown table string with recommendations
    """
    # Filter models that have successful runs and no errors
    # Handle case where successful_runs key might not exist
    # A model is valid if it has any successful runs OR has no errors (indicating it was attempted)
    valid_models = {
        model: data for model, data in summary.items()
        if data.get("errors", 0) == 0
    }

    if not valid_models:
        return "| Task Type | Recommended Model |\n|---|---|\n| - | No valid models |"

    # Find best model for each category
    # Simple Q&A: highest tokens_per_sec
    simple_qa = max(valid_models.items(),
                   key=lambda x: x[1]["tokens_per_sec"],
                   default=(None, {"tokens_per_sec": 0}))

    # Reasoning & Code: lowest response time with no errors
    reasoning_code = min(valid_models.items(),
                        key=lambda x: (x[1]["total_response_time_ms"],
                                     x[1]["errors"]),  # Secondarily minimize errors
                        default=(None, {"total_response_time_ms": float('inf')}))

    # Generate Markdown table
    recommendations = [
        "| Task Type | Recommended Model | Rationale |",
        "|---|---|---|",
        f"| Simple Q&A | {simple_qa[0] if simple_qa[0] else 'N/A'} | Highest throughput (tokens/sec: "
        f"{simple_qa[1]['tokens_per_sec']:.2f}) |",
        f"| Reasoning | {reasoning_code[0] if reasoning_code[0] else 'N/A'} | Fastest response with no errors "
        f"(avg time: {reasoning_code[1]['total_response_time_ms']:.2f}ms) |",
        f"| Code | {reasoning_code[0] if reasoning_code[0] else 'N/A'} | Same as reasoning (code requires "
        f"reasoning capabilities) |"
    ]

    return "\n".join(recommendations)


def generate_report(summary: dict[str, dict[str, Any]],
                    detailed_df: pd.DataFrame,
                    output_path: str) -> None:
    """
    Generate comprehensive benchmark report in Markdown format.

    Args:
        summary: Dictionary of model statistics
        detailed_df: DataFrame with detailed benchmark results
        output_path: Path to write the report
    """
    # Ensure output directory exists
    output_dir = os.path.dirname(output_path) if os.path.dirname(output_path) else "."
    os.makedirs(output_dir, exist_ok=True)

    # Get all models
    models = list(summary.keys())
    [m.split(":")[0] for m in models]  # Extract base model name

    # Generate timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build report content
    lines = [
        "# Ollama Benchmark Report",
        f"**Generated on:** {timestamp}",
        "",
        "## Executive Summary",
        "",
        "This report compares the performance of 4 generative models and provides "
        "recommendations for SAT task routing.",
        "",
        "## Benchmark Summary",
        "",
        "| Model | Tokens/sec | Time to First Token (ms) | Total Response Time (ms) | Successful Runs | Timeouts | Errors |",
        "|---|---|---|---|---|---|---|"
    ]

    # Add model rows
    for model, data in summary.items():
        model_name = model.split(":")[0]

        # Calculate metrics for the model
        avg_tps = data.get("tokens_per_sec", 0)
        avg_tftt = data.get("time_to_first_token_ms", 0)
        avg_time = data.get("total_response_time_ms", 0)
        successful = data.get("successful_runs", 0)
        timeouts = data.get("timeouts", 0)
        errors = data.get("errors", 0)

        # Mark timeouts/errors with emphasis
        status_markdown = f"✓ {successful}" if errors == 0 and timeouts == 0 else "⚠ {successful}"

        lines.append(
            f"| {model_name} | {avg_tps:.2f} | {avg_tftt:.2f} | {avg_time:.2f} | "
            f"{status_markdown} | {timeouts} | {errors} |"
        )

    lines.extend([
        "",
        "## Execution Summary",
        "",
        f"- **Total Models Benchmarked:** {len(models)}",
        f"- **Total Runs:** {sum(data.get('total_runs', 0) for data in summary.values())}",
        f"- **Successful Runs:** {sum(data.get('successful_runs', 0) for data in summary.values())}",
        f"- **Timeouts:** {sum(data.get('timeouts', 0) for data in summary.values())}",
        f"- **Errors:** {sum(data.get('errors', 0) for data in summary.values())}",
        ""
    ])

    # Recommendations
    lines.extend([
        "## Recommendations",
        "",
        generate_recommendations(summary),
        ""
    ])

    # Detailed Results
    lines.extend([
        "## Detailed Results",
        "",
        "### Per-Model Analysis",
        ""
    ])

    # Group by model
    for model in models:
        model_name = model.split(":")[0]
        model_data = summary[model]

        lines.extend([
            f"#### {model_name}",
            "",
            f"- **Average Tokens/sec:** {model_data.get('tokens_per_sec', 0):.2f}",
            f"- **Average Time to First Token:** {model_data.get('time_to_first_token_ms', 0):.2f} ms",
            f"- **Average Total Response Time:** {model_data.get('total_response_time_ms', 0):.2f} ms",
            f"- **Successful Runs:** {model_data.get('successful_runs', 0)}",
            f"- **Timeouts:** {model_data.get('timeouts', 0)}",
            f"- **Errors:** {model_data.get('errors', 0)}",
            ""
        ])

        # Add per-prompt details if available
        model_rows = detailed_df[detailed_df["model_name"] == model]
        if not model_rows.empty:
            lines.append("##### Per-Prompt Results:")
            lines.append("")

            for _, row in model_rows.iterrows():
                status_icon = "✓" if row.get("status") == "success" else "⚠"
                lines.append(f"- **{status_icon}** Prompt: {row.get('prompt', 'N/A')[:80]}...")
                lines.append(f"  - Tokens/sec: {row.get('tokens_per_sec', 0):.2f}")
                lines.append(f"  - Time to First Token: {row.get('time_to_first_token_ms', 0):.2f} ms")
                lines.append(f"  - Total Response Time: {row.get('total_response_time_ms', 0):.2f} ms")
                lines.append(f"  - Status: {row.get('status', 'unknown').upper()}")
                lines.append("")

    lines.append("---")
    lines.append("*Generated by SAT Benchmark Report Generator*")

    # Write report
    with open(output_path, "w") as f:
        f.write("\n".join(lines))


def main() -> None:
    """
    Main entry point for the report generator CLI.

    Usage:
        python -m src.benchmarking.report_generator --input benchmark_results.json --output ollama_benchmark.md

    The default output path is ~/projects/system-reports/ollama_benchmark.md
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate benchmark report from Ollama benchmark results"
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to input JSON file with benchmark results"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="~/projects/system-reports/ollama_benchmark.md",
        help="Path to output Markdown report (default: ~/projects/system-reports/ollama_benchmark.md)"
    )

    args = parser.parse_args()

    # Resolve output path
    output_path = os.path.expanduser(args.output)

    # Check if input file exists
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' does not exist", file=sys.stderr)
        sys.exit(1)

    # Load benchmark data
    try:
        with open(args.input) as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Input file '{args.input}' does not exist", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in input file: {e}", file=sys.stderr)
        sys.exit(1)

    # Analyze results
    try:
        summary, detailed_df = analyze_results(data)
    except Exception as e:
        print(f"Error: Failed to analyze results: {e}", file=sys.stderr)
        sys.exit(1)

    # Generate report
    try:
        generate_report(summary, detailed_df, output_path)
        print(f"Report generated successfully: {output_path}")
    except Exception as e:
        print(f"Error: Failed to generate report: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
