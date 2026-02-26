{
  "systemAnalysis": {
    "filesToChange": [
      "src/db/llm_cost_db.py",
      "src/web/app.py",
      "src/monitoring/gpu_monitor.py"
    ],
    "systemImpact": "The change adds a new, non-critical reporting page to the existing web dashboard. It will have a negligible impact on the performance of the core SAT system. The new GPU monitoring utility will run a lightweight local command.",
    "externalDependencies": [
      "nvidia-smi command-line tool must be installed and in the system's PATH for GPU utilization to be reported."
    ]
  },
  "executionSteps": [
    {
      "step": 1,
      "description": "Create a new GPU monitoring utility to collect NVIDIA GPU utilization.",
      "commands": [],
      "files": [
        {
          "path": "src/monitoring/gpu_monitor.py",
          "change": "Create a new file with a function `get_gpu_utilization` that executes `nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits` using `subprocess` and returns the utilization percentage. It should handle errors gracefully if `nvidia-smi` is not found."
        }
      ]
    },
    {
      "step": 2,
      "description": "Extend the LLM cost database class with methods to aggregate cost and usage data.",
      "commands": [],
      "files": [
        {
          "path": "src/db/llm_cost_db.py",
          "change": "Add a new method `get_cost_summary()` to the `LLMCostDB` class. This method will execute SQL queries to return a dictionary containing: total calls and costs per model for the last day, last 7 days, and last 30 days."
        }
      ]
    },
    {
      "step": 3,
      "description": "Add a new API endpoint to the web dashboard to serve the cost data.",
      "commands": [],
      "files": [
        {
          "path": "src/web/app.py",
          "change": "Import `LLMCostDB` and `get_gpu_utilization`. Add a new FastAPI route `@app.get("/api/costs")` that calls the new `get_cost_summary()` method and the `get_gpu_utilization()` function, then returns the combined data as a JSON response."
        }
      ]
    },
    {
      "step": 4,
      "description": "Add a new page to the dashboard to visualize the cost report.",
      "commands": [],
      "files": [
        {
          "path": "src/web/app.py",
          "change": "Create a new Jinja2 template string named `COSTS_TEMPLATE`. Add a new route `@app.get("/costs", response_class=HTMLResponse)` that renders this template. The page should fetch data from the `/api/costs` endpoint using JavaScript and display it in tables and cards. Add a link to '/costs' in the main navigation bar."
        }
      ]
    }
  ],
  "verificationScript": "verify_script.sh created and executable",
  "rollbackPlan": [
    "git checkout -- src/db/llm_cost_db.py src/web/app.py",
    "rm -f src/monitoring/gpu_monitor.py"
  ]
}
