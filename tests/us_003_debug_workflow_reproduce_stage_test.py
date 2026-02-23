"""
IMPLEMENTATION PLAN for US-003:

Components:
  - src/workflows/debug_workflow.py (modification of `reproduce` function):
      - Responsibility: Extract `failure_context` from `StoryState`. Simulate reproduction attempt.
        Update `StoryState` with `reproduction_status` and `reproduction_details`.

Data Flow:
  - Input: `StoryState` object (containing `failure_context: str`), `RoutingEngine` (mocked).
  - Internal: Access `state['failure_context']`. Simulate reproduction.
  - Output: Modified `StoryState` object.

Integration Points:
  - `DebugWorkflow` class (`src/workflows/debug_workflow.py`): Contains the `reproduce` node.
  - `StoryState` (`src/workflows/state.py`): The state object passed to and modified by `reproduce`.
    Assumes `StoryState` will be extended with `reproduction_status` and `reproduction_details`.
  - LangGraph: Manages the overall workflow and transitions.

Edge Cases:
  - `failure_context` is an empty string.
  - `failure_context` contains a specific pattern indicating a reproducible issue.
  - `failure_context` contains a specific pattern indicating a non-reproducible issue.

Test Cases:
  1. [AC 1] -> `test_reproduce_stage_function_exists`: Verify the `reproduce` function can be imported and called.
  2. [AC 2] -> `test_reproduce_stage_accepts_and_uses_failure_context`: Ensure `reproduce` function accesses `failure_context` from `StoryState`.
  3. [AC 3] -> `test_reproduce_stage_simulates_failure_condition_and_updates_state`: Verify `reproduce` updates `StoryState` with reproduction outcome and details.
  4. [AC 4] -> `test_reproduce_stage_returns_updated_state_for_transition`: Verify `reproduce` function returns the modified `StoryState` object, allowing LangGraph to transition.

Edge Case Tests:
  - `test_reproduce_stage_handles_empty_failure_context`: Verify `reproduce` handles an empty `failure_context` gracefully.
  - `test_reproduce_stage_records_non_reproducible_outcome`: Verify state is updated correctly when reproduction attempt is unsuccessful.
"""

import pytest
from unittest.mock import MagicMock, patch

# Attempt to import the reproduce function directly for unit testing
from src.workflows.debug_workflow import reproduce
from src.workflows.state import create_initial_state, StoryState

