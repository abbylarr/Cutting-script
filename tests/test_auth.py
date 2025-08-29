"""
Tests for authentication functionality.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.auth import auth_service
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin


class TestAuthService:
    """Test authentication service methods."""
    
    def test_password_hashing(self):
        """Test password hashing and verification."""
        password = "testpassword123"
        hashed = auth_service.get_password_hash(password)
        
        # Hash should be different from original password
        assert hashed != password
        
        # Verification should work
        assert auth_service.verify_password(password, hashed) is True
        
        # Wrong password should fail
        assert auth_service.verify_password("wrongpassword", hashed) is False
    
    def test_jwt_token_creation_and_verification(self):
        """Test JWT token creation and verification."""
        data = {"sub": "test-user-id", "email": "test@example.com"}
        token = auth_service.create_access_token(data)
        
        # Token should be a string
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Verify token
        payload = auth_service.verify_token(token)
        assert payload is not None
        assert payload["sub"] == "test-user-id"
        assert payload["email"] == "test@example.com"
        assert "exp" in payload
    
    def test_invalid_token_verification(self):
        """Test verification of invalid tokens."""
        # Invalid token should return None
        assert auth_service.verify_token("invalid-token") is None
        assert auth_service.verify_token("") is None
    
    def test_create_user(self, db_session: Session):
        """Test user creation."""
        user_create = UserCreate(email="test@example.com", password="testpassword123")
        user = auth_service.create_user(db_session, user_create)
        
        assert user.email == "test@example.com"
        assert user.password_hash != "testpassword123"  # Should be hashed
        assert user.balance == 0.00
        assert user.id is not None
    
    def test_create_duplicate_user(self, db_session: Session):
        """Test creating user with duplicate email."""
        user_create = UserCreate(email="test@example.com", password="testpassword123")
        
        # Create first user
        auth_service.create_user(db_session, user_create)
        
        # Try to create duplicate user
        with pytest.raises(ValueError, match="User with this email already exists"):
            auth_service.create_user(db_session, user_create)
    
    def test_authenticate_user(self, db_session: Session):
        """Test user authentication."""
        # Create user
        user_create = UserCreate(email="test@example.com", password="testpassword123")
        created_user = auth_service.create_user(db_session, user_create)
        
        # Authenticate with correct credentials
        user = auth_service.authenticate_user(db_session, "test@example.com", "testpassword123")
        assert user is not None
        assert user.id == created_user.id
        
        # Authenticate with wrong password
        user = auth_service.authenticate_user(db_session, "test@example.com", "wrongpassword")
        assert user is None
        
        # Authenticate with wrong email
        user = auth_service.authenticate_user(db_session, "wrong@example.com", "testpassword123")
        assert user is None
    
    def test_login_user(self, db_session: Session):
        """Test user login and token generation."""
        # Create user
        user_create = UserCreate(email="test@example.com", password="testpassword123")
        auth_service.create_user(db_session, user_create)
        
        # Login with correct credentials
        user_login = UserLogin(email="test@example.com", password="testpassword123")
        token_response = auth_service.login_user(db_session, user_login)
        
        assert token_response.access_token is not None
        assert token_response.token_type == "bearer"
        assert token_response.expires_in > 0
        
        # Verify token contains correct data
        payload = auth_service.verify_token(token_response.access_token)
        assert payload["email"] == "test@example.com"
    
    def test_login_invalid_credentials(self, db_session: Session):
        """Test login with invalid credentials."""
        user_login = UserLogin(email="nonexistent@example.com", password="password")
        
        with pytest.raises(ValueError, match="Invalid email or password"):
            auth_service.login_user(db_session, user_login)


class TestAuthAPI:
    """Test authentication API endpoints."""
    
    def test_register_user(self, client: TestClient, test_user_data):
        """Test user registration endpoint."""
        response = client.post("/api/v1/auth/register", json=test_user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == test_user_data["email"]
        assert "id" in data
        assert "balance" in data
        assert "created_at" in data
        assert "password" not in data  # Password should not be returned
    
    def test_register_duplicate_user(self, client: TestClient, test_user_data):
        """Test registering user with duplicate email."""
        # Register first user
        client.post("/api/v1/auth/register", json=test_user_data)
        
        # Try to register duplicate
        response = client.post("/api/v1/auth/register", json=test_user_data)
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]
    
    def test_register_invalid_data(self, client: TestClient):
        """Test registration with invalid data."""
        # Invalid email
        response = client.post("/api/v1/auth/register", json={
            "email": "invalid-email",
            "password": "testpassword123"
        })
        assert response.status_code == 422
        
        # Short password
        response = client.post("/api/v1/auth/register", json={
            "email": "test@example.com",
            "password": "short"
        })
        assert response.status_code == 422
    
    def test_login_user(self, client: TestClient, test_user_data):
        """Test user login endpoint."""
        # Register user first
        client.post("/api/v1/auth/register", json=test_user_data)
        
        # Login
        response = client.post("/api/v1/auth/login", json=test_user_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
    
    def test_login_invalid_credentials(self, client: TestClient):
        """Test login with invalid credentials."""
        response = client.post("/api/v1/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "wrongpassword"
        })
        
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]
    
    def test_get_current_user(self, client: TestClient, test_user_data):
        """Test getting current user information."""
        # Register and login user
        client.post("/api/v1/auth/register", json=test_user_data)
        login_response = client.post("/api/v1/auth/login", json=test_user_data)
        token = login_response.json()["access_token"]
        
        # Get current user info
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user_data["email"]
        assert "id" in data
        assert "balance" in data
    
    def test_get_current_user_unauthorized(self, client: TestClient):
        """Test getting current user without authentication."""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 403  # No authorization header
        
        # Invalid token
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid-token"}
        )
        assert response.status_code == 401
    
    def test_get_user_balance(self, client: TestClient, test_user_data):
        """Test getting user balance."""
        # Register and login user
        client.post("/api/v1/auth/register", json=test_user_data)
        login_response = client.post("/api/v1/auth/login", json=test_user_data)
        token = login_response.json()["access_token"]
        
        # Get balance
        response = client.get(
            "/api/v1/auth/balance",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "balance" in data
        assert "available_minutes" in data
        assert data["balance"] == "0.00"  # New user should have 0 balance
        assert data["available_minutes"] == 0.0