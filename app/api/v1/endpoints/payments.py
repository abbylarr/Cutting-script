"""
Payment API endpoints for СБП integration.
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.schemas.transaction import PaymentRequest, PaymentResponse, PaymentConfirmation
from app.services.payment import payment_service


router = APIRouter()


@router.post("/create", response_model=PaymentResponse)
async def create_payment(
    payment_request: PaymentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new СБП payment.
    """
    try:
        if payment_request.amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment amount must be positive"
            )
        
        payment_response = payment_service.create_payment(
            db, 
            str(current_user.id), 
            payment_request
        )
        
        return payment_response
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create payment: {str(e)}"
        )


@router.get("/status/{payment_id}")
async def get_payment_status(
    payment_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get payment status.
    """
    payment_data = payment_service.get_payment_status(payment_id)
    
    if not payment_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    # Check if user owns this payment
    if payment_data["user_id"] != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return {
        "payment_id": payment_data["payment_id"],
        "amount": float(payment_data["amount"]),
        "status": payment_data["status"],
        "created_at": payment_data["created_at"],
        "expires_at": payment_data.get("expires_at"),
        "payment_url": payment_data.get("payment_url")
    }


@router.post("/confirm")
async def confirm_payment(
    confirmation: PaymentConfirmation,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Confirm payment (webhook endpoint for СБП).
    In production, this would verify webhook signature.
    """
    try:
        success = payment_service.confirm_payment(db, confirmation)
        
        if success:
            return {"status": "success", "message": "Payment confirmed"}
        else:
            return {"status": "failed", "message": "Payment failed"}
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to confirm payment: {str(e)}"
        )


@router.post("/cancel/{payment_id}")
async def cancel_payment(
    payment_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Cancel a pending payment.
    """
    try:
        # Check if payment exists and belongs to user
        payment_data = payment_service.get_payment_status(payment_id)
        
        if not payment_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        if payment_data["user_id"] != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        success = payment_service.cancel_payment(payment_id)
        
        if success:
            return {"status": "cancelled", "message": "Payment cancelled successfully"}
        else:
            return {"status": "failed", "message": "Failed to cancel payment"}
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel payment: {str(e)}"
        )


# Test endpoints for development (remove in production)
@router.post("/test/complete/{payment_id}")
async def test_complete_payment(
    payment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Test endpoint to simulate payment completion.
    Remove this in production.
    """
    try:
        # Check if payment exists and belongs to user
        payment_data = payment_service.get_payment_status(payment_id)
        
        if not payment_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        if payment_data["user_id"] != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Simulate payment completion
        confirmation = payment_service.simulate_payment_completion(payment_id)
        success = payment_service.confirm_payment(db, confirmation)
        
        if success:
            return {"status": "completed", "message": "Payment completed successfully"}
        else:
            return {"status": "failed", "message": "Failed to complete payment"}
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete payment: {str(e)}"
        )


@router.post("/test/fail/{payment_id}")
async def test_fail_payment(
    payment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Test endpoint to simulate payment failure.
    Remove this in production.
    """
    try:
        # Check if payment exists and belongs to user
        payment_data = payment_service.get_payment_status(payment_id)
        
        if not payment_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        if payment_data["user_id"] != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Simulate payment failure
        confirmation = payment_service.simulate_payment_failure(payment_id)
        payment_service.confirm_payment(db, confirmation)
        
        return {"status": "failed", "message": "Payment failed"}
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fail payment: {str(e)}"
        )