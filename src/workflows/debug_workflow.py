"""
DebugWorkflow — LangGraph state machine for debugging tasks.

Flow: REPRODUCE → DIAGNOSE → ROUTING → [dev | config | maint | report]

Each outcome branch delegates to the appropriate specialized workflow:
- dev: DevTDDWorkflow (ARCHITECT → PLAN → TEST → CODE → VERIFY → LEARN)
- config: ConfigTDDWorkflow (PLAN → TEST → EXECUTE → VERIFY_SCRIPT → LEARN)
- maint: MaintenanceWorkflow (PLAN → TEST → EXECUTE → VERIFY → LEARN)
- report: ResearchWorkflow (GATHER → ANALYZE → SYNTHESIZE)

The debug context (failure_context, reproduction details, diagnosis) is
injected into the story description so the sub-workflow's LLM phases have
full awareness of what went wrong and why.
"""

import logging
from typing import Literal

from langgraph.graph import END, StateGraph

from src.llm.routing_engine import RoutingEngine
from src.workflows.base_workflow import BaseWorkflow
from src.workflows.state import StoryState

logger = logging.getLogger(__name__)


def simulate_reproduction(failure_context: str, working_directory: str = None) -> dict:
    """
    Attempt to reproduce a failure by re-running the failing test.

    Strategy:
    1. Extract test file/function from failure context
    2. Re-run the test to confirm the failure still exists
    3. Fall back to keyword heuristic if no test can be identified
    """
    if not failure_context.strip():
        return {"status": "not_applicable", "details": "No failure context provided."}

    # Try to extract a test file reference from the failure context
    import re
    import subprocess

    test_file_match = re.search(
        r'(tests?/\S+\.py)(?:::(\S+))?',
        failure_context,
    )

    if test_file_match and working_directory:
        test_file = test_file_match.group(1)
        test_func = test_file_match.group(2)
        test_target = f"{test_file}::{test_func}" if test_func else test_file

        try:
            result = subprocess.run(
                ["python", "-m", "pytest", test_target, "-x", "--tb=short", "-q"],
                cwd=working_directory,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                return {
                    "status": "reproduced",
                    "method": "test_reexecution",
                    "test_target": test_target,
                    "details": f"Test failure reproduced by re-running {test_target}:\n{result.stdout[-500:]}",
                }
            else:
                return {
                    "status": "not_reproduced",
                    "method": "test_reexecution",
                    "test_target": test_target,
                    "details": f"Test {test_target} now passes — failure may be transient.",
                }
        except subprocess.TimeoutExpired:
            return {
                "status": "reproduced",
                "method": "test_reexecution",
                "test_target": test_target,
                "details": f"Test {test_target} timed out (>120s) — likely stuck or resource-bound.",
            }
        except Exception as e:
            logger.warning(f"Test re-execution failed: {e}")
            # Fall through to keyword heuristic

    # Fallback: keyword heuristic
    error_indicators = [
        "error", "failure", "fault", "exception", "traceback",
        "failed", "crash", "timeout", "refused", "denied",
    ]
    if any(term in failure_context.lower() for term in error_indicators):
        return {
            "status": "reproduced",
            "method": "keyword_heuristic",
            "details": f"Failure pattern detected in context: {failure_context[:200]}",
        }
    return {
        "status": "not_reproduced",
        "method": "keyword_heuristic",
        "details": f"Could not reproduce failure from context: {failure_context[:200]}",
    }


def categorize_diagnosis(reproduction_details: str) -> dict:
    """
    Categorize a diagnosed issue into one of four outcomes.
    """
    details_lower = reproduction_details.lower()

    if any(term in details_lower for term in [
        "disk", "space", "memory", "permissions", "service", "restart",
        "oom", "quota", "mount", "pid",
    ]):
        return {
            "category": "maintenance",
            "reasoning": "System resource or infrastructure issue requiring maintenance",
        }

    if any(term in details_lower for term in [
        "config", "parameter", "port", "invalid", "env", "setting",
        "credential", "key", "path",
    ]):
        return {
            "category": "config",
            "reasoning": "Configuration parameter or setting issue",
        }

    if "not reproduced" in details_lower or "not_reproduced" in details_lower:
        return {
            "category": "review",
            "reasoning": "Non-reproducible issue — informational review only",
        }

    return {
        "category": "development",
        "reasoning": "Code-level issue requiring development fix",
    }


def _enrich_story_with_debug_context(state: StoryState) -> StoryState:
    """Inject debug context into the story description so sub-workflow LLM
    phases understand the failure being debugged."""
    story = dict(state.get("story", {}))
    original_desc = story.get("description", "")

    debug_context = (
        f"\n\n---\n**Debug Context (auto-injected)**\n"
        f"- Reproduction status: {state.get('reproduction_status', 'unknown')}\n"
        f"- Reproduction details: {state.get('reproduction_details', 'N/A')}\n"
        f"- Diagnosis: {state.get('diagnosis_category', 'unknown')} — "
        f"{state.get('diagnosis_reasoning', 'N/A')}\n"
        f"- Original failure: {state.get('failure_context', 'N/A')[:500]}\n"
        f"---\n"
    )
    story["description"] = original_desc + debug_context
    state["story"] = story
    return state


# --- Core node functions ---

def reproduce(state: StoryState, routing_engine: RoutingEngine) -> StoryState:
    logger.info("Debug: REPRODUCE — attempting to reproduce failure")
    failure_context = state.get("failure_context", "")
    working_dir = state.get("working_directory")
    outcome = simulate_reproduction(failure_context, working_directory=working_dir)
    state["reproduction_status"] = outcome["status"]
    state["reproduction_details"] = outcome["details"]
    state["reproduction_method"] = outcome.get("method", "keyword_heuristic")
    logger.info(f"Debug: reproduction={outcome['status']} method={outcome.get('method', 'keyword_heuristic')}")

    # Log reproduction event for daily digest monitoring
    try:
        from src.db.database_manager import DatabaseManager
        db = DatabaseManager()
        db.log_event(
            event_type="debug_reproduction",
            data={
                "status": outcome["status"],
                "method": outcome.get("method", "keyword_heuristic"),
                "story_id": state.get("story", {}).get("id", "unknown"),
            },
        )
    except Exception:
        pass  # Best-effort monitoring

    return state


def diagnose(state: StoryState, routing_engine: RoutingEngine) -> StoryState:
    logger.info("Debug: DIAGNOSE — categorizing issue")
    reproduction_details = state.get("reproduction_details", "")
    diagnosis = categorize_diagnosis(reproduction_details)
    state["diagnosis_category"] = diagnosis["category"]
    state["diagnosis_reasoning"] = diagnosis["reasoning"]
    logger.info(f"Debug: diagnosis={diagnosis['category']} — {diagnosis['reasoning']}")
    return state


def routing(state: StoryState, routing_engine: RoutingEngine) -> StoryState:
    logger.info("Debug: ROUTING — preparing for sub-workflow dispatch")
    return _enrich_story_with_debug_context(state)


# --- Outcome branch nodes ---

def _run_sub_workflow(state: StoryState, workflow_cls, routing_engine: RoutingEngine) -> StoryState:
    """Instantiate and run a sub-workflow, returning the merged state."""
    try:
        sub_wf = workflow_cls(routing_engine=routing_engine)
        compiled = sub_wf.compile()
        result = compiled.invoke(dict(state))
        # Merge sub-workflow outputs back into our state
        state.update(result)
        logger.info(f"Debug: sub-workflow {workflow_cls.__name__} completed")
    except Exception as e:
        logger.error(f"Debug: sub-workflow {workflow_cls.__name__} failed: {e}")
        state["failure_context"] = (
            state.get("failure_context", "") +
            f"\nSub-workflow {workflow_cls.__name__} error: {e}"
        )
    return state


def dev_workflow(state: StoryState, routing_engine: RoutingEngine) -> StoryState:
    """Route to DevTDDWorkflow for code-level fixes."""
    logger.info("Debug: dispatching to DevTDDWorkflow")
    from src.workflows.dev_tdd_workflow import DevTDDWorkflow
    return _run_sub_workflow(state, DevTDDWorkflow, routing_engine)


def config_workflow(state: StoryState, routing_engine: RoutingEngine) -> StoryState:
    """Route to ConfigTDDWorkflow for configuration fixes."""
    logger.info("Debug: dispatching to ConfigTDDWorkflow")
    from src.workflows.config_tdd_workflow import ConfigTDDWorkflow
    return _run_sub_workflow(state, ConfigTDDWorkflow, routing_engine)


def maint_workflow(state: StoryState, routing_engine: RoutingEngine) -> StoryState:
    """Route to MaintenanceWorkflow for infrastructure fixes."""
    logger.info("Debug: dispatching to MaintenanceWorkflow")
    from src.workflows.maintenance_workflow import MaintenanceWorkflow
    return _run_sub_workflow(state, MaintenanceWorkflow, routing_engine)


def report_workflow(state: StoryState, routing_engine: RoutingEngine) -> StoryState:
    """Route to ResearchWorkflow for non-reproducible issues (investigation)."""
    logger.info("Debug: dispatching to ResearchWorkflow for investigation")
    from src.workflows.research_workflow import ResearchWorkflow
    return _run_sub_workflow(state, ResearchWorkflow, routing_engine)


class DebugWorkflow(BaseWorkflow):
    """
    Debugging workflow: REPRODUCE → DIAGNOSE → ROUTING → sub-workflow.

    After diagnosis, routes to the appropriate specialized workflow that
    actually performs the fix or investigation.
    """

    def __init__(self, routing_engine: RoutingEngine | None = None):
        super().__init__(routing_engine)
        self.app = self.compile()

    def routing_decision(self, state: StoryState) -> Literal["dev", "config", "maint", "report"]:
        category = state.get("diagnosis_category", "development")
        category_map = {
            "development": "dev",
            "config": "config",
            "maintenance": "maint",
            "review": "report",
        }
        decision = category_map.get(category, "dev")
        logger.info(f"Debug: routing decision={decision} (diagnosis={category})")
        return decision

    def run(self, state: StoryState) -> StoryState:
        return self.app.invoke(state)

    def build_graph(self) -> StateGraph:
        workflow = StateGraph(StoryState)
        re = self.routing_engine

        # Core stages
        workflow.add_node("reproduce", lambda s: reproduce(s, re))
        workflow.add_node("diagnose", lambda s: diagnose(s, re))
        workflow.add_node("routing", lambda s: routing(s, re))

        # Outcome branches — each invokes its full sub-workflow
        workflow.add_node("dev", lambda s: dev_workflow(s, re))
        workflow.add_node("config", lambda s: config_workflow(s, re))
        workflow.add_node("maint", lambda s: maint_workflow(s, re))
        workflow.add_node("report", lambda s: report_workflow(s, re))

        workflow.set_entry_point("reproduce")
        workflow.add_edge("reproduce", "diagnose")
        workflow.add_edge("diagnose", "routing")

        workflow.add_conditional_edges(
            "routing",
            self.routing_decision,
            {"dev": "dev", "config": "config", "maint": "maint", "report": "report"},
        )

        workflow.add_edge("dev", END)
        workflow.add_edge("config", END)
        workflow.add_edge("maint", END)
        workflow.add_edge("report", END)

        return workflow
