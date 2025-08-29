"""
FilmProject model for storing film metadata and montage data.
"""
from sqlalchemy import Column, String, DateTime, func, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base
from app.db.types import UUID


class FilmProject(Base):
    __tablename__ = "film_projects"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(), ForeignKey("users.id"), nullable=False)
    task_id = Column(UUID(), ForeignKey("processing_tasks.id"), nullable=False)
    title = Column(String(255), nullable=False)
    film_metadata = Column(JSONB().with_variant(Text, "sqlite"), nullable=False)  # Film metadata (production company, year, etc.)
    montage_rows = Column(JSONB().with_variant(Text, "sqlite"), nullable=True)  # Processed montage table data
    project_settings = Column(JSONB().with_variant(Text, "sqlite"), nullable=True)  # Timecode settings, standards, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="film_projects")
    processing_task = relationship("ProcessingTask", back_populates="film_project")

    def __repr__(self):
        return f"<FilmProject(id={self.id}, title={self.title}, user_id={self.user_id})>"