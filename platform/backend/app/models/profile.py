import uuid
from datetime import datetime
from sqlalchemy import JSON, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
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
    profiled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    data_source: Mapped["DataSource"] = relationship(back_populates="profiles")
