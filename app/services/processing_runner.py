"""
Wires upload → task queue → pipeline → DB persistence.
"""
import logging
from typing import Any, Dict, Optional
from uuid import UUID

from app.db.base import SessionLocal
from app.models.processing_task import ProcessingTask
from app.models.film_project import FilmProject
from app.services.task_queue import task_queue, TaskPriority, TaskProgressTracker
from app.services.pipeline_orchestrator import (
    ProcessingContext,
    get_pipeline_orchestrator,
)
from app.schemas.film_project import MontageRow

logger = logging.getLogger(__name__)


def _serialize_montage_rows(rows) -> list:
    serialized = []
    for row in rows or []:
        if isinstance(row, MontageRow):
            serialized.append(row.model_dump() if hasattr(row, "model_dump") else row.dict())
        elif hasattr(row, "model_dump"):
            serialized.append(row.model_dump())
        elif hasattr(row, "dict"):
            serialized.append(row.dict())
        elif isinstance(row, dict):
            serialized.append(row)
        else:
            serialized.append(dict(row))
    return serialized


def _persist_progress(task_id: str, progress: float, current_step: Optional[str], status: str):
    db = SessionLocal()
    try:
        task = db.query(ProcessingTask).filter(ProcessingTask.id == UUID(str(task_id))).first()
        if not task:
            return
        task.progress = progress
        task.status = status
        if current_step:
            task.current_step = current_step
        db.commit()
    except Exception as e:
        logger.warning(f"Failed to persist progress for {task_id}: {e}")
        db.rollback()
    finally:
        db.close()


def _persist_success(task_id: str, montage_rows, docx_path: Optional[str]):
    db = SessionLocal()
    try:
        task = db.query(ProcessingTask).filter(ProcessingTask.id == UUID(str(task_id))).first()
        if not task:
            return
        rows_data = _serialize_montage_rows(montage_rows)
        task.status = "completed"
        task.progress = 1.0
        task.current_step = "completed"
        task.result = rows_data
        task.error_message = None

        project = db.query(FilmProject).filter(FilmProject.task_id == task.id).first()
        if project:
            project.montage_rows = rows_data

        db.commit()
        logger.info(f"Persisted completed task {task_id}, docx={docx_path}")
    except Exception as e:
        logger.error(f"Failed to persist success for {task_id}: {e}")
        db.rollback()
    finally:
        db.close()


def _persist_failure(task_id: str, error_message: str):
    db = SessionLocal()
    try:
        task = db.query(ProcessingTask).filter(ProcessingTask.id == UUID(str(task_id))).first()
        if not task:
            return
        task.status = "failed"
        task.error_message = error_message[:2000]
        db.commit()
    except Exception as e:
        logger.error(f"Failed to persist failure for {task_id}: {e}")
        db.rollback()
    finally:
        db.close()


async def run_processing_job(
    progress_tracker: TaskProgressTracker,
    *,
    task_id: str,
    user_id: str,
    video_path: str,
    srt_path: Optional[str] = None,
    use_srt: bool = False,
    film_metadata: Optional[Dict[str, Any]] = None,
    project_settings: Optional[Dict[str, Any]] = None,
):
    """Task queue entrypoint: run pipeline and persist results."""
    _persist_progress(task_id, 0.0, "starting", "processing")

    context = ProcessingContext(
        task_id=str(task_id),
        user_id=str(user_id),
        video_path=video_path,
        srt_path=srt_path,
        use_srt=use_srt,
        film_metadata=film_metadata,
        project_settings=project_settings,
        timecode_start=(project_settings or {}).get("timecode_start", "01:00:00:00"),
        standard=(project_settings or {}).get("standard", "ГФФ"),
    )

    orchestrator = get_pipeline_orchestrator()

    # Sync progress to DB periodically via wrapping updates
    original_update = progress_tracker.update_progress
    original_start = progress_tracker.start_step
    original_complete = progress_tracker.complete_step

    async def update_progress_wrapped(progress: float, description: Optional[str] = None):
        await original_update(progress, description)
        step = (
            progress_tracker.task_info.current_step.value
            if progress_tracker.task_info.current_step
            else None
        )
        _persist_progress(task_id, progress_tracker.task_info.progress, step, "processing")

    async def start_step_wrapped(step, description=None):
        await original_start(step, description)
        _persist_progress(
            task_id,
            progress_tracker.task_info.progress,
            step.value if hasattr(step, "value") else str(step),
            "processing",
        )

    async def complete_step_wrapped():
        await original_complete()
        step = (
            progress_tracker.task_info.current_step.value
            if progress_tracker.task_info.current_step
            else None
        )
        _persist_progress(task_id, progress_tracker.task_info.progress, step, "processing")

    progress_tracker.update_progress = update_progress_wrapped
    progress_tracker.start_step = start_step_wrapped
    progress_tracker.complete_step = complete_step_wrapped

    try:
        result = await orchestrator.process_video(progress_tracker, context)
        _persist_success(task_id, result.montage_rows, result.docx_path)
        return {
            "status": "completed",
            "docx_path": result.docx_path,
            "montage_rows": len(result.montage_rows or []),
        }
    except Exception as e:
        logger.exception(f"Processing job failed for {task_id}")
        _persist_failure(task_id, str(e))
        raise


async def enqueue_video_processing(
    *,
    task_id: str,
    user_id: str,
    video_path: str,
    srt_path: Optional[str] = None,
    use_srt: bool = False,
    film_metadata: Optional[Dict[str, Any]] = None,
    project_settings: Optional[Dict[str, Any]] = None,
    priority: TaskPriority = TaskPriority.NORMAL,
) -> bool:
    """Enqueue a video processing job."""

    async def _job(progress_tracker: TaskProgressTracker):
        return await run_processing_job(
            progress_tracker,
            task_id=str(task_id),
            user_id=str(user_id),
            video_path=video_path,
            srt_path=srt_path,
            use_srt=use_srt,
            film_metadata=film_metadata,
            project_settings=project_settings,
        )

    return await task_queue.enqueue_task(
        task_id=str(task_id),
        user_id=str(user_id),
        task_func=_job,
        priority=priority,
    )
