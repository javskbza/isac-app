"""Sources router — POST/GET/DELETE /sources, POST /upload."""
import asyncio
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import get_current_user, require_admin
from app.database import get_db
from app.models.data_source import DataSource, SourceType, SourceStatus

router = APIRouter(tags=["sources"])

UPLOAD_DIR = "/tmp/uploads"


class CreateSourceRequest(BaseModel):
    name: str
    source_type: SourceType
    config: dict = {}


class SourceResponse(BaseModel):
    id: str
    name: str
    source_type: str
    status: str
    is_active: bool
    created_at: str

    class Config:
        from_attributes = True


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


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_admin),
):
    """Upload a data file and return its server-side path for use in /sources."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe_name = os.path.basename(file.filename or "upload")
    dest = os.path.join(UPLOAD_DIR, safe_name)
    contents = await file.read()
    with open(dest, "wb") as f:
        f.write(contents)
    return {"file_path": dest, "file_name": safe_name}


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
    source.is_active = False
    await db.flush()
