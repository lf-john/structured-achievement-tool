import asyncio
import httpx
import json
import time
import os

MODELS = ["qwen3:8b", "qwen2.5-coder:7b", "deepseek-r1:8b", "nemotron-mini"]
PROMPTS = [
    "Write a python function to calculate the fibonacci sequence.",
    "What are the main benefits of using a containerized application?",
    "Explain the concept of RAG in large language models.",
]
NUM_TIMED_RUNS = 3
TIMEOUT_SECONDS = 120
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OUTPUT_DIR = "output"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "benchmark_results.json")

async def run_benchmark_for_model_prompt(client, model, prompt):
    """Runs warmup and timed benchmarks for a single model-prompt pair."""
    results = {
        "model": model,
        "prompt": prompt,
        "runs": [],
        "avg_tokens_per_second": None,
        "avg_time_to_first_token": None,
        "avg_total_response_time": None,
        "status": "pending"
    }
    
    request_data = {"model": model, "prompt": prompt, "stream": False}

    try:
        # 1. Warm-up run (discarded)
        print(f"Running warm-up for {model} with prompt '{prompt[:20]}...'")
        await client.post(OLLAMA_API_URL, json=request_data, timeout=TIMEOUT_SECONDS)
        print(f"Warm-up for {model} complete.")

        # 2. Timed runs
        total_tokens_per_second = 0
        total_time_to_first_token = 0
        total_response_time = 0
        successful_runs = 0

        for i in range(NUM_TIMED_RUNS):
            print(f"  Running timed run {i+1}/{NUM_TIMED_RUNS} for {model}...")
            start_time = time.time()
            try:
                response = await client.post(OLLAMA_API_URL, json=request_data, timeout=TIMEOUT_SECONDS)
                end_time = time.time()
                
                response.raise_for_status()
                data = response.json()

                eval_count = data.get("eval_count", 0)
                eval_duration = data.get("eval_duration", 1) # Avoid division by zero
                prompt_eval_duration = data.get("prompt_eval_duration", 0)
                
                run_total_time = end_time - start_time
                tokens_per_sec = eval_count / (eval_duration / 1e9) if eval_duration > 0 else 0
                time_to_first = prompt_eval_duration / 1e9

                run_result = {
                    "run": i + 1,
                    "tokens_per_second": tokens_per_sec,
                    "time_to_first_token": time_to_first,
                    "total_response_time": run_total_time,
                    "status": "success"
                }
                results["runs"].append(run_result)
                
                total_tokens_per_second += tokens_per_sec
                total_time_to_first_token += time_to_first
                total_response_time += run_total_time
                successful_runs += 1

            except httpx.TimeoutException:
                print(f"    Timeout for {model} on run {i+1}")
                results["runs"].append({"run": i + 1, "status": "timeout"})
            except httpx.RequestError as e:
                print(f"    Request error for {model} on run {i+1}: {e}")
                results["runs"].append({"run": i + 1, "status": "error", "reason": str(e)})
            except Exception as e:
                print(f"    An unexpected error for {model} on run {i+1}: {e}")
                results["runs"].append({"run": i + 1, "status": "error", "reason": str(e)})

        if successful_runs > 0:
            results["avg_tokens_per_second"] = total_tokens_per_second / successful_runs
            results["avg_time_to_first_token"] = total_time_to_first_token / successful_runs
            results["avg_total_response_time"] = total_response_time / successful_runs
            results["status"] = "completed"
        else:
            results["status"] = "failed_all_runs"

    except httpx.TimeoutException:
        print(f"Timeout during warm-up for {model}")
        results["status"] = "timeout_on_warmup"
    except Exception as e:
        print(f"An unexpected error occurred for {model}: {e}")
        results["status"] = "error"
        results["error_message"] = str(e)
        
    return results

async def main():
    """Main function to orchestrate the benchmarking."""
    all_results = []
    # Create necessary directories
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    async with httpx.AsyncClient() as client:
        for model in MODELS:
            for prompt in PROMPTS:
                result = await run_benchmark_for_model_prompt(client, model, prompt)
                all_results.append(result)
                print("-" * 50)

    # Persist results
    with open(OUTPUT_FILE, "w") as f:
        json.dump(all_results, f, indent=2)
    
    print(f"Benchmarking complete. Results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    # Create src/benchmarking directory if it does not exist
    if not os.path.exists("src/benchmarking"):
        os.makedirs("src/benchmarking")
    asyncio.run(main())
