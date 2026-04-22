"""Sources router — CRUD for data sources, schedules, and poll logs."""
import asyncio
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, UploadFile, File, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import get_current_user, require_admin
from app.database import get_db
from app.models.data_source import DataSource, SourceType, SourceStatus
from app.models.source_schedule import SourceSchedule
from app.models.source_poll_log import SourcePollLog

router = APIRouter(tags=["sources"])

UPLOAD_DIR = "/tmp/uploads"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class CreateSourceRequest(BaseModel):
    name: str
    source_type: SourceType
    config: dict = {}


def _source_to_dict(s: DataSource) -> dict:
    return {
        "id": str(s.id),
        "name": s.name,
        "source_type": s.source_type.value,
        "config": s.config,
        "status": s.status.value,
        "is_active": s.is_active,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# File upload
# ---------------------------------------------------------------------------

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_admin),
):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe_name = os.path.basename(file.filename or "upload")
    dest = os.path.join(UPLOAD_DIR, safe_name)
    contents = await file.read()
    with open(dest, "wb") as f:
        f.write(contents)
    return {"file_path": dest, "file_name": safe_name}


# ---------------------------------------------------------------------------
# Source CRUD
# ---------------------------------------------------------------------------

@router.post("/sources", status_code=status.HTTP_201_CREATED)
async def create_source(
    body: CreateSourceRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    source = DataSource(
        name=body.name,
        source_type=body.source_type,
        config=body.config,
        status=SourceStatus.pending,
    )
    db.add(source)
    await db.flush()

    source_id = str(source.id)
    source_type = body.source_type.value
    source_config = body.config

    async def _run_pipeline():
        from app.agents import run_pipeline
        from app.agents.persist import persist_pipeline_results
        try:
            loop = asyncio.get_event_loop()
            final_state = await loop.run_in_executor(
                None, lambda: run_pipeline(source_id, source_type, source_config)
            )
            await persist_pipeline_results(final_state)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Pipeline failed for source %s", source_id)

    background_tasks.add_task(_run_pipeline)
    return _source_to_dict(source)


@router.get("/sources")
async def list_sources(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(DataSource).where(DataSource.is_active == True).order_by(DataSource.created_at.desc())
    )
    sources = result.scalars().all()
    return [_source_to_dict(s) for s in sources]


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    result = await db.execute(select(DataSource).where(DataSource.id == source_id))
    source: DataSource | None = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    # Remove beat schedule if one exists
    from app.beat_scheduler import delete_beat_entry
    delete_beat_entry(str(source_id))
    source.is_active = False
    await db.flush()


# ---------------------------------------------------------------------------
# Schedule endpoints
# ---------------------------------------------------------------------------

SCHEDULE_PRESETS = {
    "5min":   "*/5 * * * *",
    "15min":  "*/15 * * * *",
    "hourly": "0 * * * *",
    "6h":     "0 */6 * * *",
    "daily":  "0 0 * * *",
    "weekly": "0 0 * * 0",
}


class ScheduleRequest(BaseModel):
    schedule_expr: str
    enabled: bool = True


def _validate_cron(expr: str) -> None:
    try:
        from croniter import croniter
        if not croniter.is_valid(expr):
            raise ValueError
    except (ValueError, ImportError):
        raise HTTPException(status_code=400, detail=f"Invalid cron expression: {expr!r}")


@router.post("/sources/{source_id}/schedule", status_code=status.HTTP_200_OK)
async def upsert_schedule(
    source_id: uuid.UUID,
    body: ScheduleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    result = await db.execute(select(DataSource).where(DataSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    expr = SCHEDULE_PRESETS.get(body.schedule_expr, body.schedule_expr)
    _validate_cron(expr)

    sched_result = await db.execute(
        select(SourceSchedule).where(SourceSchedule.source_id == source_id)
    )
    sched = sched_result.scalar_one_or_none()

    actor_id = uuid.UUID(current_user["sub"])
    if sched is None:
        sched = SourceSchedule(
            source_id=source_id,
            schedule_expr=expr,
            enabled=body.enabled,
            created_by=actor_id,
        )
        db.add(sched)
    else:
        sched.schedule_expr = expr
        sched.enabled = body.enabled
        sched.updated_at = datetime.utcnow()

    await db.flush()

    # Sync with Beat
    from app.beat_scheduler import upsert_beat_entry, delete_beat_entry
    if body.enabled:
        upsert_beat_entry(str(source_id), expr)
        if source.status == SourceStatus.paused:
            source.status = SourceStatus.active
    else:
        delete_beat_entry(str(source_id))
        if source.status == SourceStatus.active:
            source.status = SourceStatus.paused

    return {
        "source_id": str(source_id),
        "schedule_expr": expr,
        "enabled": body.enabled,
    }


@router.get("/sources/{source_id}/schedule")
async def get_schedule(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    result = await db.execute(
        select(SourceSchedule).where(SourceSchedule.source_id == source_id)
    )
    sched = result.scalar_one_or_none()
    if not sched:
        return None
    return {
        "source_id": str(source_id),
        "schedule_expr": sched.schedule_expr,
        "enabled": sched.enabled,
        "consecutive_failures": sched.consecutive_failures,
        "created_at": sched.created_at.isoformat(),
        "updated_at": sched.updated_at.isoformat(),
    }


@router.delete("/sources/{source_id}/schedule", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    result = await db.execute(
        select(SourceSchedule).where(SourceSchedule.source_id == source_id)
    )
    sched = result.scalar_one_or_none()
    if sched:
        await db.delete(sched)
    from app.beat_scheduler import delete_beat_entry
    delete_beat_entry(str(source_id))


# ---------------------------------------------------------------------------
# Poll log
# ---------------------------------------------------------------------------

@router.get("/sources/{source_id}/poll-log")
async def get_poll_log(
    source_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    offset = (page - 1) * page_size
    result = await db.execute(
        select(SourcePollLog)
        .where(SourcePollLog.source_id == source_id)
        .order_by(SourcePollLog.started_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    logs = result.scalars().all()
    return [
        {
            "id": str(log.id),
            "started_at": log.started_at.isoformat(),
            "completed_at": log.completed_at.isoformat() if log.completed_at else None,
            "duration_ms": log.duration_ms,
            "status": log.status.value,
            "attempt_number": log.attempt_number,
            "error_message": log.error_message,
        }
        for log in logs
    ]


# ---------------------------------------------------------------------------
# Manual refresh
# ---------------------------------------------------------------------------

@router.post("/sources/{source_id}/refresh", status_code=status.HTTP_202_ACCEPTED)
async def manual_refresh(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    result = await db.execute(select(DataSource).where(DataSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if source.status == SourceStatus.disconnected:
        raise HTTPException(status_code=400, detail="Source is disconnected. Fix configuration before refreshing.")

    from app.tasks import poll_source
    task = poll_source.delay(str(source_id))
    return {"task_id": task.id, "source_id": str(source_id)}
