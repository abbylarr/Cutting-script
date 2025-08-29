"""
Cache utility functions for easy access to Redis operations.
"""
from typing import Optional, Dict, Any, List
from uuid import UUID
from app.core.redis import cache_manager


async def set_task_progress(
    task_id: str,
    progress: float,
    step: str,
    step_description: Optional[str] = None,
    eta_seconds: Optional[int] = None
) -> None:
    """Set task progress in cache."""
    await cache_manager.task_cache.set_progress(
        task_id=task_id,
        progress=progress,
        step=step,
        step_description=step_description,
        eta_seconds=eta_seconds
    )


async def get_task_progress(task_id: str) -> Optional[Dict[str, Any]]:
    """Get task progress from cache."""
    return await cache_manager.task_cache.get_progress(task_id)


async def set_task_status(task_id: str, status: str) -> None:
    """Set task status in cache."""
    await cache_manager.task_cache.set_status(task_id, status)


async def get_task_status(task_id: str) -> Optional[str]:
    """Get task status from cache."""
    return await cache_manager.task_cache.get_status(task_id)


async def set_task_error(task_id: str, error_message: str) -> None:
    """Set task error in cache."""
    await cache_manager.task_cache.set_error(task_id, error_message)


async def get_task_error(task_id: str) -> Optional[str]:
    """Get task error from cache."""
    return await cache_manager.task_cache.get_error(task_id)


async def clear_task_cache(task_id: str) -> None:
    """Clear all task data from cache."""
    await cache_manager.task_cache.delete_task_data(task_id)


async def cache_user_session(
    user_id: str,
    balance: float,
    active_tasks: Optional[List[str]] = None
) -> None:
    """Cache user session data."""
    await cache_manager.user_cache.set_session(
        user_id=user_id,
        balance=balance,
        active_tasks=active_tasks or []
    )


async def get_user_session(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user session from cache."""
    return await cache_manager.user_cache.get_session(user_id)


async def update_user_balance_cache(user_id: str, new_balance: float) -> None:
    """Update user balance in cache."""
    await cache_manager.user_cache.update_balance(user_id, new_balance)


async def add_user_active_task(user_id: str, task_id: str) -> None:
    """Add task to user's active tasks in cache."""
    await cache_manager.user_cache.add_active_task(user_id, task_id)


async def remove_user_active_task(user_id: str, task_id: str) -> None:
    """Remove task from user's active tasks in cache."""
    await cache_manager.user_cache.remove_active_task(user_id, task_id)


async def check_rate_limit(
    user_id: str,
    limit_type: str,
    max_requests: int,
    window_seconds: int
) -> Dict[str, Any]:
    """Check rate limit for user."""
    return await cache_manager.rate_limiter.check_rate_limit(
        identifier=user_id,
        limit_type=limit_type,
        max_requests=max_requests,
        window_seconds=window_seconds
    )


async def check_openai_rate_limit(user_id: str) -> Dict[str, Any]:
    """Check OpenAI API rate limit for user."""
    return await cache_manager.rate_limiter.check_openai_rate_limit(user_id)


async def check_processing_rate_limit(user_id: str) -> Dict[str, Any]:
    """Check processing rate limit for user."""
    return await cache_manager.rate_limiter.check_processing_rate_limit(user_id)


async def check_upload_rate_limit(user_id: str) -> Dict[str, Any]:
    """Check upload rate limit for user."""
    return await cache_manager.rate_limiter.check_upload_rate_limit(user_id)


async def is_cache_healthy() -> bool:
    """Check if cache (Redis) is healthy."""
    return await cache_manager.health_check()


async def close_cache_connections() -> None:
    """Close all cache connections."""
    await cache_manager.close()


# Convenience functions for common operations
async def start_task_processing(task_id: str, user_id: str) -> None:
    """Mark task as started and add to user's active tasks."""
    await set_task_status(task_id, "processing")
    await set_task_progress(task_id, 0.0, "starting", "Initializing task processing")
    await add_user_active_task(user_id, task_id)


async def complete_task_processing(task_id: str, user_id: str) -> None:
    """Mark task as completed and remove from user's active tasks."""
    await set_task_status(task_id, "completed")
    await set_task_progress(task_id, 1.0, "completed", "Task processing completed")
    await remove_user_active_task(user_id, task_id)


async def fail_task_processing(task_id: str, user_id: str, error_message: str) -> None:
    """Mark task as failed and remove from user's active tasks."""
    await set_task_status(task_id, "failed")
    await set_task_error(task_id, error_message)
    await remove_user_active_task(user_id, task_id)