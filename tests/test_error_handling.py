"""
Unit tests for error handling system.
Tests custom exceptions, error handlers, and logging functionality.
"""

import pytest
import json
import uuid
from unittest.mock import Mock, patch, MagicMock
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import (
    FilmlistException, ErrorCode, ValidationError, AuthenticationError,
    AuthorizationError, NotFoundError, BusinessLogicError, RateLimitError,
    ExternalServiceError, ProcessingError, SystemError,
    file_not_found_error, task_not_found_error, insufficient_balance_error,
    invalid_file_format_error, file_too_large_error, openai_rate_limit_error,
    ffmpeg_error
)
from app.core.error_handlers import (
    ErrorResponse, filmlist_exception_handler, http_exception_handler,
    validation_exception_handler, general_exception_handler,
    create_validation_error, create_not_found_error, create_business_logic_error,
    create_external_service_error, create_processing_error
)
from app.core.logging import FilmlistLogger, get_logger


class TestCustomExceptions:
    """Test custom exception classes."""
    
    def test_filmlist_exception_basic(self):
        """Test basic FilmlistException functionality."""
        exc = FilmlistException(
            message="Test error",
            error_code=ErrorCode.INTERNAL_ERROR,
            status_code=500
        )
        
        assert exc.message == "Test error"
        assert exc.error_code == ErrorCode.INTERNAL_ERROR
        assert exc.status_code == 500
        assert exc.details == {}
        assert "Внутренняя ошибка сервера" in exc.user_message
    
    def test_filmlist_exception_with_details(self):
        """Test FilmlistException with details and custom user message."""
        details = {"field": "video_file", "size": 1000000}
        user_msg = "Custom user message"
        
        exc = FilmlistException(
            message="Technical error",
            error_code=ErrorCode.FILE_TOO_LARGE,
            details=details,
            user_message=user_msg
        )
        
        assert exc.details == details
        assert exc.user_message == user_msg
        
        exc_dict = exc.to_dict()
        assert exc_dict["error_code"] == ErrorCode.FILE_TOO_LARGE.value
        assert exc_dict["message"] == user_msg
        assert exc_dict["details"] == details
        assert exc_dict["technical_message"] == "Technical error"
    
    def test_validation_error(self):
        """Test ValidationError exception."""
        exc = ValidationError(
            message="Invalid file format",
            error_code=ErrorCode.INVALID_FILE_FORMAT,
            field="file_format",
            value="txt"
        )
        
        assert exc.status_code == status.HTTP_400_BAD_REQUEST
        assert exc.details["field"] == "file_format"
        assert exc.details["value"] == "txt"
        assert "Неподдерживаемый формат файла" in exc.user_message
    
    def test_authentication_error(self):
        """Test AuthenticationError exception."""
        exc = AuthenticationError(
            message="Invalid token",
            error_code=ErrorCode.TOKEN_EXPIRED
        )
        
        assert exc.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc.error_code == ErrorCode.TOKEN_EXPIRED
        assert "аутентификации" in exc.user_message
    
    def test_authorization_error(self):
        """Test AuthorizationError exception."""
        exc = AuthorizationError(
            message="Access denied",
            user_message="Нет доступа к ресурсу"
        )
        
        assert exc.status_code == status.HTTP_403_FORBIDDEN
        assert exc.user_message == "Нет доступа к ресурсу"
    
    def test_not_found_error(self):
        """Test NotFoundError exception."""
        exc = NotFoundError(
            message="Task not found",
            error_code=ErrorCode.TASK_NOT_FOUND,
            resource_type="task",
            resource_id="123"
        )
        
        assert exc.status_code == status.HTTP_404_NOT_FOUND
        assert exc.details["resource_type"] == "task"
        assert exc.details["resource_id"] == "123"
    
    def test_business_logic_error(self):
        """Test BusinessLogicError exception."""
        details = {"required": 100, "available": 50}
        exc = BusinessLogicError(
            message="Insufficient balance",
            error_code=ErrorCode.INSUFFICIENT_BALANCE,
            details=details
        )
        
        assert exc.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert exc.details == details
    
    def test_rate_limit_error(self):
        """Test RateLimitError exception."""
        exc = RateLimitError(
            message="Rate limit exceeded",
            retry_after=60
        )
        
        assert exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert exc.error_code == ErrorCode.RATE_LIMIT_EXCEEDED
        assert exc.details["retry_after"] == 60
    
    def test_external_service_error(self):
        """Test ExternalServiceError exception."""
        exc = ExternalServiceError(
            message="OpenAI API error",
            error_code=ErrorCode.OPENAI_API_ERROR,
            service_name="OpenAI",
            retry_after=30
        )
        
        assert exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert exc.details["service"] == "OpenAI"
        assert exc.details["retry_after"] == 30
    
    def test_processing_error(self):
        """Test ProcessingError exception."""
        exc = ProcessingError(
            message="FFmpeg failed",
            error_code=ErrorCode.FFMPEG_ERROR,
            step="audio_extraction",
            task_id="task_123"
        )
        
        assert exc.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert exc.details["processing_step"] == "audio_extraction"
        assert exc.details["task_id"] == "task_123"
    
    def test_system_error(self):
        """Test SystemError exception."""
        exc = SystemError(
            message="Database connection failed",
            error_code=ErrorCode.DATABASE_ERROR,
            component="postgresql"
        )
        
        assert exc.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert exc.details["component"] == "postgresql"


