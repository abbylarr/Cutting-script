"""
Unit tests for task queue and progress tracking system.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.task_queue import (
    TaskQueue, TaskInfo, TaskPriority, TaskProgressTracker,
    task_queue_lifespan
)
from app.schemas.processing_task import TaskStatus, ProcessingStep


class TestTaskQueue:
    """Test cases for TaskQueue class."""
    
    @pytest.fixture
    async def task_queue(self):
        """Create a task queue for testing."""
        queue = TaskQueue(max_concurrent_tasks=2)
        await queue.start()
        yield queue
        await queue.stop()
    
    @pytest.fixture
    def mock_cache_manager(self):
        """Mock cache manager for testing."""
        with patch('app.services.task_queue.cache_manager') as mock:
            mock.task_cache.set_status = AsyncMock()
            mock.task_cache.set_progress = AsyncMock()
            mock.task_cache.set_error = AsyncMock()
            mock.task_cache.delete_task_data = AsyncMock()
            mock.user_cache.add_active_task = AsyncMock()
            mock.user_cache.remove_active_task = AsyncMock()
            yield mock
    
    async def test_enqueue_task_success(self, task_queue, mock_cache_manager):
        """Test successful task enqueueing."""
        task_id = "test-task-1"
        user_id = "user-1"
        
        async def dummy_task(progress_tracker):
            await asyncio.sleep(0.1)
        
        result = await task_queue.enqueue_task(
            task_id=task_id,
            user_id=user_id,
            task_func=dummy_task,
            priority=TaskPriority.NORMAL
        )
        
        assert result is True
        assert task_id in task_queue._tasks
        
        task_info = task_queue._tasks[task_id]
        assert task_info.task_id == task_id
        assert task_info.user_id == user_id
        assert task_info.priority == TaskPriority.NORMAL
        assert task_info.status == TaskStatus.PENDING
        
        # Verify cache calls
        mock_cache_manager.task_cache.set_status.assert_called_once_with(
            task_id, TaskStatus.PENDING.value
        )
        mock_cache_manager.user_cache.add_active_task.assert_called_once_with(
            user_id, task_id
        )
    
    async def test_enqueue_duplicate_task(self, task_queue, mock_cache_manager):
        """Test enqueueing duplicate task fails."""
        task_id = "test-task-1"
        user_id = "user-1"
        
        async def dummy_task(progress_tracker):
            pass
        
        # First enqueue should succeed
        result1 = await task_queue.enqueue_task(task_id, user_id, dummy_task)
        assert result1 is True
        
        # Second enqueue should fail
        result2 = await task_queue.enqueue_task(task_id, user_id, dummy_task)
        assert result2 is False
    
    async def test_enqueue_too_many_concurrent_tasks(self, task_queue, mock_cache_manager):
        """Test that users can't have too many concurrent tasks."""
        user_id = "user-1"
        
        async def dummy_task(progress_tracker):
            await asyncio.sleep(1.0)  # Long running task
        
        # Enqueue 3 tasks (should work)
        for i in range(3):
            await task_queue.enqueue_task(f"task-{i}", user_id, dummy_task)
        
        # 4th task should raise error
        with pytest.raises(ValueError, match="too many concurrent tasks"):
            await task_queue.enqueue_task("task-4", user_id, dummy_task)
    
    async def test_task_execution_success(self, task_queue, mock_cache_manager):
        """Test successful task execution."""
        task_id = "test-task-1"
        user_id = "user-1"
        execution_log = []
        
        async def test_task(progress_tracker):
            execution_log.append("started")
            await progress_tracker.start_step(ProcessingStep.VALIDATION, "Testing")
            await asyncio.sleep(0.1)
            await progress_tracker.complete_step()
            execution_log.append("completed")
        
        await task_queue.enqueue_task(task_id, user_id, test_task)
        
        # Wait for task to complete
        await asyncio.sleep(0.5)
        
        task_info = task_queue._tasks[task_id]
        assert task_info.status == TaskStatus.COMPLETED
        assert task_info.started_at is not None
        assert task_info.completed_at is not None
        assert execution_log == ["started", "completed"]
    
    async def test_task_execution_failure(self, task_queue, mock_cache_manager):
        """Test task execution with failure."""
        task_id = "test-task-1"
        user_id = "user-1"
        
        async def failing_task(progress_tracker):
            raise ValueError("Test error")
        
        await task_queue.enqueue_task(task_id, user_id, failing_task)
        
        # Wait for task to fail
        await asyncio.sleep(0.5)
        
        task_info = task_queue._tasks[task_id]
        assert task_info.status == TaskStatus.FAILED
        assert "Test error" in task_info.error_message
        
        # Verify error was cached
        mock_cache_manager.task_cache.set_error.assert_called()
    
    async def test_cancel_pending_task(self, task_queue, mock_cache_manager):
        """Test cancelling a pending task."""
        task_id = "test-task-1"
        user_id = "user-1"
        
        async def dummy_task(progress_tracker):
            await asyncio.sleep(1.0)
        
        await task_queue.enqueue_task(task_id, user_id, dummy_task)
        
        # Cancel immediately
        result = await task_queue.cancel_task(task_id)
        assert result is True
        
        # Wait a bit and check status
        await asyncio.sleep(0.2)
        task_info = task_queue._tasks[task_id]
        assert task_info.status == TaskStatus.FAILED
        assert "cancelled" in task_info.error_message.lower()
    
    async def test_cancel_running_task(self, task_queue, mock_cache_manager):
        """Test cancelling a running task."""
        task_id = "test-task-1"
        user_id = "user-1"
        
        async def long_task(progress_tracker):
            await asyncio.sleep(2.0)  # Long running
        
        await task_queue.enqueue_task(task_id, user_id, long_task)
        
        # Wait for task to start
        await asyncio.sleep(0.2)
        
        # Cancel the running task
        result = await task_queue.cancel_task(task_id)
        assert result is True
        
        # Wait for cancellation to take effect
        await asyncio.sleep(0.3)
        
        task_info = task_queue._tasks[task_id]
        assert task_info.status == TaskStatus.FAILED
    
    async def test_cancel_nonexistent_task(self, task_queue, mock_cache_manager):
        """Test cancelling a non-existent task."""
        result = await task_queue.cancel_task("nonexistent-task")
        assert result is False
    
    async def test_get_task_status(self, task_queue, mock_cache_manager):
        """Test getting task status."""
        task_id = "test-task-1"
        user_id = "user-1"
        
        async def dummy_task(progress_tracker):
            pass
        
        await task_queue.enqueue_task(task_id, user_id, dummy_task)
        
        task_info = await task_queue.get_task_status(task_id)
        assert task_info is not None
        assert task_info.task_id == task_id
        assert task_info.user_id == user_id
        
        # Non-existent task
        task_info = await task_queue.get_task_status("nonexistent")
        assert task_info is None
    
    async def test_get_user_tasks(self, task_queue, mock_cache_manager):
        """Test getting all tasks for a user."""
        user_id = "user-1"
        other_user_id = "user-2"
        
        async def dummy_task(progress_tracker):
            pass
        
        # Add tasks for user-1
        await task_queue.enqueue_task("task-1", user_id, dummy_task)
        await task_queue.enqueue_task("task-2", user_id, dummy_task)
        
        # Add task for user-2
        await task_queue.enqueue_task("task-3", other_user_id, dummy_task)
        
        user_tasks = await task_queue.get_user_tasks(user_id)
        assert len(user_tasks) == 2
        assert all(task.user_id == user_id for task in user_tasks)
        
        other_user_tasks = await task_queue.get_user_tasks(other_user_id)
        assert len(other_user_tasks) == 1
        assert other_user_tasks[0].user_id == other_user_id
    
    async def test_cleanup_completed_tasks(self, task_queue, mock_cache_manager):
        """Test cleanup of old completed tasks."""
        task_id = "test-task-1"
        user_id = "user-1"
        cleanup_called = False
        
        def cleanup_callback():
            nonlocal cleanup_called
            cleanup_called = True
        
        async def dummy_task(progress_tracker):
            pass
        
        await task_queue.enqueue_task(
            task_id, user_id, dummy_task, 
            cleanup_callbacks=[cleanup_callback]
        )
        
        # Wait for task to complete
        await asyncio.sleep(0.3)
        
        # Manually set completion time to past
        task_info = task_queue._tasks[task_id]
        task_info.completed_at = datetime.utcnow() - timedelta(hours=25)
        
        # Run cleanup
        cleaned_count = await task_queue.cleanup_completed_tasks(max_age_hours=24)
        
        assert cleaned_count == 1
        assert task_id not in task_queue._tasks
        assert cleanup_called is True
        
        # Verify cache cleanup calls
        mock_cache_manager.task_cache.delete_task_data.assert_called_with(task_id)
        mock_cache_manager.user_cache.remove_active_task.assert_called_with(user_id, task_id)
    
    async def test_priority_ordering(self, task_queue, mock_cache_manager):
        """Test that high priority tasks are processed first."""
        execution_order = []
        
        async def task_with_id(task_id):
            async def task_func(progress_tracker):
                execution_order.append(task_id)
                await asyncio.sleep(0.1)
            return task_func
        
        # Enqueue tasks with different priorities
        await task_queue.enqueue_task("low", "user-1", await task_with_id("low"), TaskPriority.LOW)
        await task_queue.enqueue_task("high", "user-1", await task_with_id("high"), TaskPriority.HIGH)
        await task_queue.enqueue_task("normal", "user-1", await task_with_id("normal"), TaskPriority.NORMAL)
        
        # Wait for all tasks to complete
        await asyncio.sleep(1.0)
        
        # High priority should be processed first
        assert execution_order[0] == "high"