class TestReproduceStageFunction:

    @pytest.fixture
    def mock_routing_engine(self):
        return MagicMock()

    @pytest.fixture
    def initial_story_state(self) -> StoryState:
        return create_initial_state(
            story={"id": "US-003", "title": "Test Story"},
            task_id="task-123",
            task_description="Reproduce stage test",
            working_directory="/tmp/test",
            max_attempts=1
        )

    def test_reproduce_stage_function_exists(self, initial_story_state, mock_routing_engine):
        """
        [AC 1] Test that the `reproduce` function can be imported and called.
        """
        # Calling the function should not raise an immediate error if it exists.
        # The initial implementation in debug_workflow.py simply logs and returns state.
        returned_state = reproduce(initial_story_state, mock_routing_engine)
        assert returned_state is not None
        assert returned_state == initial_story_state # Initially it just returns the input state

    def test_reproduce_stage_accepts_and_uses_failure_context(self, initial_story_state, mock_routing_engine):
        """
        [AC 2] Ensure `reproduce` function accepts and implicitly uses `failure_context` from `StoryState`.
        We'll mock an internal function that the `reproduce` stage *would* call
        to process the failure context.
        """
        initial_story_state['failure_context'] = "ERROR: File not found in /app/data"

        # Mock a hypothetical internal reproduction logic function
        with patch('src.workflows.debug_workflow.simulate_reproduction') as mock_simulate_reproduction:
            mock_simulate_reproduction.return_value = {"status": "reproduced", "details": "Error message found."}
            
            returned_state = reproduce(initial_story_state, mock_routing_engine)
            
            mock_simulate_reproduction.assert_called_once_with(initial_story_state['failure_context'])
            assert 'reproduction_status' in returned_state # This assertion will fail initially
            assert returned_state['reproduction_status'] == "reproduced"
            assert 'reproduction_details' in returned_state
            assert returned_state['reproduction_details'] == "Error message found."
            assert returned_state == initial_story_state


    def test_reproduce_stage_simulates_failure_condition_and_updates_state(self, initial_story_state, mock_routing_engine):
        """
        [AC 3] Verify `reproduce` updates `StoryState` with reproduction outcome and details.
        Simulate a successful reproduction scenario.
        """
        initial_story_state['failure_context'] = "Segmentation fault at address 0xdeadbeef"

        with patch('src.workflows.debug_workflow.simulate_reproduction') as mock_simulate_reproduction:
            mock_simulate_reproduction.return_value = {"status": "reproduced", "details": "Segfault pattern matched."}
            
            returned_state = reproduce(initial_story_state, mock_routing_engine)
            
            assert mock_simulate_reproduction.called
            assert 'reproduction_status' in returned_state # This assertion will fail initially
            assert returned_state['reproduction_status'] == "reproduced"
            assert 'reproduction_details' in returned_state
            assert returned_state['reproduction_details'] == "Segfault pattern matched."
            assert returned_state == initial_story_state

    def test_reproduce_stage_returns_updated_state_for_transition(self, initial_story_state, mock_routing_engine):
        """
        [AC 4] Verify `reproduce` function returns the modified `StoryState` object,
        allowing LangGraph to transition.
        The function itself returns the state; LangGraph's graph definition handles the transition.
        """
        initial_story_state['failure_context'] = "Error in line 42"
        
        with patch('src.workflows.debug_workflow.simulate_reproduction') as mock_simulate_reproduction:
            mock_simulate_reproduction.return_value = {"status": "reproduced", "details": "Simulated fix applied."}
            
            returned_state = reproduce(initial_story_state, mock_routing_engine)
            
            assert returned_state is not None
            assert isinstance(returned_state, StoryState)
            assert 'reproduction_status' in returned_state # This assertion will fail initially
            assert 'reproduction_details' in returned_state
            assert returned_state['reproduction_status'] == "reproduced"
            # It should return the same object reference, but modified
            assert returned_state is initial_story_state

    def test_reproduce_stage_handles_empty_failure_context(self, initial_story_state, mock_routing_engine):
        """
        Edge Case: Verify `reproduce` handles an empty `failure_context` gracefully.
        It should still call the simulation but perhaps yield a 'not_reproduced' status.
        """
        initial_story_state['failure_context'] = ""

        with patch('src.workflows.debug_workflow.simulate_reproduction') as mock_simulate_reproduction:
            mock_simulate_reproduction.return_value = {"status": "not_reproduced", "details": "No specific failure context provided."}
            
            returned_state = reproduce(initial_story_state, mock_routing_engine)
            
            mock_simulate_reproduction.assert_called_once_with("")
            assert 'reproduction_status' in returned_state # This assertion will fail initially
            assert returned_state['reproduction_status'] == "not_reproduced"
            assert 'reproduction_details' in returned_state
            assert returned_state['reproduction_details'] == "No specific failure context provided."


    def test_reproduce_stage_records_non_reproducible_outcome(self, initial_story_state, mock_routing_engine):
        """
        Edge Case: Verify state is updated correctly when reproduction attempt is unsuccessful.
        """
        initial_story_state['failure_context'] = "Intermittent network glitch"

        with patch('src.workflows.debug_workflow.simulate_reproduction') as mock_simulate_reproduction:
            mock_simulate_reproduction.return_value = {"status": "not_reproduced", "details": "Could not consistently reproduce network glitch."}
            
            returned_state = reproduce(initial_story_state, mock_routing_engine)
            
            assert mock_simulate_reproduction.called
            assert 'reproduction_status' in returned_state # This assertion will fail initially
            assert returned_state['reproduction_status'] == "not_reproduced"
            assert 'reproduction_details' in returned_state
            assert returned_state['reproduction_details'] == "Could not consistently reproduce network glitch."


# At the END of your test file, ALWAYS include:
import sys
# Pytest handles exit codes automatically. We expect import errors or assertion failures.
# This ensures that if run without pytest, it would also signal failure.
if __name__ == "__main__":
    pytest.main([__file__]) # Run pytest on this file
    sys.exit(1) # Ensure a non-zero exit code if tests fail or if the file runs without pytest
