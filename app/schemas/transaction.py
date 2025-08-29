"""
Transaction-related Pydantic schemas for API validation.
"""
from typing import Optional
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import UUID
from enum import Enum


class TransactionType(str, Enum):
    CHARGE = "charge"
    PAYMENT = "payment"
    REFUND = "refund"


class TransactionCreate(BaseModel):
    amount: Decimal = Field(..., gt=0, decimal_places=2, description="Transaction amount")
    type: TransactionType
    description: Optional[str] = None
    reference_id: Optional[str] = Field(None, description="External payment reference")


class TransactionResponse(BaseModel):
    id: UUID
    user_id: UUID
    amount: Decimal = Field(..., decimal_places=2)
    type: TransactionType
    description: Optional[str] = None
    reference_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PaymentRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, decimal_places=2, description="Payment amount in rubles")
    payment_method: str = Field("sbp", description="Payment method (currently only СБП)")


class PaymentResponse(BaseModel):
    payment_id: str = Field(..., description="Payment ID for tracking")
    payment_url: Optional[str] = Field(None, description="Payment URL for СБП")
    amount: Decimal = Field(..., decimal_places=2)
    status: str = Field(..., description="Payment status")


class PaymentConfirmation(BaseModel):
    payment_id: str = Field(..., description="Payment ID to confirm")
    reference_id: str = Field(..., description="External payment reference")
    status: str = Field(..., description="Payment status from provider")


class BalanceOperation(BaseModel):
    user_id: UUID
    amount: Decimal = Field(..., decimal_places=2)
    operation: str = Field(..., description="Operation type: add or subtract")
    description: str = Field(..., description="Operation description")