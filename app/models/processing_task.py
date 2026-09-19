"""
ProcessingTask model for video processing jobs.
"""
from sqlalchemy import Column, String, Float, Text, DateTime, Boolean, func, ForeignKey
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base
from app.db.types import UUID, JSONType


class ProcessingTask(Base):
    __tablename__ = "processing_tasks"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(), ForeignKey("users.id"), nullable=False)
    status = Column(String(50), nullable=False, default="pending")  # pending, processing, completed, failed
    video_filename = Column(String(255), nullable=False)
    video_path = Column(String(500), nullable=False)
    srt_path = Column(String(500), nullable=True)
    file_hash = Column(String(64), nullable=True)  # SHA256 hash for integrity verification
    estimated_cost = Column(Float, nullable=True)  # Estimated processing cost in rubles
    use_srt = Column(Boolean, nullable=False, default=False)  # Whether to use SRT mode
    progress = Column(Float, default=0.0, nullable=False)
    current_step = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    result = Column(JSONType(), nullable=True)  # Stores montage rows as JSON
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="processing_tasks")
    film_project = relationship("FilmProject", back_populates="processing_task", uselist=False)

    def __repr__(self):
        return f"<ProcessingTask(id={self.id}, status={self.status}, user_id={self.user_id})>"