import time
from typing import Any

from src.batch_processing.lead_data_source import LeadDataSource
from src.batch_processing.lead_scorer import LeadScorer
from src.batch_processing.progress_tracker import ProgressTracker


class LeadScoringBatchProcessor:
    """
    Orchestrates the batch processing pipeline for lead scoring.
    Handles fetching leads, scoring them, tracking progress, and resuming from interruptions.
    """

    def __init__(
        self,
        data_source: LeadDataSource,
        scorer: LeadScorer,
        progress_tracker: ProgressTracker,
        batch_size: int
    ):
        self.data_source = data_source
        self.scorer = scorer
        self.progress_tracker = progress_tracker
        self.batch_size = batch_size
        self.total_leads = 0
        self.start_time = None

    def run(self) -> None:
        """
        Executes the lead scoring batch processing pipeline.
        """
        self.start_time = time.time() # Initialize start time
        initial_progress = self.progress_tracker.get_progress()
        last_processed_id = initial_progress.get("last_processed_id")
        self.total_leads = self.data_source.get_total_leads()

        processed_count = self._calculate_processed_count(last_processed_id)

        while True:
            leads_batch, current_last_id = self.data_source.fetch_leads_batch(last_id=last_processed_id, batch_size=self.batch_size)

            if not leads_batch:
                # If total_leads was 0 from the start, we still called fetch_leads_batch once.
                # If total_leads was > 0, but no more batches, then we are done.
                break

            self.scorer.score_leads(leads_batch)

            if current_last_id is not None:
                last_processed_id = current_last_id
                processed_count += len(leads_batch)

            self._update_and_persist_progress(last_processed_id, processed_count)

    def _calculate_processed_count(self, last_processed_id: Any) -> int:
        """
        Calculates the number of leads processed so far based on the last_processed_id.
        This is a simplification; in a real system, you might query the data source
        to count leads with an ID less than or equal to last_processed_id.
        For this implementation, we assume IDs are sequential and start from 1.
        """
        if last_processed_id is None:
            return 0
        # This assumes last_processed_id directly correlates to the count of processed leads.
        # E.g., if last_processed_id is 100, then 100 leads have been processed.
        return last_processed_id

    def _update_and_persist_progress(self, last_processed_id: int, processed_count: int) -> None:
        """
        Calculates and updates the progress, then persists it using the ProgressTracker.
        """
        if self.total_leads == 0:
            percentage_complete = 0.0
        else:
            percentage_complete = (processed_count / self.total_leads) * 100

        elapsed_time = time.time() - self.start_time
        if processed_count > 0:
            # Estimate total time based on current progress and elapsed time
            estimated_total_time = (elapsed_time / processed_count) * self.total_leads
            estimated_time_remaining_seconds = estimated_total_time - elapsed_time
            estimated_time_remaining = self._format_time_remaining(estimated_time_remaining_seconds)
        else:
            estimated_time_remaining = "N/A"

        self.progress_tracker.update_progress(
            last_processed_id=last_processed_id,
            percentage_complete=percentage_complete,
            total_leads=self.total_leads,
            estimated_time_remaining=estimated_time_remaining
        )

    def _format_time_remaining(self, seconds: float) -> str:
        """
        Formats the estimated time remaining into a human-readable string.
        """
        if seconds < 0:
            return "0s"
        minutes, seconds = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
