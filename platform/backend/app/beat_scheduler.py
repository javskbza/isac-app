"""Beat schedule management — load/reload source poll schedules into redbeat."""
import logging
from typing import Optional

from redbeat import RedBeatSchedulerEntry
from celery.schedules import crontab

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


def _parse_cron(expr: str) -> crontab:
    """Parse a 5-field cron expression into a Celery crontab."""
    parts = expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression (expected 5 fields): {expr!r}")
    minute, hour, day_of_month, month_of_year, day_of_week = parts
    return crontab(
        minute=minute,
        hour=hour,
        day_of_month=day_of_month,
        month_of_year=month_of_year,
        day_of_week=day_of_week,
    )


def _entry_key(source_id: str) -> str:
    return f"poll_source:{source_id}"


def upsert_beat_entry(source_id: str, schedule_expr: str) -> None:
    """Create or update a redbeat entry for the given source."""
    try:
        entry = RedBeatSchedulerEntry(
            name=_entry_key(source_id),
            task="app.tasks.poll_source",
            schedule=_parse_cron(schedule_expr),
            args=[source_id],
            app=celery_app,
        )
        entry.save()
        logger.info("Beat: upserted schedule for source %s (%s)", source_id, schedule_expr)
    except Exception:
        logger.exception("Beat: failed to upsert schedule for source %s", source_id)


def delete_beat_entry(source_id: str) -> None:
    """Remove the redbeat entry for the given source, if it exists."""
    try:
        entry = RedBeatSchedulerEntry.from_key(
            _entry_key(source_id), app=celery_app
        )
        entry.delete()
        logger.info("Beat: deleted schedule for source %s", source_id)
    except KeyError:
        pass  # Entry didn't exist — no-op
    except Exception:
        logger.exception("Beat: failed to delete schedule for source %s", source_id)


def load_all_schedules() -> None:
    """
    Called at application startup.
    Reads all enabled source_schedules from DB and registers them in redbeat.
    Runs synchronously (called from a sync context in main.py startup event).
    """
    import asyncio
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.config import settings
    from app.models.source_schedule import SourceSchedule

    async def _load():
        engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as db:
            result = await db.execute(
                select(SourceSchedule).where(SourceSchedule.enabled == True)
            )
            schedules = result.scalars().all()
            for sched in schedules:
                upsert_beat_entry(str(sched.source_id), sched.schedule_expr)
            logger.info("Beat: loaded %d schedule(s) from database", len(schedules))
        await engine.dispose()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_load())
    except Exception:
        logger.exception("Beat: failed to load schedules at startup")
    finally:
        loop.close()
