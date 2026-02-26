# LLM Routing System and Setup Guide

## 1. Introduction

The LLM Routing System is designed to intelligently select the optimal Large Language Model (LLM) for various tasks, balancing task complexity, cost-efficiency, and model capabilities. It integrates both local (Ollama) and cloud-based (Claude) LLMs, incorporating advanced routing logic, cost tracking, and fallback mechanisms to ensure robust and efficient operation. Additionally, it integrates with a batch processing pipeline for tasks like lead scoring.

## 2. Core Components

### 2.1. Task Routing (`src/llm_router.py`)

The `LLMRouter` provides a high-level classification of incoming tasks, routing them to either Ollama or Claude based on keyword matching in the task description.

*   **Ollama Tasks**: Identified by keywords such as "lead scoring," "industry classification," "email subject line generation," "sentiment analysis," and "simple text summarization."
*   **Claude Tasks**: Identified by keywords related to "personalized email body generation," "multi-paragraph outreach sequences," "complex analysis," and "prospect-facing content."
*   **Ollama Health Check**: Before routing to Ollama, a health check is performed. If Ollama is unavailable, the task is routed to an `ollama_unavailable` state, triggering fallback procedures.
*   **Default Routing**: Ambiguous tasks, or those not explicitly matching Ollama keywords, are defaulted to Claude, assuming higher complexity.

### 2.2. LLM Selection Engine (`src/llm/routing_engine.py`)

The `RoutingEngine` provides a sophisticated mechanism for selecting the best LLM provider based on several factors:

*   **Agent Complexity**: Each agent is assigned a complexity rating (from 1 to 10), influencing model selection.
*   **Model Power Ratings**: LLMs are rated by their power and code generation capabilities.
*   **Preference Hierarchy**: Prioritizes local models, then cheaper cloud models, then more expensive cloud models.
*   **Configuration Overrides**: Allows specific LLM models to be hardcoded for particular phases via `config.json`.
*   **Rate Limiting**: Tracks rate-limited providers and introduces cooldown periods. A "rate limit cascade" (multiple providers rate-limited within a window) triggers a global pause for all LLM calls to prevent service disruption.
*   **Agentic Capabilities**: Distinguishes between "agentic" LLMs (with filesystem read/write access) required for certain tasks (e.g., `coder`, `planner`) and text-only models (like Ollama).
*   **Power Adequacy**: Ensures selected models meet a minimum power threshold relative to the task's complexity.

### 2.3. Ollama Integration (`src/llm/ollama_client.py`)

The `OllamaClient` handles interactions with the local Ollama instance, primarily for generating responses using specified models (e.g., `qwen3:8b`). Its health is checked by the `LLMRouter` to determine availability.

### 2.4. Claude API Integration and Fallback (`src/llm/llm_generation_service.py`)

The `LLMGenerationService` orchestrates LLM content generation, with a focus on Claude integration and robust fallback.

*   **Claude Primary**: Attempts to generate content (e.g., emails) using a Claude model (defaulting to `opus`).
*   **Cost Check**: Before invoking Claude, it checks the available budget via `LLMCostTracker` to ensure affordability.
*   **Fallback to Ollama (Qwen3 8B)**: If Claude's budget is exhausted, the Claude API fails, or any unexpected error occurs, the system automatically falls back to a local Ollama model (e.g., `qwen3:8b`).
*   **Human Review Flag**: Content generated via fallback is automatically flagged with `[HUMAN REVIEW REQUIRED]`, indicating it might need manual inspection.
*   **Notifications**: Triggers ntfy.sh notifications upon fallback events, informing administrators of the change in LLM usage.

### 2.5. Cost Tracking and Budget Management

*   **`LLMCostTracker` (`src/llm_cost_tracker.py`)**: (Currently a mock) This component is designed to track API calls and associated costs for various LLM providers (Claude, Ollama). It provides summaries for daily, weekly, and monthly costs, and can calculate cost per lead.
*   **`LLMBudgetConfig` (`src/llm_budget_config.py`)**: Loads budget configurations from `config.json`, including daily/monthly budgets and warning thresholds. It also manages model pricing information.

## 3. Routing Logic in Detail

The routing process combines initial task classification with a more granular selection based on agent requirements and model characteristics.

1.  **Initial Classification (`LLMRouter`)**: A quick keyword-based assessment determines if a task is generally suited for Ollama (simpler, cheaper tasks) or Claude (complex, creative tasks).
2.  **Detailed Selection (`RoutingEngine`)**: If a task is not definitively routed by `LLMRouter` or requires advanced consideration (e.g., agentic capabilities), the `RoutingEngine` takes over. It applies a series of rules:
    *   **Config Overrides**: Direct model assignments for specific phases or agents take precedence.
    *   **Complexity Thresholds**: Tasks with very low complexity might bypass LLMs entirely or be routed to basic models.
    *   **Agentic Requirements**: Tasks requiring filesystem access (e.g., `coder` agent) are exclusively routed to agentic LLMs (e.g., Claude models).
    *   **Power Adequacy**: Models must possess sufficient power to handle the task's complexity.
    *   **Provider-Specific Rules**:
        *   **Claude**: Used when task complexity is equal to or greater than the model's power, to avoid overspending on simple tasks.
        *   **Local (Ollama)**: Preferred for tasks with complexity up to 6, provided the model has adequate power. `nemotron` is a specific fallback for very low complexity tasks (<=3).
        *   **Other Commercial Models**: Eligible when task complexity is within a certain range of the model's power.
    *   **Fallback Providers**: The `select_with_fallback` method identifies a primary and a secondary (fallback) provider based on task type (reasoning, code, classification) and configured preferences.

## 4. Batch Processing Pipeline Integration

The LLM Routing System can be integrated with batch processing workflows, such as lead scoring, which leverages Ollama for efficient, high-volume tasks.

*   **`LeadDataSource`**: An abstract interface for fetching leads in manageable batches from various sources.
*   **`LeadScorer`**: An abstract interface for applying scoring logic to leads, potentially using Ollama for analysis.
*   **`LeadScoringBatchProcessor`**: Orchestrates the entire batch scoring process, including fetching, scoring, and tracking progress, with mechanisms for resuming interrupted jobs.

## 5. Setup Guide: Claude API Key Configuration

To enable Claude API integration, you must configure your Claude API key.

**Environment Variable Configuration (Recommended):**

The most secure and recommended method is to set your Claude API key as an environment variable. This prevents hardcoding sensitive information directly into the codebase.

1.  **Obtain API Key**: Acquire your Claude API key from Anthropic.
2.  **Set Environment Variable**:
    On Linux/macOS:
    ```bash
    export ANTHROPIC_API_KEY="your_claude_api_key_here"
    ```
    On Windows (Command Prompt):
    ```cmd
    set ANTHROPIC_API_KEY="your_claude_api_key_here"
    ```
    On Windows (PowerShell):
    ```powershell
    $env:ANTHROPIC_API_KEY="your_claude_api_key_here"
    ```
    Replace `"your_claude_api_key_here"` with your actual API key. For persistent configuration across sessions, add this line to your shell's profile file (e.g., `~/.bashrc`, `~/.zshrc`, `~/.profile`, or system-wide environment configuration).

**(Note: This document assumes the use of an `ANTHROPIC_API_KEY` environment variable for Claude API access, potentially read by an underlying CLI tool like `anthropic-cli` or a Python library. Actual implementation details might vary based on the specific library or CLI wrapper used in `src/llm/cli_runner.py`.)**