class TestTaskProgressTracker:
    """Test cases for TaskProgressTracker class."""
    
    @pytest.fixture
    def mock_cache_manager(self):
        """Mock cache manager for testing."""
        with patch('app.services.task_queue.cache_manager') as mock:
            mock.task_cache.set_progress = AsyncMock()
            yield mock
    
    @pytest.fixture
    def task_info(self):
        """Create a task info for testing."""
        return TaskInfo(
            task_id="test-task",
            user_id="user-1",
            priority=TaskPriority.NORMAL,
            created_at=datetime.utcnow(),
            started_at=datetime.utcnow()
        )
    
    async def test_set_total_steps(self, task_info, mock_cache_manager):
        """Test setting total steps."""
        tracker = TaskProgressTracker("test-task", task_info)
        
        await tracker.set_total_steps(5)
        assert tracker._total_steps == 5
    
    async def test_start_step(self, task_info, mock_cache_manager):
        """Test starting a processing step."""
        tracker = TaskProgressTracker("test-task", task_info)
        await tracker.set_total_steps(3)
        
        await tracker.start_step(ProcessingStep.VALIDATION, "Validating video")
        
        assert task_info.current_step == ProcessingStep.VALIDATION
        assert tracker._step_start_time is not None
        
        # Verify cache call
        mock_cache_manager.task_cache.set_progress.assert_called_once()
        call_args = mock_cache_manager.task_cache.set_progress.call_args
        assert call_args[0][0] == "test-task"  # task_id
        assert call_args[0][2] == ProcessingStep.VALIDATION.value  # step
        assert call_args[0][3] == "Validating video"  # description
    
    async def test_complete_step(self, task_info, mock_cache_manager):
        """Test completing a processing step."""
        tracker = TaskProgressTracker("test-task", task_info)
        await tracker.set_total_steps(3)
        
        await tracker.start_step(ProcessingStep.VALIDATION)
        await tracker.complete_step()
        
        assert tracker._completed_steps == 1
        assert task_info.progress == 1.0 / 3.0  # 1 of 3 steps completed
    
    async def test_update_progress(self, task_info, mock_cache_manager):
        """Test updating progress within a step."""
        tracker = TaskProgressTracker("test-task", task_info)
        await tracker.set_total_steps(2)
        
        await tracker.start_step(ProcessingStep.VALIDATION)
        await tracker.update_progress(0.5, "Half way through validation")
        
        # Should be 0.5 * (1/2) = 0.25 total progress
        assert task_info.progress == 0.25
        
        # Verify cache call
        mock_cache_manager.task_cache.set_progress.assert_called()
    
    async def test_check_cancellation(self, task_info, mock_cache_manager):
        """Test cancellation checking."""
        tracker = TaskProgressTracker("test-task", task_info)
        
        # Should not raise when not cancelled
        tracker.check_cancellation()
        
        # Should raise when cancelled
        task_info.cancellation_requested = True
        with pytest.raises(asyncio.CancelledError):
            tracker.check_cancellation()


