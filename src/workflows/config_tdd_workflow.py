"""
Config TDD Workflow — For system setup and configuration tasks.

PLAN → TEST_WRITER → TDD_RED_CHECK → EXECUTE → TDD_GREEN_CHECK → VERIFY_SCRIPT → LEARN

TDD pattern applied to config tasks:
- Test Writer writes verification tests before config changes
- TDD Red Check confirms tests fail (config not yet applied)
- Execute applies the configuration
- TDD Green Check confirms tests pass (config applied correctly)
- Verify Script runs additional verification scripts

Loopbacks:
- TDD_RED_CHECK fail → TEST_WRITER (tests should fail but didn't)
- TDD_GREEN_CHECK fail → EXECUTE (tests should pass but didn't)
- VERIFY_SCRIPT fail → EXECUTE (verification script failed)
"""

from functools import partial
from langgraph.graph import StateGraph, END

from src.workflows.state import StoryState
from src.workflows.base_workflow import (
    BaseWorkflow,
    phase_node,
    test_check_node,
    check_test_decision,
    verify_decision,
)


class ConfigTDDWorkflow(BaseWorkflow):

    def build_graph(self) -> StateGraph:
        builder = StateGraph(StoryState)
        re = self.routing_engine

        builder.add_node("plan", partial(phase_node, phase_name="PLAN", agent_name="planner", routing_engine=re))
        builder.add_node("test_writer", partial(phase_node, phase_name="TEST_WRITER", agent_name="test_writer", routing_engine=re))
        builder.add_node("tdd_red_check", partial(test_check_node, phase_name="TDD_RED_CHECK", expect_failure=True))
        builder.add_node("execute", partial(phase_node, phase_name="EXECUTE", agent_name="executor", routing_engine=re))
        builder.add_node("tdd_green_check", partial(test_check_node, phase_name="TDD_GREEN_CHECK", expect_failure=False))
        builder.add_node("verify_script", partial(phase_node, phase_name="VERIFY_SCRIPT", agent_name="validator", routing_engine=re))
        builder.add_node("learn", partial(phase_node, phase_name="LEARN", agent_name="learner", routing_engine=re))

        builder.set_entry_point("plan")

        builder.add_edge("plan", "test_writer")
        builder.add_edge("test_writer", "tdd_red_check")

        # TDD_RED_CHECK: pass → execute, fail → test_writer
        builder.add_conditional_edges("tdd_red_check", check_test_decision, {
            "pass": "execute",
            "fail": "test_writer",
        })

        builder.add_edge("execute", "tdd_green_check")

        # TDD_GREEN_CHECK: pass → verify_script, fail → execute
        builder.add_conditional_edges("tdd_green_check", check_test_decision, {
            "pass": "verify_script",
            "fail": "execute",
        })

        builder.add_conditional_edges("verify_script", verify_decision, {
            "pass": "learn",
            "fail": "execute",
        })

        builder.add_edge("learn", END)

        return builder
