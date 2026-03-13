"""
IMPLEMENTATION PLAN for US-011:

Components:
  - LeadScoringBatchProcessor: Orchestrates the batch processing, manages state, and interacts with data source and scorer.
  - LeadDataSource: An abstract interface (or mock for tests) to fetch leads in batches and track the last processed ID.
  - LeadScorer: An abstract interface (or mock for tests) for the actual lead scoring logic.
  - ProgressTracker: A utility to persist and retrieve the state of the batch processing (last processed ID, completion percentage, estimated time).

Data Flow:
  1. Initialize LeadScoringBatchProcessor with LeadDataSource, LeadScorer, and ProgressTracker.
  2. Processor retrieves last_processed_id from ProgressTracker.
  3. Processor fetches a batch of leads from LeadDataSource, starting from last_processed_id.
  4. Processor sends the batch to LeadScorer for scoring.
  5. Processor updates ProgressTracker with the new last_processed_id and calculated progress.
  6. Repeat until LeadDataSource indicates no more leads.

Integration Points:
  - Interacts with a data layer (mocked by LeadDataSource).
  - Uses a scoring service (mocked by LeadScorer).
  - Persists state using ProgressTracker (mocked for tests, could be a file or database in real implementation).

Edge Cases:
  - Empty lead list from data source.
  - Number of leads less than batch size.
  - Interruption/resumption at various stages of processing.
  - Errors during lead scoring of a batch.
"""

from unittest.mock import ANY, MagicMock, call

import pytest

from src.batch_processing.lead_data_source import LeadDataSource
from src.batch_processing.lead_scorer import LeadScorer
from src.batch_processing.lead_scoring_batch_processor import LeadScoringBatchProcessor
from src.batch_processing.progress_tracker import ProgressTracker


