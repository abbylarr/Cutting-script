"""
Simple tests for task queue functionality.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.task_queue import TaskQueue, TaskInfo, TaskPriority, TaskProgressTracker
from app.schemas.processing_task import TaskStatus, ProcessingStep


@pytest.mark.asyncio
async def test_task_queue_basic_functionality():
    """Test basic task queue functionality."""
    
    # Mock cache manager
    with patch('app.services.task_queue.cache_manager') as mock_cache:
        mock_cache.task_cache.set_status = AsyncMock()
        mock_cache.task_cache.set_progress = AsyncMock()
        mock_cache.user_cache.add_active_task = AsyncMock()
        
        queue = TaskQueue(max_concurrent_tasks=1)
        
        try:
            await queue.start()
            
            # Test task enqueueing
            task_id = "test-task"
            user_id = "test-user"
            execution_log = []
            
            async def test_task(progress_tracker):
                execution_log.append("task_started")
                await progress_tracker.start_step(ProcessingStep.VALIDATION, "Testing")
                await asyncio.sleep(0.1)
                await progress_tracker.complete_step()
                execution_log.append("task_completed")
            
            # Enqueue task
            result = await queue.enqueue_task(task_id, user_id, test_task)
            assert result is True
            
            # Wait for task to complete
            await asyncio.sleep(0.5)
            
            # Check task status
            task_info = await queue.get_task_status(task_id)
            assert task_info is not None
            assert task_info.status == TaskStatus.COMPLETED
            assert execution_log == ["task_started", "task_completed"]
            
        finally:
            await queue.stop()


@pytest.mark.asyncio
async def test_progress_tracker_functionality():
    """Test progress tracker functionality."""
    
    with patch('app.services.task_queue.cache_manager') as mock_cache:
        mock_cache.task_cache.set_progress = AsyncMock()
        
        task_info = TaskInfo(
            task_id="test-task",
            user_id="test-user",
            priority=TaskPriority.NORMAL,
            created_at=datetime.utcnow()
        )
        
        tracker = TaskProgressTracker("test-task", task_info)
        
        # Test setting total steps
        await tracker.set_total_steps(3)
        assert tracker._total_steps == 3
        
        # Test starting a step
        await tracker.start_step(ProcessingStep.VALIDATION, "Validating")
        assert task_info.current_step == ProcessingStep.VALIDATION
        
        # Test completing a step
        await tracker.complete_step()
        assert tracker._completed_steps == 1
        
        # Test progress calculation
        expected_progress = 1.0 / 3.0  # 1 of 3 steps completed
        assert abs(task_info.progress - expected_progress) < 0.01
        
        # Verify cache calls were made
        mock_cache.task_cache.set_progress.assert_called()


@pytest.mark.asyncio
async def test_task_cancellation():
    """Test task cancellation functionality."""
    
    with patch('app.services.task_queue.cache_manager') as mock_cache:
        mock_cache.task_cache.set_status = AsyncMock()
        mock_cache.task_cache.set_error = AsyncMock()
        mock_cache.user_cache.add_active_task = AsyncMock()
        
        queue = TaskQueue(max_concurrent_tasks=1)
        
        try:
            await queue.start()
            
            task_id = "cancel-test"
            user_id = "test-user"
            
            async def long_running_task(progress_tracker):
                await asyncio.sleep(2.0)  # Long running task
            
            # Enqueue task
            await queue.enqueue_task(task_id, user_id, long_running_task)
            
            # Wait a bit for task to start
            await asyncio.sleep(0.1)
            
            # Cancel the task
            result = await queue.cancel_task(task_id)
            assert result is True
            
            # Wait for cancellation to take effect
            await asyncio.sleep(0.3)
            
            # Check task status
            task_info = await queue.get_task_status(task_id)
            assert task_info.status == TaskStatus.FAILED
            
        finally:
            await queue.stop()


@pytest.mark.asyncio
async def test_pipeline_orchestrator_basic():
    """Test basic pipeline orchestrator functionality."""
    
    from app.services.pipeline_orchestrator import ProcessingContext
    
    # Create a minimal context
    context = ProcessingContext(
        task_id="test-task",
        user_id="test-user",
        video_path="/path/to/video.mp4"
    )
    
    # Test context initialization
    assert context.task_id == "test-task"
    assert context.use_srt is False
    assert context.partial_results == {}
    
    # Test partial results
    context.save_partial_result("validation", {"test": "data"})
    result = context.get_partial_result("validation")
    assert result == {"test": "data"}
    
    # Test orchestrator initialization
    with patch.multiple(
        'app.services.pipeline_orchestrator',
        VideoValidationService=MagicMock,
        AudioExtractionService=MagicMock,
        SceneDetectionService=MagicMock,
        TranscriptionService=MagicMock,
        SpeakerDiarizationService=MagicMock,
        TextProcessingService=MagicMock,
        KeyframeExtractionService=MagicMock,
        GPTVisualAnalysisService=MagicMock,
        DialogueSceneMappingService=MagicMock,
        MusicDetectionService=MagicMock,
        MontageTableAssemblyService=MagicMock,
        DOCXGeneratorService=MagicMock
    ):
        from app.services.pipeline_orchestrator import PipelineOrchestrator
        orchestrator = PipelineOrchestrator()
        
        # Test step selection for normal mode
        steps = orchestrator._get_steps_for_context(context)
        assert len(steps) == len(orchestrator.processing_steps)
        
        # Test step selection for SRT mode
        context.use_srt = True
        srt_steps = orchestrator._get_steps_for_context(context)
        assert len(srt_steps) < len(steps)  # Should have fewer steps
        
        # Test ETA calculation
        from app.services.video_processor import VideoMetadata
        context.video_metadata = VideoMetadata(
            duration=120.0, fps=25.0, width=1920, height=1080,
            codec="h264", format="mp4"
        )
        
        eta = orchestrator._calculate_eta(context, ProcessingStep.VALIDATION)
        assert eta is not None
        assert eta >= 10  # Minimum ETA


if __name__ == "__main__":
    pytest.main([__file__])