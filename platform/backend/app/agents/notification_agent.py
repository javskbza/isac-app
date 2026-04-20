"""NotificationAgent — creates in-app notification records for anomalies and forecasts."""
import logging
import uuid
from datetime import datetime, timezone
from app.agents.state import AgentState

logger = logging.getLogger(__name__)

NOTIFIABLE_TYPES = {"anomaly", "forecast", "trend"}


def notification_agent(state: AgentState) -> AgentState:
    """Create notification records for high-priority insights.

    In a real deployment this would write to the DB and fan-out to all active users.
    Here we produce notification payloads for the caller to persist.
    """
    source_id = state.get("source_id", "unknown")
    logs = list(state.get("logs", []))
    errors = dict(state.get("errors", {}))
    insights = state.get("insights", [])

    log_entry = {
        "agent_name": "NotificationAgent",
        "source_id": source_id,
        "started_at": datetime.now(tz=timezone.utc).isoformat(),
        "status": "running",
    }

    try:
        notification_ids = []
        notifications = []

        for insight in insights:
            if insight.get("type") not in NOTIFIABLE_TYPES:
                continue

            notif_id = str(uuid.uuid4())
            notification_ids.append(notif_id)
            notifications.append(
                {
                    "id": notif_id,
                    "insight_id": insight.get("id"),  # will be set after DB persist
                    "title": insight["title"],
                    "body": insight["body"],
                    "insight_type": insight["type"],
                    "source_id": source_id,
                    "is_read": False,
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            )

        log_entry.update(
            {
                "status": "success",
                "completed_at": datetime.now(tz=timezone.utc).isoformat(),
                "output_summary": f"Queued {len(notifications)} notification(s) for delivery",
            }
        )
        logs.append(log_entry)

        return {
            **state,
            "notification_ids": notification_ids,
            "notifications_payload": notifications,
            "logs": logs,
            "errors": errors,
        }

    except Exception as exc:
        logger.exception("NotificationAgent failed for source %s", source_id)
        error_msg = str(exc)
        log_entry.update({"status": "error", "error_message": error_msg})
        logs.append(log_entry)
        errors["NotificationAgent"] = error_msg
        return {**state, "notification_ids": [], "logs": logs, "errors": errors}
