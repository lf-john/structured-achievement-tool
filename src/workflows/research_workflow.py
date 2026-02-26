"""
Research Workflow — For information gathering and analysis.

PARALLEL_GATHER → ANALYZE → SYNTHESIZE

Phase 3 enhancement:
- Single GATHER node replaced with parallel_gather_node running 3 channels:
  gather_web, gather_code, gather_docs — all merge before ANALYZE.

No loopbacks — linear pipeline.
"""

from functools import partial
from langgraph.graph import StateGraph, END

from src.workflows.state import StoryState
from src.workflows.base_workflow import (
    BaseWorkflow,
    phase_node,
    parallel_gather_node,
)


class ResearchWorkflow(BaseWorkflow):

    def build_graph(self) -> StateGraph:
        builder = StateGraph(StoryState)
        re = self.routing_engine

        # Parallel gather replaces single gather node
        builder.add_node("parallel_gather", partial(parallel_gather_node, routing_engine=re))
        builder.add_node("analyze", partial(phase_node, phase_name="ANALYZE", agent_name="analyzer", routing_engine=re))
        builder.add_node("synthesize", partial(phase_node, phase_name="SYNTHESIZE", agent_name="synthesizer", routing_engine=re))

        builder.set_entry_point("parallel_gather")
        builder.add_edge("parallel_gather", "analyze")
        builder.add_edge("analyze", "synthesize")
        builder.add_edge("synthesize", END)

        return builder
