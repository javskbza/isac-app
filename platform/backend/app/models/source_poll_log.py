import uuid
import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base


class PollStatus(str, enum.Enum):
    success = "success"
    failure = "failure"


class SourcePollLog(Base):
    __tablename__ = "source_poll_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[PollStatus] = mapped_column(SAEnum(PollStatus), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    data_source: Mapped["DataSource"] = relationship(back_populates="poll_logs")

    __table_args__ = (
        Index("ix_source_poll_log_source_started", "source_id", "started_at"),
    )
