"""
Example of using the task queue and pipeline orchestrator together.
"""
import asyncio
import logging
from pathlib import Path

from app.services.task_queue import task_queue, TaskPriority
from app.services.pipeline_orchestrator import ProcessingContext, get_pipeline_orchestrator

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_video_processing_task(progress_tracker):
    """
    Example task that uses the pipeline orchestrator to process a video.
    """
    logger.info("Starting video processing task")
    
    # Create processing context
    context = ProcessingContext(
        task_id=progress_tracker.task_id,
        user_id=progress_tracker.task_info.user_id,
        video_path="/path/to/example_video.mp4",
        use_srt=False  # Use auto-transcription mode
    )
    
    # Get pipeline orchestrator
    orchestrator = get_pipeline_orchestrator()
    
    try:
        # Process video through the pipeline
        result_context = await orchestrator.process_video(progress_tracker, context)
        
        logger.info(f"Video processing completed successfully!")
        logger.info(f"Generated document: {result_context.docx_path}")
        
        return {
            "status": "completed",
            "docx_path": result_context.docx_path,
            "montage_rows": len(result_context.montage_rows) if result_context.montage_rows else 0
        }
        
    except Exception as e:
        logger.error(f"Video processing failed: {e}")
        raise


async def example_srt_processing_task(progress_tracker):
    """
    Example task that processes video with SRT file.
    """
    logger.info("Starting SRT-based video processing task")
    
    # Create processing context for SRT mode
    context = ProcessingContext(
        task_id=progress_tracker.task_id,
        user_id=progress_tracker.task_info.user_id,
        video_path="/path/to/example_video.mp4",
        srt_path="/path/to/subtitles.srt",
        use_srt=True  # Use SRT mode
    )
    
    # Get pipeline orchestrator
    orchestrator = get_pipeline_orchestrator()
    
    try:
        # Process video through the pipeline
        result_context = await orchestrator.process_video(progress_tracker, context)
        
        logger.info(f"SRT-based processing completed successfully!")
        logger.info(f"Generated document: {result_context.docx_path}")
        
        return {
            "status": "completed",
            "docx_path": result_context.docx_path,
            "montage_rows": len(result_context.montage_rows) if result_context.montage_rows else 0
        }
        
    except Exception as e:
        logger.error(f"SRT-based processing failed: {e}")
        raise


async def main():
    """
    Main example function demonstrating task queue usage.
    """
    logger.info("Starting task processing example")
    
    try:
        # Start the task queue
        await task_queue.start()
        
        # Enqueue a normal video processing task
        task_id_1 = "example-video-task-1"
        user_id = "example-user"
        
        success = await task_queue.enqueue_task(
            task_id=task_id_1,
            user_id=user_id,
            task_func=example_video_processing_task,
            priority=TaskPriority.HIGH
        )
        
        if success:
            logger.info(f"Enqueued video processing task: {task_id_1}")
        else:
            logger.error(f"Failed to enqueue task: {task_id_1}")
        
        # Enqueue an SRT-based processing task
        task_id_2 = "example-srt-task-1"
        
        success = await task_queue.enqueue_task(
            task_id=task_id_2,
            user_id=user_id,
            task_func=example_srt_processing_task,
            priority=TaskPriority.NORMAL
        )
        
        if success:
            logger.info(f"Enqueued SRT processing task: {task_id_2}")
        else:
            logger.error(f"Failed to enqueue task: {task_id_2}")
        
        # Monitor task progress
        await monitor_tasks([task_id_1, task_id_2])
        
    except Exception as e:
        logger.error(f"Example failed: {e}")
    
    finally:
        # Stop the task queue
        await task_queue.stop()
        logger.info("Task processing example completed")


async def monitor_tasks(task_ids):
    """
    Monitor the progress of tasks until they complete.
    """
    logger.info(f"Monitoring tasks: {task_ids}")
    
    completed_tasks = set()
    
    while len(completed_tasks) < len(task_ids):
        for task_id in task_ids:
            if task_id in completed_tasks:
                continue
            
            task_info = await task_queue.get_task_status(task_id)
            if task_info:
                logger.info(f"Task {task_id}: {task_info.status.value} - Progress: {task_info.progress:.2f}")
                
                if task_info.status.value in ["completed", "failed"]:
                    completed_tasks.add(task_id)
                    logger.info(f"Task {task_id} finished with status: {task_info.status.value}")
                    
                    if task_info.error_message:
                        logger.error(f"Task {task_id} error: {task_info.error_message}")
        
        # Wait before checking again
        await asyncio.sleep(2.0)
    
    logger.info("All tasks completed")


async def example_task_cancellation():
    """
    Example of task cancellation functionality.
    """
    logger.info("Starting task cancellation example")
    
    try:
        await task_queue.start()
        
        # Create a long-running task
        async def long_running_task(progress_tracker):
            await progress_tracker.start_step("processing", "Long running operation")
            await asyncio.sleep(10.0)  # Simulate long operation
            await progress_tracker.complete_step()
        
        task_id = "cancellation-example"
        user_id = "example-user"
        
        # Enqueue the task
        await task_queue.enqueue_task(task_id, user_id, long_running_task)
        logger.info(f"Enqueued long-running task: {task_id}")
        
        # Wait a bit for task to start
        await asyncio.sleep(1.0)
        
        # Cancel the task
        cancelled = await task_queue.cancel_task(task_id)
        if cancelled:
            logger.info(f"Successfully cancelled task: {task_id}")
        else:
            logger.error(f"Failed to cancel task: {task_id}")
        
        # Wait for cancellation to take effect
        await asyncio.sleep(2.0)
        
        # Check final status
        task_info = await task_queue.get_task_status(task_id)
        if task_info:
            logger.info(f"Final task status: {task_info.status.value}")
    
    finally:
        await task_queue.stop()


if __name__ == "__main__":
    # Run the main example
    asyncio.run(main())
    
    # Uncomment to run cancellation example
    # asyncio.run(example_task_cancellation())