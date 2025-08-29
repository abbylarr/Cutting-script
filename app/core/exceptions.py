"""
Custom exception classes for the filmlist application.
Provides structured error handling with proper HTTP status codes and user-friendly messages.
"""

from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status
from enum import Enum


class ErrorCode(str, Enum):
    """Standardized error codes for the application."""
    
    # Validation Errors (4xx)
    INVALID_FILE_FORMAT = "INVALID_FILE_FORMAT"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    INVALID_VIDEO_CODEC = "INVALID_VIDEO_CODEC"
    VIDEO_TOO_SHORT = "VIDEO_TOO_SHORT"
    VIDEO_TOO_LONG = "VIDEO_TOO_LONG"
    INVALID_RESOLUTION = "INVALID_RESOLUTION"
    INVALID_FRAME_RATE = "INVALID_FRAME_RATE"
    CORRUPTED_FILE = "CORRUPTED_FILE"
    
    # Authentication & Authorization Errors (4xx)
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    ACCOUNT_SUSPENDED = "ACCOUNT_SUSPENDED"
    
    # Business Logic Errors (4xx)
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    TASK_ALREADY_PROCESSING = "TASK_ALREADY_PROCESSING"
    TASK_NOT_COMPLETED = "TASK_NOT_COMPLETED"
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    INVALID_MONTAGE_DATA = "INVALID_MONTAGE_DATA"
    
    # Rate Limiting Errors (4xx)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    TOO_MANY_CONCURRENT_TASKS = "TOO_MANY_CONCURRENT_TASKS"
    
    # External Service Errors (5xx)
    OPENAI_API_ERROR = "OPENAI_API_ERROR"
    OPENAI_RATE_LIMIT = "OPENAI_RATE_LIMIT"
    HUGGINGFACE_API_ERROR = "HUGGINGFACE_API_ERROR"
    PAYMENT_SERVICE_ERROR = "PAYMENT_SERVICE_ERROR"
    
    # Processing Errors (5xx)
    FFMPEG_ERROR = "FFMPEG_ERROR"
    SCENE_DETECTION_ERROR = "SCENE_DETECTION_ERROR"
    TRANSCRIPTION_ERROR = "TRANSCRIPTION_ERROR"
    DIARIZATION_ERROR = "DIARIZATION_ERROR"
    VISUAL_ANALYSIS_ERROR = "VISUAL_ANALYSIS_ERROR"
    DOCUMENT_GENERATION_ERROR = "DOCUMENT_GENERATION_ERROR"
    
    # System Errors (5xx)
    DATABASE_ERROR = "DATABASE_ERROR"
    REDIS_ERROR = "REDIS_ERROR"
    FILE_SYSTEM_ERROR = "FILE_SYSTEM_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class FilmlistException(Exception):
    """Base exception class for filmlist application."""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        self.user_message = user_message or self._get_user_friendly_message()
        super().__init__(self.message)
    
    def _get_user_friendly_message(self) -> str:
        """Generate user-friendly error message based on error code."""
        user_messages = {
            ErrorCode.INVALID_FILE_FORMAT: "Неподдерживаемый формат файла. Пожалуйста, загрузите видео в формате MP4, AVI, MOV или MKV.",
            ErrorCode.FILE_TOO_LARGE: "Размер файла превышает допустимый лимит (2 ГБ). Пожалуйста, сожмите видео или разделите на части.",
            ErrorCode.FILE_NOT_FOUND: "Файл не найден. Пожалуйста, проверьте правильность загрузки.",
            ErrorCode.INVALID_VIDEO_CODEC: "Неподдерживаемый видеокодек. Рекомендуется использовать H.264 или H.265.",
            ErrorCode.VIDEO_TOO_SHORT: "Видео слишком короткое для обработки. Минимальная длительность: 1 секунда.",
            ErrorCode.VIDEO_TOO_LONG: "Видео слишком длинное для обработки. Максимальная длительность: 4 часа.",
            ErrorCode.INVALID_RESOLUTION: "Разрешение видео слишком низкое. Минимальное разрешение: 320x240.",
            ErrorCode.CORRUPTED_FILE: "Файл поврежден или не может быть прочитан. Пожалуйста, загрузите другой файл.",
            
            ErrorCode.INSUFFICIENT_BALANCE: "Недостаточно средств на балансе для обработки видео. Пожалуйста, пополните баланс.",
            ErrorCode.TASK_NOT_FOUND: "Задача не найдена или у вас нет доступа к ней.",
            ErrorCode.TASK_ALREADY_PROCESSING: "Задача уже обрабатывается. Пожалуйста, дождитесь завершения.",
            ErrorCode.TASK_NOT_COMPLETED: "Задача еще не завершена. Пожалуйста, дождитесь окончания обработки.",
            
            ErrorCode.RATE_LIMIT_EXCEEDED: "Превышен лимит запросов. Пожалуйста, повторите попытку через несколько минут.",
            ErrorCode.TOO_MANY_CONCURRENT_TASKS: "Слишком много одновременных задач. Пожалуйста, дождитесь завершения текущих задач.",
            
            ErrorCode.OPENAI_API_ERROR: "Временная недоступность сервиса транскрипции. Попробуйте позже или используйте SRT файл.",
            ErrorCode.OPENAI_RATE_LIMIT: "Превышен лимит запросов к сервису ИИ. Обработка будет продолжена автоматически.",
            ErrorCode.PAYMENT_SERVICE_ERROR: "Ошибка платежной системы. Пожалуйста, попробуйте другой способ оплаты.",
            
            ErrorCode.FFMPEG_ERROR: "Ошибка обработки видео. Проверьте формат и целостность файла.",
            ErrorCode.SCENE_DETECTION_ERROR: "Ошибка определения сцен. Попробуйте с другим видео или обратитесь в поддержку.",
            ErrorCode.TRANSCRIPTION_ERROR: "Ошибка транскрипции аудио. Попробуйте загрузить SRT файл вручную.",
            ErrorCode.DOCUMENT_GENERATION_ERROR: "Ошибка создания документа. Пожалуйста, попробуйте еще раз.",
            
            ErrorCode.INTERNAL_ERROR: "Внутренняя ошибка сервера. Мы работаем над устранением проблемы."
        }
        
        return user_messages.get(self.error_code, "Произошла неожиданная ошибка. Пожалуйста, обратитесь в поддержку.")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error_code": self.error_code.value,
            "message": self.user_message,
            "details": self.details,
            "technical_message": self.message
        }


