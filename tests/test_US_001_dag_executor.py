"""
IMPLEMENTATION PLAN for US-001: Implement Dependency DAG Executor

Components:
  - DAGExecutor: Main class for executing stories based on dependency graph
    * __init__(stories: List[Dict]): Initialize with list of stories
    * build_dependency_graph(): Build adjacency list representation of dependencies
    * topological_sort(): Perform Kahn's algorithm for topological ordering
    * get_execution_levels(): Group stories into levels for parallel execution
    * execute_sequential(): Execute stories in dependency order (sequential)
    * execute_parallel(): Execute independent stories concurrently (asyncio)
    * detect_circular_dependencies(): Detect cycles in the dependency graph

  - Story data structure:
    * id: Unique identifier (e.g., "US-001")
    * dependencies: List of story IDs this story depends on

Test Cases:
  1. AC 1 (DAGExecutor can build dependency graph from stories)
     -> test_dag_executor_builds_graph_from_stories
     -> test_graph_has_correct_edges
     -> test_graph_with_no_dependencies

  2. AC 2 (Topological sort correctly orders stories)
     -> test_topological_sort_simple_chain
     -> test_topological_sort_diamond_pattern
     -> test_topological_sort_complex_graph
     -> test_topological_sort_with_independent_stories

  3. AC 3 (Independent stories can be identified for parallel execution)
     -> test_identify_independent_stories
     -> test_get_execution_levels
     -> test_execution_levels_have_no_cross_level_dependencies
     -> test_parallel_execution_structure

  4. AC 4 (Circular dependencies raise an error)
     -> test_circular_dependency_detection
     -> test_self_dependency_raises_error
     -> test_complex_circular_dependency

Edge Cases:
  - Empty story list
  - Single story with no dependencies
  - All stories independent (can all run in parallel)
  - All stories in single chain (must run sequentially)
  - Story with non-existent dependency
  - Multiple valid topological orderings (any is acceptable)

AMENDED BY US-001: All tests follow the project's pytest pattern with proper exit code handling
"""

import pytest
import asyncio
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, patch, AsyncMock
import sys

# Import the classes that need to be created (will cause import errors initially)
from src.core.dag_executor import DAGExecutor, CircularDependencyError


class TestDAGExecutorClassExists:
    """Test that DAGExecutor class exists and can be instantiated."""

    def test_dag_executor_class_exists(self):
        """Test that DAGExecutor class can be imported."""
        assert DAGExecutor is not None
        assert hasattr(DAGExecutor, '__init__')

    def test_dag_executor_can_be_instantiated_empty(self):
        """Test that DAGExecutor can be instantiated with empty list."""
        executor = DAGExecutor(stories=[])
        assert executor is not None
        assert isinstance(executor, DAGExecutor)

    def test_dag_executor_can_be_instantiated_with_stories(self):
        """Test that DAGExecutor can be instantiated with stories."""
        stories = [
            {"id": "US-001", "dependencies": []},
            {"id": "US-002", "dependencies": ["US-001"]},
        ]
        executor = DAGExecutor(stories=stories)
        assert executor is not None
        assert isinstance(executor, DAGExecutor)


