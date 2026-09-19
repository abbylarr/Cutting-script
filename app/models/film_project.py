"""
FilmProject model for storing film metadata and montage data.
"""
from sqlalchemy import Column, String, DateTime, func, ForeignKey, Text
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base
from app.db.types import UUID, JSONType


class FilmProject(Base):
    __tablename__ = "film_projects"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(), ForeignKey("users.id"), nullable=False)
    task_id = Column(UUID(), ForeignKey("processing_tasks.id"), nullable=False)
    title = Column(String(255), nullable=False)
    film_metadata = Column(JSONType(), nullable=False)
    montage_rows = Column(JSONType(), nullable=True)
    project_settings = Column(JSONType(), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="film_projects")
    processing_task = relationship("ProcessingTask", back_populates="film_project")

    def __repr__(self):
        return f"<FilmProject(id={self.id}, title={self.title}, user_id={self.user_id})>"