class ValidationError(FilmlistException):
    """Exception for validation errors (4xx status codes)."""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        user_message: Optional[str] = None
    ):
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = value
        
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
            user_message=user_message
        )


class AuthenticationError(FilmlistException):
    """Exception for authentication errors (401 status code)."""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.INVALID_CREDENTIALS,
        user_message: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_401_UNAUTHORIZED,
            user_message=user_message or "Ошибка аутентификации. Пожалуйста, войдите в систему."
        )


class AuthorizationError(FilmlistException):
    """Exception for authorization errors (403 status code)."""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.INSUFFICIENT_PERMISSIONS,
        user_message: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_403_FORBIDDEN,
            user_message=user_message or "Недостаточно прав для выполнения операции."
        )


class NotFoundError(FilmlistException):
    """Exception for resource not found errors (404 status code)."""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        user_message: Optional[str] = None
    ):
        details = {}
        if resource_type:
            details["resource_type"] = resource_type
        if resource_id:
            details["resource_id"] = resource_id
        
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
            user_message=user_message
        )


class BusinessLogicError(FilmlistException):
    """Exception for business logic errors (422 status code)."""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        user_message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
            user_message=user_message
        )


class RateLimitError(FilmlistException):
    """Exception for rate limiting errors (429 status code)."""
    
    def __init__(
        self,
        message: str,
        retry_after: Optional[int] = None,
        user_message: Optional[str] = None
    ):
        details = {}
        if retry_after:
            details["retry_after"] = retry_after
        
        super().__init__(
            message=message,
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details,
            user_message=user_message
        )


