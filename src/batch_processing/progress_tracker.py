import abc
from typing import Dict, Any, Optional

class ProgressTracker(abc.ABC):
    """Abstract base class for tracking and persisting batch processing progress."""

    @abc.abstractmethod
    def get_progress(self) -> Dict[str, Any]:
        """
        Retrieves the last saved progress state.

        Returns:
            A dictionary containing progress information, e.g., {"last_processed_id": ..., "total_leads": ..., "percentage_complete": ..., "estimated_time_remaining": ...}
        """
        pass

    @abc.abstractmethod
    def update_progress(self, last_processed_id: Optional[int], percentage_complete: float, total_leads: int, estimated_time_remaining: str) -> None:
        """
        Updates and persists the current progress state.

        Args:
            last_processed_id: The ID of the last lead successfully processed.
            percentage_complete: The completion percentage (0.0 to 100.0).
            total_leads: The total number of leads to process.
            estimated_time_remaining: A string representing the estimated time left.
        """
        pass
