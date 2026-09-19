"""
Redis connection and utilities for caching and task tracking.
Falls back to in-memory store when Redis is unavailable (autonomous / offline mode).
"""
import json
import logging
from typing import Optional, Dict, Any, Union
from datetime import datetime
import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger(__name__)


class InMemoryStore:
    """Simple TTL-aware in-memory key-value store."""

    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}

    def _expired(self, key: str) -> bool:
        exp = self._expiry.get(key)
        if exp is None:
            return False
        if datetime.utcnow().timestamp() > exp:
            self._data.pop(key, None)
            self._expiry.pop(key, None)
            return True
        return False

    async def setex(self, key: str, seconds: int, value: str) -> None:
        self._data[key] = value
        self._expiry[key] = datetime.utcnow().timestamp() + seconds

    async def get(self, key: str) -> Optional[str]:
        if self._expired(key):
            return None
        return self._data.get(key)

    async def delete(self, *keys: str) -> int:
        count = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                self._expiry.pop(key, None)
                count += 1
        return count

    async def ping(self) -> bool:
        return True

    async def ttl(self, key: str) -> int:
        if self._expired(key) or key not in self._expiry:
            return -2
        return max(0, int(self._expiry[key] - datetime.utcnow().timestamp()))

    async def zremrangebyscore(self, key: str, min_score, max_score) -> int:
        return 0

    async def zcard(self, key: str) -> int:
        return 0

    async def zadd(self, key: str, mapping: dict) -> int:
        return 0

    async def expire(self, key: str, seconds: int) -> bool:
        if key in self._data:
            self._expiry[key] = datetime.utcnow().timestamp() + seconds
            return True
        return False

    def pipeline(self):
        return _MemoryPipeline(self)

    async def close(self) -> None:
        pass


class _MemoryPipeline:
    def __init__(self, store: InMemoryStore):
        self.store = store
        self._ops = []

    def zremrangebyscore(self, key, min_s, max_s):
        self._ops.append(("zrem", key))
        return self

    def zcard(self, key):
        self._ops.append(("zcard", key))
        return self

    def zadd(self, key, mapping):
        self._ops.append(("zadd", key, mapping))
        return self

    def expire(self, key, seconds):
        self._ops.append(("expire", key, seconds))
        return self

    async def execute(self):
        # Return stub results matching check_rate_limit expectations: [rem, card, add, expire]
        return [0, 0, 1, True]


class RedisClient:
    def __init__(self):
        self.redis_url = settings.REDIS_URL
        self._client = None
        self._pool = None
        self._memory: Optional[InMemoryStore] = None
        self._use_memory = False

    async def get_client(self):
        """Get Redis client, or in-memory store if Redis is down / autonomous."""
        if self._use_memory and self._memory is not None:
            return self._memory

        if self._client is not None:
            return self._client

        try:
            self._pool = redis.ConnectionPool.from_url(
                self.redis_url,
                decode_responses=True,
                max_connections=20,
                retry_on_timeout=True,
                socket_connect_timeout=1.0,
            )
            client = redis.Redis(connection_pool=self._pool)
            await client.ping()
            self._client = client
            logger.info("Connected to Redis")
            return self._client
        except Exception as e:
            logger.warning(f"Redis unavailable ({e}); using in-memory cache")
            self._use_memory = True
            self._memory = InMemoryStore()
            if self._pool:
                try:
                    await self._pool.disconnect()
                except Exception:
                    pass
                self._pool = None
            return self._memory

    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None
        if self._pool:
            await self._pool.disconnect()
            self._pool = None
        self._memory = None


class TaskProgressCache:
    """Cache for task progress tracking."""

    def __init__(self, redis_client: RedisClient):
        self.redis_client = redis_client
        self.prefix = "task"

    def _get_key(self, task_id: str, suffix: str = "progress") -> str:
        return f"{self.prefix}:{task_id}:{suffix}"

    async def set_progress(
        self,
        task_id: str,
        progress: float,
        step: str,
        step_description: Optional[str] = None,
        eta_seconds: Optional[int] = None,
    ) -> None:
        try:
            client = await self.redis_client.get_client()
            progress_data = {
                "progress": progress,
                "step": step,
                "step_description": step_description,
                "eta_seconds": eta_seconds,
                "updated_at": datetime.utcnow().isoformat(),
            }
            await client.setex(self._get_key(task_id), 3600, json.dumps(progress_data))
        except Exception as e:
            logger.debug(f"set_progress skipped: {e}")

    async def get_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        try:
            client = await self.redis_client.get_client()
            data = await client.get(self._get_key(task_id))
            return json.loads(data) if data else None
        except Exception:
            return None

    async def set_status(self, task_id: str, status: str) -> None:
        try:
            client = await self.redis_client.get_client()
            await client.setex(self._get_key(task_id, "status"), 3600, status)
        except Exception as e:
            logger.debug(f"set_status skipped: {e}")

    async def get_status(self, task_id: str) -> Optional[str]:
        try:
            client = await self.redis_client.get_client()
            return await client.get(self._get_key(task_id, "status"))
        except Exception:
            return None

    async def set_error(self, task_id: str, error_message: str) -> None:
        try:
            client = await self.redis_client.get_client()
            await client.setex(self._get_key(task_id, "error"), 3600, error_message)
        except Exception as e:
            logger.debug(f"set_error skipped: {e}")

    async def get_error(self, task_id: str) -> Optional[str]:
        try:
            client = await self.redis_client.get_client()
            return await client.get(self._get_key(task_id, "error"))
        except Exception:
            return None

    async def delete_task_data(self, task_id: str) -> None:
        try:
            client = await self.redis_client.get_client()
            await client.delete(
                self._get_key(task_id, "progress"),
                self._get_key(task_id, "status"),
                self._get_key(task_id, "error"),
            )
        except Exception as e:
            logger.debug(f"delete_task_data skipped: {e}")


