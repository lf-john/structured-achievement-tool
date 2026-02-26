# LLM Routing System and Setup Guide

## 1. Overview

The LLM Routing System is designed to intelligently select the optimal Large Language Model (LLM) for various tasks based on complexity, cost, and availability. It integrates local Ollama models for cost-effective, simpler tasks and cloud-based Claude models for more complex or agentic workflows, incorporating robust fallback mechanisms and cost tracking.

## 2. Core Components

### 2.1 LLM Router (`src/llm_router.py`)
The `LLMRouter` is the entry point for task classification and initial routing. It categorizes incoming tasks as either 'ollama' or 'claude' based on keywords in the task description and checks Ollama's health before routing.

### 2.2 Routing Engine (`src/llm/routing_engine.py`)
The `RoutingEngine` is responsible for detailed LLM provider selection. It applies a set of rules and preferences to choose the best model (primary and fallback) considering agent complexity, model power, cost tiers, and availability. It also manages rate-limiting and global pause mechanisms to prevent API abuse.

### 2.3 LLM Generation Service (`src/llm/llm_generation_service.py`)
The `LLMGenerationService` handles the execution of LLM calls, specifically for content generation (e.g., emails). It integrates with the cost tracker and implements the primary fallback logic from Claude to a local Ollama model (Qwen3 8B) if Claude is unavailable or exceeds budget.

### 2.4 Embedding Service (`src/core/embedding_service.py`)
The `EmbeddingService` is dedicated to generating text embeddings using local Ollama models, primarily 'nomic-embed-text'. It includes health checks and an auto-recovery mechanism to restart the Ollama service if it becomes unresponsive.

### 2.5 LLM Cost Tracker (`src/llm_cost_tracker.py`)
The `LLMCostTracker` provides functionality to monitor and summarize API calls and estimated costs for both Claude and Ollama usage. It includes methods for daily, weekly, and monthly cost summaries, and a budget check for Claude API calls.

### 2.6 LLM Providers (`src/llm/providers.py`)
This module centralizes the configuration for different LLM providers, defining their names, model IDs, and command-line interfaces (`cli_command`) for execution.

## 3. Task Routing Logic

The system employs a two-tiered routing approach:

1.  **Initial Classification (`LLMRouter`):**
    *   Tasks are classified based on keywords in their description.
    *   **Ollama Tasks (Examples):** "lead scoring", "industry classification", "email subject line", "sentiment analysis", "simple text summarization".
    *   **Claude Tasks (Examples):** "personalized email body generation", "multi-paragraph outreach sequences", "complex analysis", "prospect-facing content".
    *   **Priority:** Claude-matching tasks take precedence. If an Ollama-matching task is identified, the system first checks Ollama's health.
    *   **Default/Ambiguity:** Ambiguous tasks or Ollama-bound tasks where Ollama is unavailable are routed to Claude. If Ollama is unavailable, the router explicitly returns "ollama_unavailable".

2.  **Detailed Provider Selection (`RoutingEngine`):**
    *   After initial classification (or for direct calls), the `RoutingEngine` refines the choice using four rules, considering agent complexity, model power, and cost:
        *   **Rule 1 (Claude Models):** Eligible only if task complexity is greater than or equal to the model's power rating (to avoid overspending).
        *   **Rule 2 (Other Commercial Models):** Eligible if task complexity is greater than or equal to the model's power rating minus 2.
        *   **Rule 3 (Local Models - General):** Preferred if task complexity is less than or equal to 6 AND the model's power is greater than or equal to the complexity.
        *   **Rule 4 (Local Nemotron):** Preferred if the model is "nemotron" and task complexity is less than or equal to 3.
    *   **Minimum Adequate Power:** A model must be sufficiently powerful for the task (power must be within 1 level of complexity).
    *   **Agentic Agents:** Specific agents (e.g., `coder`, `executor`) require models with filesystem access (agentic capabilities); Ollama models are typically text-only and not used for these.
    *   **Prioritization:** Eligible providers are sorted by: 1) not rate-limited, 2) local preference, 3) cheapest cost tier, and 4) highest power.

## 4. Ollama Integration

Ollama is integrated as the primary local LLM provider for cost-effective and simpler tasks, as well as for generating embeddings.

*   **Embedding Generation:** The `EmbeddingService` uses Ollama's `nomic-embed-text` model (2048-token context window) to generate 768-dimensional embeddings. Text is truncated to 7500 characters to fit the context window.
*   **Health Checks & Resilience:** The `EmbeddingService` includes `check_ollama_health()` to verify Ollama's responsiveness. In case of failure, it attempts to restart the Ollama service via `sudo systemctl restart ollama` and retries the operation, raising an `OllamaUnavailableError` if recovery fails.
*   **Direct Execution:** The `qwen:8b` model is run directly via `ollama run qwen:8b` for generation tasks.

## 5. Claude API Integration

Claude models (e.g., `claude-3-opus-20240229`) are integrated for complex tasks, especially those requiring advanced reasoning or multi-paragraph content generation.

*   **Generation Service:** The `LLMGenerationService` prioritizes Claude for email generation.
*   **Cost Management:** Before invoking Claude, the system checks the `LLMCostTracker` to ensure the Claude budget is not exhausted.
*   **CLI Execution:** Claude models are invoked via an `anthropic-cli` command.

## 6. Cost Tracking

The `LLMCostTracker` (placeholder functionality) is designed to provide visibility into LLM expenditures:

