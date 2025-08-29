"""
Tests for payment functionality.
"""
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.payment import payment_service
from app.services.billing import billing_service
from app.services.auth import auth_service
from app.schemas.user import UserCreate
from app.schemas.transaction import PaymentRequest, PaymentConfirmation


class TestPaymentService:
    """Test payment service methods."""
    
    def test_create_payment(self, db_session: Session):
        """Test creating a СБП payment."""
        # Create user
        user_create = UserCreate(email="test@example.com", password="testpassword123")
        user = auth_service.create_user(db_session, user_create)
        
        # Create payment request
        payment_request = PaymentRequest(amount=Decimal('500.00'), payment_method="sbp")
        
        # Create payment
        payment_response = payment_service.create_payment(db_session, str(user.id), payment_request)
        
        # Check response
        assert payment_response.amount == Decimal('500.00')
        assert payment_response.status == "pending"
        assert payment_response.payment_id is not None
        assert payment_response.payment_url is not None
        assert "qr.nspk.ru" in payment_response.payment_url
    
    def test_get_payment_status(self, db_session: Session):
        """Test getting payment status."""
        # Create user and payment
        user_create = UserCreate(email="test@example.com", password="testpassword123")
        user = auth_service.create_user(db_session, user_create)
        
        payment_request = PaymentRequest(amount=Decimal('300.00'), payment_method="sbp")
        payment_response = payment_service.create_payment(db_session, str(user.id), payment_request)
        
        # Get payment status
        payment_data = payment_service.get_payment_status(payment_response.payment_id)
        
        assert payment_data is not None
        assert payment_data["payment_id"] == payment_response.payment_id
        assert payment_data["user_id"] == str(user.id)
        assert payment_data["amount"] == Decimal('300.00')
        assert payment_data["status"] == "pending"
    
    def test_confirm_payment_success(self, db_session: Session):
        """Test successful payment confirmation."""
        # Create user and payment
        user_create = UserCreate(email="test@example.com", password="testpassword123")
        user = auth_service.create_user(db_session, user_create)
        
        payment_request = PaymentRequest(amount=Decimal('1000.00'), payment_method="sbp")
        payment_response = payment_service.create_payment(db_session, str(user.id), payment_request)
        
        # Confirm payment
        confirmation = PaymentConfirmation(
            payment_id=payment_response.payment_id,
            reference_id="sbp_ref_12345",
            status="completed"
        )
        
        success = payment_service.confirm_payment(db_session, confirmation)
        
        # Check payment confirmed
        assert success is True
        
        # Check payment status updated
        payment_data = payment_service.get_payment_status(payment_response.payment_id)
        assert payment_data["status"] == "completed"
        assert payment_data["reference_id"] == "sbp_ref_12345"
        
        # Check user balance updated
        balance = billing_service.get_user_balance(db_session, str(user.id))
        assert balance == Decimal('1000.00')
    
    def test_confirm_payment_failure(self, db_session: Session):
        """Test payment confirmation failure."""
        # Create user and payment
        user_create = UserCreate(email="test@example.com", password="testpassword123")
        user = auth_service.create_user(db_session, user_create)
        
        payment_request = PaymentRequest(amount=Decimal('500.00'), payment_method="sbp")
        payment_response = payment_service.create_payment(db_session, str(user.id), payment_request)
        
        # Confirm payment as failed
        confirmation = PaymentConfirmation(
            payment_id=payment_response.payment_id,
            reference_id="",
            status="failed"
        )
        
        success = payment_service.confirm_payment(db_session, confirmation)
        
        # Check payment failed
        assert success is False
        
        # Check payment status updated
        payment_data = payment_service.get_payment_status(payment_response.payment_id)
        assert payment_data["status"] == "failed"
        
        # Check user balance not updated
        balance = billing_service.get_user_balance(db_session, str(user.id))
        assert balance == Decimal('0.00')
    
    def test_confirm_nonexistent_payment(self, db_session: Session):
        """Test confirming non-existent payment."""
        confirmation = PaymentConfirmation(
            payment_id="nonexistent-payment-id",
            reference_id="ref_123",
            status="completed"
        )
        
        with pytest.raises(ValueError, match="Payment not found"):
            payment_service.confirm_payment(db_session, confirmation)
    
    def test_confirm_already_processed_payment(self, db_session: Session):
        """Test confirming already processed payment."""
        # Create user and payment
        user_create = UserCreate(email="test@example.com", password="testpassword123")
        user = auth_service.create_user(db_session, user_create)
        
        payment_request = PaymentRequest(amount=Decimal('200.00'), payment_method="sbp")
        payment_response = payment_service.create_payment(db_session, str(user.id), payment_request)
        
        # Confirm payment first time
        confirmation = PaymentConfirmation(
            payment_id=payment_response.payment_id,
            reference_id="ref_123",
            status="completed"
        )
        payment_service.confirm_payment(db_session, confirmation)
        
        # Try to confirm again
        with pytest.raises(ValueError, match="Payment already processed"):
            payment_service.confirm_payment(db_session, confirmation)
    
    def test_cancel_payment(self, db_session: Session):
        """Test cancelling a payment."""
        # Create user and payment
        user_create = UserCreate(email="test@example.com", password="testpassword123")
        user = auth_service.create_user(db_session, user_create)
        
        payment_request = PaymentRequest(amount=Decimal('400.00'), payment_method="sbp")
        payment_response = payment_service.create_payment(db_session, str(user.id), payment_request)
        
        # Cancel payment
        success = payment_service.cancel_payment(payment_response.payment_id)
        
        assert success is True
        
        # Check payment status
        payment_data = payment_service.get_payment_status(payment_response.payment_id)
        assert payment_data["status"] == "cancelled"
    
    def test_cancel_nonexistent_payment(self):
        """Test cancelling non-existent payment."""
        with pytest.raises(ValueError, match="Payment not found"):
            payment_service.cancel_payment("nonexistent-payment-id")
    
    def test_simulate_payment_completion(self, db_session: Session):
        """Test simulating payment completion."""
        # Create user and payment
        user_create = UserCreate(email="test@example.com", password="testpassword123")
        user = auth_service.create_user(db_session, user_create)
        
        payment_request = PaymentRequest(amount=Decimal('600.00'), payment_method="sbp")
        payment_response = payment_service.create_payment(db_session, str(user.id), payment_request)
        
        # Simulate completion
        confirmation = payment_service.simulate_payment_completion(payment_response.payment_id)
        
        assert confirmation.payment_id == payment_response.payment_id
        assert confirmation.status == "completed"
        assert confirmation.reference_id is not None
        assert "sbp_ref_" in confirmation.reference_id
    
    def test_simulate_payment_failure(self, db_session: Session):
        """Test simulating payment failure."""
        # Create user and payment
        user_create = UserCreate(email="test@example.com", password="testpassword123")
        user = auth_service.create_user(db_session, user_create)
        
        payment_request = PaymentRequest(amount=Decimal('700.00'), payment_method="sbp")
        payment_response = payment_service.create_payment(db_session, str(user.id), payment_request)
        
        # Simulate failure
        confirmation = payment_service.simulate_payment_failure(payment_response.payment_id)
        
        assert confirmation.payment_id == payment_response.payment_id
        assert confirmation.status == "failed"
        assert confirmation.reference_id == ""


