"""TrendAgent — detects directional trends in numeric time-series fields."""
import logging
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from app.agents.state import AgentState

logger = logging.getLogger(__name__)

MIN_POINTS = 5  # minimum data points to attempt trend detection


def _detect_trend(series: pd.Series) -> dict:
    """Fit a linear regression and classify the trend direction."""
    clean = series.dropna().reset_index(drop=True)
    if len(clean) < MIN_POINTS:
        return {"direction": "insufficient_data", "slope": None, "r_squared": None}

    x = np.arange(len(clean), dtype=float)
    y = clean.values.astype(float)

    # Linear regression via least squares
    x_mean, y_mean = x.mean(), y.mean()
    slope = float(np.sum((x - x_mean) * (y - y_mean)) / np.sum((x - x_mean) ** 2))
    intercept = float(y_mean - slope * x_mean)

    y_pred = slope * x + intercept
    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - y_mean) ** 2))
    r_squared = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

    # Classify direction
    relative_slope = slope / abs(y_mean) if abs(y_mean) > 1e-9 else slope
    if r_squared < 0.1:
        direction = "flat"
    elif relative_slope > 0.01:
        direction = "upward"
    elif relative_slope < -0.01:
        direction = "downward"
    else:
        direction = "flat"

    return {
        "direction": direction,
        "slope": round(slope, 6),
        "intercept": round(intercept, 6),
        "r_squared": round(r_squared, 4),
        "n_points": len(clean),
    }


def trend_agent(state: AgentState) -> AgentState:
    """Detect directional trends in all numeric columns of the DataFrame."""
    source_id = state.get("source_id", "unknown")
    df: pd.DataFrame = state.get("dataframe")

    logs = list(state.get("logs", []))
    errors = dict(state.get("errors", {}))

    log_entry = {
        "agent_name": "TrendAgent",
        "source_id": source_id,
        "started_at": datetime.now(tz=timezone.utc).isoformat(),
        "status": "running",
    }

    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        errors["TrendAgent"] = "No DataFrame available"
        log_entry.update({"status": "error", "error_message": errors["TrendAgent"]})
        logs.append(log_entry)
        return {**state, "trends": [], "logs": logs, "errors": errors}

    try:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        trends = []

        for col in numeric_cols:
            result = _detect_trend(df[col])
            trends.append(
                {
                    "column": col,
                    "direction": result["direction"],
                    "slope": result["slope"],
                    "r_squared": result["r_squared"],
                    "n_points": result.get("n_points"),
                    "detected_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            )

        significant = [t for t in trends if t["direction"] in ("upward", "downward")]

        log_entry.update(
            {
                "status": "success",
                "completed_at": datetime.now(tz=timezone.utc).isoformat(),
                "output_summary": (
                    f"Analyzed {len(numeric_cols)} numeric columns; "
                    f"{len(significant)} significant trends found"
                ),
            }
        )
        logs.append(log_entry)

        return {**state, "trends": trends, "logs": logs, "errors": errors}

    except Exception as exc:
        logger.exception("TrendAgent failed for source %s", source_id)
        error_msg = str(exc)
        log_entry.update({"status": "error", "error_message": error_msg})
        logs.append(log_entry)
        errors["TrendAgent"] = error_msg
        return {**state, "trends": [], "logs": logs, "errors": errors}
