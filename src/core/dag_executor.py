"""
Dependency DAG Executor

This module implements a DAG (Directed Acyclic Graph) executor that can:
- Build a dependency graph from a list of stories
- Perform topological sort to determine execution order
- Group stories into levels for parallel execution
- Detect circular dependencies
- Execute stories sequentially or in parallel
"""

import asyncio
from typing import Dict, List, Any, Optional
from collections import deque


class CircularDependencyError(Exception):
    """Raised when a circular dependency is detected in the story graph."""
    pass


class DAGExecutor:
    """Executor for stories with dependencies.

    Attributes:
        stories: List of story dictionaries with 'id' and 'dependencies' keys
        _stories_by_id: Dictionary mapping story IDs to story dictionaries
        runner: Optional PhaseRunner instance for executing stories
    """

    def __init__(self, stories: List[Dict[str, Any]], runner: Optional[Any] = None):
        """Initialize the DAGExecutor with a list of stories.

        Args:
            stories: List of story dictionaries, each with 'id' and 'dependencies' keys
            runner: Optional PhaseRunner instance for story execution
        """
        self.stories = stories
        self._stories_by_id: Dict[str, Dict[str, Any]] = {}
        self.runner = runner

        # Build ID lookup table
        for story in stories:
            story_id = story.get("id")
            if story_id:
                self._stories_by_id[story_id] = story

    def build_dependency_graph(self) -> Dict[str, List[str]]:
        """Build an adjacency list representation of the dependency graph.

        Returns:
            Dictionary mapping story IDs to lists of their dependencies
        """
        graph: Dict[str, List[str]] = {}

        for story in self.stories:
            story_id = story.get("id", "")
            dependencies = story.get("dependencies", [])

            if story_id:
                graph[story_id] = list(dependencies)

        return graph

    def topological_sort(self) -> List[str]:
        """Perform Kahn's algorithm for topological ordering of stories.

        Returns:
            List of story IDs in topological order

        Raises:
            CircularDependencyError: If a circular dependency is detected
        """
        graph = self.build_dependency_graph()

        if not graph:
            return []

        # Handle self-dependency first
        for story_id in graph:
            if story_id in graph[story_id]:
                raise CircularDependencyError(f"Story {story_id} depends on itself")

        # Calculate in-degree for each node
        # in-degree = number of dependencies a story has (edges pointing TO it)
        in_degree: Dict[str, int] = {story_id: 0 for story_id in graph}

        for story_id in graph:
            for dep in graph[story_id]:
                # dep is a dependency of story_id
                # So story_id has an incoming edge from dep
                # We need to increment in_degree for story_id, not dep
                if dep in graph:
                    in_degree[story_id] += 1

        # Initialize queue with nodes that have no dependencies (in-degree = 0)
        queue = deque([story_id for story_id in graph if in_degree[story_id] == 0])

        # Track topological order
        topo_order: List[str] = []
        visited_count = 0

        while queue:
            # Sort queue for deterministic ordering (lexicographic)
            sorted_queue = sorted(queue)
            current = sorted_queue[0]
            queue.remove(current)

            topo_order.append(current)
            visited_count += 1

            # Reduce in-degree for all nodes that depend on current
            for dep_id in graph:
                # If current is in dep_id's dependencies, decrement dep_id's in-degree
                if current in graph[dep_id]:
                    in_degree[dep_id] -= 1
                    if in_degree[dep_id] == 0:
                        queue.append(dep_id)

        # Check for circular dependencies
        if visited_count != len(graph):
            # Detect which nodes form the cycle
            unvisited = [node for node in graph if node not in topo_order]
            raise CircularDependencyError(f"Circular dependency detected involving: {unvisited}")

        return topo_order

    def detect_circular_dependencies(self) -> bool:
        """Detect if there are circular dependencies in the graph.

        Returns:
            True if circular dependencies exist, False otherwise
        """
        try:
            self.topological_sort()
            return False
        except CircularDependencyError:
            return True

    def get_execution_levels(self) -> List[List[str]]:
        """Group stories into levels for parallel execution.

        Stories in the same level have no dependencies on each other and can be executed concurrently.
        Stories in level N depend only on stories in levels < N.

        Returns:
            List of lists, where each inner list contains story IDs that can run in parallel
        """
        graph = self.build_dependency_graph()

        if not graph:
            return []

        # Use topological sort as base
        topo_order = self.topological_sort()

        # Create mapping of story to its dependencies
        story_to_deps: Dict[str, set] = {}
        for story_id in graph:
            story_to_deps[story_id] = set(graph[story_id])

        # Group into levels
        levels: List[List[str]] = []
        assigned: set = set()

        for story_id in topo_order:
            if story_id in assigned:
                continue

            # Find all unassigned stories whose dependencies are all assigned
            level_candidates: List[str] = []

            for candidate_id in topo_order:
                if candidate_id in assigned:
                    continue

                # Check if all dependencies are assigned
                deps = story_to_deps.get(candidate_id, set())
                if deps.issubset(assigned):
                    level_candidates.append(candidate_id)

            # Add candidates as a new level
            if level_candidates:
                levels.append(level_candidates)
                assigned.update(level_candidates)

        return levels

    def _execute_story(self, story_id: str) -> Dict[str, Any]:
        """Execute a single story.

        Args:
            story_id: The ID of the story to execute

        Returns:
            Dictionary with execution result
        """
        story = self._stories_by_id.get(story_id, {})
        result = {
            "id": story_id,
            "status": "completed",
            "story": story
        }
        return result

    async def _execute_story_async(self, story_id: str) -> Dict[str, Any]:
        """Execute a single story asynchronously.

        Args:
            story_id: The ID of the story to execute

        Returns:
            Dictionary with execution result
        """
        # Simulate async execution
        await asyncio.sleep(0)
        return self._execute_story(story_id)

    def execute_sequential(self) -> List[Dict[str, Any]]:
        """Execute stories in topological order (sequential).

        Returns:
            List of execution results in order
        """
        order = self.topological_sort()
        results: List[Dict[str, Any]] = []

        for story_id in order:
            result = self._execute_story(story_id)
            results.append(result)

        return results

    async def execute_parallel(self) -> List[Dict[str, Any]]:
        """Execute stories with parallel execution of independent stories.

        Stories in the same execution level run concurrently using asyncio.
        Each level runs after the previous level completes.

        Returns:
            List of execution results
        """
        levels = self.get_execution_levels()
        all_results: List[Dict[str, Any]] = []

        for level in levels:
            # Execute all stories in this level concurrently
            tasks = [self._execute_story_async(story_id) for story_id in level]
            level_results = await asyncio.gather(*tasks)
            all_results.extend(level_results)

        return all_results
