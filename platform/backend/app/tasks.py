"""Celery tasks — poll_source is the primary scheduled task."""
import asyncio
import logging
from datetime import datetime, timezone

from celery import Task
from app.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery worker."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3, name="app.tasks.poll_source")
def poll_source(self: Task, source_id: str) -> dict:
    """
    Scheduled and manual poll task.
    Runs IngestAgent → ProfileAgent → downstream agents via run_pipeline.
    Handles retries with exponential backoff on failure.
    After 3 consecutive failures marks the source degraded and notifies admins.
    """
    return _run_async(_poll_source_async(self, source_id))


async def _poll_source_async(task: Task, source_id: str) -> dict:
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.data_source import DataSource, SourceStatus
    from app.models.source_schedule import SourceSchedule
    from app.models.source_poll_log import SourcePollLog, PollStatus
    from app.models.user import User, UserRole, UserStatus
    from app.models.notification import Notification
    from app.models.insight import Insight, InsightType
    from app.agents import run_pipeline
    from app.agents.persist import persist_pipeline_results
    import uuid

    started_at = datetime.now(tz=timezone.utc)
    attempt_number = task.request.retries + 1

    # ------------------------------------------------------------------
    # 1. Fetch source config from DB
    # ------------------------------------------------------------------
    async with AsyncSessionLocal() as db:
        source_result = await db.execute(
            select(DataSource).where(DataSource.id == uuid.UUID(source_id))
        )
        source = source_result.scalar_one_or_none()
        if source is None:
            logger.error("poll_source: source %s not found", source_id)
            return {"status": "error", "reason": "source_not_found"}

        if source.status == SourceStatus.disconnected:
            logger.info("poll_source: source %s is disconnected — skipping", source_id)
            return {"status": "skipped", "reason": "disconnected"}

        source_type = source.source_type.value
        source_config = source.config

    # ------------------------------------------------------------------
    # 2. Write poll log entry (running)
    # ------------------------------------------------------------------
    poll_log_id = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        db.add(SourcePollLog(
            id=poll_log_id,
            source_id=uuid.UUID(source_id),
            started_at=started_at.replace(tzinfo=None),
            status=PollStatus.failure,  # will update on success
            attempt_number=attempt_number,
        ))
        await db.commit()

    # ------------------------------------------------------------------
    # 3. Run pipeline
    # ------------------------------------------------------------------
    try:
        final_state = run_pipeline(source_id, source_type, source_config)
        has_errors = bool(final_state.get("errors"))

        if has_errors:
            raise RuntimeError(f"Pipeline errors: {final_state['errors']}")

        await persist_pipeline_results(final_state)

        completed_at = datetime.now(tz=timezone.utc)
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)

        # ------------------------------------------------------------------
        # 4. Success: update poll log, reset consecutive_failures, mark active
        # ------------------------------------------------------------------
        async with AsyncSessionLocal() as db:
            log_result = await db.execute(
                select(SourcePollLog).where(SourcePollLog.id == poll_log_id)
            )
            poll_log = log_result.scalar_one_or_none()
            if poll_log:
                poll_log.status = PollStatus.success
                poll_log.completed_at = completed_at.replace(tzinfo=None)
                poll_log.duration_ms = duration_ms

            src_result = await db.execute(
                select(DataSource).where(DataSource.id == uuid.UUID(source_id))
            )
            src = src_result.scalar_one_or_none()
            if src:
                src.status = SourceStatus.active

            sched_result = await db.execute(
                select(SourceSchedule).where(SourceSchedule.source_id == uuid.UUID(source_id))
            )
            sched = sched_result.scalar_one_or_none()
            if sched:
                sched.consecutive_failures = 0

            await db.commit()

        logger.info("poll_source: source %s polled successfully in %dms", source_id, duration_ms)
        return {"status": "success", "duration_ms": duration_ms}

    except Exception as exc:
        completed_at = datetime.now(tz=timezone.utc)
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)
        error_msg = str(exc)

        logger.error("poll_source: source %s failed (attempt %d): %s",
                     source_id, attempt_number, error_msg)

        # ------------------------------------------------------------------
        # 5. Failure: update poll log, increment consecutive_failures
        # ------------------------------------------------------------------
        async with AsyncSessionLocal() as db:
            log_result = await db.execute(
                select(SourcePollLog).where(SourcePollLog.id == poll_log_id)
            )
            poll_log = log_result.scalar_one_or_none()
            if poll_log:
                poll_log.status = PollStatus.failure
                poll_log.completed_at = completed_at.replace(tzinfo=None)
                poll_log.duration_ms = duration_ms
                poll_log.error_message = error_msg[:2000]

            sched_result = await db.execute(
                select(SourceSchedule).where(SourceSchedule.source_id == uuid.UUID(source_id))
            )
            sched = sched_result.scalar_one_or_none()
            new_failures = (sched.consecutive_failures + 1) if sched else 1
            if sched:
                sched.consecutive_failures = new_failures

            # Mark degraded and notify admins after 3 consecutive failures
            if new_failures >= 3:
                src_result = await db.execute(
                    select(DataSource).where(DataSource.id == uuid.UUID(source_id))
                )
                src = src_result.scalar_one_or_none()
                if src and src.status != SourceStatus.degraded:
                    src.status = SourceStatus.degraded
                    # Notify all active admins
                    admins_result = await db.execute(
                        select(User).where(
                            User.role == UserRole.admin,
                            User.status == UserStatus.active,
                        )
                    )
                    admins = admins_result.scalars().all()
                    # Create a synthetic insight to drive the notification
                    degraded_insight = Insight(
                        data_source_id=uuid.UUID(source_id),
                        insight_type=InsightType.summary,
                        title=f"Source '{src.name}' is degraded",
                        body=(
                            f"The data source '{src.name}' has failed 3 consecutive scheduled polls. "
                            f"Last error: {error_msg[:200]}"
                        ),
                        data={"source_id": source_id, "consecutive_failures": new_failures},
                    )
                    db.add(degraded_insight)
                    await db.flush()
                    for admin in admins:
                        db.add(Notification(
                            user_id=admin.id,
                            insight_id=degraded_insight.id,
                            title=degraded_insight.title,
                            is_read=False,
                        ))

            await db.commit()

        # Retry with exponential backoff: 30s, 120s, 600s
        backoff = [30, 120, 600]
        retry_in = backoff[min(task.request.retries, len(backoff) - 1)]

        if task.request.retries < task.max_retries:
            raise task.retry(exc=exc, countdown=retry_in)

        # All retries exhausted — leave as degraded (already set above)
        return {"status": "failed", "error": error_msg}