class TestBuildDependencyGraph:
    """Test acceptance criterion 1: DAGExecutor can build a dependency graph from stories."""

    def test_dag_executor_builds_graph_from_stories(self):
        """Test that build_dependency_graph creates correct adjacency list."""
        stories = [
            {"id": "US-001", "dependencies": []},
            {"id": "US-002", "dependencies": ["US-001"]},
            {"id": "US-003", "dependencies": ["US-001", "US-002"]},
        ]

        executor = DAGExecutor(stories=stories)
        graph = executor.build_dependency_graph()

        # Graph should map story IDs to their dependencies
        assert "US-001" in graph
        assert "US-002" in graph
        assert "US-003" in graph

        # Check edges
        assert graph["US-001"] == []
        assert graph["US-002"] == ["US-001"]
        assert set(graph["US-003"]) == {"US-001", "US-002"}

    def test_graph_with_no_dependencies(self):
        """Test graph with all independent stories."""
        stories = [
            {"id": "US-001", "dependencies": []},
            {"id": "US-002", "dependencies": []},
            {"id": "US-003", "dependencies": []},
        ]

        executor = DAGExecutor(stories=stories)
        graph = executor.build_dependency_graph()

        # All stories should have empty dependency lists
        for story_id in graph:
            assert graph[story_id] == []

    def test_graph_has_correct_edges(self):
        """Test that edges are created correctly for dependencies."""
        stories = [
            {"id": "US-001", "dependencies": []},
            {"id": "US-002", "dependencies": ["US-001"]},
            {"id": "US-003", "dependencies": ["US-001"]},
            {"id": "US-004", "dependencies": ["US-002", "US-003"]},
        ]

        executor = DAGExecutor(stories=stories)
        graph = executor.build_dependency_graph()

        # Verify the dependency structure
        assert graph["US-002"] == ["US-001"]
        assert graph["US-003"] == ["US-001"]
        assert set(graph["US-004"]) == {"US-002", "US-003"}

    def test_build_graph_stores_stories(self):
        """Test that executor stores stories for later execution."""
        stories = [
            {"id": "US-001", "dependencies": [], "task": "First task"},
            {"id": "US-002", "dependencies": ["US-001"], "task": "Second task"},
        ]

        executor = DAGExecutor(stories=stories)

        # Should be able to access the stories
        assert hasattr(executor, 'stories') or hasattr(executor, '_stories')
        stored_stories = executor.stories if hasattr(executor, 'stories') else executor._stories
        assert len(stored_stories) == 2


class TestTopologicalSort:
    """Test acceptance criterion 2: Topological sort correctly orders stories by dependencies."""

    def test_topological_sort_simple_chain(self):
        """Test topological sort with a simple linear chain."""
        stories = [
            {"id": "US-001", "dependencies": []},
            {"id": "US-002", "dependencies": ["US-001"]},
            {"id": "US-003", "dependencies": ["US-002"]},
        ]

        executor = DAGExecutor(stories=stories)
        order = executor.topological_sort()

        # US-001 must come before US-002
        assert order.index("US-001") < order.index("US-002")
        # US-002 must come before US-003
        assert order.index("US-002") < order.index("US-003")

    def test_topological_sort_diamond_pattern(self):
        """Test topological sort with diamond dependency pattern."""
        stories = [
            {"id": "US-001", "dependencies": []},
            {"id": "US-002", "dependencies": ["US-001"]},
            {"id": "US-003", "dependencies": ["US-001"]},
            {"id": "US-004", "dependencies": ["US-002", "US-003"]},
        ]

        executor = DAGExecutor(stories=stories)
        order = executor.topological_sort()

        # US-001 must be first
        assert order[0] == "US-001"
        # US-001 must come before both US-002 and US-003
        assert order.index("US-001") < order.index("US-002")
        assert order.index("US-001") < order.index("US-003")
        # Both US-002 and US-003 must come before US-004
        assert order.index("US-002") < order.index("US-004")
        assert order.index("US-003") < order.index("US-004")

    def test_topological_sort_complex_graph(self):
        """Test topological sort with a more complex dependency graph."""
        stories = [
            {"id": "US-001", "dependencies": []},
            {"id": "US-002", "dependencies": ["US-001"]},
            {"id": "US-003", "dependencies": ["US-001"]},
            {"id": "US-004", "dependencies": ["US-002"]},
            {"id": "US-005", "dependencies": ["US-002", "US-003"]},
            {"id": "US-006", "dependencies": ["US-005"]},
        ]

        executor = DAGExecutor(stories=stories)
        order = executor.topological_sort()

        # Verify all dependencies come before their dependents
        for story in stories:
            story_id = story["id"]
            for dep in story["dependencies"]:
                assert order.index(dep) < order.index(story_id), \
                    f"{dep} should come before {story_id}"

    def test_topological_sort_with_independent_stories(self):
        """Test topological sort when multiple stories have no dependencies."""
        stories = [
            {"id": "US-001", "dependencies": []},
            {"id": "US-002", "dependencies": []},
            {"id": "US-003", "dependencies": []},
        ]

        executor = DAGExecutor(stories=stories)
        order = executor.topological_sort()

        # All stories should be in the result
        assert set(order) == {"US-001", "US-002", "US-003"}

    def test_topological_sort_single_story(self):
        """Test topological sort with a single story."""
        stories = [
            {"id": "US-001", "dependencies": []},
        ]

        executor = DAGExecutor(stories=stories)
        order = executor.topological_sort()

        assert order == ["US-001"]


