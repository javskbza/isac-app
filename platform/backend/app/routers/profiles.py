"""Profiles router — GET /profiles/{source_id}."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import get_current_user
from app.database import get_db
from app.models.profile import Profile

router = APIRouter(tags=["profiles"])


@router.get("/profiles/{source_id}")
async def get_profile(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Profile)
        .where(Profile.data_source_id == source_id)
        .order_by(Profile.profiled_at.desc())
        .limit(1)
    )
    profile: Profile | None = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found for this source")

    return {
        "id": str(profile.id),
        "source_id": str(profile.data_source_id),
        "statistics": profile.statistics,
        "null_rates": profile.null_rates,
        "distributions": profile.distributions,
        "profiled_at": profile.profiled_at.isoformat(),
    }
