"""
Tests for billing functionality.
"""
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.billing import billing_service
from app.services.auth import auth_service
from app.schemas.user import UserCreate
from app.schemas.transaction import TransactionType


class TestBillingService:
    """Test billing service methods."""
    
    def test_calculate_cost(self):
        """Test cost calculation."""
        # Test basic calculation
        cost = billing_service.calculate_cost(10.0)  # 10 minutes
        expected = Decimal('750.00')  # 10 * 75
        assert cost == expected
        
        # Test fractional minutes
        cost = billing_service.calculate_cost(1.5)  # 1.5 minutes
        expected = Decimal('112.50')  # 1.5 * 75
        assert cost == expected
        
        # Test zero minutes
        cost = billing_service.calculate_cost(0.0)
        expected = Decimal('0.00')
        assert cost == expected
    
    def test_get_user_balance(self, db_session: Session):
        """Test getting user balance."""
        # Create user
        user_create = UserCreate(email="test@example.com", password="testpassword123")
        user = auth_service.create_user(db_session, user_create)
        
        # Get balance (should be 0.00 for new user)
        balance = billing_service.get_user_balance(db_session, str(user.id))
        assert balance == Decimal('0.00')
    
    def test_get_available_minutes(self, db_session: Session):
        """Test calculating available minutes."""
        # Create user
        user_create = UserCreate(email="test@example.com", password="testpassword123")
        user = auth_service.create_user(db_session, user_create)
        
        # Get available minutes (should be 0.0 for new user)
        minutes = billing_service.get_available_minutes(db_session, str(user.id))
        assert minutes == 0.0
        
        # Add funds and check minutes
        billing_service.add_funds(db_session, str(user.id), Decimal('150.00'), "Test payment")
        minutes = billing_service.get_available_minutes(db_session, str(user.id))
        assert minutes == 2.0  # 150 / 75 = 2 minutes
    
    def test_has_sufficient_balance(self, db_session: Session):
        """Test checking sufficient balance."""
        # Create user
        user_create = UserCreate(email="test@example.com", password="testpassword123")
        user = auth_service.create_user(db_session, user_create)
        
        # Check insufficient balance
        has_balance = billing_service.has_sufficient_balance(db_session, str(user.id), Decimal('100.00'))
        assert has_balance is False
        
        # Add funds
        billing_service.add_funds(db_session, str(user.id), Decimal('200.00'), "Test payment")
        
        # Check sufficient balance
        has_balance = billing_service.has_sufficient_balance(db_session, str(user.id), Decimal('100.00'))
        assert has_balance is True
        
        # Check exact balance
        has_balance = billing_service.has_sufficient_balance(db_session, str(user.id), Decimal('200.00'))
        assert has_balance is True
        
        # Check insufficient balance
        has_balance = billing_service.has_sufficient_balance(db_session, str(user.id), Decimal('300.00'))
        assert has_balance is False
    
    def test_add_funds(self, db_session: Session):
        """Test adding funds to user balance."""
        # Create user
        user_create = UserCreate(email="test@example.com", password="testpassword123")
        user = auth_service.create_user(db_session, user_create)
        
        # Add funds
        transaction = billing_service.add_funds(
            db_session, 
            str(user.id), 
            Decimal('500.00'), 
            "Test payment",
            "payment_ref_123"
        )
        
        # Check transaction
        assert transaction.amount == Decimal('500.00')
        assert transaction.type == TransactionType.PAYMENT
        assert transaction.description == "Test payment"
        assert transaction.reference_id == "payment_ref_123"
        
        # Check balance updated
        balance = billing_service.get_user_balance(db_session, str(user.id))
        assert balance == Decimal('500.00')
    
    def test_charge_user(self, db_session: Session):
        """Test charging user for processing."""
        # Create user and add funds
        user_create = UserCreate(email="test@example.com", password="testpassword123")
        user = auth_service.create_user(db_session, user_create)
        billing_service.add_funds(db_session, str(user.id), Decimal('300.00'), "Initial payment")
        
        # Charge user
        transaction = billing_service.charge_user(
            db_session,
            str(user.id),
            Decimal('150.00'),
            "Video processing - 2 minutes"
        )
        
        # Check transaction
        assert transaction.amount == Decimal('-150.00')  # Negative for charges
        assert transaction.type == TransactionType.CHARGE
        assert transaction.description == "Video processing - 2 minutes"
        
        # Check balance updated
        balance = billing_service.get_user_balance(db_session, str(user.id))
        assert balance == Decimal('150.00')  # 300 - 150
    
    def test_charge_user_insufficient_balance(self, db_session: Session):
        """Test charging user with insufficient balance."""
        # Create user (no funds)
        user_create = UserCreate(email="test@example.com", password="testpassword123")
        user = auth_service.create_user(db_session, user_create)
        
        # Try to charge user
        with pytest.raises(ValueError, match="Insufficient balance"):
            billing_service.charge_user(
                db_session,
                str(user.id),
                Decimal('100.00'),
                "Video processing"
            )
    
    def test_refund_user(self, db_session: Session):
        """Test refunding user."""
        # Create user
        user_create = UserCreate(email="test@example.com", password="testpassword123")
        user = auth_service.create_user(db_session, user_create)
        
        # Refund user
        transaction = billing_service.refund_user(
            db_session,
            str(user.id),
            Decimal('100.00'),
            "Processing failed - refund",
            "refund_ref_456"
        )
        
        # Check transaction
        assert transaction.amount == Decimal('100.00')
        assert transaction.type == TransactionType.REFUND
        assert transaction.description == "Processing failed - refund"
        assert transaction.reference_id == "refund_ref_456"
        
        # Check balance updated
        balance = billing_service.get_user_balance(db_session, str(user.id))
        assert balance == Decimal('100.00')
    
    def test_get_user_transactions(self, db_session: Session):
        """Test getting user transaction history."""
        # Create user
        user_create = UserCreate(email="test@example.com", password="testpassword123")
        user = auth_service.create_user(db_session, user_create)
        
        # Create multiple transactions
        billing_service.add_funds(db_session, str(user.id), Decimal('500.00'), "Payment 1")
        billing_service.charge_user(db_session, str(user.id), Decimal('75.00'), "Processing 1")
        billing_service.add_funds(db_session, str(user.id), Decimal('200.00'), "Payment 2")
        billing_service.refund_user(db_session, str(user.id), Decimal('25.00'), "Refund 1")
        
        # Get transactions
        transactions = billing_service.get_user_transactions(db_session, str(user.id))
        
        # Check we got all transactions
        assert len(transactions) == 4
        
        # Check transaction types are present (order may vary)
        transaction_types = [t.type for t in transactions]
        assert TransactionType.REFUND in transaction_types
        assert TransactionType.PAYMENT in transaction_types
        assert TransactionType.CHARGE in transaction_types
        assert transaction_types.count(TransactionType.PAYMENT) == 2  # Two payments
    
    def test_user_not_found_operations(self, db_session: Session):
        """Test operations with non-existent user."""
        fake_user_id = "00000000-0000-0000-0000-000000000000"
        
        # Test charge user
        with pytest.raises(ValueError, match="User not found"):
            billing_service.charge_user(db_session, fake_user_id, Decimal('100.00'), "Test")
        
        # Test add funds
        with pytest.raises(ValueError, match="User not found"):
            billing_service.add_funds(db_session, fake_user_id, Decimal('100.00'), "Test")
        
        # Test refund
        with pytest.raises(ValueError, match="User not found"):
            billing_service.refund_user(db_session, fake_user_id, Decimal('100.00'), "Test")