class TestConvenienceFunctions:
    """Test convenience functions for creating common errors."""
    
    def test_file_not_found_error(self):
        """Test file_not_found_error function."""
        exc = file_not_found_error("/path/to/file.mp4")
        
        assert isinstance(exc, NotFoundError)
        assert exc.error_code == ErrorCode.FILE_NOT_FOUND
        assert exc.details["resource_type"] == "file"
        assert exc.details["resource_id"] == "/path/to/file.mp4"
    
    def test_task_not_found_error(self):
        """Test task_not_found_error function."""
        task_id = "task_123"
        exc = task_not_found_error(task_id)
        
        assert isinstance(exc, NotFoundError)
        assert exc.error_code == ErrorCode.TASK_NOT_FOUND
        assert exc.details["resource_type"] == "task"
        assert exc.details["resource_id"] == task_id
    
    def test_insufficient_balance_error(self):
        """Test insufficient_balance_error function."""
        exc = insufficient_balance_error(required=100.0, available=50.0)
        
        assert isinstance(exc, BusinessLogicError)
        assert exc.error_code == ErrorCode.INSUFFICIENT_BALANCE
        assert exc.details["required_balance"] == 100.0
        assert exc.details["available_balance"] == 50.0
        assert exc.details["deficit"] == 50.0
    
    def test_invalid_file_format_error(self):
        """Test invalid_file_format_error function."""
        exc = invalid_file_format_error("txt", ["mp4", "avi", "mov"])
        
        assert isinstance(exc, ValidationError)
        assert exc.error_code == ErrorCode.INVALID_FILE_FORMAT
        assert exc.details["field"] == "file_format"
        assert exc.details["value"] == "txt"
        assert "mp4, avi, mov" in exc.user_message
    
    def test_file_too_large_error(self):
        """Test file_too_large_error function."""
        file_size = 3 * 1024**3  # 3GB
        max_size = 2 * 1024**3   # 2GB
        exc = file_too_large_error(file_size, max_size)
        
        assert isinstance(exc, ValidationError)
        assert exc.error_code == ErrorCode.FILE_TOO_LARGE
        assert exc.details["field"] == "file_size"
        assert exc.details["value"] == file_size
        assert "3.0 ГБ" in exc.user_message
        assert "2.0 ГБ" in exc.user_message
    
    def test_openai_rate_limit_error(self):
        """Test openai_rate_limit_error function."""
        exc = openai_rate_limit_error(retry_after=120)
        
        assert isinstance(exc, ExternalServiceError)
        assert exc.error_code == ErrorCode.OPENAI_RATE_LIMIT
        assert exc.details["service"] == "OpenAI"
        assert exc.details["retry_after"] == 120
    
    def test_ffmpeg_error(self):
        """Test ffmpeg_error function."""
        exc = ffmpeg_error("audio_extraction", "Invalid codec")
        
        assert isinstance(exc, ProcessingError)
        assert exc.error_code == ErrorCode.FFMPEG_ERROR
        assert exc.details["step"] == "audio_extraction"
        assert "audio_extraction" in exc.user_message


