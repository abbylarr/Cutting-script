"""
Authentication API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.schemas.user import (
    UserCreate, 
    UserLogin, 
    UserResponse, 
    TokenResponse,
    BalanceResponse
)
from app.services.auth import auth_service
from app.core.config import settings


router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_create: UserCreate,
    db: Session = Depends(get_db)
):
    """
    Register a new user and return JWT token.
    """
    try:
        user = auth_service.create_user(db, user_create)
        
        # Create token for the new user
        from datetime import timedelta
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = auth_service.create_access_token(
            data={"sub": str(user.id), "email": user.email},
            expires_delta=access_token_expires
        )
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.model_validate(user)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось создать пользователя"
        )


@router.post("/login", response_model=TokenResponse)
async def login_user(
    user_login: UserLogin,
    db: Session = Depends(get_db)
):
    """
    Login user and return JWT token.
    """
    try:
        token_response = auth_service.login_user(db, user_login)
        return token_response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user information.
    """
    return UserResponse.model_validate(current_user)


@router.get("/balance", response_model=BalanceResponse)
async def get_user_balance(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user balance and available processing minutes.
    """
    available_minutes = float(current_user.balance) / settings.RATE_PER_MINUTE
    
    return BalanceResponse(
        balance=current_user.balance,
        available_minutes=available_minutes
    )