import uuid
import enum
from datetime import datetime
from sqlalchemy import String, JSON, DateTime, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base


class InsightType(str, enum.Enum):
    anomaly = "anomaly"
    trend = "trend"
    forecast = "forecast"
    pattern = "pattern"
    summary = "summary"


class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="CASCADE")
    )
    insight_type: Mapped[InsightType] = mapped_column(SAEnum(InsightType))
    title: Mapped[str] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSON, default={})
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    data_source: Mapped["DataSource"] = relationship(back_populates="insights")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="insight")
