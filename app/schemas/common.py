"""
Common Pydantic schemas for API validation.
"""
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field
from enum import Enum


class HTTPError(BaseModel):
    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Specific error code")
    timestamp: Optional[str] = Field(None, description="Error timestamp")


class ValidationError(BaseModel):
    field: str = Field(..., description="Field that failed validation")
    message: str = Field(..., description="Validation error message")
    value: Optional[Any] = Field(None, description="Invalid value that was provided")


class ValidationErrorResponse(BaseModel):
    detail: str = "Validation error"
    errors: List[ValidationError] = Field(..., description="List of validation errors")


class SuccessResponse(BaseModel):
    success: bool = True
    message: str = Field(..., description="Success message")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional response data")


class PaginationParams(BaseModel):
    page: int = Field(1, ge=1, description="Page number (1-based)")
    size: int = Field(20, ge=1, le=100, description="Number of items per page")


class PaginatedResponse(BaseModel):
    items: List[Any] = Field(..., description="List of items for current page")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total number of pages")


class HealthCheck(BaseModel):
    status: str = Field("healthy", description="Service health status")
    version: str = Field(..., description="API version")
    timestamp: str = Field(..., description="Current timestamp")
    services: Dict[str, str] = Field(..., description="Status of dependent services")


class APIInfo(BaseModel):
    name: str = Field("Filmlist API", description="API name")
    version: str = Field("1.0.0", description="API version")
    description: str = Field("API for automated montage list generation", description="API description")
    docs_url: str = Field("/docs", description="Documentation URL")


class RateLimitInfo(BaseModel):
    requests_remaining: int = Field(..., description="Requests remaining in current window")
    reset_time: int = Field(..., description="Time when rate limit resets (Unix timestamp)")
    limit: int = Field(..., description="Total requests allowed per window")


class ProcessingCost(BaseModel):
    duration_minutes: float = Field(..., description="Video duration in minutes")
    rate_per_minute: float = Field(..., description="Cost per minute in rubles")
    total_cost: float = Field(..., description="Total estimated cost in rubles")
    user_balance: float = Field(..., description="Current user balance")
    sufficient_balance: bool = Field(..., description="Whether user has sufficient balance")