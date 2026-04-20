"""ForecastAgent — generates short-horizon forecasts using Prophet."""
import logging
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from app.agents.state import AgentState

logger = logging.getLogger(__name__)

MIN_ROWS = 10
FORECAST_PERIODS = 7  # default: 7 future periods


def _forecast_column(df: pd.DataFrame, col: str, periods: int = FORECAST_PERIODS) -> dict | None:
    """Attempt a Prophet forecast for the given column.

    Returns None if forecasting is not possible (insufficient data, import error, etc.).
    """
    try:
        from prophet import Prophet  # type: ignore
    except ImportError:
        logger.warning("Prophet not installed; skipping forecast for column %s", col)
        return None

    series = df[col].dropna()
    if len(series) < MIN_ROWS:
        return None

    # Build prophet DataFrame — use row index as time proxy if no datetime index
    if isinstance(df.index, pd.DatetimeIndex):
        ds = df.index[series.index]
    else:
        ds = pd.date_range(start="2020-01-01", periods=len(series), freq="D")

    prophet_df = pd.DataFrame({"ds": ds, "y": series.values})

    try:
        model = Prophet(daily_seasonality=False, weekly_seasonality=False, yearly_seasonality=False)
        model.fit(prophet_df)
        future = model.make_future_dataframe(periods=periods)
        forecast = model.predict(future)

        future_forecast = forecast.tail(periods)[["ds", "yhat", "yhat_lower", "yhat_upper"]]
        return {
            "column": col,
            "periods": periods,
            "forecast": [
                {
                    "ds": row["ds"].isoformat(),
                    "yhat": round(float(row["yhat"]), 4),
                    "yhat_lower": round(float(row["yhat_lower"]), 4),
                    "yhat_upper": round(float(row["yhat_upper"]), 4),
                }
                for _, row in future_forecast.iterrows()
            ],
            "forecasted_at": datetime.now(tz=timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.warning("Prophet forecast failed for column %s: %s", col, exc)
        return None


def forecast_agent(state: AgentState) -> AgentState:
    """Generate short-horizon forecasts for numeric columns."""
    source_id = state.get("source_id", "unknown")
    df: pd.DataFrame = state.get("dataframe")

    logs = list(state.get("logs", []))
    errors = dict(state.get("errors", {}))

    log_entry = {
        "agent_name": "ForecastAgent",
        "source_id": source_id,
        "started_at": datetime.now(tz=timezone.utc).isoformat(),
        "status": "running",
    }

    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        errors["ForecastAgent"] = "No DataFrame available"
        log_entry.update({"status": "error", "error_message": errors["ForecastAgent"]})
        logs.append(log_entry)
        return {**state, "forecasts": [], "logs": logs, "errors": errors}

    try:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        forecasts = []

        for col in numeric_cols:
            result = _forecast_column(df, col)
            if result:
                forecasts.append(result)

        log_entry.update(
            {
                "status": "success",
                "completed_at": datetime.now(tz=timezone.utc).isoformat(),
                "output_summary": f"Generated forecasts for {len(forecasts)} of {len(numeric_cols)} numeric columns",
            }
        )
        logs.append(log_entry)

        return {**state, "forecasts": forecasts, "logs": logs, "errors": errors}

    except Exception as exc:
        logger.exception("ForecastAgent failed for source %s", source_id)
        error_msg = str(exc)
        log_entry.update({"status": "error", "error_message": error_msg})
        logs.append(log_entry)
        errors["ForecastAgent"] = error_msg
        return {**state, "forecasts": [], "logs": logs, "errors": errors}
