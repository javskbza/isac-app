"""Agent logs router — GET /agents/log."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import get_current_user
from app.database import get_db
from app.models.agent_log import AgentLog

router = APIRouter(tags=["agents"])


@router.get("/agents/log")
async def get_agent_log(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    limit: int = 100,
):
    result = await db.execute(
        select(AgentLog)
        .order_by(AgentLog.started_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()

    return [
        {
            "id": str(log.id),
            "source_id": str(log.data_source_id) if log.data_source_id else None,
            "agent_name": log.agent_name,
            "status": log.status.value,
            "output_summary": log.output_summary,
            "error_message": log.error_message,
            "started_at": log.started_at.isoformat(),
            "completed_at": log.completed_at.isoformat() if log.completed_at else None,
        }
        for log in logs
    ]