class ExternalServiceError(FilmlistException):
    """Exception for external service errors (502/503 status codes)."""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        service_name: Optional[str] = None,
        retry_after: Optional[int] = None,
        user_message: Optional[str] = None
    ):
        details = {}
        if service_name:
            details["service"] = service_name
            details["service_name"] = service_name  # Keep both for compatibility
        if retry_after:
            details["retry_after"] = retry_after
        
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        if error_code in [ErrorCode.OPENAI_RATE_LIMIT]:
            status_code = status.HTTP_502_BAD_GATEWAY
        
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
            details=details,
            user_message=user_message
        )


class ProcessingError(FilmlistException):
    """Exception for processing pipeline errors (500 status code)."""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        step: Optional[str] = None,
        task_id: Optional[str] = None,
        user_message: Optional[str] = None
    ):
        details = {}
        if step:
            details["step"] = step
            details["processing_step"] = step  # Keep both for compatibility
        if task_id:
            details["task_id"] = task_id
        
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
            user_message=user_message
        )


class SystemError(FilmlistException):
    """Exception for system-level errors (500 status code)."""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        component: Optional[str] = None,
        user_message: Optional[str] = None
    ):
        details = {}
        if component:
            details["component"] = component
        
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
            user_message=user_message or "Внутренняя ошибка сервера. Мы работаем над устранением проблемы."
        )


# Convenience functions for common error scenarios
def file_not_found_error(file_path: str) -> NotFoundError:
    """Create a file not found error."""
    return NotFoundError(
        message=f"File not found: {file_path}",
        error_code=ErrorCode.FILE_NOT_FOUND,
        resource_type="file",
        resource_id=file_path
    )


def task_not_found_error(task_id: str) -> NotFoundError:
    """Create a task not found error."""
    return NotFoundError(
        message=f"Task not found: {task_id}",
        error_code=ErrorCode.TASK_NOT_FOUND,
        resource_type="task",
        resource_id=task_id
    )


def insufficient_balance_error(required: float, available: float) -> BusinessLogicError:
    """Create an insufficient balance error."""
    return BusinessLogicError(
        message=f"Insufficient balance: required {required}, available {available}",
        error_code=ErrorCode.INSUFFICIENT_BALANCE,
        details={
            "required_balance": required,
            "available_balance": available,
            "deficit": required - available
        }
    )


def invalid_file_format_error(file_format: str, supported_formats: List[str]) -> ValidationError:
    """Create an invalid file format error."""
    return ValidationError(
        message=f"Invalid file format: {file_format}",
        error_code=ErrorCode.INVALID_FILE_FORMAT,
        field="file_format",
        value=file_format,
        user_message=f"Неподдерживаемый формат файла '{file_format}'. Поддерживаемые форматы: {', '.join(supported_formats)}"
    )


def file_too_large_error(file_size: int, max_size: int) -> ValidationError:
    """Create a file too large error."""
    return ValidationError(
        message=f"File size {file_size} exceeds maximum {max_size}",
        error_code=ErrorCode.FILE_TOO_LARGE,
        field="file_size",
        value=file_size,
        user_message=f"Размер файла ({file_size / (1024**3):.1f} ГБ) превышает максимально допустимый ({max_size / (1024**3):.1f} ГБ)"
    )


def openai_rate_limit_error(retry_after: Optional[int] = None) -> ExternalServiceError:
    """Create an OpenAI rate limit error."""
    return ExternalServiceError(
        message="OpenAI API rate limit exceeded",
        error_code=ErrorCode.OPENAI_RATE_LIMIT,
        service_name="OpenAI",
        retry_after=retry_after,
        user_message="Превышен лимит запросов к сервису ИИ. Обработка будет продолжена автоматически через несколько минут."
    )


def ffmpeg_error(operation: str, stderr: str) -> ProcessingError:
    """Create an FFmpeg processing error."""
    return ProcessingError(
        message=f"FFmpeg {operation} failed: {stderr}",
        error_code=ErrorCode.FFMPEG_ERROR,
        step=operation,
        user_message=f"Ошибка обработки видео на этапе '{operation}'. Проверьте формат и целостность файла."
    )