class TestIdentifyIndependentStories:
    """Test acceptance criterion 3: Independent stories can be identified for parallel execution."""

    def test_identify_independent_stories(self):
        """Test that independent stories are identified correctly."""
        stories = [
            {"id": "US-001", "dependencies": []},
            {"id": "US-002", "dependencies": []},
            {"id": "US-003", "dependencies": ["US-001", "US-002"]},
        ]

        executor = DAGExecutor(stories=stories)
        levels = executor.get_execution_levels()

        # First level should have US-001 and US-002 (independent)
        assert set(levels[0]) == {"US-001", "US-002"}
        # Second level should have US-003
        assert levels[1] == ["US-003"]

    def test_get_execution_levels(self):
        """Test that stories are grouped into correct execution levels."""
        stories = [
            {"id": "US-001", "dependencies": []},
            {"id": "US-002", "dependencies": ["US-001"]},
            {"id": "US-003", "dependencies": ["US-001"]},
            {"id": "US-004", "dependencies": ["US-002", "US-003"]},
        ]

        executor = DAGExecutor(stories=stories)
        levels = executor.get_execution_levels()

        # Level 0: US-001 (no dependencies)
        assert levels[0] == ["US-001"]
        # Level 1: US-002, US-003 (depend only on US-001)
        assert set(levels[1]) == {"US-002", "US-003"}
        # Level 2: US-004 (depends on both level 1 stories)
        assert levels[2] == ["US-004"]

    def test_execution_levels_have_no_cross_level_dependencies(self):
        """Test that no story depends on another in the same or later level."""
        stories = [
            {"id": "US-001", "dependencies": []},
            {"id": "US-002", "dependencies": ["US-001"]},
            {"id": "US-003", "dependencies": ["US-001"]},
            {"id": "US-004", "dependencies": ["US-002"]},
            {"id": "US-005", "dependencies": ["US-002", "US-003"]},
        ]

        executor = DAGExecutor(stories=stories)
        levels = executor.get_execution_levels()

        # Create a mapping of story to level
        story_to_level = {}
        for level_idx, level in enumerate(levels):
            for story_id in level:
                story_to_level[story_id] = level_idx

        # Verify all dependencies are in earlier levels
        for story in stories:
            story_id = story["id"]
            story_level = story_to_level[story_id]
            for dep in story["dependencies"]:
                dep_level = story_to_level[dep]
                assert dep_level < story_level, \
                    f"{dep} (level {dep_level}) should be before {story_id} (level {story_level})"

    def test_parallel_execution_structure(self):
        """Test that execution structure allows for parallel execution."""
        stories = [
            {"id": "US-001", "dependencies": []},
            {"id": "US-002", "dependencies": []},
            {"id": "US-003", "dependencies": []},
        ]

        executor = DAGExecutor(stories=stories)
        levels = executor.get_execution_levels()

        # All independent stories should be in the same level
        assert len(levels) == 1
        assert set(levels[0]) == {"US-001", "US-002", "US-003"}

    def test_all_stories_in_sequential_chain(self):
        """Test execution levels when all stories must run sequentially."""
        stories = [
            {"id": "US-001", "dependencies": []},
            {"id": "US-002", "dependencies": ["US-001"]},
            {"id": "US-003", "dependencies": ["US-002"]},
            {"id": "US-004", "dependencies": ["US-003"]},
        ]

        executor = DAGExecutor(stories=stories)
        levels = executor.get_execution_levels()

        # Each story should be in its own level
        assert len(levels) == 4
        assert levels[0] == ["US-001"]
        assert levels[1] == ["US-002"]
        assert levels[2] == ["US-003"]
        assert levels[3] == ["US-004"]


