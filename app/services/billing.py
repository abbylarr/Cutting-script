"""
Billing service for balance management and cost calculations.
"""
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.config import settings
from app.models.user import User
from app.models.transaction import Transaction
from app.schemas.transaction import TransactionCreate, TransactionType


class BillingService:
    """Service for handling billing operations and balance management."""
    
    def __init__(self):
        self.rate_per_minute = Decimal(str(settings.RATE_PER_MINUTE))
    
    def calculate_cost(self, duration_minutes: float) -> Decimal:
        """Calculate cost for video processing based on duration."""
        return Decimal(str(duration_minutes)) * self.rate_per_minute
    
    def get_user_balance(self, db: Session, user_id: str) -> Decimal:
        """Get current user balance."""
        stmt = select(User.balance).where(User.id == user_id)
        result = db.execute(stmt)
        balance = result.scalar_one_or_none()
        return balance or Decimal('0.00')
    
    def has_sufficient_balance(self, db: Session, user_id: str, cost: Decimal) -> bool:
        """Check if user has sufficient balance for the cost."""
        current_balance = self.get_user_balance(db, user_id)
        return current_balance >= cost
    
    def get_available_minutes(self, db: Session, user_id: str) -> float:
        """Calculate available processing minutes based on current balance."""
        current_balance = self.get_user_balance(db, user_id)
        if self.rate_per_minute == 0:
            return 0.0
        return float(current_balance / self.rate_per_minute)
    
    def charge_user(self, db: Session, user_id: str, amount: Decimal, description: str) -> Transaction:
        """Charge user for processing (deduct from balance)."""
        # Get user first
        stmt = select(User).where(User.id == user_id)
        result = db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")
        
        # Check if user has sufficient balance
        if not self.has_sufficient_balance(db, user_id, amount):
            raise ValueError("Insufficient balance")
        
        # Deduct from balance
        user.balance -= amount
        
        # Create transaction record
        transaction = Transaction(
            user_id=user_id,
            amount=-amount,  # Negative for charges
            type=TransactionType.CHARGE,
            description=description
        )
        
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        
        return transaction
    
    def add_funds(self, db: Session, user_id: str, amount: Decimal, description: str, reference_id: Optional[str] = None) -> Transaction:
        """Add funds to user balance (from payment)."""
        # Get user
        stmt = select(User).where(User.id == user_id)
        result = db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")
        
        # Add to balance
        user.balance += amount
        
        # Create transaction record
        transaction = Transaction(
            user_id=user_id,
            amount=amount,  # Positive for payments
            type=TransactionType.PAYMENT,
            description=description,
            reference_id=reference_id
        )
        
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        
        return transaction
    
    def get_user_transactions(self, db: Session, user_id: str, limit: int = 50) -> list[Transaction]:
        """Get user transaction history."""
        stmt = (
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.created_at.desc())
            .limit(limit)
        )
        result = db.execute(stmt)
        return result.scalars().all()
    
    def refund_user(self, db: Session, user_id: str, amount: Decimal, description: str, reference_id: Optional[str] = None) -> Transaction:
        """Refund amount to user balance."""
        # Get user
        stmt = select(User).where(User.id == user_id)
        result = db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")
        
        # Add refund to balance
        user.balance += amount
        
        # Create transaction record
        transaction = Transaction(
            user_id=user_id,
            amount=amount,  # Positive for refunds
            type=TransactionType.REFUND,
            description=description,
            reference_id=reference_id
        )
        
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        
        return transaction


# Global billing service instance
billing_service = BillingService()