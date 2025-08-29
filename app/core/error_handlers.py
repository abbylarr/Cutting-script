"""
Error handling middleware and exception handlers for FastAPI application.
Provides structured error responses and comprehensive logging.
"""

import traceback
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Union

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import FilmlistException, ErrorCode, SystemError
from app.core.logging import get_logger

logger = get_logger("error_handlers")


class ErrorResponse:
    """Standardized error response format."""
    
    def __init__(
        self,
        error_code: str,
        message: str,
        status_code: int,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None
    ):
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.request_id = request_id or str(uuid.uuid4())
        self.details = details or {}
        self.timestamp = timestamp or datetime.utcnow().isoformat() + "Z"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        response_data = {
            "error": True,
            "error_code": self.error_code,
            "message": self.message,
            "request_id": self.request_id,
            "timestamp": self.timestamp
        }
        
        if self.details:
            response_data["details"] = self.details
        
        return response_data
    
    def to_json_response(self) -> JSONResponse:
        """Convert to FastAPI JSONResponse."""
        return JSONResponse(
            status_code=self.status_code,
            content=self.to_dict()
        )


async def filmlist_exception_handler(request: Request, exc: FilmlistException) -> JSONResponse:
    """Handle custom filmlist exceptions."""
    
    request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
    
    # Log the error with full context
    logger.log_error_with_context(
        error=exc,
        context={
            "request_id": request_id,
            "request_method": request.method,
            "request_url": str(request.url),
            "user_agent": request.headers.get("user-agent"),
            "client_ip": request.client.host if request.client else None
        },
        user_message=exc.user_message
    )
    
    # Create error response
    error_response = ErrorResponse(
        error_code=exc.error_code.value,
        message=exc.user_message,
        status_code=exc.status_code,
        request_id=request_id,
        details=exc.details
    )
    
    return error_response.to_json_response()


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTP exceptions."""
    
    request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
    
    # Map HTTP status codes to error codes
    status_to_error_code = {
        400: ErrorCode.INTERNAL_ERROR,
        401: ErrorCode.INVALID_CREDENTIALS,
        403: ErrorCode.INSUFFICIENT_PERMISSIONS,
        404: ErrorCode.TASK_NOT_FOUND,
        422: ErrorCode.INTERNAL_ERROR,
        429: ErrorCode.RATE_LIMIT_EXCEEDED,
        500: ErrorCode.INTERNAL_ERROR,
        502: ErrorCode.INTERNAL_ERROR,
        503: ErrorCode.INTERNAL_ERROR
    }
    
    error_code = status_to_error_code.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    
    # Log the error
    logger.error(
        f"HTTP exception: {exc.status_code} - {exc.detail}",
        extra={
            "request_id": request_id,
            "status_code": exc.status_code,
            "error_detail": exc.detail,
            "request_method": request.method,
            "request_url": str(request.url)
        }
    )
    
    # Create user-friendly message
    user_messages = {
        400: "Неверный запрос. Проверьте правильность данных.",
        401: "Необходима авторизация для доступа к ресурсу.",
        403: "Недостаточно прав для выполнения операции.",
        404: "Запрашиваемый ресурс не найден.",
        422: "Ошибка валидации данных.",
        429: "Превышен лимит запросов. Повторите попытку позже.",
        500: "Внутренняя ошибка сервера.",
        502: "Ошибка внешнего сервиса.",
        503: "Сервис временно недоступен."
    }
    
    user_message = user_messages.get(exc.status_code, "Произошла неожиданная ошибка.")
    
    error_response = ErrorResponse(
        error_code=error_code.value,
        message=user_message,
        status_code=exc.status_code,
        request_id=request_id,
        details={"original_detail": exc.detail} if exc.detail != user_message else {}
    )
    
    return error_response.to_json_response()


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic validation errors."""
    
    request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
    
    # Extract validation errors
    validation_errors = []
    for error in exc.errors():
        field_path = " -> ".join(str(loc) for loc in error["loc"])
        validation_errors.append({
            "field": field_path,
            "message": error["msg"],
            "type": error["type"],
            "input": error.get("input")
        })
    
    # Log validation error
    logger.warning(
        f"Validation error: {len(validation_errors)} field(s) failed validation",
        extra={
            "request_id": request_id,
            "validation_errors": validation_errors,
            "request_method": request.method,
            "request_url": str(request.url)
        }
    )
    
    error_response = ErrorResponse(
        error_code=ErrorCode.INTERNAL_ERROR.value,
        message="Ошибка валидации данных. Проверьте правильность заполнения полей.",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        request_id=request_id,
        details={
            "validation_errors": validation_errors,
            "fields_count": len(validation_errors)
        }
    )
    
    return error_response.to_json_response()


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all other unhandled exceptions."""
    
    request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
    
    # Log the unexpected error with full traceback
    logger.critical(
        f"Unhandled exception: {type(exc).__name__}: {str(exc)}",
        extra={
            "request_id": request_id,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "request_method": request.method,
            "request_url": str(request.url),
            "traceback": traceback.format_exc()
        }
    )
    
    # Create generic error response (don't expose internal details)
    error_response = ErrorResponse(
        error_code=ErrorCode.INTERNAL_ERROR.value,
        message="Произошла внутренняя ошибка сервера. Мы работаем над устранением проблемы.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        request_id=request_id
    )
    
    return error_response.to_json_response()


class ErrorHandlerMiddleware:
    """Middleware to add request tracking and error context."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Generate request ID
        request_id = str(uuid.uuid4())
        
        # Add request ID to scope
        scope["state"] = getattr(scope, "state", {})
        scope["state"]["request_id"] = request_id
        
        # Log request start
        request = Request(scope, receive)
        logger.log_api_request(
            method=request.method,
            path=str(request.url.path),
            extra={
                "request_id": request_id,
                "query_params": dict(request.query_params),
                "user_agent": request.headers.get("user-agent"),
                "client_ip": request.client.host if request.client else None
            }
        )
        
        await self.app(scope, receive, send)


