
import json
import sys
from pathlib import Path

# Add src to path to allow for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

try:
    from agents.llm_router import LLMTRouter
except ImportError as e:
    print(f"Error: Failed to import LLMTRouter. Make sure src/agents/llm_router.py exists. Details: {e}", file=sys.stderr)
    sys.exit(1)

# Test cases based on the story description
TEST_CASES = {
    "ollama": [
        "Score this lead based on company size",
        "Classify the industry for this company: 'Tech'",
        "Estimate the company size for 'Acme Corp'",
        "Choose the best email subject line variant",
        "Analyze the sentiment of this customer feedback",
        "Deduplicate these contact records",
        "Provide a simple text summarization of this article"
    ],
    "claude": [
        "Generate a personalized email body for a follow-up",
        "Write a multi-paragraph outreach sequence for a new product launch",
        "Perform a complex analysis of market trends",
        "Create prospect-facing content about our new feature"
    ]
}

def run_verification():
    print("--- Running LLM Router Verification ---")
    
    # Check if config and router files exist
    config_path = Path("config.json")
    router_path = Path("src/agents/llm_router.py")

    if not config_path.is_file():
        print(f"Error: config.json not found at {config_path.resolve()}", file=sys.stderr)
        return False
        
    if not router_path.is_file():
        print(f"Error: llm_router.py not found at {router_path.resolve()}", file=sys.stderr)
        return False

    try:
        router = LLMTRouter(config_path=str(config_path))
    except Exception as e:
        print(f"Error: Failed to instantiate LLMTRouter. Details: {e}", file=sys.stderr)
        return False

    all_passed = True
    
    for expected_provider, tasks in TEST_CASES.items():
        for task in tasks:
            try:
                routed_provider = router.route_task(task)
                if routed_provider == expected_provider:
                    print(f"[PASS] Task: '{task[:40]}...' -> Routed to {routed_provider}")
                else:
                    print(f"[FAIL] Task: '{task[:40]}...' -> Expected {expected_provider}, Got {routed_provider}", file=sys.stderr)
                    all_passed = False
            except Exception as e:
                print(f"[FAIL] Task: '{task[:40]}...' -> An exception occurred: {e}", file=sys.stderr)
                all_passed = False

    print("--- Verification Complete ---")
    return all_passed

if __name__ == "__main__":
    if run_verification():
        print("Verification successful: All tasks routed correctly.")
        sys.exit(0)
    else:
        print("Verification failed: One or more tasks were routed incorrectly.", file=sys.stderr)
        sys.exit(1)
