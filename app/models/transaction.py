"""
Transaction model for billing and payment tracking.
"""
from sqlalchemy import Column, String, DECIMAL, Text, DateTime, func, ForeignKey
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base
from app.db.types import UUID


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(), ForeignKey("users.id"), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    type = Column(String(50), nullable=False)  # 'charge' | 'payment' | 'refund'
    description = Column(Text, nullable=True)
    reference_id = Column(String(255), nullable=True)  # External payment reference
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="transactions")

    def __repr__(self):
        return f"<Transaction(id={self.id}, type={self.type}, amount={self.amount}, user_id={self.user_id})>"