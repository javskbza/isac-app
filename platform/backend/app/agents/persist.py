"""Persist pipeline results (profile, insights, notifications) to the database."""
import logging
import uuid
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.database import AsyncSessionLocal
from app.models.data_source import DataSource, SourceStatus
from app.models.profile import Profile
from app.models.insight import Insight, InsightType
from app.models.notification import Notification
from app.models.agent_log import AgentLog, AgentStatus
from app.models.user import User
from app.agents.state import AgentState

logger = logging.getLogger(__name__)

NOTIFIABLE_TYPES = {"anomaly", "forecast", "trend"}


async def persist_pipeline_results(state: AgentState) -> None:
    """Write profile, insights, and notifications to the DB; update source status."""
    source_id = state.get("source_id")
    errors = state.get("errors", {})

    async with AsyncSessionLocal() as db:
        try:
            # Fetch source
            result = await db.execute(
                select(DataSource).where(DataSource.id == uuid.UUID(source_id))
            )
            source = result.scalar_one_or_none()
            if source is None:
                logger.error("Source %s not found during persist", source_id)
                return

            if errors:
                source.status = SourceStatus.error
                await db.commit()
                logger.warning("Pipeline errors for source %s: %s", source_id, errors)
                return

            # Persist profile
            profile_data = state.get("profile")
            if profile_data:
                profile = Profile(
                    data_source_id=source.id,
                    statistics=profile_data.get("statistics", {}),
                    null_rates=profile_data.get("null_rates", {}),
                    distributions=profile_data.get("distributions", {}),
                )
                db.add(profile)
                await db.flush()

            # Persist insights
            insight_type_map = {t.value: t for t in InsightType}
            saved_insights: list[Insight] = []
            for card in state.get("insights", []):
                itype = insight_type_map.get(card.get("type", "summary"), InsightType.summary)
                insight = Insight(
                    data_source_id=source.id,
                    insight_type=itype,
                    title=card["title"],
                    body=card["body"],
                    data=card.get("data") or {},
                )
                db.add(insight)
                saved_insights.append(insight)
            await db.flush()

            # Persist notifications for all active users (notifiable insight types only)
            users_result = await db.execute(select(User).where(User.is_active == True))
            users = users_result.scalars().all()

            for insight in saved_insights:
                if insight.insight_type.value not in NOTIFIABLE_TYPES:
                    continue
                for user in users:
                    db.add(Notification(
                        user_id=user.id,
                        insight_id=insight.id,
                        title=insight.title,
                        is_read=False,
                    ))

            # Persist agent logs
            from datetime import datetime, timezone
            for entry in state.get("logs", []):
                status_val = entry.get("status", "success")
                raw_started = entry.get("started_at")
                raw_completed = entry.get("completed_at")
                db.add(AgentLog(
                    data_source_id=source.id,
                    agent_name=entry.get("agent_name", "unknown"),
                    status=AgentStatus.success if status_val == "success" else AgentStatus.error,
                    output_summary=entry.get("output_summary"),
                    error_message=entry.get("error_message"),
                    started_at=datetime.fromisoformat(raw_started).replace(tzinfo=None) if raw_started else datetime.utcnow(),
                    completed_at=datetime.fromisoformat(raw_completed).replace(tzinfo=None) if raw_completed else None,
                ))

            # Mark source active
            source.status = SourceStatus.active
            await db.commit()
            logger.info(
                "Persisted pipeline results for source %s: %d insight(s)",
                source_id, len(saved_insights),
            )

        except Exception:
            await db.rollback()
            logger.exception("Failed to persist pipeline results for source %s", source_id)
            try:
                async with AsyncSessionLocal() as db2:
                    result = await db2.execute(
                        select(DataSource).where(DataSource.id == uuid.UUID(source_id))
                    )
                    src = result.scalar_one_or_none()
                    if src:
                        src.status = SourceStatus.error
                        await db2.commit()
            except Exception:
                pass
