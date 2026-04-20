"""Shared LangGraph state for the agent pipeline."""
from typing import TypedDict, Optional, Any
import pandas as pd


class AgentState(TypedDict, total=False):
    # Input
    source_id: str
    source_config: dict
    source_type: str  # "file" | "rest_api"

    # Ingest output
    dataframe: Any  # pd.DataFrame (not serializable natively; held in memory)
    raw_data: dict   # JSON-serializable snapshot for DB

    # Profile output
    profile: dict    # column stats, null rates, distributions

    # Schema output
    schema: dict

    # Trend output
    trends: list[dict]

    # Forecast output
    forecasts: list[dict]

    # Anomaly output
    anomalies: list[dict]

    # Pattern output
    patterns: list[dict]

    # Insight output
    insights: list[dict]

    # Notifications created
    notification_ids: list[str]

    # Agent log entries
    logs: list[dict]

    # Error tracking
    errors: dict[str, str]
