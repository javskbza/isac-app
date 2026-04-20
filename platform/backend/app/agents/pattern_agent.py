"""PatternAgent — identifies seasonality, recurring patterns, and correlations."""
import logging
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from app.agents.state import AgentState

logger = logging.getLogger(__name__)

MIN_ROWS = 10


def _compute_correlations(df: pd.DataFrame) -> dict:
    """Compute pairwise Pearson correlations for numeric columns."""
    numeric_df = df.select_dtypes(include=[np.number])
    if numeric_df.shape[1] < 2:
        return {}
    corr_matrix = numeric_df.corr()
    strong = []
    cols = corr_matrix.columns.tolist()
    for i, col_a in enumerate(cols):
        for col_b in cols[i + 1:]:
            val = corr_matrix.loc[col_a, col_b]
            if abs(val) >= 0.7 and not np.isnan(val):
                strong.append(
                    {
                        "column_a": col_a,
                        "column_b": col_b,
                        "correlation": round(float(val), 4),
                        "direction": "positive" if val > 0 else "negative",
                    }
                )
    return {"strong_correlations": strong, "matrix_columns": cols}


def _detect_seasonality(series: pd.Series) -> dict:
    """Simple seasonality check via autocorrelation at common lags."""
    clean = series.dropna()
    if len(clean) < MIN_ROWS:
        return {"detected": False}

    try:
        lags_to_check = [7, 12, 24, 30, 52, 365]
        detected_lags = []
        for lag in lags_to_check:
            if lag >= len(clean):
                continue
            autocorr = clean.autocorr(lag=lag)
            if autocorr is not None and not np.isnan(autocorr) and abs(autocorr) > 0.5:
                detected_lags.append({"lag": lag, "autocorrelation": round(float(autocorr), 4)})
        return {"detected": bool(detected_lags), "lags": detected_lags}
    except Exception:
        return {"detected": False}


def pattern_agent(state: AgentState) -> AgentState:
    """Identify patterns, seasonality, and correlations in the dataset."""
    source_id = state.get("source_id", "unknown")
    df: pd.DataFrame = state.get("dataframe")

    logs = list(state.get("logs", []))
    errors = dict(state.get("errors", {}))

    log_entry = {
        "agent_name": "PatternAgent",
        "source_id": source_id,
        "started_at": datetime.now(tz=timezone.utc).isoformat(),
        "status": "running",
    }

    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        errors["PatternAgent"] = "No DataFrame available"
        log_entry.update({"status": "error", "error_message": errors["PatternAgent"]})
        logs.append(log_entry)
        return {**state, "patterns": [], "logs": logs, "errors": errors}

    try:
        patterns = []

        # Correlation patterns
        corr_result = _compute_correlations(df)
        if corr_result.get("strong_correlations"):
            patterns.append(
                {
                    "type": "correlation",
                    "description": f"Found {len(corr_result['strong_correlations'])} strong correlations (|r| >= 0.7)",
                    "data": corr_result,
                    "detected_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            )

        # Seasonality per numeric column
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        for col in numeric_cols:
            seasonality = _detect_seasonality(df[col])
            if seasonality.get("detected"):
                lags = [str(l["lag"]) for l in seasonality.get("lags", [])]
                patterns.append(
                    {
                        "type": "seasonality",
                        "column": col,
                        "description": f"Seasonality detected in '{col}' at lags: {', '.join(lags)}",
                        "data": seasonality,
                        "detected_at": datetime.now(tz=timezone.utc).isoformat(),
                    }
                )

        # Recurring value patterns (high-frequency values in categorical columns)
        categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
        for col in categorical_cols:
            vc = df[col].value_counts(normalize=True)
            dominant = vc[vc > 0.5]
            if not dominant.empty:
                top_val = dominant.index[0]
                pct = round(float(dominant.iloc[0]) * 100, 1)
                patterns.append(
                    {
                        "type": "dominant_value",
                        "column": col,
                        "description": f"'{top_val}' dominates column '{col}' ({pct}% of values)",
                        "data": {"value": str(top_val), "percentage": pct},
                        "detected_at": datetime.now(tz=timezone.utc).isoformat(),
                    }
                )

        log_entry.update(
            {
                "status": "success",
                "completed_at": datetime.now(tz=timezone.utc).isoformat(),
                "output_summary": f"Identified {len(patterns)} patterns",
            }
        )
        logs.append(log_entry)

        return {**state, "patterns": patterns, "logs": logs, "errors": errors}

    except Exception as exc:
        logger.exception("PatternAgent failed for source %s", source_id)
        error_msg = str(exc)
        log_entry.update({"status": "error", "error_message": error_msg})
        logs.append(log_entry)
        errors["PatternAgent"] = error_msg
        return {**state, "patterns": [], "logs": logs, "errors": errors}
