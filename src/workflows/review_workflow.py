"""
Review Workflow — For code/document analysis and quality review.

ANALYZE → REVIEW → REPORT

No loopbacks — linear pipeline.
"""

from functools import partial

from langgraph.graph import END, StateGraph

from src.workflows.base_workflow import BaseWorkflow, phase_node
from src.workflows.state import StoryState


class ReviewWorkflow(BaseWorkflow):

    def build_graph(self) -> StateGraph:
        builder = StateGraph(StoryState)
        re = self.routing_engine

        builder.add_node("analyze", partial(phase_node, phase_name="ANALYZE", agent_name="analyzer", routing_engine=re))
        builder.add_node("review", partial(phase_node, phase_name="REVIEW", agent_name="reviewer", routing_engine=re))
        builder.add_node("report", partial(phase_node, phase_name="REPORT", agent_name="reporter", routing_engine=re))

        builder.set_entry_point("analyze")
        builder.add_edge("analyze", "review")
        builder.add_edge("review", "report")
        builder.add_edge("report", END)

        return builder