class TestBillingAPI:
    """Test billing API endpoints."""
    
    def test_get_balance(self, client: TestClient, test_user_data):
        """Test getting user balance via API."""
        # Register and login user
        client.post("/api/v1/auth/register", json=test_user_data)
        login_response = client.post("/api/v1/auth/login", json=test_user_data)
        token = login_response.json()["access_token"]
        
        # Get balance
        response = client.get(
            "/api/v1/billing/balance",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "balance" in data
        assert "available_minutes" in data
        assert data["balance"] == "0.00"
        assert data["available_minutes"] == 0.0
    
    def test_calculate_cost(self, client: TestClient, test_user_data):
        """Test cost calculation via API."""
        # Register and login user
        client.post("/api/v1/auth/register", json=test_user_data)
        login_response = client.post("/api/v1/auth/login", json=test_user_data)
        token = login_response.json()["access_token"]
        
        # Calculate cost
        response = client.post(
            "/api/v1/billing/calculate-cost?duration_minutes=2.0",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["duration_minutes"] == 2.0
        assert data["cost_rubles"] == 150.0  # 2 * 75
        assert data["rate_per_minute"] == 75.0
    
    def test_calculate_cost_invalid_duration(self, client: TestClient, test_user_data):
        """Test cost calculation with invalid duration."""
        # Register and login user
        client.post("/api/v1/auth/register", json=test_user_data)
        login_response = client.post("/api/v1/auth/login", json=test_user_data)
        token = login_response.json()["access_token"]
        
        # Try negative duration
        response = client.post(
            "/api/v1/billing/calculate-cost?duration_minutes=-1.0",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 400
        assert "Duration must be positive" in response.json()["detail"]
    
    def test_check_balance(self, client: TestClient, test_user_data):
        """Test checking sufficient balance via API."""
        # Register and login user
        client.post("/api/v1/auth/register", json=test_user_data)
        login_response = client.post("/api/v1/auth/login", json=test_user_data)
        token = login_response.json()["access_token"]
        
        # Check balance for 1 minute processing
        response = client.post(
            "/api/v1/billing/check-balance?duration_minutes=1.0",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["duration_minutes"] == 1.0
        assert data["required_cost"] == 75.0
        assert data["current_balance"] == 0.0
        assert data["sufficient_balance"] is False
        assert data["shortfall"] == 75.0
    
    def test_get_transactions_empty(self, client: TestClient, test_user_data):
        """Test getting empty transaction history."""
        # Register and login user
        client.post("/api/v1/auth/register", json=test_user_data)
        login_response = client.post("/api/v1/auth/login", json=test_user_data)
        token = login_response.json()["access_token"]
        
        # Get transactions
        response = client.get(
            "/api/v1/billing/transactions",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_unauthorized_access(self, client: TestClient):
        """Test accessing billing endpoints without authentication."""
        # Try to access balance without token
        response = client.get("/api/v1/billing/balance")
        assert response.status_code == 403
        
        # Try to access transactions without token
        response = client.get("/api/v1/billing/transactions")
        assert response.status_code == 403