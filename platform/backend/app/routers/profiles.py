"""Profiles router — GET /profiles/{source_id} and /profiles/{source_id}/anomalies."""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import get_current_user
from app.database import get_db
from app.models.profile import Profile

router = APIRouter(tags=["profiles"])


def _profile_response(profile: Profile) -> dict:
    return {
        "id": str(profile.id),
        "source_id": str(profile.data_source_id),
        # Summary counts (v2)
        "total_rows": profile.total_rows,
        "total_columns": profile.total_columns,
        "categorical_count": _count_by_classification(profile.statistics, "categorical"),
        "discrete_count": _count_by_classification(profile.statistics, "discrete"),
        "continuous_count": _count_by_classification(profile.statistics, "continuous"),
        # Per-column detail (includes data_classification, pk_candidate, mode, kde, time_series)
        "statistics": profile.statistics,
        "null_rates": profile.null_rates,
        "distributions": profile.distributions,
        "profiled_at": profile.profiled_at.isoformat(),
    }


def _count_by_classification(statistics: dict, classification: str) -> int:
    if not statistics:
        return 0
    return sum(
        1 for col_stats in statistics.values()
        if isinstance(col_stats, dict) and col_stats.get("data_classification") == classification
    )


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

    return _profile_response(profile)


@router.get("/profiles/{source_id}/anomalies")
async def get_anomalies(
    source_id: uuid.UUID,
    column: Optional[str] = Query(default=None, description="Filter by column name"),
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

    anomalies = profile.zscore_anomalies or []
    if column:
        anomalies = [a for a in anomalies if a.get("column") == column]

    return {
        "source_id": str(source_id),
        "column": column,
        "total": len(anomalies),
        "anomalies": anomalies,
    }
