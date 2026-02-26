{
  "systemAnalysis": {
    "filesToChange": [
      "config.json",
      "src/orchestrator_v2.py",
      "src/agents/llm_router.py",
      "tests/test_llm_router.py",
      "docs/LLM_ROUTING_LOGIC.md"
    ],
    "systemImpact": "This change will alter the core task processing logic by introducing a routing layer that determines which LLM (Ollama or Claude) to use. A failure in the router could prevent tasks from being processed. It also introduces a new external dependency on the Claude API, requiring API key management.",
    "externalDependencies": [
      "Claude API (new)",
      "Ollama (existing)"
    ]
  },
  "executionSteps": [
    {
      "step": 1,
      "description": "Update the main configuration file to include the Claude API key and define the keywords for routing decisions. This centralizes the configuration for easy management.",
      "commands": [],
      "files": [
        {
          "path": "config.json",
          "change": "Add 'claude_api_key' and 'llm_routing_rules' to the JSON structure. The rules will contain keywords that map to either 'ollama' or 'claude'."
        }
      ]
    },
    {
      "step": 2,
      "description": "Create the new LLM routing agent. This module will contain the core logic for classifying tasks based on the rules defined in config.json.",
      "commands": [],
      "files": [
        {
          "path": "src/agents/llm_router.py",
          "change": "Create a new file and implement the `LLMTRouter` class. It will load `config.json`, and have a method `route_task(task_description)` that returns either 'ollama' or 'claude'."
        }
      ]
    },
    {
      "step": 3,
      "description": "Add unit tests for the new router to ensure its logic is correct and robust. Tests will cover all routing criteria.",
      "commands": [],
      "files": [
        {
          "path": "tests/test_llm_router.py",
          "change": "Create a new test file with pytest unit tests for the `LLMTRouter` class. Mock the configuration and test various task descriptions to assert the correct provider is returned."
        }
      ]
    },
    {
      "step": 4,
      "description": "Integrate the new router into the main orchestrator, so that incoming tasks are first classified before being sent to an LLM.",
      "commands": [],
      "files": [
        {
          "path": "src/orchestrator_v2.py",
          "change": "Import and instantiate the `LLMTRouter`. Modify the task processing logic to call the router and use its output to determine which LLM service to invoke."
        }
      ]
    },
    {
      "step": 5,
      "description": "Create documentation for the routing logic as required by the acceptance criteria.",
      "commands": [],
      "files": [
        {
          "path": "docs/LLM_ROUTING_LOGIC.md",
          "change": "Create a new markdown file documenting the decision criteria for routing tasks to Ollama vs. Claude, explaining the keywords and task types for each."
        }
      ]
    },
    {
      "step": 6,
      "description": "Create the Python script that will be used by the main verification shell script to test the routing logic end-to-end from a user's perspective.",
      "commands": [],
      "files": [
        {
          "path": ".tmp_sdt/verify_router_logic.py",
          "change": "Create a new Python script that imports `LLMTRouter`, runs a series of predefined test cases against it, and exits with code 0 on success or 1 on failure."
        }
      ]
    },
    {
      "step": 7,
      "description": "Create the final verification shell script. This script will set up the environment and execute the Python verification script to confirm the feature is working correctly.",
      "commands": ["chmod +x verify_script.sh"],
      "files": [
        {
          "path": "verify_script.sh",
          "change": "Create a new bash script that activates the Python virtual environment, runs the `.tmp_sdt/verify_router_logic.py` script, and checks its exit code."
        }
      ]
    }
  ],
  "verificationScript": "verify_script.sh created and executable",
  "rollbackPlan": [
    "git checkout -- config.json src/orchestrator_v2.py",
    "rm src/agents/llm_router.py tests/test_llm_router.py docs/LLM_ROUTING_LOGIC.md .tmp_sdt/verify_router_logic.py verify_script.sh"
  ]
}
