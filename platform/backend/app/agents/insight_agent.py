"""InsightAgent — synthesizes agent outputs into human-readable insight cards."""
import logging
from datetime import datetime, timezone
from app.agents.state import AgentState

logger = logging.getLogger(__name__)


def _trend_insight(trend: dict, source_id: str) -> dict:
    col = trend["column"]
    direction = trend["direction"]
    r2 = trend.get("r_squared", 0) or 0
    strength = "strong" if r2 > 0.7 else "moderate" if r2 > 0.4 else "weak"

    return {
        "source_id": source_id,
        "type": "trend",
        "title": f"{direction.capitalize()} trend detected in '{col}'",
        "body": (
            f"Column '{col}' shows a {strength} {direction} trend "
            f"(R²={r2:.2f}). This may indicate a meaningful directional shift "
            f"in this metric over the observed period."
        ),
        "data": trend,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }


def _anomaly_insight(anomalies: list, source_id: str) -> dict | None:
    if not anomalies:
        return None
    count = len(anomalies)
    worst = min(anomalies, key=lambda a: a["anomaly_score"])
    return {
        "source_id": source_id,
        "type": "anomaly",
        "title": f"{count} anomalous row{'s' if count > 1 else ''} detected",
        "body": (
            f"Isolation Forest flagged {count} data point{'s' if count > 1 else ''} as anomalous. "
            f"The most unusual record is at row {worst['row_index']} "
            f"(anomaly score: {worst['anomaly_score']:.3f}). "
            "Review these rows for data quality issues or genuine outliers."
        ),
        "data": {"count": count, "worst_row": worst},
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }


def _forecast_insight(forecast: dict, source_id: str) -> dict:
    col = forecast["column"]
    periods = forecast["periods"]
    last = forecast["forecast"][-1] if forecast["forecast"] else {}
    yhat = last.get("yhat")

    return {
        "source_id": source_id,
        "type": "forecast",
        "title": f"Forecast ready for '{col}'",
        "body": (
            f"A {periods}-period forecast has been generated for '{col}'. "
            + (f"Projected value at the end of the horizon: {yhat:.2f}." if yhat is not None else "")
        ),
        "data": forecast,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }


def _pattern_insight(pattern: dict, source_id: str) -> dict:
    return {
        "source_id": source_id,
        "type": "pattern",
        "title": f"Pattern identified: {pattern['type'].replace('_', ' ').title()}",
        "body": pattern["description"],
        "data": pattern["data"],
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }


def _summary_insight(state: AgentState) -> dict:
    source_id = state.get("source_id", "unknown")
    raw_data = state.get("raw_data", {})
    rows = raw_data.get("row_count", "?")
    cols = raw_data.get("columns", [])

    trend_count = len([t for t in state.get("trends", []) if t.get("direction") not in ("flat", "insufficient_data")])
    anomaly_count = len(state.get("anomalies", []))
    forecast_count = len(state.get("forecasts", []))
    pattern_count = len(state.get("patterns", []))

    return {
        "source_id": source_id,
        "type": "summary",
        "title": "Data source analysis complete",
        "body": (
            f"Analysis of this data source ({rows} rows, {len(cols)} columns) is complete. "
            f"Found: {trend_count} significant trend(s), {anomaly_count} anomaly/anomalies, "
            f"{forecast_count} forecast(s), and {pattern_count} pattern(s)."
        ),
        "data": {
            "rows": rows,
            "columns": len(cols),
            "trends": trend_count,
            "anomalies": anomaly_count,
            "forecasts": forecast_count,
            "patterns": pattern_count,
        },
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }


def insight_agent(state: AgentState) -> AgentState:
    """Synthesize all agent findings into human-readable insight cards."""
    source_id = state.get("source_id", "unknown")
    logs = list(state.get("logs", []))
    errors = dict(state.get("errors", {}))

    log_entry = {
        "agent_name": "InsightAgent",
        "source_id": source_id,
        "started_at": datetime.now(tz=timezone.utc).isoformat(),
        "status": "running",
    }

    try:
        insights = []

        # Always produce a summary insight
        insights.append(_summary_insight(state))

        # Trend insights (only for significant trends)
        for trend in state.get("trends", []):
            if trend.get("direction") not in ("flat", "insufficient_data"):
                insights.append(_trend_insight(trend, source_id))

        # Anomaly insight
        anomaly_card = _anomaly_insight(state.get("anomalies", []), source_id)
        if anomaly_card:
            insights.append(anomaly_card)

        # Forecast insights
        for forecast in state.get("forecasts", []):
            insights.append(_forecast_insight(forecast, source_id))

        # Pattern insights
        for pattern in state.get("patterns", []):
            insights.append(_pattern_insight(pattern, source_id))

        log_entry.update(
            {
                "status": "success",
                "completed_at": datetime.now(tz=timezone.utc).isoformat(),
                "output_summary": f"Generated {len(insights)} insight card(s)",
            }
        )
        logs.append(log_entry)

        return {**state, "insights": insights, "logs": logs, "errors": errors}

    except Exception as exc:
        logger.exception("InsightAgent failed for source %s", source_id)
        error_msg = str(exc)
        log_entry.update({"status": "error", "error_message": error_msg})
        logs.append(log_entry)
        errors["InsightAgent"] = error_msg
        return {**state, "insights": [], "logs": logs, "errors": errors}
