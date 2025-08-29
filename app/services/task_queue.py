"""
Asynchronous task queue and progress tracking system.
"""
import asyncio
import uuid
from typing import Dict, Optional, Callable, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging
import traceback
from contextlib import asynccontextmanager

from app.core.redis import cache_manager
from app.schemas.processing_task import TaskStatus, ProcessingStep


logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3


@dataclass
class TaskInfo:
    """Information about a queued task."""
    task_id: str
    user_id: str
    priority: TaskPriority
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING
    current_step: Optional[ProcessingStep] = None
    progress: float = 0.0
    error_message: Optional[str] = None
    cancellation_requested: bool = False
    cleanup_callbacks: List[Callable] = field(default_factory=list)


class TaskQueue:
    """Asynchronous task queue with priority support and progress tracking."""
    
    def __init__(self, max_concurrent_tasks: int = 5):
        self.max_concurrent_tasks = max_concurrent_tasks
        self._tasks: Dict[str, TaskInfo] = {}
        self._queue = asyncio.PriorityQueue()
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._workers: List[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()
        self._worker_count = 3  # Number of worker coroutines
        
    async def start(self):
        """Start the task queue workers."""
        logger.info(f"Starting task queue with {self._worker_count} workers")
        
        for i in range(self._worker_count):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self._workers.append(worker)
    
    async def stop(self):
        """Stop the task queue and cancel all running tasks."""
        logger.info("Stopping task queue...")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Cancel all running tasks
        for task_id, task in self._running_tasks.items():
            logger.info(f"Cancelling running task: {task_id}")
            task.cancel()
            
            # Update task status
            if task_id in self._tasks:
                await self._update_task_status(task_id, TaskStatus.FAILED, "Task cancelled during shutdown")
        
        # Wait for workers to finish
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        
        # Clear state
        self._running_tasks.clear()
        self._workers.clear()
        
        logger.info("Task queue stopped")
    
    async def enqueue_task(
        self,
        task_id: str,
        user_id: str,
        task_func: Callable,
        priority: TaskPriority = TaskPriority.NORMAL,
        cleanup_callbacks: Optional[List[Callable]] = None
    ) -> bool:
        """
        Enqueue a task for processing.
        
        Args:
            task_id: Unique identifier for the task
            user_id: ID of the user who owns the task
            task_func: Async function to execute
            priority: Task priority
            cleanup_callbacks: Functions to call during cleanup
            
        Returns:
            True if task was enqueued, False if already exists
        """
        if task_id in self._tasks:
            logger.warning(f"Task {task_id} already exists")
            return False
        
        # Check if user has too many concurrent tasks
        user_task_count = sum(1 for task in self._tasks.values() 
                             if task.user_id == user_id and task.status == TaskStatus.PROCESSING)
        
        if user_task_count >= 3:  # Max 3 concurrent tasks per user
            raise ValueError("User has too many concurrent tasks")
        
        # Create task info
        task_info = TaskInfo(
            task_id=task_id,
            user_id=user_id,
            priority=priority,
            created_at=datetime.utcnow(),
            cleanup_callbacks=cleanup_callbacks or []
        )
        
        self._tasks[task_id] = task_info
        
        # Add to queue with priority (lower number = higher priority)
        priority_value = -priority.value  # Negative for correct priority ordering
        await self._queue.put((priority_value, datetime.utcnow(), task_id, task_func))
        
        # Update Redis cache
        await cache_manager.task_cache.set_status(task_id, TaskStatus.PENDING.value)
        await cache_manager.user_cache.add_active_task(user_id, task_id)
        
        logger.info(f"Enqueued task {task_id} for user {user_id} with priority {priority.name}")
        return True
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task.
        
        Args:
            task_id: ID of the task to cancel
            
        Returns:
            True if task was cancelled, False if not found or already completed
        """
        if task_id not in self._tasks:
            return False
        
        task_info = self._tasks[task_id]
        
        # If task is running, cancel it
        if task_id in self._running_tasks:
            self._running_tasks[task_id].cancel()
            task_info.cancellation_requested = True
            logger.info(f"Cancelled running task {task_id}")
        else:
            # Mark as cancelled if not yet started
            await self._update_task_status(task_id, TaskStatus.FAILED, "Task cancelled by user")
            logger.info(f"Marked pending task {task_id} as cancelled")
        
        return True
    
    async def get_task_status(self, task_id: str) -> Optional[TaskInfo]:
        """Get current status of a task."""
        return self._tasks.get(task_id)
    
    async def get_user_tasks(self, user_id: str) -> List[TaskInfo]:
        """Get all tasks for a specific user."""
        return [task for task in self._tasks.values() if task.user_id == user_id]
    
    async def cleanup_completed_tasks(self, max_age_hours: int = 24):
        """Clean up completed tasks older than specified age."""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        tasks_to_remove = []
        
        for task_id, task_info in self._tasks.items():
            if (task_info.status in [TaskStatus.COMPLETED, TaskStatus.FAILED] and
                task_info.completed_at and task_info.completed_at < cutoff_time):
                
                # Run cleanup callbacks
                for cleanup_func in task_info.cleanup_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(cleanup_func):
                            await cleanup_func()
                        else:
                            cleanup_func()
                    except Exception as e:
                        logger.error(f"Error in cleanup callback for task {task_id}: {e}")
                
                # Remove from Redis cache
                await cache_manager.task_cache.delete_task_data(task_id)
                await cache_manager.user_cache.remove_active_task(task_info.user_id, task_id)
                
                tasks_to_remove.append(task_id)
        
        # Remove from memory
        for task_id in tasks_to_remove:
            del self._tasks[task_id]
            logger.info(f"Cleaned up completed task {task_id}")
        
        return len(tasks_to_remove)
    
    async def _worker(self, worker_name: str):
        """Worker coroutine that processes tasks from the queue."""
        logger.info(f"Started worker: {worker_name}")
        
        while not self._shutdown_event.is_set():
            try:
                # Wait for a task with timeout
                try:
                    priority, queued_at, task_id, task_func = await asyncio.wait_for(
                        self._queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Check if we have capacity
                if len(self._running_tasks) >= self.max_concurrent_tasks:
                    # Put task back in queue
                    await self._queue.put((priority, queued_at, task_id, task_func))
                    await asyncio.sleep(0.1)
                    continue
                
                # Start processing the task
                task_coroutine = asyncio.create_task(
                    self._process_task(task_id, task_func)
                )
                self._running_tasks[task_id] = task_coroutine
                
                logger.info(f"Worker {worker_name} started processing task {task_id}")
                
            except Exception as e:
                logger.error(f"Error in worker {worker_name}: {e}")
                await asyncio.sleep(1.0)
        
        logger.info(f"Worker {worker_name} stopped")
    
    async def _process_task(self, task_id: str, task_func: Callable):
        """Process a single task."""
        task_info = self._tasks.get(task_id)
        if not task_info:
            logger.error(f"Task info not found for {task_id}")
            return
        
        try:
            # Update task status to processing
            task_info.started_at = datetime.utcnow()
            await self._update_task_status(task_id, TaskStatus.PROCESSING)
            
            # Create progress tracker for this task
            progress_tracker = TaskProgressTracker(task_id, task_info)
            
            # Execute the task function with progress tracker
            if asyncio.iscoroutinefunction(task_func):
                await task_func(progress_tracker)
            else:
                # Run sync function in thread pool
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, task_func, progress_tracker)
            
            # Mark as completed
            task_info.completed_at = datetime.utcnow()
            await self._update_task_status(task_id, TaskStatus.COMPLETED)
            
            logger.info(f"Task {task_id} completed successfully")
            
        except asyncio.CancelledError:
            # Task was cancelled
            task_info.completed_at = datetime.utcnow()
            await self._update_task_status(task_id, TaskStatus.FAILED, "Task was cancelled")
            logger.info(f"Task {task_id} was cancelled")
            
        except Exception as e:
            # Task failed
            error_msg = f"Task failed: {str(e)}"
            task_info.completed_at = datetime.utcnow()
            task_info.error_message = error_msg
            await self._update_task_status(task_id, TaskStatus.FAILED, error_msg)
            
            logger.error(f"Task {task_id} failed: {e}")
            logger.error(traceback.format_exc())
            
        finally:
            # Remove from running tasks
            if task_id in self._running_tasks:
                del self._running_tasks[task_id]
    
    async def _update_task_status(
        self, 
        task_id: str, 
        status: TaskStatus, 
        error_message: Optional[str] = None
    ):
        """Update task status in memory and Redis."""
        if task_id in self._tasks:
            task_info = self._tasks[task_id]
            task_info.status = status
            if error_message:
                task_info.error_message = error_message
        
        # Update Redis cache
        await cache_manager.task_cache.set_status(task_id, status.value)
        if error_message:
            await cache_manager.task_cache.set_error(task_id, error_message)


class TaskProgressTracker:
    """Helper class for tracking task progress within a task function."""
    
    def __init__(self, task_id: str, task_info: TaskInfo):
        self.task_id = task_id
        self.task_info = task_info
        self._step_start_time: Optional[datetime] = None
        self._total_steps = 0
        self._completed_steps = 0
    
    async def set_total_steps(self, total_steps: int):
        """Set the total number of steps for ETA calculation."""
        self._total_steps = total_steps
    
    async def start_step(self, step: ProcessingStep, description: Optional[str] = None):
        """Mark the start of a processing step."""
        self.task_info.current_step = step
        self._step_start_time = datetime.utcnow()
        
        # Calculate progress based on completed steps
        if self._total_steps > 0:
            progress = self._completed_steps / self._total_steps
        else:
            progress = self.task_info.progress
        
        # Calculate ETA
        eta_seconds = None
        if self._completed_steps > 0 and self._step_start_time and self.task_info.started_at:
            elapsed = (self._step_start_time - self.task_info.started_at).total_seconds()
            avg_step_time = elapsed / self._completed_steps
            remaining_steps = self._total_steps - self._completed_steps
            eta_seconds = int(avg_step_time * remaining_steps)
        
        # Update progress in Redis
        await cache_manager.task_cache.set_progress(
            self.task_id,
            progress,
            step.value,
            description,
            eta_seconds
        )
        
        logger.info(f"Task {self.task_id} started step: {step.value} - {description}")
    
    async def complete_step(self):
        """Mark the current step as completed."""
        if self._step_start_time:
            duration = (datetime.utcnow() - self._step_start_time).total_seconds()
            logger.info(f"Task {self.task_id} completed step: {self.task_info.current_step.value} in {duration:.2f}s")
        
        self._completed_steps += 1
        
        # Update progress
        if self._total_steps > 0:
            progress = min(1.0, self._completed_steps / self._total_steps)
            self.task_info.progress = progress
            
            await cache_manager.task_cache.set_progress(
                self.task_id,
                progress,
                self.task_info.current_step.value if self.task_info.current_step else "unknown"
            )
    
    async def update_progress(self, progress: float, description: Optional[str] = None):
        """Update progress within the current step."""
        # Combine step progress with overall progress
        if self._total_steps > 0:
            step_progress = self._completed_steps / self._total_steps
            step_weight = 1.0 / self._total_steps
            total_progress = step_progress + (progress * step_weight)
        else:
            total_progress = progress
        
        self.task_info.progress = min(1.0, total_progress)
        
        await cache_manager.task_cache.set_progress(
            self.task_id,
            self.task_info.progress,
            self.task_info.current_step.value if self.task_info.current_step else "unknown",
            description
        )
    
    def check_cancellation(self):
        """Check if task cancellation was requested."""
        if self.task_info.cancellation_requested:
            raise asyncio.CancelledError("Task cancellation requested")


# Global task queue instance
task_queue = TaskQueue()


@asynccontextmanager
async def task_queue_lifespan():
    """Context manager for task queue lifecycle."""
    try:
        await task_queue.start()
        yield task_queue
    finally:
        await task_queue.stop()