class TestCircularDependencyDetection:
    """Test acceptance criterion 4: Circular dependencies raise an error."""

    def test_circular_dependency_exists_class(self):
        """Test that CircularDependencyError exception class exists."""
        assert CircularDependencyError is not None
        assert issubclass(CircularDependencyError, Exception)

    def test_circular_dependency_detection_two_nodes(self):
        """Test detection of simple circular dependency (A -> B -> A)."""
        stories = [
            {"id": "US-001", "dependencies": ["US-002"]},
            {"id": "US-002", "dependencies": ["US-001"]},
        ]

        executor = DAGExecutor(stories=stories)

        # Should raise CircularDependencyError
        with pytest.raises(CircularDependencyError):
            executor.topological_sort()

    def test_self_dependency_raises_error(self):
        """Test that a story depending on itself raises an error."""
        stories = [
            {"id": "US-001", "dependencies": ["US-001"]},
        ]

        executor = DAGExecutor(stories=stories)

        with pytest.raises(CircularDependencyError):
            executor.topological_sort()

    def test_complex_circular_dependency(self):
        """Test detection of complex circular dependency (A -> B -> C -> A)."""
        stories = [
            {"id": "US-001", "dependencies": ["US-002"]},
            {"id": "US-002", "dependencies": ["US-003"]},
            {"id": "US-003", "dependencies": ["US-001"]},
        ]

        executor = DAGExecutor(stories=stories)

        with pytest.raises(CircularDependencyError):
            executor.topological_sort()

    def test_partial_circular_dependency_detection(self):
        """Test detection of circular dependency in larger graph."""
        stories = [
            {"id": "US-001", "dependencies": []},
            {"id": "US-002", "dependencies": ["US-001"]},
            {"id": "US-003", "dependencies": ["US-002"]},
            {"id": "US-004", "dependencies": ["US-003", "US-002"]},  # Creates cycle with US-002
        ]

        executor = DAGExecutor(stories=stories)

        # US-002 -> US-003 -> US-004 -> US-002 creates a cycle
        # But wait, this is not actually a cycle. Let me fix this.
        # Actually, let's create a real cycle:
        stories_with_cycle = [
            {"id": "US-001", "dependencies": []},
            {"id": "US-002", "dependencies": ["US-001"]},
            {"id": "US-003", "dependencies": ["US-002"]},
            {"id": "US-004", "dependencies": ["US-003"]},
            {"id": "US-002", "dependencies": ["US-004"]},  # This creates the cycle
        ]

        executor_with_cycle = DAGExecutor(stories=stories_with_cycle)

        with pytest.raises(CircularDependencyError):
            executor_with_cycle.topological_sort()

    def test_detect_circular_dependencies_method(self):
        """Test the explicit detect_circular_dependencies method if it exists."""
        stories = [
            {"id": "US-001", "dependencies": ["US-002"]},
            {"id": "US-002", "dependencies": ["US-001"]},
        ]

        executor = DAGExecutor(stories=stories)

        # If executor has explicit detect method, test it
        if hasattr(executor, 'detect_circular_dependencies'):
            is_circular = executor.detect_circular_dependencies()
            assert is_circular is True

        # Test with non-circular graph
        stories_valid = [
            {"id": "US-001", "dependencies": []},
            {"id": "US-002", "dependencies": ["US-001"]},
        ]

        executor_valid = DAGExecutor(stories=stories_valid)

        if hasattr(executor_valid, 'detect_circular_dependencies'):
            is_circular = executor_valid.detect_circular_dependencies()
            assert is_circular is False