class TestPaymentAPI:
    """Test payment API endpoints."""
    
    def test_create_payment(self, client: TestClient, test_user_data):
        """Test creating payment via API."""
        # Register and login user
        client.post("/api/v1/auth/register", json=test_user_data)
        login_response = client.post("/api/v1/auth/login", json=test_user_data)
        token = login_response.json()["access_token"]
        
        # Create payment
        payment_data = {"amount": 500.00, "payment_method": "sbp"}
        response = client.post(
            "/api/v1/payments/create",
            json=payment_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "payment_id" in data
        assert float(data["amount"]) == 500.0
        assert data["status"] == "pending"
        assert "payment_url" in data
    
    def test_create_payment_invalid_amount(self, client: TestClient, test_user_data):
        """Test creating payment with invalid amount."""
        # Register and login user
        client.post("/api/v1/auth/register", json=test_user_data)
        login_response = client.post("/api/v1/auth/login", json=test_user_data)
        token = login_response.json()["access_token"]
        
        # Try negative amount
        payment_data = {"amount": -100.00, "payment_method": "sbp"}
        response = client.post(
            "/api/v1/payments/create",
            json=payment_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 422  # Pydantic validation error
        # The error will be in the validation details
    
    def test_get_payment_status(self, client: TestClient, test_user_data):
        """Test getting payment status via API."""
        # Register and login user
        client.post("/api/v1/auth/register", json=test_user_data)
        login_response = client.post("/api/v1/auth/login", json=test_user_data)
        token = login_response.json()["access_token"]
        
        # Create payment
        payment_data = {"amount": 300.00, "payment_method": "sbp"}
        create_response = client.post(
            "/api/v1/payments/create",
            json=payment_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        payment_id = create_response.json()["payment_id"]
        
        # Get payment status
        response = client.get(
            f"/api/v1/payments/status/{payment_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["payment_id"] == payment_id
        assert data["amount"] == 300.0
        assert data["status"] == "pending"
    
    def test_get_nonexistent_payment_status(self, client: TestClient, test_user_data):
        """Test getting status of non-existent payment."""
        # Register and login user
        client.post("/api/v1/auth/register", json=test_user_data)
        login_response = client.post("/api/v1/auth/login", json=test_user_data)
        token = login_response.json()["access_token"]
        
        # Try to get non-existent payment
        response = client.get(
            "/api/v1/payments/status/nonexistent-payment-id",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 404
        assert "Payment not found" in response.json()["detail"]
    
    def test_cancel_payment(self, client: TestClient, test_user_data):
        """Test cancelling payment via API."""
        # Register and login user
        client.post("/api/v1/auth/register", json=test_user_data)
        login_response = client.post("/api/v1/auth/login", json=test_user_data)
        token = login_response.json()["access_token"]
        
        # Create payment
        payment_data = {"amount": 400.00, "payment_method": "sbp"}
        create_response = client.post(
            "/api/v1/payments/create",
            json=payment_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        payment_id = create_response.json()["payment_id"]
        
        # Cancel payment
        response = client.post(
            f"/api/v1/payments/cancel/{payment_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"
    
    def test_test_complete_payment(self, client: TestClient, test_user_data):
        """Test completing payment via test endpoint."""
        # Register and login user
        client.post("/api/v1/auth/register", json=test_user_data)
        login_response = client.post("/api/v1/auth/login", json=test_user_data)
        token = login_response.json()["access_token"]
        
        # Create payment
        payment_data = {"amount": 1000.00, "payment_method": "sbp"}
        create_response = client.post(
            "/api/v1/payments/create",
            json=payment_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        payment_id = create_response.json()["payment_id"]
        
        # Complete payment using test endpoint
        response = client.post(
            f"/api/v1/payments/test/complete/{payment_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        
        # Check balance was updated
        balance_response = client.get(
            "/api/v1/billing/balance",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert balance_response.json()["balance"] == "1000.00"
    
    def test_unauthorized_access(self, client: TestClient):
        """Test accessing payment endpoints without authentication."""
        # Try to create payment without token
        payment_data = {"amount": 100.00, "payment_method": "sbp"}
        response = client.post("/api/v1/payments/create", json=payment_data)
        assert response.status_code == 403
        
        # Try to get payment status without token
        response = client.get("/api/v1/payments/status/some-payment-id")
        assert response.status_code == 403