"""AnomalyAgent — Isolation Forest (v1) + z-score (v2, powers Card #5)."""
import logging
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from app.agents.state import AgentState

logger = logging.getLogger(__name__)

MIN_ROWS = 10
CONTAMINATION = 0.05
ZSCORE_THRESHOLD = 3.0


# ---------------------------------------------------------------------------
# Z-score path (powers Card #5)
# ---------------------------------------------------------------------------

def _compute_zscore_anomalies(df: pd.DataFrame) -> list[dict]:
    """
    For every numeric column, flag rows where abs(z_score) > 3.
    Returns a flat list of anomaly records — one per (row, column) pair.
    Each record includes the full row contents for the audit panel.
    """
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    anomalies: list[dict] = []
    now = datetime.now(tz=timezone.utc).isoformat()

    for col in numeric_cols:
        series = df[col].dropna()
        if len(series) < 2:
            continue
        mean = float(series.mean())
        std = float(series.std())
        if std == 0:
            continue

        z_scores = (series - mean) / std
        flagged_idx = series.index[z_scores.abs() > ZSCORE_THRESHOLD]

        for idx in flagged_idx:
            row = df.loc[idx]
            full_row: dict = {}
            for k, v in row.items():
                if pd.isna(v):
                    full_row[str(k)] = None
                elif isinstance(v, (np.integer,)):
                    full_row[str(k)] = int(v)
                elif isinstance(v, (np.floating,)):
                    full_row[str(k)] = float(v)
                else:
                    full_row[str(k)] = str(v)

            anomalies.append({
                "row_index": int(idx),
                "column": col,
                "value": float(df.loc[idx, col]),
                "z_score": round(float(z_scores.loc[idx]), 4),
                "mean": round(mean, 4),
                "std": round(std, 4),
                "full_row": full_row,
                "detected_at": now,
            })

    return anomalies


# ---------------------------------------------------------------------------
# Main agent
# ---------------------------------------------------------------------------

def anomaly_agent(state: AgentState) -> AgentState:
    """Run Isolation Forest (v1 path) and z-score detection (v2 path)."""
    source_id = state.get("source_id", "unknown")
    df: pd.DataFrame = state.get("dataframe")

    logs = list(state.get("logs", []))
    errors = dict(state.get("errors", {}))

    log_entry = {
        "agent_name": "AnomalyAgent",
        "source_id": source_id,
        "started_at": datetime.now(tz=timezone.utc).isoformat(),
        "status": "running",
    }

    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        errors["AnomalyAgent"] = "No DataFrame available"
        log_entry.update({"status": "error", "error_message": errors["AnomalyAgent"]})
        logs.append(log_entry)
        return {**state, "anomalies": [], "zscore_anomalies": [], "logs": logs, "errors": errors}

    try:
        # ------------------------------------------------------------------
        # v1 path: Isolation Forest
        # ------------------------------------------------------------------
        numeric_df = df.select_dtypes(include=[np.number]).dropna()
        isolation_anomalies: list[dict] = []

        if len(numeric_df) >= MIN_ROWS and not numeric_df.empty:
            model = IsolationForest(contamination=CONTAMINATION, random_state=42, n_estimators=100)
            preds = model.fit_predict(numeric_df)
            scores = model.score_samples(numeric_df)

            anomaly_mask = preds == -1
            anomaly_indices = numeric_df.index[anomaly_mask].tolist()
            anomaly_scores = scores[anomaly_mask].tolist()

            for idx, score in zip(anomaly_indices, anomaly_scores):
                row_data = numeric_df.loc[idx].to_dict()
                isolation_anomalies.append({
                    "row_index": int(idx),
                    "anomaly_score": round(float(score), 4),
                    "values": {k: float(v) if not np.isnan(v) else None for k, v in row_data.items()},
                    "detected_at": datetime.now(tz=timezone.utc).isoformat(),
                })

        # ------------------------------------------------------------------
        # v2 path: Z-score per column
        # ------------------------------------------------------------------
        zscore_anomalies = _compute_zscore_anomalies(df)

        log_entry.update({
            "status": "success",
            "completed_at": datetime.now(tz=timezone.utc).isoformat(),
            "output_summary": (
                f"Isolation Forest: {len(isolation_anomalies)} anomalies; "
                f"Z-score (>3σ): {len(zscore_anomalies)} flagged values"
            ),
        })
        logs.append(log_entry)

        return {
            **state,
            "anomalies": isolation_anomalies,
            "zscore_anomalies": zscore_anomalies,
            "logs": logs,
            "errors": errors,
        }

    except Exception as exc:
        logger.exception("AnomalyAgent failed for source %s", source_id)
        error_msg = str(exc)
        log_entry.update({"status": "error", "error_message": error_msg})
        logs.append(log_entry)
        errors["AnomalyAgent"] = error_msg
        return {**state, "anomalies": [], "zscore_anomalies": [], "logs": logs, "errors": errors}
