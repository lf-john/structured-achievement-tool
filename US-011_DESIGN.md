### US-011: Batch Lead Scoring Pipeline Design

#### 1. Overview

This document outlines the design for a batch processing pipeline to score an initial set of 30,000 leads from Mautic. The primary goals are to ensure the process is efficient, robust, and resumable.

#### 2. Components

-   **Scoring Script (`src/batch_lead_scorer.py`):** A new standalone Python script that will contain the core logic for fetching, scoring, and updating leads. It will be designed to be invoked from the command line.
-   **State File (`.memory/batch_lead_scorer_state.json`):** A JSON file to store the state of the batch job, enabling resumability. This file will store the ID of the last successfully processed contact.
-   **LLM Scorer:** The script will leverage existing components like `src/industry_classifier.py` for the core lead scoring logic, ensuring consistency with real-time scoring.

#### 3. Execution Flow & Background Processing

The script is designed for manual or scheduled execution. It can be run as a background job using standard Unix utilities.

**Direct Execution:**
```bash
python src/batch_lead_scorer.py
```

**Background Execution with `nohup`:**
```bash
nohup python src/batch_lead_scorer.py > .logs/lead_scorer.log 2>&1 &
```
This ensures the process continues running even if the terminal session is closed and logs all output for later review.

#### 4. Detailed Logic

1.  **Initialization:**
    *   On startup, the script will read the state from `.memory/batch_lead_scorer_state.json`.
    *   The state file contains `last_processed_id`. If the file or property is missing, the script assumes a fresh start and begins processing from the first contact.

2.  **Batching:**
    *   The script will fetch contacts from the Mautic API in batches (e.g., size of 100).
    *   To retrieve the correct segment of leads, it will use Mautic's API filtering to fetch contacts with an ID greater than `last_processed_id`, ordered by ID ascendingly.
    *   *Example Mautic API filter:* `GET /api/contacts?limit=100&orderBy=id&orderByDir=ASC&where[0][col]=id&where[0][expr]=gt&where[0][val]={last_processed_id}`

3.  **Scoring & Updating:**
    *   For each contact in the retrieved batch, the script will invoke the scoring logic.
    *   After scoring, the new score will be persisted back to Mautic via an API update call for that contact.

4.  **State Management & Resumability:**
    *   After every single contact is successfully scored and updated in Mautic, the script will update the `last_processed_id` in the `.memory/batch_lead_scorer_state.json` file.
    *   Updating the state file after each contact (instead of after the whole batch) provides finer-grained resumability and minimizes reprocessing in case of failure.

5.  **Progress Tracking:**
    *   At the beginning of the job, the script will make an API call to Mautic to get the total count of contacts to be scored.
    *   After each batch is processed, a progress update will be logged to stdout and the log file. The update will include:
        *   Percentage complete: `(processed_count / total_count) * 100`
        *   Estimated Time Remaining (ETR): Calculated based on the average processing time per batch.
        *   *Example Log:* `[INFO] Batch 15/300 complete. 5.0% done. ETR: 2 hours 30 minutes.`

#### 5. Error Handling

-   **API Failures:** If a Mautic API call fails, the script will implement a retry mechanism with exponential backoff. If it continues to fail after several retries, the script will log the error and exit, preserving the last state.
-   **Scoring Failures:** If an individual contact fails during the scoring process, the error will be logged, the contact will be skipped, and the script will proceed to the next contact to avoid halting the entire job.