def setup_error_handlers(app):
    """Setup all error handlers for the FastAPI application."""
    
    # Add middleware
    app.add_middleware(ErrorHandlerMiddleware)
    
    # Add exception handlers
    app.add_exception_handler(FilmlistException, filmlist_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    
    logger.info("Error handlers configured successfully")


# Utility functions for creating common errors
def create_validation_error(
    field: str, 
    message: str, 
    value: Any = None,
    error_code: ErrorCode = ErrorCode.INTERNAL_ERROR
) -> FilmlistException:
    """Create a validation error with proper formatting."""
    from app.core.exceptions import ValidationError
    
    return ValidationError(
        message=f"Validation failed for field '{field}': {message}",
        error_code=error_code,
        field=field,
        value=value
    )


def create_not_found_error(
    resource_type: str,
    resource_id: str,
    error_code: ErrorCode = ErrorCode.TASK_NOT_FOUND
) -> FilmlistException:
    """Create a not found error with proper formatting."""
    from app.core.exceptions import NotFoundError
    
    return NotFoundError(
        message=f"{resource_type.title()} not found: {resource_id}",
        error_code=error_code,
        resource_type=resource_type,
        resource_id=resource_id
    )


def create_business_logic_error(
    message: str,
    error_code: ErrorCode,
    details: Optional[Dict[str, Any]] = None
) -> FilmlistException:
    """Create a business logic error with proper formatting."""
    from app.core.exceptions import BusinessLogicError
    
    return BusinessLogicError(
        message=message,
        error_code=error_code,
        details=details
    )


def create_external_service_error(
    service_name: str,
    operation: str,
    error_message: str,
    error_code: ErrorCode,
    retry_after: Optional[int] = None
) -> FilmlistException:
    """Create an external service error with proper formatting."""
    from app.core.exceptions import ExternalServiceError
    
    return ExternalServiceError(
        message=f"{service_name} {operation} failed: {error_message}",
        error_code=error_code,
        service_name=service_name,
        retry_after=retry_after
    )


def create_processing_error(
    step: str,
    error_message: str,
    error_code: ErrorCode,
    task_id: Optional[str] = None
) -> FilmlistException:
    """Create a processing error with proper formatting."""
    from app.core.exceptions import ProcessingError
    
    return ProcessingError(
        message=f"Processing step '{step}' failed: {error_message}",
        error_code=error_code,
        step=step,
        task_id=task_id
    )