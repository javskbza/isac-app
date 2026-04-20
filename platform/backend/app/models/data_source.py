import uuid
import enum
from datetime import datetime
from sqlalchemy import String, JSON, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base


class SourceType(str, enum.Enum):
    file = "file"
    rest_api = "rest_api"


class SourceStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    error = "error"


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(SAEnum(SourceType))
    config: Mapped[dict] = mapped_column(JSON, default={})
    status: Mapped[SourceStatus] = mapped_column(SAEnum(SourceStatus), default=SourceStatus.pending)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    schemas: Mapped[list["Schema"]] = relationship(back_populates="data_source")
    profiles: Mapped[list["Profile"]] = relationship(back_populates="data_source")
    insights: Mapped[list["Insight"]] = relationship(back_populates="data_source")
    agent_logs: Mapped[list["AgentLog"]] = relationship(back_populates="data_source")
