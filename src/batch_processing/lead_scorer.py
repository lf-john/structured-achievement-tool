import abc


class LeadScorer(abc.ABC):
    """Abstract base class for scoring leads."""

    @abc.abstractmethod
    def score_leads(self, leads: list[dict]) -> None:
        """
        Applies scoring logic to a list of leads. Modifies leads in place or persists scores.

        Args:
            leads: A list of lead dictionaries to be scored.
        """
        pass