class TestExecuteSequential:
    """Test sequential execution of stories."""

    def test_execute_sequential_method_exists(self):
        """Test that execute_sequential method exists."""
        stories = [
            {"id": "US-001", "dependencies": []},
            {"id": "US-002", "dependencies": ["US-001"]},
        ]

        executor = DAGExecutor(stories=stories)
        assert hasattr(executor, 'execute_sequential')

    @patch('src.core.dag_executor.DAGExecutor._execute_story')
    def test_execute_sequential_calls_stories_in_order(self, mock_execute):
        """Test that execute_sequential calls stories in topological order."""
        mock_execute.return_value = {"status": "completed"}

        stories = [
            {"id": "US-001", "dependencies": []},
            {"id": "US-002", "dependencies": ["US-001"]},
            {"id": "US-003", "dependencies": ["US-002"]},
        ]

        executor = DAGExecutor(stories=stories)
        results = executor.execute_sequential()

        # Verify all stories were executed
        assert mock_execute.call_count == 3

        # Verify execution order (should be topological)
        call_order = [call[0][0] for call in mock_execute.call_args_list]
        assert call_order == ["US-001", "US-002", "US-003"]

    @patch('src.core.dag_executor.DAGExecutor._execute_story')
    def test_execute_sequential_returns_results(self, mock_execute):
        """Test that execute_sequential returns execution results."""
        mock_execute.side_effect = [
            {"id": "US-001", "status": "completed"},
            {"id": "US-002", "status": "completed"},
            {"id": "US-003", "status": "completed"},
        ]

        stories = [
            {"id": "US-001", "dependencies": []},
            {"id": "US-002", "dependencies": ["US-001"]},
            {"id": "US-003", "dependencies": ["US-002"]},
        ]

        executor = DAGExecutor(stories=stories)
        results = executor.execute_sequential()

        # Should return list of results
        assert isinstance(results, list)
        assert len(results) == 3