class TestErrorResponse:
    """Test ErrorResponse class."""
    
    def test_error_response_basic(self):
        """Test basic ErrorResponse functionality."""
        response = ErrorResponse(
            error_code="TEST_ERROR",
            message="Test message",
            status_code=400
        )
        
        response_dict = response.to_dict()
        
        assert response_dict["error"] is True
        assert response_dict["error_code"] == "TEST_ERROR"
        assert response_dict["message"] == "Test message"
        assert "request_id" in response_dict
        assert "timestamp" in response_dict
    
    def test_error_response_with_details(self):
        """Test ErrorResponse with details."""
        details = {"field": "test", "value": 123}
        response = ErrorResponse(
            error_code="VALIDATION_ERROR",
            message="Validation failed",
            status_code=422,
            details=details
        )
        
        response_dict = response.to_dict()
        assert response_dict["details"] == details
    
    def test_error_response_json_response(self):
        """Test ErrorResponse JSON response generation."""
        response = ErrorResponse(
            error_code="TEST_ERROR",
            message="Test message",
            status_code=400
        )
        
        json_response = response.to_json_response()
        assert json_response.status_code == 400
        
        content = json.loads(json_response.body)
        assert content["error"] is True
        assert content["error_code"] == "TEST_ERROR"


class TestErrorHandlers:
    """Test error handler functions."""
    
    @pytest.fixture
    def mock_request(self):
        """Create a mock request object."""
        request = Mock()
        request.method = "POST"
        request.url.path = "/api/v1/test"
        request.url = Mock()
        request.url.__str__ = Mock(return_value="http://localhost/api/v1/test")
        request.headers = {"user-agent": "test-client"}
        request.client = Mock()
        request.client.host = "127.0.0.1"
        request.state = Mock()
        request.state.request_id = "test-request-id"
        return request
    
    @pytest.mark.asyncio
    async def test_filmlist_exception_handler(self, mock_request):
        """Test filmlist exception handler."""
        exc = ValidationError(
            message="Test validation error",
            error_code=ErrorCode.INVALID_FILE_FORMAT,
            field="file_format",
            value="txt"
        )
        
        with patch('app.core.error_handlers.logger') as mock_logger:
            response = await filmlist_exception_handler(mock_request, exc)
        
        assert response.status_code == 400
        content = json.loads(response.body)
        
        assert content["error"] is True
        assert content["error_code"] == ErrorCode.INVALID_FILE_FORMAT.value
        assert "Неподдерживаемый формат файла" in content["message"]
        assert content["request_id"] == "test-request-id"
        
        # Verify logging was called
        mock_logger.log_error_with_context.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_http_exception_handler(self, mock_request):
        """Test HTTP exception handler."""
        exc = HTTPException(
            status_code=404,
            detail="Resource not found"
        )
        
        with patch('app.core.error_handlers.logger') as mock_logger:
            response = await http_exception_handler(mock_request, exc)
        
        assert response.status_code == 404
        content = json.loads(response.body)
        
        assert content["error"] is True
        assert content["message"] == "Запрашиваемый ресурс не найден."
        
        # Verify logging was called
        mock_logger.error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validation_exception_handler(self, mock_request):
        """Test validation exception handler."""
        # Create a mock validation error
        validation_error = {
            "loc": ("body", "file_format"),
            "msg": "field required",
            "type": "value_error.missing",
            "input": None
        }
        
        exc = RequestValidationError([validation_error])
        
        with patch('app.core.error_handlers.logger') as mock_logger:
            response = await validation_exception_handler(mock_request, exc)
        
        assert response.status_code == 422
        content = json.loads(response.body)
        
        assert content["error"] is True
        assert "валидации данных" in content["message"]
        assert "validation_errors" in content["details"]
        
        # Verify logging was called
        mock_logger.warning.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_general_exception_handler(self, mock_request):
        """Test general exception handler."""
        exc = ValueError("Unexpected error")
        
        with patch('app.core.error_handlers.logger') as mock_logger:
            response = await general_exception_handler(mock_request, exc)
        
        assert response.status_code == 500
        content = json.loads(response.body)
        
        assert content["error"] is True
        assert content["error_code"] == ErrorCode.INTERNAL_ERROR.value
        assert "внутренняя ошибка сервера" in content["message"]
        
        # Verify critical logging was called
        mock_logger.critical.assert_called_once()


