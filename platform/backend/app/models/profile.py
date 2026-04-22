import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import JSON, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models.base import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="CASCADE")
    )
    statistics: Mapped[dict] = mapped_column(JSON, default={})
    null_rates: Mapped[dict] = mapped_column(JSON, default={})
    distributions: Mapped[dict] = mapped_column(JSON, default={})
    total_rows: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_columns: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    zscore_anomalies: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    profiled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    data_source: Mapped["DataSource"] = relationship(back_populates="profiles")