*   **API Call Tracking:** Records total API calls for both Claude and Ollama.
*   **Cost Summaries:** Provides daily, weekly, and monthly cost breakdowns.
*   **Budget Management:** The `can_afford_claude` method (currently a placeholder) is intended to enforce budgetary limits for Claude API usage, triggering a fallback if the budget is exceeded.

## 7. Fallback Logic

Robust fallback mechanisms ensure continuous operation even if a preferred LLM is unavailable or too expensive.

*   **Router-Level Fallback:** If Ollama is unhealthy for an Ollama-bound task, the `LLMRouter` routes it to `ollama_unavailable`, which then triggers a fallback to Claude. If a task is ambiguous, it defaults to Claude.
*   **Generation Service Fallback (`LLMGenerationService`):**
    *   **Primary Fallback:** If Claude API calls fail or exceed the budget, the system automatically falls back to a local Ollama model, specifically `qwen:8b`.
    *   **Human Review Flag:** Content generated via fallback is explicitly marked with `[HUMAN REVIEW REQUIRED]` and a flag is set, indicating that human oversight is necessary.
    *   **Notifications:** A high-priority `ntfy.sh` notification is sent upon a fallback event, detailing the reason.
*   **Routing Engine Fallback (`select_with_fallback`):** The `RoutingEngine` selects both a primary and a specific fallback provider based on task complexity (reasoning, code, classification) and `routing_preferences` configured in `config.json`.

## 8. Batch Processing Pipeline (Design)

Based on the `US-011_DESIGN.md`, a batch lead scoring pipeline is designed to process leads efficiently and resumably. This pipeline leverages the LLM routing system for scoring.

*   **Components:**
    *   **Scoring Script (`src/batch_lead_scorer.py` - design):** A standalone Python script for fetching, scoring, and updating leads.
    *   **State File (`.memory/batch_lead_scorer_state.json`):** Stores `last_processed_id` for resumability.
    *   **LLM Scorer:** Utilizes existing components like `src/industry_classifier.py` and, by extension, the LLM routing system for the core scoring logic.
*   **Execution Flow:** Designed for manual or scheduled execution, potentially as a background job using `nohup`.
*   **Detailed Logic:**
    *   **Initialization:** Reads `last_processed_id` from the state file; starts from the first contact if missing.
    *   **Batching:** Fetches contacts from Mautic API in batches (e.g., 100), filtering by `id > last_processed_id`.
    *   **Scoring & Updating:** Invokes the scoring logic (via LLM routing) for each contact and updates Mautic.
    *   **State Management:** Updates `last_processed_id` in the state file after *each* successfully processed contact for fine-grained resumability.
    *   **Progress Tracking:** Logs percentage complete and Estimated Time Remaining (ETR) after each batch.
*   **Error Handling:** Implements retry mechanisms with exponential backoff for Mautic API failures and skips individual contact scoring failures to prevent job halts.

## 9. Claude API Key Configuration

The Claude API key is crucial for accessing Claude models.

*   **Mechanism:** The `anthropic-cli` command is used to interact with the Claude API. It is expected that the `ANTHROPIC_API_KEY` environment variable is set in the environment where `anthropic-cli` is executed.
*   **Setup:**
    1.  Obtain your Claude API key from Anthropic.
    2.  Set it as an environment variable in your shell profile (e.g., `~/.bashrc`, `~/.zshrc`) or directly before running commands:
        ```bash
        export ANTHROPIC_API_KEY="your_claude_api_key_here"
        ```
    3.  For services (e.g., `systemd` units), ensure this environment variable is correctly passed to the service's execution environment.

## 10. Setup Guide

### 10.1 Ollama Installation and Model Setup

1.  **Install Ollama:** Follow the official Ollama installation instructions for your operating system.
    ```bash
    curl -fsSL https://ollama.com/install.sh | sh
    ```
2.  **Download Models:** Download the required Ollama models.
    *   For embeddings: `nomic-embed-text`
        ```bash
        ollama run nomic-embed-text
        ```
    *   For generation/fallback: `qwen:8b` (or `qwen3:8b` if available)
        ```bash
        ollama run qwen:8b
        ```
3.  **Verify Ollama Service:** Ensure the Ollama service is running.
    ```bash
    systemctl --user status ollama.service
    ```
    If not running, start it:
    ```bash
    systemctl --user start ollama.service
    ```

### 10.2 Claude API Key Configuration

1.  **Obtain API Key:** Get your `ANTHROPIC_API_KEY` from Anthropic.
2.  **Set Environment Variable:** Add the API key to your environment. For shell sessions:
    ```bash
    export ANTHROPIC_API_KEY="YOUR_CLAUDE_API_KEY"
    ```
    For systemd services, you'll need to configure this in the service unit file (e.g., `Environment="ANTHROPIC_API_KEY=..."`).

### 10.3 Project Configuration

Ensure `config.json` (if present and used by `RoutingEngine`) is correctly configured, especially for `phase_models` overrides and `routing_preferences` for fallback.
```json
{
  "phase_models": {
    "DESIGN": "opus",
    "CODER": "qwen2_coder"
  },
  "routing_preferences": {
    "reasoning_backup": "deepseek_r1",
    "code_backup": "qwen25_coder",
    "classification_backup": "nemotron"
  },
  "default_primary": "sonnet",
  "default_backup": "deepseek_r1"
}
```
