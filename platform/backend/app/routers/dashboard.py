"""Dashboard router — GET/PUT /api/dashboard/layout."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import get_current_user
from app.database import get_db
from app.models.user_dashboard_layout import UserDashboardLayout

router = APIRouter(tags=["dashboard"])

# Default starter layout for first-time users (12-column grid, rowHeight=80)
DEFAULT_LAYOUT = {
    "grid": [
        {"i": "data_profile",      "x": 0,  "y": 0,  "w": 4,  "h": 3},
        {"i": "profile_details",   "x": 4,  "y": 0,  "w": 8,  "h": 3},
        {"i": "descriptive_stats", "x": 0,  "y": 3,  "w": 6,  "h": 4},
        {"i": "trend_analysis",    "x": 6,  "y": 3,  "w": 6,  "h": 4},
        {"i": "anomaly_detection", "x": 0,  "y": 7,  "w": 6,  "h": 4},
        {"i": "forecast",          "x": 6,  "y": 7,  "w": 6,  "h": 4},
        {"i": "insights",          "x": 0,  "y": 11, "w": 12, "h": 4},
    ],
    "widget_state": {},
}


@router.get("/api/dashboard/layout")
async def get_layout(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(current_user["sub"])
    result = await db.execute(
        select(UserDashboardLayout).where(UserDashboardLayout.user_id == user_id)
    )
    layout_row = result.scalar_one_or_none()
    if layout_row is None:
        return DEFAULT_LAYOUT
    return layout_row.layout


@router.put("/api/dashboard/layout")
async def save_layout(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(current_user["sub"])
    result = await db.execute(
        select(UserDashboardLayout).where(UserDashboardLayout.user_id == user_id)
    )
    layout_row = result.scalar_one_or_none()
    now = datetime.utcnow()

    if layout_row is None:
        layout_row = UserDashboardLayout(
            user_id=user_id,
            layout=body,
            updated_at=now,
        )
        db.add(layout_row)
    else:
        layout_row.layout = body
        layout_row.updated_at = now

    return {"saved": True}
