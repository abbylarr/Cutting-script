"""
Payment service for СБП (Fast Payment System) integration.
"""
import uuid
from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.services.billing import billing_service
from app.schemas.transaction import PaymentRequest, PaymentResponse, PaymentConfirmation


class PaymentService:
    """Service for handling СБП payments."""
    
    def __init__(self):
        # In production, these would come from environment variables
        self.sbp_merchant_id = "test_merchant_id"
        self.sbp_api_key = "test_api_key"
        self.sbp_api_url = "https://api.sbp.ru/v1"  # Mock URL
        self.callback_url = "https://filmlist.ru/api/v1/payments/callback"
        
        # Mock payment storage (in production, use Redis or database)
        self._mock_payments: Dict[str, Dict[str, Any]] = {}
    
    def create_payment(self, db: Session, user_id: str, payment_request: PaymentRequest) -> PaymentResponse:
        """Create a new СБП payment."""
        # Generate unique payment ID
        payment_id = str(uuid.uuid4())
        
        # In production, this would make an API call to СБП
        # For now, we'll create a mock payment
        payment_data = {
            "payment_id": payment_id,
            "user_id": user_id,
            "amount": payment_request.amount,
            "status": "pending",
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(minutes=15),  # СБП payments typically expire in 15 minutes
            "payment_url": f"https://qr.nspk.ru/pay/{payment_id}",  # Mock QR payment URL
            "reference_id": None
        }
        
        # Store payment data (in production, store in database)
        self._mock_payments[payment_id] = payment_data
        
        return PaymentResponse(
            payment_id=payment_id,
            payment_url=payment_data["payment_url"],
            amount=payment_request.amount,
            status="pending"
        )
    
    def get_payment_status(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """Get payment status from СБП."""
        # In production, this would query the СБП API
        return self._mock_payments.get(payment_id)
    
    def confirm_payment(self, db: Session, confirmation: PaymentConfirmation) -> bool:
        """Confirm payment and add funds to user balance."""
        payment_data = self.get_payment_status(confirmation.payment_id)
        
        if not payment_data:
            raise ValueError("Payment not found")
        
        if payment_data["status"] != "pending":
            raise ValueError(f"Payment already processed with status: {payment_data['status']}")
        
        # Verify payment confirmation (in production, verify signature/webhook authenticity)
        if confirmation.status == "completed":
            # Add funds to user balance
            try:
                billing_service.add_funds(
                    db,
                    payment_data["user_id"],
                    payment_data["amount"],
                    f"СБП payment - {confirmation.payment_id}",
                    confirmation.reference_id
                )
                
                # Update payment status
                payment_data["status"] = "completed"
                payment_data["reference_id"] = confirmation.reference_id
                payment_data["completed_at"] = datetime.utcnow()
                
                return True
            
            except Exception as e:
                # Mark payment as failed
                payment_data["status"] = "failed"
                payment_data["error"] = str(e)
                raise ValueError(f"Failed to add funds: {str(e)}")
        
        elif confirmation.status == "failed":
            payment_data["status"] = "failed"
            payment_data["error"] = "Payment failed"
            return False
        
        else:
            raise ValueError(f"Unknown payment status: {confirmation.status}")
    
    def cancel_payment(self, payment_id: str) -> bool:
        """Cancel a pending payment."""
        payment_data = self.get_payment_status(payment_id)
        
        if not payment_data:
            raise ValueError("Payment not found")
        
        if payment_data["status"] != "pending":
            raise ValueError(f"Cannot cancel payment with status: {payment_data['status']}")
        
        # In production, this would call СБП API to cancel the payment
        payment_data["status"] = "cancelled"
        payment_data["cancelled_at"] = datetime.utcnow()
        
        return True
    
    def check_expired_payments(self, db: Session) -> int:
        """Check and mark expired payments (should be run periodically)."""
        expired_count = 0
        current_time = datetime.utcnow()
        
        for payment_id, payment_data in self._mock_payments.items():
            if (payment_data["status"] == "pending" and 
                payment_data["expires_at"] < current_time):
                
                payment_data["status"] = "expired"
                payment_data["expired_at"] = current_time
                expired_count += 1
        
        return expired_count
    
    def simulate_payment_completion(self, payment_id: str, reference_id: str = None) -> PaymentConfirmation:
        """
        Simulate payment completion for testing purposes.
        In production, this would be called by СБП webhook.
        """
        payment_data = self.get_payment_status(payment_id)
        
        if not payment_data:
            raise ValueError("Payment not found")
        
        if not reference_id:
            reference_id = f"sbp_ref_{uuid.uuid4().hex[:8]}"
        
        return PaymentConfirmation(
            payment_id=payment_id,
            reference_id=reference_id,
            status="completed"
        )
    
    def simulate_payment_failure(self, payment_id: str) -> PaymentConfirmation:
        """
        Simulate payment failure for testing purposes.
        """
        payment_data = self.get_payment_status(payment_id)
        
        if not payment_data:
            raise ValueError("Payment not found")
        
        return PaymentConfirmation(
            payment_id=payment_id,
            reference_id="",
            status="failed"
        )


# Global payment service instance
payment_service = PaymentService()