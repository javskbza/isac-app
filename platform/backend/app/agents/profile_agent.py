"""ProfileAgent — computes statistics, column classification, pk_candidate, KDE, and time-series."""
import logging
import re
from datetime import datetime, timezone
from typing import Any
import pandas as pd
import numpy as np
from app.agents.state import AgentState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Classification constants
# ---------------------------------------------------------------------------
DISCRETE_MAX_UNIQUE = 20
DISCRETE_MAX_RATIO = 0.05
_CODE_PATTERN = re.compile(
    r'\b(id|zip|code|year|yr|iso|fips|sku|num|no|nbr|pk|key|index)\b',
    re.IGNORECASE,
)


def _is_code_column(name: str) -> bool:
    return bool(_CODE_PATTERN.search(name))


def _classify_column(col_name: str, series: pd.Series, total_rows: int) -> str:
    dtype = series.dtype

    if pd.api.types.is_bool_dtype(dtype):
        return "categorical"

    if pd.api.types.is_object_dtype(dtype) or isinstance(dtype, pd.CategoricalDtype):
        return "categorical"

    if pd.api.types.is_datetime64_any_dtype(dtype) or pd.api.types.is_timedelta64_dtype(dtype):
        return "continuous"

    if pd.api.types.is_integer_dtype(dtype):
        return "discrete"

    if pd.api.types.is_float_dtype(dtype):
        if _is_code_column(col_name):
            return "discrete"
        unique_count = int(series.nunique())
        if unique_count <= DISCRETE_MAX_UNIQUE:
            return "discrete"
        unique_ratio = unique_count / total_rows if total_rows > 0 else 1.0
        if unique_ratio <= DISCRETE_MAX_RATIO:
            return "discrete"
        return "continuous"

    return "categorical"


# ---------------------------------------------------------------------------
# Stat helpers
# ---------------------------------------------------------------------------

def _safe_stat(value: Any) -> Any:
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value) if not np.isnan(value) else None
    if isinstance(value, float) and np.isnan(value):
        return None
    return value


def _compute_mode(series: pd.Series) -> Any:
    try:
        modes = series.dropna().mode()
        if modes.empty:
            return None
        return _safe_stat(modes.iloc[0])
    except Exception:
        return None


def _compute_kde(series: pd.Series, n_points: int = 200) -> list[dict]:
    """Compute a KDE curve using scipy.stats.gaussian_kde."""
    try:
        from scipy.stats import gaussian_kde
        clean = series.dropna().astype(float)
        if len(clean) < 5:
            return []
        kde = gaussian_kde(clean)
        x_min, x_max = float(clean.min()), float(clean.max())
        padding = (x_max - x_min) * 0.1 or 1.0
        x = np.linspace(x_min - padding, x_max + padding, n_points)
        y = kde(x)
        return [{"x": round(float(xi), 4), "y": round(float(yi), 6)} for xi, yi in zip(x, y)]
    except Exception:
        return []


def _compute_time_series(
    df: pd.DataFrame,
    numeric_col: str,
    date_col: str,
    max_points: int = 500,
) -> list[dict]:
    """
    Aggregate numeric_col against date_col.
    Auto-buckets: hourly ≤3 days, daily ≤90 days, weekly ≤1 year, monthly otherwise.
    """
    try:
        tmp = df[[date_col, numeric_col]].dropna()
        if len(tmp) < 2:
            return []
        tmp = tmp.copy()
        tmp[date_col] = pd.to_datetime(tmp[date_col], errors="coerce")
        tmp = tmp.dropna(subset=[date_col])
        if len(tmp) < 2:
            return []

        date_range = (tmp[date_col].max() - tmp[date_col].min()).days
        if date_range <= 3:
            freq = "h"
        elif date_range <= 90:
            freq = "D"
        elif date_range <= 365:
            freq = "W"
        else:
            freq = "ME"

        aggregated = (
            tmp.set_index(date_col)
            .resample(freq)[numeric_col]
            .mean()
            .dropna()
        )

        # Downsample if needed
        if len(aggregated) > max_points:
            step = len(aggregated) // max_points
            aggregated = aggregated.iloc[::step]

        return [
            {"date": idx.isoformat(), "value": round(float(val), 4)}
            for idx, val in aggregated.items()
        ]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Main agent
# ---------------------------------------------------------------------------

def profile_agent(state: AgentState) -> AgentState:
    """Compute per-column statistics, classification, pk_candidate, KDE, and time-series."""
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
        total_columns = len(df.columns)

        # Identify date columns for time-series computation
        date_columns = [
            col for col in df.columns
            if pd.api.types.is_datetime64_any_dtype(df[col])
        ]

        categorical_count = 0
        discrete_count = 0
        continuous_count = 0

        for col in df.columns:
            series = df[col]
            null_count = int(series.isna().sum())
            null_rate = null_count / total_rows if total_rows > 0 else 0.0
            null_rates[col] = round(null_rate, 4)

            classification = _classify_column(col, series, total_rows)
            if classification == "categorical":
                categorical_count += 1
            elif classification == "discrete":
                discrete_count += 1
            else:
                continuous_count += 1

            cardinality = int(series.nunique())
            pk_candidate = bool(null_rate == 0.0 and cardinality == total_rows and total_rows > 0)

            col_stats: dict = {
                "dtype": str(series.dtype),
                "null_count": null_count,
                "null_rate": round(null_rate, 4),
                "count": int(series.notna().sum()),
                "cardinality": cardinality,
                "data_classification": classification,
                "pk_candidate": pk_candidate,
                "mode": _compute_mode(series),
            }

            if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series.dtype):
                col_stats.update(
                    {
                        "min": _safe_stat(series.min()),
                        "max": _safe_stat(series.max()),
                        "mean": _safe_stat(series.mean()),
                        "median": _safe_stat(series.median()),
                        "std": _safe_stat(series.std()),
                    }
                )
                # KDE curve (numeric columns)
                col_stats["kde"] = _compute_kde(series)

                # Pre-aggregated time-series for each date column
                if date_columns:
                    col_stats["time_series"] = {
                        date_col: _compute_time_series(df, col, date_col)
                        for date_col in date_columns
                    }
                else:
                    col_stats["time_series"] = {}

                # Histogram buckets (up to 10)
                try:
                    counts, bin_edges = np.histogram(series.dropna(), bins=min(10, max(1, int(series.nunique()))))
                    distributions[col] = {
                        "type": "histogram",
                        "counts": counts.tolist(),
                        "bin_edges": [round(float(e), 4) for e in bin_edges],
                    }
                except Exception:
                    distributions[col] = {"type": "histogram", "counts": [], "bin_edges": []}
            else:
                value_counts = series.value_counts().head(10).to_dict()
                col_stats["top_values"] = {str(k): int(v) for k, v in value_counts.items()}
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
            "total_columns": total_columns,
            "categorical_count": categorical_count,
            "discrete_count": discrete_count,
            "continuous_count": continuous_count,
            "profiled_at": datetime.now(tz=timezone.utc).isoformat(),
        }

        log_entry.update(
            {
                "status": "success",
                "completed_at": datetime.now(tz=timezone.utc).isoformat(),
                "output_summary": (
                    f"Profiled {total_columns} columns across {total_rows} rows "
                    f"(categorical={categorical_count}, discrete={discrete_count}, continuous={continuous_count})"
                ),
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