class TestErrorHandlerUtilities:
    """Test error handler utility functions."""
    
    def test_create_validation_error(self):
        """Test create_validation_error utility."""
        exc = create_validation_error(
            field="email",
            message="Invalid email format",
            value="invalid-email",
            error_code=ErrorCode.INTERNAL_ERROR
        )
        
        assert isinstance(exc, ValidationError)
        assert exc.details["field"] == "email"
        assert exc.details["value"] == "invalid-email"
        assert "email" in exc.message
    
    def test_create_not_found_error(self):
        """Test create_not_found_error utility."""
        exc = create_not_found_error(
            resource_type="user",
            resource_id="123",
            error_code=ErrorCode.TASK_NOT_FOUND
        )
        
        assert isinstance(exc, NotFoundError)
        assert exc.details["resource_type"] == "user"
        assert exc.details["resource_id"] == "123"
        assert "User not found" in exc.message
    
    def test_create_business_logic_error(self):
        """Test create_business_logic_error utility."""
        details = {"balance": 50, "required": 100}
        exc = create_business_logic_error(
            message="Insufficient funds",
            error_code=ErrorCode.INSUFFICIENT_BALANCE,
            details=details
        )
        
        assert isinstance(exc, BusinessLogicError)
        assert exc.details == details
        assert exc.error_code == ErrorCode.INSUFFICIENT_BALANCE
    
    def test_create_external_service_error(self):
        """Test create_external_service_error utility."""
        exc = create_external_service_error(
            service_name="OpenAI",
            operation="transcription",
            error_message="API timeout",
            error_code=ErrorCode.OPENAI_API_ERROR,
            retry_after=60
        )
        
        assert isinstance(exc, ExternalServiceError)
        assert exc.details["service_name"] == "OpenAI"
        assert exc.details["retry_after"] == 60
        assert "OpenAI transcription failed" in exc.message
    
    def test_create_processing_error(self):
        """Test create_processing_error utility."""
        exc = create_processing_error(
            step="video_validation",
            error_message="Invalid codec",
            error_code=ErrorCode.FFMPEG_ERROR,
            task_id="task_123"
        )
        
        assert isinstance(exc, ProcessingError)
        assert exc.details["step"] == "video_validation"
        assert exc.details["task_id"] == "task_123"
        assert "video_validation" in exc.message


