"""
Structured logging configuration for the filmlist application.
Provides detailed context and stack traces for error handling.
"""

import logging
import logging.config
import sys
import traceback
import json
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
from contextlib import contextmanager

from app.core.config import settings


class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON logs."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        
        # Base log data
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception information if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields from the log record
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in {
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
                'module', 'exc_info', 'exc_text', 'stack_info', 'lineno', 'funcName',
                'created', 'msecs', 'relativeCreated', 'thread', 'threadName',
                'processName', 'process', 'getMessage'
            }:
                extra_fields[key] = value
        
        if extra_fields:
            log_data["extra"] = extra_fields
        
        return json.dumps(log_data, ensure_ascii=False, default=str)


class FilmlistLogger:
    """Enhanced logger with context management for filmlist application."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._context: Dict[str, Any] = {}
    
    def set_context(self, **kwargs) -> None:
        """Set persistent context for all log messages."""
        self._context.update(kwargs)
    
    def clear_context(self) -> None:
        """Clear all context."""
        self._context.clear()
    
    @contextmanager
    def context(self, **kwargs):
        """Temporary context manager for log messages."""
        old_context = self._context.copy()
        self._context.update(kwargs)
        try:
            yield
        finally:
            self._context = old_context
    
    def _log_with_context(self, level: int, msg: str, *args, **kwargs):
        """Log message with current context."""
        # Merge context with any extra kwargs
        extra = kwargs.get('extra', {})
        extra.update(self._context)
        kwargs['extra'] = extra
        
        self.logger.log(level, msg, *args, **kwargs)
    
    def debug(self, msg: str, *args, **kwargs):
        """Log debug message with context."""
        self._log_with_context(logging.DEBUG, msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        """Log info message with context."""
        self._log_with_context(logging.INFO, msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        """Log warning message with context."""
        self._log_with_context(logging.WARNING, msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        """Log error message with context."""
        self._log_with_context(logging.ERROR, msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs):
        """Log critical message with context."""
        self._log_with_context(logging.CRITICAL, msg, *args, **kwargs)
    
    def exception(self, msg: str, *args, **kwargs):
        """Log exception with full traceback and context."""
        kwargs['exc_info'] = True
        self._log_with_context(logging.ERROR, msg, *args, **kwargs)
    
    def log_processing_step(self, task_id: str, step: str, status: str, **kwargs):
        """Log processing step with standardized format."""
        self.info(
            f"Processing step {status}: {step}",
            extra={
                "task_id": task_id,
                "processing_step": step,
                "step_status": status,
                **kwargs
            }
        )
    
    def log_api_request(self, method: str, path: str, user_id: Optional[str] = None, **kwargs):
        """Log API request with standardized format."""
        self.info(
            f"API request: {method} {path}",
            extra={
                "request_method": method,
                "request_path": path,
                "user_id": user_id,
                **kwargs
            }
        )
    
    def log_external_service_call(self, service: str, operation: str, status: str, **kwargs):
        """Log external service call with standardized format."""
        self.info(
            f"External service call: {service}.{operation} -> {status}",
            extra={
                "external_service": service,
                "service_operation": operation,
                "call_status": status,
                **kwargs
            }
        )
    
    def log_error_with_context(
        self, 
        error: Exception, 
        context: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None
    ):
        """Log error with full context and user-friendly message."""
        error_context = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "user_message": user_message
        }
        
        if context:
            error_context.update(context)
        
        # Check if it's a filmlist exception with additional context
        if hasattr(error, 'error_code'):
            error_context.update({
                "error_code": error.error_code.value,
                "status_code": error.status_code,
                "details": getattr(error, 'details', {})
            })
        
        self.exception(
            f"Error occurred: {str(error)}",
            extra=error_context
        )


def setup_logging() -> None:
    """Configure logging for the application."""
    
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Determine log level
    log_level = getattr(logging, getattr(settings, 'LOG_LEVEL', 'INFO').upper())
    
    # Logging configuration
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'structured': {
                '()': StructuredFormatter,
            },
            'simple': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': log_level,
                'formatter': 'simple',
                'stream': sys.stdout
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': log_level,
                'formatter': 'structured',
                'filename': log_dir / 'filmlist.log',
                'maxBytes': 10 * 1024 * 1024,  # 10MB
                'backupCount': 5,
                'encoding': 'utf-8'
            },
            'error_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': logging.ERROR,
                'formatter': 'structured',
                'filename': log_dir / 'errors.log',
                'maxBytes': 10 * 1024 * 1024,  # 10MB
                'backupCount': 10,
                'encoding': 'utf-8'
            }
        },
        'loggers': {
            'app': {
                'level': log_level,
                'handlers': ['console', 'file', 'error_file'],
                'propagate': False
            },
            'uvicorn': {
                'level': logging.INFO,
                'handlers': ['console'],
                'propagate': False
            },
            'uvicorn.error': {
                'level': logging.INFO,
                'handlers': ['console', 'error_file'],
                'propagate': False
            },
            'uvicorn.access': {
                'level': logging.INFO,
                'handlers': ['console'],
                'propagate': False
            }
        },
        'root': {
            'level': log_level,
            'handlers': ['console', 'file']
        }
    }
    
    logging.config.dictConfig(config)


def get_logger(name: str) -> FilmlistLogger:
    """Get a logger instance with enhanced functionality."""
    return FilmlistLogger(f"app.{name}")


# Performance monitoring decorator
def log_performance(logger: FilmlistLogger):
    """Decorator to log function performance."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            
            try:
                result = func(*args, **kwargs)
                
                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()
                
                logger.info(
                    f"Function {func.__name__} completed successfully",
                    extra={
                        "function": func.__name__,
                        "duration_seconds": duration,
                        "status": "success"
                    }
                )
                
                return result
                
            except Exception as e:
                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()
                
                logger.error(
                    f"Function {func.__name__} failed",
                    extra={
                        "function": func.__name__,
                        "duration_seconds": duration,
                        "status": "error",
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    }
                )
                
                raise
        
        return wrapper
    return decorator


# Async version of performance monitoring decorator
def log_async_performance(logger: FilmlistLogger):
    """Decorator to log async function performance."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            
            try:
                result = await func(*args, **kwargs)
                
                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()
                
                logger.info(
                    f"Async function {func.__name__} completed successfully",
                    extra={
                        "function": func.__name__,
                        "duration_seconds": duration,
                        "status": "success"
                    }
                )
                
                return result
                
            except Exception as e:
                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()
                
                logger.error(
                    f"Async function {func.__name__} failed",
                    extra={
                        "function": func.__name__,
                        "duration_seconds": duration,
                        "status": "error",
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    }
                )
                
                raise
        
        return wrapper
    return decorator


# Context manager for request tracking
@contextmanager
def request_context(logger: FilmlistLogger, request_id: str, user_id: Optional[str] = None):
    """Context manager for tracking requests across the application."""
    logger.set_context(
        request_id=request_id,
        user_id=user_id,
        request_start_time=datetime.utcnow().isoformat()
    )
    
    try:
        yield logger
    finally:
        logger.clear_context()


# Initialize logging when module is imported
setup_logging()