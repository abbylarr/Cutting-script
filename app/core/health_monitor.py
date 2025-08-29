"""
Service health monitoring and automatic failover system.
Monitors external services and provides fallback mechanisms.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, Awaitable
from enum import Enum
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

from app.core.logging import get_logger
from app.core.exceptions import ExternalServiceError, ErrorCode

logger = get_logger("health_monitor")


class ServiceStatus(str, Enum):
    """Service health status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Health check configuration and results."""
    service_name: str
    check_function: Callable[[], Awaitable[bool]]
    interval_seconds: int = 60
    timeout_seconds: int = 10
    failure_threshold: int = 3
    recovery_threshold: int = 2
    
    # Runtime state
    status: ServiceStatus = ServiceStatus.UNKNOWN
    last_check: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    total_checks: int = 0
    total_failures: int = 0
    last_error: Optional[str] = None
    response_times: list = field(default_factory=list)
    
    def __post_init__(self):
        """Initialize response times list with limited size."""
        if not self.response_times:
            self.response_times = []
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_checks == 0:
            return 0.0
        return ((self.total_checks - self.total_failures) / self.total_checks) * 100
    
    @property
    def average_response_time(self) -> float:
        """Calculate average response time in seconds."""
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)
    
    def add_response_time(self, response_time: float):
        """Add response time measurement (keep last 100 measurements)."""
        self.response_times.append(response_time)
        if len(self.response_times) > 100:
            self.response_times.pop(0)


class HealthMonitor:
    """Service health monitoring system with automatic failover."""
    
    def __init__(self):
        self.health_checks: Dict[str, HealthCheck] = {}
        self.fallback_handlers: Dict[str, Callable] = {}
        self.monitoring_task: Optional[asyncio.Task] = None
        self.is_monitoring = False
        
    def register_service(
        self,
        service_name: str,
        check_function: Callable[[], Awaitable[bool]],
        fallback_handler: Optional[Callable] = None,
        interval_seconds: int = 60,
        timeout_seconds: int = 10,
        failure_threshold: int = 3,
        recovery_threshold: int = 2
    ):
        """
        Register a service for health monitoring.
        
        Args:
            service_name: Unique service identifier
            check_function: Async function that returns True if service is healthy
            fallback_handler: Optional fallback handler for when service is unhealthy
            interval_seconds: How often to check service health
            timeout_seconds: Timeout for health checks
            failure_threshold: Consecutive failures before marking unhealthy
            recovery_threshold: Consecutive successes before marking healthy
        """
        self.health_checks[service_name] = HealthCheck(
            service_name=service_name,
            check_function=check_function,
            interval_seconds=interval_seconds,
            timeout_seconds=timeout_seconds,
            failure_threshold=failure_threshold,
            recovery_threshold=recovery_threshold
        )
        
        if fallback_handler:
            self.fallback_handlers[service_name] = fallback_handler
        
        logger.info(f"Registered health check for service: {service_name}")
    
    async def start_monitoring(self):
        """Start the health monitoring background task."""
        if self.is_monitoring:
            logger.warning("Health monitoring is already running")
            return
        
        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Health monitoring started")
    
    async def stop_monitoring(self):
        """Stop the health monitoring background task."""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Health monitoring stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop that runs health checks."""
        logger.info("Health monitoring loop started")
        
        try:
            while self.is_monitoring:
                # Run health checks for all registered services
                check_tasks = []
                for service_name, health_check in self.health_checks.items():
                    if self._should_check_service(health_check):
                        task = asyncio.create_task(
                            self._check_service_health(health_check)
                        )
                        check_tasks.append(task)
                
                # Wait for all health checks to complete
                if check_tasks:
                    await asyncio.gather(*check_tasks, return_exceptions=True)
                
                # Sleep for a short interval before next round
                await asyncio.sleep(5)  # Check every 5 seconds if any service needs checking
                
        except asyncio.CancelledError:
            logger.info("Health monitoring loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Health monitoring loop error: {e}")
            # Continue monitoring despite errors
            if self.is_monitoring:
                await asyncio.sleep(10)  # Wait before retrying
                await self._monitoring_loop()
    
    def _should_check_service(self, health_check: HealthCheck) -> bool:
        """Determine if a service should be checked now."""
        if health_check.last_check is None:
            return True
        
        time_since_check = datetime.utcnow() - health_check.last_check
        return time_since_check.total_seconds() >= health_check.interval_seconds
    
    async def _check_service_health(self, health_check: HealthCheck):
        """Perform health check for a single service."""
        service_name = health_check.service_name
        start_time = time.time()
        
        try:
            # Run health check with timeout
            is_healthy = await asyncio.wait_for(
                health_check.check_function(),
                timeout=health_check.timeout_seconds
            )
            
            response_time = time.time() - start_time
            health_check.add_response_time(response_time)
            
            # Update health check state
            health_check.last_check = datetime.utcnow()
            health_check.total_checks += 1
            
            if is_healthy:
                health_check.consecutive_failures = 0
                health_check.consecutive_successes += 1
                health_check.last_error = None
                
                # Check if service has recovered
                if (health_check.status != ServiceStatus.HEALTHY and 
                    health_check.consecutive_successes >= health_check.recovery_threshold):
                    
                    old_status = health_check.status
                    health_check.status = ServiceStatus.HEALTHY
                    
                    logger.info(
                        f"Service {service_name} recovered",
                        extra={
                            "service": service_name,
                            "old_status": old_status,
                            "new_status": health_check.status,
                            "consecutive_successes": health_check.consecutive_successes,
                            "response_time": response_time
                        }
                    )
                
                elif health_check.status == ServiceStatus.UNKNOWN:
                    health_check.status = ServiceStatus.HEALTHY
                    logger.info(f"Service {service_name} is healthy")
            
            else:
                # Health check returned False
                await self._handle_health_check_failure(
                    health_check, 
                    "Health check returned False",
                    response_time
                )
        
        except asyncio.TimeoutError:
            response_time = time.time() - start_time
            await self._handle_health_check_failure(
                health_check,
                f"Health check timed out after {health_check.timeout_seconds}s",
                response_time
            )
        
        except Exception as e:
            response_time = time.time() - start_time
            await self._handle_health_check_failure(
                health_check,
                f"Health check failed: {str(e)}",
                response_time
            )
    
    async def _handle_health_check_failure(
        self, 
        health_check: HealthCheck, 
        error_message: str,
        response_time: float
    ):
        """Handle a failed health check."""
        service_name = health_check.service_name
        
        health_check.last_check = datetime.utcnow()
        health_check.total_checks += 1
        health_check.total_failures += 1
        health_check.consecutive_successes = 0
        health_check.consecutive_failures += 1
        health_check.last_error = error_message
        health_check.add_response_time(response_time)
        
        # Determine new status
        old_status = health_check.status
        
        if health_check.consecutive_failures >= health_check.failure_threshold:
            health_check.status = ServiceStatus.UNHEALTHY
        elif health_check.consecutive_failures > 1:
            health_check.status = ServiceStatus.DEGRADED
        
        # Log status change
        if old_status != health_check.status:
            logger.warning(
                f"Service {service_name} status changed",
                extra={
                    "service": service_name,
                    "old_status": old_status,
                    "new_status": health_check.status,
                    "consecutive_failures": health_check.consecutive_failures,
                    "error": error_message,
                    "response_time": response_time
                }
            )
        else:
            logger.debug(
                f"Service {service_name} health check failed",
                extra={
                    "service": service_name,
                    "status": health_check.status,
                    "consecutive_failures": health_check.consecutive_failures,
                    "error": error_message
                }
            )
    
    def get_service_status(self, service_name: str) -> ServiceStatus:
        """Get current status of a service."""
        health_check = self.health_checks.get(service_name)
        if not health_check:
            return ServiceStatus.UNKNOWN
        return health_check.status
    
    def is_service_healthy(self, service_name: str) -> bool:
        """Check if a service is currently healthy."""
        return self.get_service_status(service_name) == ServiceStatus.HEALTHY
    
    def get_service_info(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a service."""
        health_check = self.health_checks.get(service_name)
        if not health_check:
            return None
        
        return {
            "service_name": service_name,
            "status": health_check.status,
            "last_check": health_check.last_check.isoformat() if health_check.last_check else None,
            "consecutive_failures": health_check.consecutive_failures,
            "consecutive_successes": health_check.consecutive_successes,
            "total_checks": health_check.total_checks,
            "total_failures": health_check.total_failures,
            "success_rate": health_check.success_rate,
            "average_response_time": health_check.average_response_time,
            "last_error": health_check.last_error,
            "failure_threshold": health_check.failure_threshold,
            "recovery_threshold": health_check.recovery_threshold
        }
    
    def get_all_services_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status information for all registered services."""
        return {
            service_name: self.get_service_info(service_name)
            for service_name in self.health_checks.keys()
        }
    
    @asynccontextmanager
    async def with_fallback(self, service_name: str):
        """
        Context manager that provides fallback handling for service calls.
        
        Usage:
            async with health_monitor.with_fallback("openai") as fallback:
                if fallback.should_use_fallback():
                    result = await fallback.execute()
                else:
                    result = await primary_service_call()
        """
        fallback_context = FallbackContext(
            service_name=service_name,
            health_monitor=self,
            fallback_handler=self.fallback_handlers.get(service_name)
        )
        
        try:
            yield fallback_context
        except Exception as e:
            # Mark service as potentially unhealthy if an exception occurs
            if service_name in self.health_checks:
                health_check = self.health_checks[service_name]
                await self._handle_health_check_failure(
                    health_check,
                    f"Service call failed: {str(e)}",
                    0.0
                )
            raise


class FallbackContext:
    """Context for handling fallback operations."""
    
    def __init__(
        self, 
        service_name: str, 
        health_monitor: HealthMonitor,
        fallback_handler: Optional[Callable] = None
    ):
        self.service_name = service_name
        self.health_monitor = health_monitor
        self.fallback_handler = fallback_handler
    
    def should_use_fallback(self) -> bool:
        """Determine if fallback should be used instead of primary service."""
        status = self.health_monitor.get_service_status(self.service_name)
        return status in [ServiceStatus.UNHEALTHY, ServiceStatus.UNKNOWN]
    
    def is_service_degraded(self) -> bool:
        """Check if service is in degraded state."""
        status = self.health_monitor.get_service_status(self.service_name)
        return status == ServiceStatus.DEGRADED
    
    async def execute_fallback(self, *args, **kwargs):
        """Execute fallback handler if available."""
        if not self.fallback_handler:
            raise ExternalServiceError(
                message=f"Service {self.service_name} is unavailable and no fallback configured",
                error_code=ErrorCode.OPENAI_API_ERROR,  # Generic external service error
                service_name=self.service_name
            )
        
        logger.info(
            f"Executing fallback for service {self.service_name}",
            extra={"service": self.service_name}
        )
        
        return await self.fallback_handler(*args, **kwargs)


# Global health monitor instance
health_monitor = HealthMonitor()


# Convenience functions for common health checks
async def check_openai_health() -> bool:
    """Health check for OpenAI API."""
    try:
        import openai
        from app.core.config import settings
        
        if not settings.OPENAI_API_KEY:
            return False
        
        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Simple API call to check if service is responsive
        response = await client.models.list()
        return len(response.data) > 0
        
    except Exception as e:
        logger.debug(f"OpenAI health check failed: {e}")
        return False


async def check_huggingface_health() -> bool:
    """Health check for HuggingFace API."""
    try:
        from app.core.config import settings
        
        if not settings.HF_TOKEN:
            return False
        
        # For now, just check if token is configured
        # In a real implementation, you might make a test API call
        return True
        
    except Exception as e:
        logger.debug(f"HuggingFace health check failed: {e}")
        return False


async def check_redis_health() -> bool:
    """Health check for Redis."""
    try:
        from app.core.redis import redis_client
        
        # Simple ping to check Redis connectivity
        await redis_client.ping()
        return True
        
    except Exception as e:
        logger.debug(f"Redis health check failed: {e}")
        return False


async def check_database_health() -> bool:
    """Health check for PostgreSQL database."""
    try:
        from app.db.base import SessionLocal
        
        # Simple query to check database connectivity
        with SessionLocal() as db:
            db.execute("SELECT 1")
            return True
        
    except Exception as e:
        logger.debug(f"Database health check failed: {e}")
        return False


# Initialize health monitoring for common services
async def setup_health_monitoring():
    """Setup health monitoring for all external services."""
    
    # Register OpenAI service
    health_monitor.register_service(
        service_name="openai",
        check_function=check_openai_health,
        interval_seconds=120,  # Check every 2 minutes
        failure_threshold=2,   # Mark unhealthy after 2 failures
        recovery_threshold=1   # Mark healthy after 1 success
    )
    
    # Register HuggingFace service
    health_monitor.register_service(
        service_name="huggingface",
        check_function=check_huggingface_health,
        interval_seconds=300,  # Check every 5 minutes
        failure_threshold=3,
        recovery_threshold=2
    )
    
    # Register Redis service
    health_monitor.register_service(
        service_name="redis",
        check_function=check_redis_health,
        interval_seconds=60,   # Check every minute
        failure_threshold=2,
        recovery_threshold=1
    )
    
    # Register Database service
    health_monitor.register_service(
        service_name="database",
        check_function=check_database_health,
        interval_seconds=60,   # Check every minute
        failure_threshold=2,
        recovery_threshold=1
    )
    
    # Start monitoring
    await health_monitor.start_monitoring()
    
    logger.info("Health monitoring setup completed")


# Cleanup function
async def cleanup_health_monitoring():
    """Cleanup health monitoring on application shutdown."""
    await health_monitor.stop_monitoring()
    logger.info("Health monitoring cleanup completed")