class TestFilmlistLogger:
    """Test FilmlistLogger functionality."""
    
    def test_logger_context(self):
        """Test logger context management."""
        logger = FilmlistLogger("test")
        
        # Set context
        logger.set_context(user_id="123", task_id="task_456")
        
        with patch.object(logger.logger, 'log') as mock_log:
            logger.info("Test message")
            
            # Verify context was included
            call_args = mock_log.call_args
            extra = call_args[1]['extra']
            assert extra['user_id'] == "123"
            assert extra['task_id'] == "task_456"
        
        # Clear context
        logger.clear_context()
        
        with patch.object(logger.logger, 'log') as mock_log:
            logger.info("Test message 2")
            
            # Verify context was cleared
            call_args = mock_log.call_args
            extra = call_args[1]['extra']
            assert 'user_id' not in extra
            assert 'task_id' not in extra
    
    def test_logger_temporary_context(self):
        """Test logger temporary context manager."""
        logger = FilmlistLogger("test")
        logger.set_context(user_id="123")
        
        with logger.context(task_id="task_456", step="validation"):
            with patch.object(logger.logger, 'log') as mock_log:
                logger.info("Test message")
                
                # Verify both contexts are present
                call_args = mock_log.call_args
                extra = call_args[1]['extra']
                assert extra['user_id'] == "123"
                assert extra['task_id'] == "task_456"
                assert extra['step'] == "validation"
        
        # Verify original context is restored
        with patch.object(logger.logger, 'log') as mock_log:
            logger.info("Test message 2")
            
            call_args = mock_log.call_args
            extra = call_args[1]['extra']
            assert extra['user_id'] == "123"
            assert 'task_id' not in extra
            assert 'step' not in extra
    
    def test_logger_specialized_methods(self):
        """Test specialized logging methods."""
        logger = FilmlistLogger("test")
        
        with patch.object(logger.logger, 'log') as mock_log:
            # Test processing step logging
            logger.log_processing_step("task_123", "validation", "started", duration=1.5)
            
            call_args = mock_log.call_args
            extra = call_args[1]['extra']
            assert extra['task_id'] == "task_123"
            assert extra['processing_step'] == "validation"
            assert extra['step_status'] == "started"
            assert extra['duration'] == 1.5
        
        with patch.object(logger.logger, 'log') as mock_log:
            # Test API request logging
            logger.log_api_request("POST", "/api/v1/upload", user_id="user_123")
            
            call_args = mock_log.call_args
            extra = call_args[1]['extra']
            assert extra['request_method'] == "POST"
            assert extra['request_path'] == "/api/v1/upload"
            assert extra['user_id'] == "user_123"
        
        with patch.object(logger.logger, 'log') as mock_log:
            # Test external service call logging
            logger.log_external_service_call("OpenAI", "transcription", "success", duration=5.2)
            
            call_args = mock_log.call_args
            extra = call_args[1]['extra']
            assert extra['external_service'] == "OpenAI"
            assert extra['service_operation'] == "transcription"
            assert extra['call_status'] == "success"
            assert extra['duration'] == 5.2
    
    def test_logger_error_with_context(self):
        """Test error logging with context."""
        logger = FilmlistLogger("test")
        
        exc = ValidationError(
            message="Test error",
            error_code=ErrorCode.INVALID_FILE_FORMAT
        )
        
        context = {"task_id": "task_123", "file_name": "test.txt"}
        
        with patch.object(logger, 'exception') as mock_exception:
            logger.log_error_with_context(
                error=exc,
                context=context,
                user_message="User friendly message"
            )
            
            call_args = mock_exception.call_args
            extra = call_args[1]['extra']
            assert extra['error_type'] == "ValidationError"
            assert extra['error_code'] == ErrorCode.INVALID_FILE_FORMAT.value
            assert extra['task_id'] == "task_123"
            assert extra['file_name'] == "test.txt"
            assert extra['user_message'] == "User friendly message"


class TestIntegrationScenarios:
    """Test integration scenarios with error handling."""
    
    def test_video_validation_error_flow(self):
        """Test complete error flow for video validation."""
        # Simulate video validation error
        exc = invalid_file_format_error("txt", ["mp4", "avi", "mov"])
        
        # Verify exception properties
        assert exc.error_code == ErrorCode.INVALID_FILE_FORMAT
        assert exc.status_code == 400
        assert "txt" in str(exc.details["value"])
        assert "mp4, avi, mov" in exc.user_message
        
        # Verify it can be converted to API response
        exc_dict = exc.to_dict()
        assert exc_dict["error_code"] == ErrorCode.INVALID_FILE_FORMAT.value
        assert exc_dict["message"] == exc.user_message
    
    def test_processing_pipeline_error_flow(self):
        """Test error flow for processing pipeline failures."""
        # Simulate FFmpeg error
        exc = ffmpeg_error("audio_extraction", "Invalid codec: unknown")
        
        assert exc.error_code == ErrorCode.FFMPEG_ERROR
        assert exc.status_code == 500
        assert exc.details["step"] == "audio_extraction"
        assert "audio_extraction" in exc.user_message
        
        # Simulate OpenAI rate limit
        exc2 = openai_rate_limit_error(retry_after=120)
        
        assert exc2.error_code == ErrorCode.OPENAI_RATE_LIMIT
        assert exc2.details["retry_after"] == 120
        assert "автоматически" in exc2.user_message
    
    def test_business_logic_error_flow(self):
        """Test error flow for business logic violations."""
        # Simulate insufficient balance
        exc = insufficient_balance_error(required=150.0, available=75.0)
        
        assert exc.error_code == ErrorCode.INSUFFICIENT_BALANCE
        assert exc.status_code == 422
        assert exc.details["deficit"] == 75.0
        assert "средств на балансе" in exc.user_message
        
        # Simulate task not found
        exc2 = task_not_found_error("nonexistent_task")
        
        assert exc2.error_code == ErrorCode.TASK_NOT_FOUND
        assert exc2.status_code == 404
        assert exc2.details["resource_id"] == "nonexistent_task"


if __name__ == "__main__":
    pytest.main([__file__])