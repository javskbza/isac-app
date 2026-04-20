"""OrchestratorAgent — sequential agent pipeline (ingest → profile → … → notification)."""
import logging
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

# Keep these for backwards-compat with any imports
build_agent_graph = None
get_compiled_graph = None


def run_pipeline(source_id: str, source_type: str, source_config: dict) -> AgentState:
    """Run the full agent pipeline sequentially for a given data source."""
    state: AgentState = {
        "source_id": source_id,
        "source_type": source_type,
        "source_config": source_config,
        "logs": [],
        "errors": {},
    }

    state = ingest_agent(state)

    if "IngestAgent" in state.get("errors", {}):
        logger.warning("IngestAgent failed for source %s — aborting pipeline", source_id)
        return state

    state = profile_agent(state)
    state = trend_agent(state)
    state = forecast_agent(state)
    state = anomaly_agent(state)
    state = pattern_agent(state)
    state = insight_agent(state)
    state = notification_agent(state)

    return state
