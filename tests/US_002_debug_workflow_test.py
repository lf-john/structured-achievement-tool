"""
US-002: Debug Workflow State Machine Tests

Tests that DebugWorkflow defines the correct states and transitions:
- Core stages: reproduce, diagnose, routing
- Outcome branches: dev, config, maint, report
- Graph construction succeeds
"""

import pytest
from src.workflows.debug_workflow import DebugWorkflow
from unittest.mock import MagicMock


class TestDebugWorkflow:

    def test_debug_workflow_class_exists_and_can_be_instantiated(self):
        """[AC 1] Test that DebugWorkflow class can be imported and instantiated."""
        workflow = DebugWorkflow()
        assert workflow is not None
        assert isinstance(workflow, DebugWorkflow)

    def test_debug_workflow_defines_reproduce_diagnose_routing_states(self):
        """[AC 2] Test that the state machine defines reproduce, diagnose, and routing as core stages."""
        mock_routing_engine = MagicMock()
        workflow_instance = DebugWorkflow(routing_engine=mock_routing_engine)
        graph = workflow_instance.build_graph()
        assert "reproduce" in graph.nodes
        assert "diagnose" in graph.nodes
        assert "routing" in graph.nodes

    def test_debug_workflow_defines_routing_outcome_transitions(self):
        """[AC 3] Test that outcome branch nodes (dev, config, maint, report) exist in the graph."""
        mock_routing_engine = MagicMock()
        workflow_instance = DebugWorkflow(routing_engine=mock_routing_engine)
        graph = workflow_instance.build_graph()
        assert "dev" in graph.nodes
        assert "config" in graph.nodes
        assert "maint" in graph.nodes
        assert "report" in graph.nodes

    def test_debug_workflow_constructs_graph_successfully(self):
        """[AC 4] Test that the state machine graph can be constructed successfully."""
        mock_routing_engine = MagicMock()
        workflow_instance = DebugWorkflow(routing_engine=mock_routing_engine)
        graph = workflow_instance.build_graph()
        assert graph is not None