class UserSessionCache:
    def __init__(self, redis_client: RedisClient):
        self.redis_client = redis_client
        self.prefix = "user"

    def _get_key(self, user_id: str, suffix: str = "session") -> str:
        return f"{self.prefix}:{user_id}:{suffix}"

    async def set_session(
        self,
        user_id: str,
        balance: float,
        active_tasks: list = None,
        expire_seconds: int = 1800,
    ) -> None:
        try:
            client = await self.redis_client.get_client()
            session_data = {
                "balance": balance,
                "active_tasks": active_tasks or [],
                "last_activity": datetime.utcnow().isoformat(),
            }
            await client.setex(self._get_key(user_id), expire_seconds, json.dumps(session_data))
        except Exception as e:
            logger.debug(f"set_session skipped: {e}")

    async def get_session(self, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            client = await self.redis_client.get_client()
            data = await client.get(self._get_key(user_id))
            return json.loads(data) if data else None
        except Exception:
            return None

    async def update_balance(self, user_id: str, new_balance: float) -> None:
        session = await self.get_session(user_id)
        if not session:
            return
        session["balance"] = new_balance
        session["last_activity"] = datetime.utcnow().isoformat()
        try:
            client = await self.redis_client.get_client()
            key = self._get_key(user_id)
            ttl = await client.ttl(key)
            if ttl and ttl > 0:
                await client.setex(key, ttl, json.dumps(session))
        except Exception:
            pass

    async def add_active_task(self, user_id: str, task_id: str) -> None:
        session = await self.get_session(user_id)
        if not session:
            await self.set_session(user_id, 0.0, [task_id])
            return
        if task_id not in session["active_tasks"]:
            session["active_tasks"].append(task_id)
            try:
                client = await self.redis_client.get_client()
                key = self._get_key(user_id)
                ttl = await client.ttl(key)
                await client.setex(key, ttl if ttl and ttl > 0 else 1800, json.dumps(session))
            except Exception:
                pass

    async def remove_active_task(self, user_id: str, task_id: str) -> None:
        session = await self.get_session(user_id)
        if not session or task_id not in session.get("active_tasks", []):
            return
        session["active_tasks"].remove(task_id)
        try:
            client = await self.redis_client.get_client()
            key = self._get_key(user_id)
            ttl = await client.ttl(key)
            await client.setex(key, ttl if ttl and ttl > 0 else 1800, json.dumps(session))
        except Exception:
            pass


class RateLimiter:
    def __init__(self, redis_client: RedisClient):
        self.redis_client = redis_client
        self.prefix = "rate_limit"

    def _get_key(self, identifier: str, limit_type: str) -> str:
        return f"{self.prefix}:{limit_type}:{identifier}"

    async def check_rate_limit(
        self,
        identifier: str,
        limit_type: str,
        max_requests: int,
        window_seconds: int,
    ) -> Dict[str, Union[bool, int]]:
        # In autonomous mode or memory store — always allow
        if settings.AUTONOMOUS_MODE or settings.SKIP_BILLING:
            return {
                "allowed": True,
                "remaining": max_requests,
                "reset_time": int(datetime.utcnow().timestamp()) + window_seconds,
                "current_requests": 0,
            }

        try:
            client = await self.redis_client.get_client()
            if isinstance(client, InMemoryStore):
                return {
                    "allowed": True,
                    "remaining": max_requests,
                    "reset_time": int(datetime.utcnow().timestamp()) + window_seconds,
                    "current_requests": 0,
                }

            key = self._get_key(identifier, limit_type)
            current_time = int(datetime.utcnow().timestamp())
            window_start = current_time - window_seconds
            pipe = client.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.zadd(key, {str(current_time): current_time})
            pipe.expire(key, window_seconds)
            results = await pipe.execute()
            current_requests = results[1]
            allowed = current_requests < max_requests
            remaining = max(0, max_requests - current_requests - 1)
            return {
                "allowed": allowed,
                "remaining": remaining,
                "reset_time": current_time + window_seconds,
                "current_requests": current_requests,
            }
        except Exception as e:
            logger.warning(f"Rate limit check failed, allowing request: {e}")
            return {
                "allowed": True,
                "remaining": max_requests,
                "reset_time": int(datetime.utcnow().timestamp()) + window_seconds,
                "current_requests": 0,
            }

    async def check_openai_rate_limit(self, user_id: str) -> Dict[str, Union[bool, int]]:
        return await self.check_rate_limit(user_id, "openai", 60, 60)

    async def check_processing_rate_limit(self, user_id: str) -> Dict[str, Union[bool, int]]:
        return await self.check_rate_limit(user_id, "processing", 3, 3600)

    async def check_upload_rate_limit(self, user_id: str) -> Dict[str, Union[bool, int]]:
        return await self.check_rate_limit(user_id, "upload", 10, 3600)


class CacheManager:
    def __init__(self):
        self.redis_client = RedisClient()
        self.task_cache = TaskProgressCache(self.redis_client)
        self.user_cache = UserSessionCache(self.redis_client)
        self.rate_limiter = RateLimiter(self.redis_client)

    async def health_check(self) -> bool:
        try:
            client = await self.redis_client.get_client()
            await client.ping()
            return True
        except Exception:
            return False

    async def close(self):
        await self.redis_client.close()


cache_manager = CacheManager()
