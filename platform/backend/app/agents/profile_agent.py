"""ProfileAgent — computes statistics: nulls, distributions, min/max, cardinality."""
import logging
from datetime import datetime, timezone
from typing import Any
import pandas as pd
import numpy as np
from app.agents.state import AgentState

logger = logging.getLogger(__name__)


def _safe_stat(value: Any) -> Any:
    """Convert numpy types to Python primitives for JSON serialization."""
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value) if not np.isnan(value) else None
    if isinstance(value, float) and np.isnan(value):
        return None
    return value


def profile_agent(state: AgentState) -> AgentState:
    """Compute per-column statistics from the ingested DataFrame."""
    source_id = state.get("source_id", "unknown")
    df: pd.DataFrame = state.get("dataframe")

    logs = list(state.get("logs", []))
    errors = dict(state.get("errors", {}))

    log_entry = {
        "agent_name": "ProfileAgent",
        "source_id": source_id,
        "started_at": datetime.now(tz=timezone.utc).isoformat(),
        "status": "running",
    }

    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        errors["ProfileAgent"] = "No DataFrame available (IngestAgent may have failed)"
        log_entry.update({"status": "error", "error_message": errors["ProfileAgent"]})
        logs.append(log_entry)
        return {**state, "logs": logs, "errors": errors}

    try:
        statistics: dict = {}
        null_rates: dict = {}
        distributions: dict = {}

        total_rows = len(df)

        for col in df.columns:
            series = df[col]
            null_count = int(series.isna().sum())
            null_rate = null_count / total_rows if total_rows > 0 else 0.0
            null_rates[col] = round(null_rate, 4)

            col_stats: dict = {
                "dtype": str(series.dtype),
                "null_count": null_count,
                "null_rate": round(null_rate, 4),
                "count": int(series.notna().sum()),
            }

            if pd.api.types.is_numeric_dtype(series):
                col_stats.update(
                    {
                        "min": _safe_stat(series.min()),
                        "max": _safe_stat(series.max()),
                        "mean": _safe_stat(series.mean()),
                        "median": _safe_stat(series.median()),
                        "std": _safe_stat(series.std()),
                        "cardinality": int(series.nunique()),
                    }
                )
                # Histogram buckets (up to 10)
                try:
                    counts, bin_edges = np.histogram(series.dropna(), bins=min(10, int(series.nunique())))
                    distributions[col] = {
                        "type": "histogram",
                        "counts": counts.tolist(),
                        "bin_edges": [round(float(e), 4) for e in bin_edges],
                    }
                except Exception:
                    distributions[col] = {"type": "histogram", "counts": [], "bin_edges": []}
            else:
                # Categorical
                value_counts = series.value_counts().head(10).to_dict()
                col_stats.update(
                    {
                        "cardinality": int(series.nunique()),
                        "top_values": {str(k): int(v) for k, v in value_counts.items()},
                    }
                )
                distributions[col] = {
                    "type": "categorical",
                    "value_counts": {str(k): int(v) for k, v in value_counts.items()},
                }

            statistics[col] = col_stats

        profile = {
            "statistics": statistics,
            "null_rates": null_rates,
            "distributions": distributions,
            "total_rows": total_rows,
            "total_columns": len(df.columns),
            "profiled_at": datetime.now(tz=timezone.utc).isoformat(),
        }

        log_entry.update(
            {
                "status": "success",
                "completed_at": datetime.now(tz=timezone.utc).isoformat(),
                "output_summary": f"Profiled {len(df.columns)} columns across {total_rows} rows",
            }
        )
        logs.append(log_entry)

        return {**state, "profile": profile, "logs": logs, "errors": errors}

    except Exception as exc:
        logger.exception("ProfileAgent failed for source %s", source_id)
        error_msg = str(exc)
        log_entry.update({"status": "error", "error_message": error_msg})
        logs.append(log_entry)
        errors["ProfileAgent"] = error_msg
        return {**state, "logs": logs, "errors": errors}
