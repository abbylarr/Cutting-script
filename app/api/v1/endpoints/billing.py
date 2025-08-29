"""
Billing and payment API endpoints.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from decimal import Decimal

from app.core.auth import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.schemas.transaction import (
    TransactionResponse, 
    PaymentRequest, 
    PaymentResponse,
    BalanceOperation
)
from app.schemas.user import BalanceResponse
from app.services.billing import billing_service


router = APIRouter()


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user balance and available processing minutes.
    """
    balance = billing_service.get_user_balance(db, str(current_user.id))
    available_minutes = billing_service.get_available_minutes(db, str(current_user.id))
    
    return BalanceResponse(
        balance=balance,
        available_minutes=available_minutes
    )


@router.get("/transactions", response_model=List[TransactionResponse])
async def get_transactions(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user transaction history.
    """
    transactions = billing_service.get_user_transactions(db, str(current_user.id), limit)
    return [TransactionResponse.model_validate(t) for t in transactions]


@router.post("/calculate-cost")
async def calculate_processing_cost(
    duration_minutes: float,
    current_user: User = Depends(get_current_user)
):
    """
    Calculate cost for video processing based on duration.
    """
    if duration_minutes <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duration must be positive"
        )
    
    cost = billing_service.calculate_cost(duration_minutes)
    
    return {
        "duration_minutes": duration_minutes,
        "cost_rubles": float(cost),
        "rate_per_minute": float(billing_service.rate_per_minute)
    }


@router.post("/check-balance")
async def check_sufficient_balance(
    duration_minutes: float,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if user has sufficient balance for processing.
    """
    if duration_minutes <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duration must be positive"
        )
    
    cost = billing_service.calculate_cost(duration_minutes)
    has_balance = billing_service.has_sufficient_balance(db, str(current_user.id), cost)
    current_balance = billing_service.get_user_balance(db, str(current_user.id))
    
    return {
        "duration_minutes": duration_minutes,
        "required_cost": float(cost),
        "current_balance": float(current_balance),
        "sufficient_balance": has_balance,
        "shortfall": float(max(Decimal('0.00'), cost - current_balance))
    }


@router.post("/charge", response_model=TransactionResponse)
async def charge_user_balance(
    duration_minutes: float,
    description: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Charge user for video processing (internal use).
    """
    try:
        if duration_minutes <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duration must be positive"
            )
        
        cost = billing_service.calculate_cost(duration_minutes)
        transaction = billing_service.charge_user(
            db, 
            str(current_user.id), 
            cost, 
            description
        )
        
        return TransactionResponse.model_validate(transaction)
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to charge user"
        )


@router.post("/refund", response_model=TransactionResponse)
async def refund_user_balance(
    amount: Decimal,
    description: str,
    reference_id: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Refund amount to user balance (admin use).
    """
    try:
        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Amount must be positive"
            )
        
        transaction = billing_service.refund_user(
            db,
            str(current_user.id),
            amount,
            description,
            reference_id
        )
        
        return TransactionResponse.model_validate(transaction)
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process refund"
        )