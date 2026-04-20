"""AnomalyAgent — uses Isolation Forest to flag statistical outliers."""
import logging
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from app.agents.state import AgentState

logger = logging.getLogger(__name__)

MIN_ROWS = 10
CONTAMINATION = 0.05  # expected fraction of outliers


def anomaly_agent(state: AgentState) -> AgentState:
    """Detect anomalies using Isolation Forest on numeric features."""
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
        return {**state, "anomalies": [], "logs": logs, "errors": errors}

    try:
        numeric_df = df.select_dtypes(include=[np.number]).dropna()

        if len(numeric_df) < MIN_ROWS or numeric_df.empty:
            log_entry.update(
                {
                    "status": "success",
                    "completed_at": datetime.now(tz=timezone.utc).isoformat(),
                    "output_summary": "Insufficient numeric data for anomaly detection",
                }
            )
            logs.append(log_entry)
            return {**state, "anomalies": [], "logs": logs, "errors": errors}

        model = IsolationForest(contamination=CONTAMINATION, random_state=42, n_estimators=100)
        preds = model.fit_predict(numeric_df)
        scores = model.score_samples(numeric_df)

        anomaly_mask = preds == -1
        anomaly_indices = numeric_df.index[anomaly_mask].tolist()
        anomaly_scores = scores[anomaly_mask].tolist()

        anomalies = []
        for idx, score in zip(anomaly_indices, anomaly_scores):
            row_data = numeric_df.loc[idx].to_dict()
            anomalies.append(
                {
                    "row_index": int(idx),
                    "anomaly_score": round(float(score), 4),
                    "values": {k: float(v) if not np.isnan(v) else None for k, v in row_data.items()},
                    "detected_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            )

        log_entry.update(
            {
                "status": "success",
                "completed_at": datetime.now(tz=timezone.utc).isoformat(),
                "output_summary": (
                    f"Detected {len(anomalies)} anomalies in {len(numeric_df)} rows "
                    f"({len(numeric_df.columns)} numeric features)"
                ),
            }
        )
        logs.append(log_entry)

        return {**state, "anomalies": anomalies, "logs": logs, "errors": errors}

    except Exception as exc:
        logger.exception("AnomalyAgent failed for source %s", source_id)
        error_msg = str(exc)
        log_entry.update({"status": "error", "error_message": error_msg})
        logs.append(log_entry)
        errors["AnomalyAgent"] = error_msg
        return {**state, "anomalies": [], "logs": logs, "errors": errors}
