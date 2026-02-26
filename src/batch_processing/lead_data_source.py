import abc
from typing import List, Dict, Optional, Tuple

class LeadDataSource(abc.ABC):
    """Abstract base class for fetching leads in batches."""

    @abc.abstractmethod
    def fetch_leads_batch(self, last_id: Optional[int], batch_size: int) -> Tuple[List[Dict], Optional[int]]:
        """
        Fetches a batch of leads starting from a given ID.

        Args:
            last_id: The ID of the last processed lead, or None to start from the beginning.
            batch_size: The maximum number of leads to fetch in this batch.

        Returns:
            A tuple containing:
                - A list of lead dictionaries.
                - The ID of the last lead in the current batch, or None if no leads were fetched.
        """
        pass

    @abc.abstractmethod
    def get_total_leads(self) -> int:
        """
        Returns the total number of leads available for processing.
        """
        pass
