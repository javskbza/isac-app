"""IngestAgent — fetches and normalizes data from connectors into pandas DataFrames."""
import logging
from datetime import datetime, timezone
from app.connectors.registry import ConnectorRegistry
from app.agents.state import AgentState

logger = logging.getLogger(__name__)


def ingest_agent(state: AgentState) -> AgentState:
    """Fetch data from the configured connector and normalize to a DataFrame."""
    source_id = state.get("source_id", "unknown")
    source_type = state.get("source_type", "file")
    source_config = state.get("source_config", {})

    logs = list(state.get("logs", []))
    errors = dict(state.get("errors", {}))

    log_entry = {
        "agent_name": "IngestAgent",
        "source_id": source_id,
        "started_at": datetime.now(tz=timezone.utc).isoformat(),
        "status": "running",
    }

    try:
        connector = ConnectorRegistry.create(source_type, source_config)
        connector.connect(source_config)
        df = connector.fetch_data()
        schema = connector.get_schema()
        metadata = connector.get_metadata()

        # Build JSON-serializable snapshot
        raw_data = {
            "row_count": len(df),
            "columns": list(df.columns),
            "dtypes": {col: str(df[col].dtype) for col in df.columns},
            "sample": df.head(5).to_dict(orient="records"),
        }

        schema_dict = {
            "row_count": schema.row_count,
            "inferred_at": schema.inferred_at,
            "columns": [
                {
                    "name": c.name,
                    "dtype": c.dtype,
                    "nullable": c.nullable,
                    "cardinality": c.cardinality,
                    "sample_values": c.sample_values,
                }
                for c in schema.columns
            ],
        }

        log_entry.update(
            {
                "status": "success",
                "completed_at": datetime.now(tz=timezone.utc).isoformat(),
                "output_summary": f"Ingested {len(df)} rows, {len(df.columns)} columns from {metadata.name}",
            }
        )
        logs.append(log_entry)

        return {
            **state,
            "dataframe": df,
            "raw_data": raw_data,
            "schema": schema_dict,
            "logs": logs,
            "errors": errors,
        }

    except Exception as exc:
        logger.exception("IngestAgent failed for source %s", source_id)
        error_msg = str(exc)
        log_entry.update(
            {
                "status": "error",
                "completed_at": datetime.now(tz=timezone.utc).isoformat(),
                "error_message": error_msg,
            }
        )
        logs.append(log_entry)
        errors["IngestAgent"] = error_msg

        return {**state, "logs": logs, "errors": errors}