class TestTaskQueueLifespan:
    """Test cases for task queue lifespan management."""
    
    @pytest.fixture
    def mock_task_queue(self):
        """Mock task queue for testing."""
        with patch('app.services.task_queue.task_queue') as mock:
            mock.start = AsyncMock()
            mock.stop = AsyncMock()
            yield mock
    
    async def test_lifespan_context_manager(self, mock_task_queue):
        """Test task queue lifespan context manager."""
        async with task_queue_lifespan() as queue:
            assert queue == mock_task_queue
            mock_task_queue.start.assert_called_once()
        
        mock_task_queue.stop.assert_called_once()
    
    async def test_lifespan_exception_handling(self, mock_task_queue):
        """Test that task queue is stopped even if exception occurs."""
        with pytest.raises(ValueError):
            async with task_queue_lifespan():
                raise ValueError("Test error")
        
        mock_task_queue.stop.assert_called_once()


@pytest.mark.asyncio
async def test_integration_task_lifecycle():
    """Integration test for complete task lifecycle."""
    queue = TaskQueue(max_concurrent_tasks=1)
    
    try:
        await queue.start()
        
        task_id = "integration-test"
        user_id = "test-user"
        steps_completed = []
        
        async def integration_task(progress_tracker):
            await progress_tracker.set_total_steps(3)
            
            # Step 1
            await progress_tracker.start_step(ProcessingStep.VALIDATION, "Validating")
            await asyncio.sleep(0.1)
            steps_completed.append("validation")
            await progress_tracker.complete_step()
            
            # Step 2
            await progress_tracker.start_step(ProcessingStep.AUDIO_EXTRACTION, "Extracting audio")
            await asyncio.sleep(0.1)
            steps_completed.append("audio")
            await progress_tracker.complete_step()
            
            # Step 3
            await progress_tracker.start_step(ProcessingStep.SCENE_DETECTION, "Detecting scenes")
            await asyncio.sleep(0.1)
            steps_completed.append("scenes")
            await progress_tracker.complete_step()
        
        # Enqueue and wait for completion
        with patch('app.services.task_queue.cache_manager') as mock_cache:
            mock_cache.task_cache.set_status = AsyncMock()
            mock_cache.task_cache.set_progress = AsyncMock()
            mock_cache.user_cache.add_active_task = AsyncMock()
            
            await queue.enqueue_task(task_id, user_id, integration_task)
            
            # Wait for completion
            await asyncio.sleep(1.0)
            
            # Verify task completed successfully
            task_info = await queue.get_task_status(task_id)
            assert task_info.status == TaskStatus.COMPLETED
            assert task_info.progress == 1.0
            assert steps_completed == ["validation", "audio", "scenes"]
    
    finally:
        await queue.stop()