"""Insights router — GET /insights/{source_id}."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import get_current_user
from app.database import get_db
from app.models.insight import Insight

router = APIRouter(tags=["insights"])


@router.get("/insights/{source_id}")
async def get_insights(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Insight)
        .where(Insight.data_source_id == source_id)
        .order_by(Insight.created_at.desc())
    )
    insights = result.scalars().all()

    return [
        {
            "id": str(i.id),
            "source_id": str(i.data_source_id),
            "type": i.insight_type.value,
            "title": i.title,
            "body": i.body,
            "data": i.data,
            "created_at": i.created_at.isoformat(),
        }
        for i in insights
    ]
