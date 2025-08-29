"""
Redis connection and utilities for caching and task tracking.
"""
import json
import asyncio
from typing import Optional, Dict, Any, Union
from datetime import datetime, timedelta
import redis.asyncio as redis
from app.core.config import settings


class RedisClient:
    def __init__(self):
        self.redis_url = settings.REDIS_URL
        self._client = None
        self._pool = None
    
    async def get_client(self) -> redis.Redis:
        """Get Redis client instance with connection pooling."""
        if self._client is None:
            self._pool = redis.ConnectionPool.from_url(
                self.redis_url, 
                decode_responses=True,
                max_connections=20,
                retry_on_timeout=True
            )
            self._client = redis.Redis(connection_pool=self._pool)
        return self._client
    
    async def close(self):
        """Close Redis connection and pool."""
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()


class TaskProgressCache:
    """Cache for task progress tracking."""
    
    def __init__(self, redis_client: RedisClient):
        self.redis_client = redis_client
        self.prefix = "task"
    
    def _get_key(self, task_id: str, suffix: str = "progress") -> str:
        """Generate Redis key for task data."""
        return f"{self.prefix}:{task_id}:{suffix}"
    
    async def set_progress(
        self, 
        task_id: str, 
        progress: float, 
        step: str, 
        step_description: Optional[str] = None,
        eta_seconds: Optional[int] = None
    ) -> None:
        """Set task progress information."""
        client = await self.redis_client.get_client()
        
        progress_data = {
            "progress": progress,
            "step": step,
            "step_description": step_description,
            "eta_seconds": eta_seconds,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        key = self._get_key(task_id)
        await client.setex(key, 3600, json.dumps(progress_data))  # Expire in 1 hour
    
    async def get_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task progress information."""
        client = await self.redis_client.get_client()
        key = self._get_key(task_id)
        
        data = await client.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def set_status(self, task_id: str, status: str) -> None:
        """Set task status."""
        client = await self.redis_client.get_client()
        key = self._get_key(task_id, "status")
        await client.setex(key, 3600, status)
    
    async def get_status(self, task_id: str) -> Optional[str]:
        """Get task status."""
        client = await self.redis_client.get_client()
        key = self._get_key(task_id, "status")
        return await client.get(key)
    
    async def set_error(self, task_id: str, error_message: str) -> None:
        """Set task error message."""
        client = await self.redis_client.get_client()
        key = self._get_key(task_id, "error")
        await client.setex(key, 3600, error_message)
    
    async def get_error(self, task_id: str) -> Optional[str]:
        """Get task error message."""
        client = await self.redis_client.get_client()
        key = self._get_key(task_id, "error")
        return await client.get(key)
    
    async def delete_task_data(self, task_id: str) -> None:
        """Delete all task-related data."""
        client = await self.redis_client.get_client()
        keys = [
            self._get_key(task_id, "progress"),
            self._get_key(task_id, "status"),
            self._get_key(task_id, "error")
        ]
        await client.delete(*keys)


class UserSessionCache:
    """Cache for user session data."""
    
    def __init__(self, redis_client: RedisClient):
        self.redis_client = redis_client
        self.prefix = "user"
    
    def _get_key(self, user_id: str, suffix: str = "session") -> str:
        """Generate Redis key for user data."""
        return f"{self.prefix}:{user_id}:{suffix}"
    
    async def set_session(
        self, 
        user_id: str, 
        balance: float, 
        active_tasks: list = None,
        expire_seconds: int = 1800  # 30 minutes
    ) -> None:
        """Set user session data."""
        client = await self.redis_client.get_client()
        
        session_data = {
            "balance": balance,
            "active_tasks": active_tasks or [],
            "last_activity": datetime.utcnow().isoformat()
        }
        
        key = self._get_key(user_id)
        await client.setex(key, expire_seconds, json.dumps(session_data))
    
    async def get_session(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user session data."""
        client = await self.redis_client.get_client()
        key = self._get_key(user_id)
        
        data = await client.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def update_balance(self, user_id: str, new_balance: float) -> None:
        """Update user balance in session cache."""
        session = await self.get_session(user_id)
        if session:
            session["balance"] = new_balance
            session["last_activity"] = datetime.utcnow().isoformat()
            
            client = await self.redis_client.get_client()
            key = self._get_key(user_id)
            # Keep existing TTL
            ttl = await client.ttl(key)
            if ttl > 0:
                await client.setex(key, ttl, json.dumps(session))
    
    async def add_active_task(self, user_id: str, task_id: str) -> None:
        """Add task to user's active tasks."""
        session = await self.get_session(user_id)
        if session:
            if task_id not in session["active_tasks"]:
                session["active_tasks"].append(task_id)
                session["last_activity"] = datetime.utcnow().isoformat()
                
                client = await self.redis_client.get_client()
                key = self._get_key(user_id)
                ttl = await client.ttl(key)
                if ttl > 0:
                    await client.setex(key, ttl, json.dumps(session))
    
    async def remove_active_task(self, user_id: str, task_id: str) -> None:
        """Remove task from user's active tasks."""
        session = await self.get_session(user_id)
        if session and task_id in session["active_tasks"]:
            session["active_tasks"].remove(task_id)
            session["last_activity"] = datetime.utcnow().isoformat()
            
            client = await self.redis_client.get_client()
            key = self._get_key(user_id)
            ttl = await client.ttl(key)
            if ttl > 0:
                await client.setex(key, ttl, json.dumps(session))


class RateLimiter:
    """Rate limiting utilities using Redis."""
    
    def __init__(self, redis_client: RedisClient):
        self.redis_client = redis_client
        self.prefix = "rate_limit"
    
    def _get_key(self, identifier: str, limit_type: str) -> str:
        """Generate Redis key for rate limiting."""
        return f"{self.prefix}:{limit_type}:{identifier}"
    
    async def check_rate_limit(
        self, 
        identifier: str, 
        limit_type: str, 
        max_requests: int, 
        window_seconds: int
    ) -> Dict[str, Union[bool, int]]:
        """
        Check if request is within rate limit.
        
        Returns:
            Dict with 'allowed' (bool), 'remaining' (int), 'reset_time' (int)
        """
        client = await self.redis_client.get_client()
        key = self._get_key(identifier, limit_type)
        
        current_time = int(datetime.utcnow().timestamp())
        window_start = current_time - window_seconds
        
        # Use sliding window log approach
        pipe = client.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count current requests
        pipe.zcard(key)
        
        # Add current request
        pipe.zadd(key, {str(current_time): current_time})
        
        # Set expiration
        pipe.expire(key, window_seconds)
        
        results = await pipe.execute()
        current_requests = results[1]
        
        allowed = current_requests < max_requests
        remaining = max(0, max_requests - current_requests - 1)
        reset_time = current_time + window_seconds
        
        return {
            "allowed": allowed,
            "remaining": remaining,
            "reset_time": reset_time,
            "current_requests": current_requests
        }
    
    async def check_openai_rate_limit(self, user_id: str) -> Dict[str, Union[bool, int]]:
        """Check OpenAI API rate limit for user (60 requests per minute)."""
        return await self.check_rate_limit(
            identifier=user_id,
            limit_type="openai",
            max_requests=60,
            window_seconds=60
        )
    
    async def check_processing_rate_limit(self, user_id: str) -> Dict[str, Union[bool, int]]:
        """Check concurrent processing limit for user (3 concurrent tasks)."""
        return await self.check_rate_limit(
            identifier=user_id,
            limit_type="processing",
            max_requests=3,
            window_seconds=3600  # 1 hour window
        )
    
    async def check_upload_rate_limit(self, user_id: str) -> Dict[str, Union[bool, int]]:
        """Check upload rate limit for user (10 uploads per hour)."""
        return await self.check_rate_limit(
            identifier=user_id,
            limit_type="upload",
            max_requests=10,
            window_seconds=3600
        )


class CacheManager:
    """Main cache manager that coordinates all caching utilities."""
    
    def __init__(self):
        self.redis_client = RedisClient()
        self.task_cache = TaskProgressCache(self.redis_client)
        self.user_cache = UserSessionCache(self.redis_client)
        self.rate_limiter = RateLimiter(self.redis_client)
    
    async def health_check(self) -> bool:
        """Check if Redis is healthy."""
        try:
            client = await self.redis_client.get_client()
            await client.ping()
            return True
        except Exception:
            return False
    
    async def close(self):
        """Close all Redis connections."""
        await self.redis_client.close()


# Global cache manager instance
cache_manager = CacheManager()