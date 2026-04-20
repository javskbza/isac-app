"""OrchestratorAgent + RouterAgent — LangGraph graph wiring all 10 agents."""
import logging
from typing import Literal
from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.ingest_agent import ingest_agent
from app.agents.profile_agent import profile_agent
from app.agents.trend_agent import trend_agent
from app.agents.forecast_agent import forecast_agent
from app.agents.anomaly_agent import anomaly_agent
from app.agents.pattern_agent import pattern_agent
from app.agents.insight_agent import insight_agent
from app.agents.notification_agent import notification_agent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RouterAgent: decides whether to continue or abort after ingest
# ---------------------------------------------------------------------------

def router_agent(state: AgentState) -> Literal["analytics", "end_error"]:
    """Route: if ingest succeeded, proceed to analytics; otherwise abort."""
    if "IngestAgent" in state.get("errors", {}):
        logger.warning("RouterAgent: IngestAgent failed — routing to end_error")
        return "end_error"
    return "analytics"


# ---------------------------------------------------------------------------
# OrchestratorAgent: builds and returns the compiled LangGraph pipeline
# ---------------------------------------------------------------------------

def build_agent_graph() -> StateGraph:
    """Wire all 10 agents into a LangGraph StateGraph.

    Execution order:
        IngestAgent
            → RouterAgent (conditional: success → analytics, failure → END)
            → ProfileAgent (parallel fan-out via separate nodes)
            → TrendAgent
            → ForecastAgent
            → AnomalyAgent
            → PatternAgent
            → InsightAgent
            → NotificationAgent
            → END
    """
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("ingest", ingest_agent)
    graph.add_node("profile", profile_agent)
    graph.add_node("trend", trend_agent)
    graph.add_node("forecast", forecast_agent)
    graph.add_node("anomaly", anomaly_agent)
    graph.add_node("pattern", pattern_agent)
    graph.add_node("insight", insight_agent)
    graph.add_node("notification", notification_agent)

    # Entry point
    graph.set_entry_point("ingest")

    # Conditional routing after ingest
    graph.add_conditional_edges(
        "ingest",
        router_agent,
        {
            "analytics": "profile",
            "end_error": END,
        },
    )

    # Linear pipeline after profile
    graph.add_edge("profile", "trend")
    graph.add_edge("trend", "forecast")
    graph.add_edge("forecast", "anomaly")
    graph.add_edge("anomaly", "pattern")
    graph.add_edge("pattern", "insight")
    graph.add_edge("insight", "notification")
    graph.add_edge("notification", END)

    return graph


# Compiled graph (singleton for reuse across Celery tasks)
_compiled_graph = None


def get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_agent_graph().compile()
    return _compiled_graph


def run_pipeline(source_id: str, source_type: str, source_config: dict) -> AgentState:
    """Run the full agent pipeline for a given data source.

    This is the main entry point called by Celery tasks or directly.
    """
    initial_state: AgentState = {
        "source_id": source_id,
        "source_type": source_type,
        "source_config": source_config,
        "logs": [],
        "errors": {},
    }

    graph = get_compiled_graph()
    final_state: AgentState = graph.invoke(initial_state)
    return final_state
