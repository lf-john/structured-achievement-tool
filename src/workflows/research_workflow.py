"""
Research Workflow — For information gathering and analysis.

GATHER → ANALYZE → SYNTHESIZE

No loopbacks — linear pipeline.
"""

from functools import partial
from langgraph.graph import StateGraph, END

from src.workflows.state import StoryState
from src.workflows.base_workflow import BaseWorkflow, phase_node


class ResearchWorkflow(BaseWorkflow):

    def build_graph(self) -> StateGraph:
        builder = StateGraph(StoryState)
        re = self.routing_engine

        builder.add_node("gather", partial(phase_node, phase_name="GATHER", agent_name="gatherer", routing_engine=re))
        builder.add_node("analyze", partial(phase_node, phase_name="ANALYZE", agent_name="analyzer", routing_engine=re))
        builder.add_node("synthesize", partial(phase_node, phase_name="SYNTHESIZE", agent_name="synthesizer", routing_engine=re))

        builder.set_entry_point("gather")
        builder.add_edge("gather", "analyze")
        builder.add_edge("analyze", "synthesize")
        builder.add_edge("synthesize", END)

        return builder