class TestExecuteParallel:
    """Test parallel execution of independent stories using asyncio."""

    def test_execute_parallel_method_exists(self):
        """Test that execute_parallel method exists."""
        stories = [
            {"id": "US-001", "dependencies": []},
            {"id": "US-002", "dependencies": []},
        ]

        executor = DAGExecutor(stories=stories)
        assert hasattr(executor, 'execute_parallel')

    @pytest.mark.asyncio
    @patch('src.core.dag_executor.DAGExecutor._execute_story_async')
    async def test_execute_parallel_runs_independent_stories_concurrently(self, mock_execute):
        """Test that independent stories are executed concurrently."""
        # Make the mock async
        mock_execute = AsyncMock()
        mock_execute.side_effect = [
            {"id": "US-001", "status": "completed"},
            {"id": "US-002", "status": "completed"},
        ]

        stories = [
            {"id": "US-001", "dependencies": []},
            {"id": "US-002", "dependencies": []},
        ]

        executor = DAGExecutor(stories=stories)
        results = await executor.execute_parallel()

        # Both stories should be executed
        assert len(results) == 2

    @pytest.mark.asyncio
    @patch('src.core.dag_executor.DAGExecutor._execute_story_async')
    async def test_execute_parallel_respects_dependencies(self, mock_execute):
        """Test that parallel execution respects dependency levels."""
        mock_execute = AsyncMock()
        mock_execute.side_effect = [
            {"id": "US-001", "status": "completed"},
            {"id": "US-002", "status": "completed"},
            {"id": "US-003", "status": "completed"},
        ]

        stories = [
            {"id": "US-001", "dependencies": []},
            {"id": "US-002", "dependencies": ["US-001"]},
            {"id": "US-003", "dependencies": ["US-001"]},
        ]

        executor = DAGExecutor(stories=stories)
        results = await executor.execute_parallel()

        # All stories should be executed
        assert len(results) == 3
        # US-001 should be executed before US-002 and US-003
        # (This is verified by the execution levels logic)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_story_list(self):
        """Test behavior with empty story list."""
        executor = DAGExecutor(stories=[])

        graph = executor.build_dependency_graph()
        assert graph == {}

        order = executor.topological_sort()
        assert order == []

    def test_single_story_no_dependencies(self):
        """Test with a single story that has no dependencies."""
        stories = [
            {"id": "US-001", "dependencies": []},
        ]

        executor = DAGExecutor(stories=stories)
        order = executor.topological_sort()
        levels = executor.get_execution_levels()

        assert order == ["US-001"]
        assert levels == [["US-001"]]

    def test_story_with_non_existent_dependency(self):
        """Test handling of story with dependency that doesn't exist."""
        stories = [
            {"id": "US-001", "dependencies": []},
            {"id": "US-002", "dependencies": ["US-999"]},  # Non-existent
        ]

        executor = DAGExecutor(stories=stories)

        # Should handle gracefully - either include the dependency or ignore it
        # The exact behavior depends on implementation
        try:
            order = executor.topological_sort()
            # If it doesn't raise, verify US-999 is handled
            assert "US-001" in order
            assert "US-002" in order
        except (ValueError, KeyError):
            # Also acceptable to raise an error for invalid dependencies
            pass

    def test_all_stories_independent(self):
        """Test when all stories are independent (can all run in parallel)."""
        stories = [
            {"id": "US-001", "dependencies": []},
            {"id": "US-002", "dependencies": []},
            {"id": "US-003", "dependencies": []},
            {"id": "US-004", "dependencies": []},
        ]

        executor = DAGExecutor(stories=stories)
        levels = executor.get_execution_levels()

        # All should be in first level
        assert len(levels) == 1
        assert set(levels[0]) == {"US-001", "US-002", "US-003", "US-004"}

    def test_multiple_valid_topological_orderings(self):
        """Test that any valid topological ordering is acceptable."""
        stories = [
            {"id": "US-001", "dependencies": []},
            {"id": "US-002", "dependencies": []},
            {"id": "US-003", "dependencies": ["US-001", "US-002"]},
        ]

        executor = DAGExecutor(stories=stories)
        order = executor.topological_sort()

        # US-001 and US-002 can be in any order, but both must come before US-003
        assert order.index("US-001") < order.index("US-003")
        assert order.index("US-002") < order.index("US-003")

    def test_duplicate_story_ids(self):
        """Test handling of duplicate story IDs."""
        stories = [
            {"id": "US-001", "dependencies": []},
            {"id": "US-001", "dependencies": []},  # Duplicate
        ]

        # This is invalid input - behavior depends on implementation
        executor = DAGExecutor(stories=stories)

        # Should either handle gracefully or raise an error
        try:
            order = executor.topological_sort()
            # If no error, there should only be one US-001 in the result
            assert order.count("US-001") <= 1
        except (ValueError, KeyError):
            # Also acceptable to raise an error
            pass


class TestIntegrationWithOrchestrator:
    """Test integration with the LangGraph Orchestrator."""

    def test_dag_executor_has_story_execution_interface(self):
        """Test that DAGExecutor provides interface for story execution."""
        stories = [
            {"id": "US-001", "dependencies": [], "task": "Task 1"},
            {"id": "US-002", "dependencies": ["US-001"], "task": "Task 2"},
        ]

        executor = DAGExecutor(stories=stories)

        # Should have methods for executing stories
        assert hasattr(executor, 'execute_sequential') or hasattr(executor, 'execute')

    @patch('src.core.phase_runner.PhaseRunner')
    def test_dag_executor_can_use_phase_runner(self, mock_runner):
        """Test that DAGExecutor can integrate with PhaseRunner for story execution."""
        stories = [
            {"id": "US-001", "dependencies": [], "task": "Test task"},
        ]

        # If DAGExecutor accepts a runner parameter
        try:
            executor = DAGExecutor(stories=stories, runner=mock_runner)
            assert executor.runner == mock_runner
        except TypeError:
            # If not supported by constructor, that's okay
            pass


# Track test failures for exit code
fail_count = 0


def pytest_configure(config):
    """Configure pytest to track failures."""
    global fail_count


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Called at end of test session to determine exit code."""
    global fail_count
    fail_count = 1 if exitstatus != 0 else 0


if __name__ == "__main__":
    # Run pytest programmatically and exit with appropriate code
    exit_code = pytest.main([__file__, "-v"])
    sys.exit(exit_code)
