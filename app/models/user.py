"""
User model for authentication and billing.
"""
from sqlalchemy import Column, String, DECIMAL, DateTime, func
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base
from app.db.types import UUID


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    balance = Column(DECIMAL(10, 2), default=0.00, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    processing_tasks = relationship("ProcessingTask", back_populates="user")
    film_projects = relationship("FilmProject", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"