class TestLeadScoringBatchProcessor:
    @pytest.fixture
    def mock_data_source(self):
        """Mocks the LeadDataSource to control lead fetching behavior."""
        mock = MagicMock(spec=LeadDataSource)
        mock.fetch_leads_batch.return_value = ([], None)  # Default to no leads
        mock.get_total_leads.return_value = 0  # Default to no leads
        return mock

    @pytest.fixture
    def mock_scorer(self):
        """Mocks the LeadScorer to simulate lead scoring."""
        mock = MagicMock(spec=LeadScorer)
        mock.score_leads.return_value = None  # Scoring doesn't necessarily return a value in this design
        return mock

    @pytest.fixture
    def mock_progress_tracker(self):
        """Mocks the ProgressTracker to control and verify progress state."""
        mock = MagicMock(spec=ProgressTracker)
        mock.get_progress.return_value = {
            "last_processed_id": None,
            "total_leads": 0,
            "percentage_complete": 0.0,
            "estimated_time_remaining": "N/A",
        }
        return mock

    def test_should_process_leads_in_batches_when_multiple_batches_exist(
        self, mock_data_source, mock_scorer, mock_progress_tracker
    ):
        """
        Verify that the processor correctly fetches and processes leads in defined batches.
        Corresponds to AC: 'Design includes batching'
        """
        total_leads = 300
        batch_size = 100
        mock_data_source.get_total_leads.return_value = total_leads

        # Simulate fetching leads in batches
        mock_data_source.fetch_leads_batch.side_effect = [
            ([{"id": i} for i in range(1, 101)], 100),  # First batch: returns leads and last_id of the batch
            ([{"id": i} for i in range(101, 201)], 200),  # Second batch
            ([{"id": i} for i in range(201, 301)], 300),  # Third batch
            ([], None),  # No more leads
        ]

        processor = LeadScoringBatchProcessor(
            data_source=mock_data_source,
            scorer=mock_scorer,
            progress_tracker=mock_progress_tracker,
            batch_size=batch_size,
        )

        processor.run()

        # Check data source calls
        assert mock_data_source.fetch_leads_batch.call_count == 4
        mock_data_source.fetch_leads_batch.assert_has_calls(
            [
                call(last_id=None, batch_size=batch_size),
                call(last_id=100, batch_size=batch_size),
                call(last_id=200, batch_size=batch_size),
                call(last_id=300, batch_size=batch_size),
            ]
        )

        # Check scorer calls
        assert mock_scorer.score_leads.call_count == 3
        mock_scorer.score_leads.assert_has_calls(
            [
                call([{"id": i} for i in range(1, 101)]),
                call([{"id": i} for i in range(101, 201)]),
                call([{"id": i} for i in range(201, 301)]),
            ]
        )

        # Check progress tracker updates
        assert mock_progress_tracker.update_progress.call_count == 3
        mock_progress_tracker.update_progress.assert_has_calls(
            [
                call(
                    last_processed_id=100,
                    percentage_complete=(100 / total_leads) * 100,
                    total_leads=total_leads,
                    estimated_time_remaining=ANY,
                ),
                call(
                    last_processed_id=200,
                    percentage_complete=(200 / total_leads) * 100,
                    total_leads=total_leads,
                    estimated_time_remaining=ANY,
                ),
                call(
                    last_processed_id=300,
                    percentage_complete=(300 / total_leads) * 100,
                    total_leads=total_leads,
                    estimated_time_remaining=ANY,
                ),
            ]
        )

    def test_should_resume_processing_from_last_processed_id_when_interrupted(
        self, mock_data_source, mock_scorer, mock_progress_tracker
    ):
        """
        Verify that the pipeline can resume from where it left off after an interruption.
        Corresponds to AC: 'Design includes resumability'
        """
        total_leads = 300
        batch_size = 100
        mock_data_source.get_total_leads.return_value = total_leads

        # Simulate interruption after first batch
        mock_progress_tracker.get_progress.return_value = {
            "last_processed_id": 100,
            "percentage_complete": (100 / total_leads) * 100,
            "total_leads": total_leads,
            "estimated_time_remaining": "unknown",
        }

        # First run, should fetch from ID 101, so the first call to fetch_leads_batch will have last_id=100
        mock_data_source.fetch_leads_batch.side_effect = [
            ([{"id": i} for i in range(101, 201)], 200),  # Second batch
            ([{"id": i} for i in range(201, 301)], 300),  # Third batch
            ([], None),  # No more leads
        ]

        processor = LeadScoringBatchProcessor(
            data_source=mock_data_source,
            scorer=mock_scorer,
            progress_tracker=mock_progress_tracker,
            batch_size=batch_size,
        )

        processor.run()

        # Should start fetching from the ID after the last processed one
        assert mock_data_source.fetch_leads_batch.call_count == 3
        mock_data_source.fetch_leads_batch.assert_has_calls(
            [
                call(last_id=100, batch_size=batch_size),
                call(last_id=200, batch_size=batch_size),
                call(last_id=300, batch_size=batch_size),
            ]
        )

        assert mock_scorer.score_leads.call_count == 2  # Only the remaining two batches scored
        mock_scorer.score_leads.assert_has_calls(
            [
                call([{"id": i} for i in range(101, 201)]),
                call([{"id": i} for i in range(201, 301)]),
            ]
        )
        assert mock_progress_tracker.update_progress.call_count == 2
        mock_progress_tracker.update_progress.assert_has_calls(
            [
                call(
                    last_processed_id=200,
                    percentage_complete=(200 / total_leads) * 100,
                    total_leads=total_leads,
                    estimated_time_remaining=ANY,
                ),
                call(
                    last_processed_id=300,
                    percentage_complete=(300 / total_leads) * 100,
                    total_leads=total_leads,
                    estimated_time_remaining=ANY,
                ),
            ]
        )

    def test_should_track_progress_correctly_during_execution(
        self, mock_data_source, mock_scorer, mock_progress_tracker
    ):
        """
        Verify that progress tracking updates correctly after each batch.
        Corresponds to AC: 'Design includes progress tracking'
        """
        total_leads = 200
        batch_size = 100
        mock_data_source.get_total_leads.return_value = total_leads

        mock_data_source.fetch_leads_batch.side_effect = [
            ([{"id": i} for i in range(1, 101)], 100),
            ([{"id": i} for i in range(101, 201)], 200),
            ([], None),
        ]

        processor = LeadScoringBatchProcessor(
            data_source=mock_data_source,
            scorer=mock_scorer,
            progress_tracker=mock_progress_tracker,
            batch_size=batch_size,
        )

        processor.run()

        assert mock_progress_tracker.update_progress.call_count == 2
        mock_progress_tracker.update_progress.assert_has_calls(
            [
                call(
                    last_processed_id=100,
                    percentage_complete=50.0,
                    total_leads=total_leads,
                    estimated_time_remaining=ANY,
                ),
                call(
                    last_processed_id=200,
                    percentage_complete=100.0,
                    total_leads=total_leads,
                    estimated_time_remaining=ANY,
                ),
            ],
            any_order=False,
        )

    def test_should_handle_empty_lead_source_gracefully(self, mock_data_source, mock_scorer, mock_progress_tracker):
        """
        Verify that the pipeline handles a scenario where there are no leads to process.
        Corresponds to Edge Case: Empty inputs
        """
        mock_data_source.get_total_leads.return_value = 0
        mock_data_source.fetch_leads_batch.return_value = ([], None)  # No leads fetched, and no last_id

        processor = LeadScoringBatchProcessor(
            data_source=mock_data_source, scorer=mock_scorer, progress_tracker=mock_progress_tracker, batch_size=100
        )

        processor.run()

        mock_data_source.fetch_leads_batch.assert_called_once_with(last_id=None, batch_size=100)
        mock_scorer.score_leads.assert_not_called()
        mock_progress_tracker.update_progress.assert_not_called()
        # Ensure that get_progress is called to initialize, but no updates are made if no leads to process
        mock_progress_tracker.get_progress.assert_called_once()

    def test_should_handle_fewer_leads_than_batch_size_in_a_single_batch(
        self, mock_data_source, mock_scorer, mock_progress_tracker
    ):
        """
        Verify that the pipeline correctly processes a total number of leads
        that is less than the specified batch size in a single batch.
        Corresponds to Edge Case: Maximum/minimum values (small lead count)
        """
        total_leads = 50
        batch_size = 100
        mock_data_source.get_total_leads.return_value = total_leads

        mock_data_source.fetch_leads_batch.side_effect = [
            ([{"id": i} for i in range(1, 51)], 50),  # Single batch
            ([], None),  # No more leads
        ]

        processor = LeadScoringBatchProcessor(
            data_source=mock_data_source,
            scorer=mock_scorer,
            progress_tracker=mock_progress_tracker,
            batch_size=batch_size,
        )

        processor.run()

        assert mock_data_source.fetch_leads_batch.call_count == 2
        mock_data_source.fetch_leads_batch.assert_has_calls(
            [
                call(last_id=None, batch_size=batch_size),
                call(last_id=50, batch_size=batch_size),
            ]
        )
        assert mock_scorer.score_leads.call_count == 1
        mock_scorer.score_leads.assert_called_once_with([{"id": i} for i in range(1, 51)])
        mock_progress_tracker.update_progress.assert_called_once_with(
            last_processed_id=50, percentage_complete=100.0, total_leads=total_leads, estimated_time_remaining=ANY
        )
