"""
File upload endpoints for video and SRT files.
"""
import json
import logging
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status, Form
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.cache import check_upload_rate_limit
from app.core.config import settings
from app.db.base import get_db
from app.models.user import User
from app.models.processing_task import ProcessingTask
from app.models.film_project import FilmProject
from app.schemas.upload import (
    UploadResponse, SRTUploadResponse, UploadError,
)
from app.services.upload import upload_service
from app.services.billing import billing_service
from app.services.processing_runner import enqueue_video_processing
from app.services.task_queue import TaskPriority

logger = logging.getLogger(__name__)
router = APIRouter()


def _parse_json_form(raw: Optional[str], field_name: str) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("must be a JSON object")
        return data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name}: {e}",
        )


@router.post("/upload", response_model=UploadResponse)
async def upload_video(
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    settings_json: Optional[str] = Form(None, alias="settings"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload video file for processing.

    Accepts optional Form fields:
    - metadata: JSON FilmMetadata
    - settings: JSON {timecode_start, standard, use_srt, fps?}
    """
    rate_limit_result = await check_upload_rate_limit(str(current_user.id))
    if not rate_limit_result["allowed"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Upload rate limit exceeded. "
                f"Try again in {rate_limit_result['retry_after']} seconds"
            ),
        )

    validation_result = await upload_service.validate_video_file(file)
    if not validation_result.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=UploadError(
                error="Video validation failed",
                details=[
                    {"field": "file", "message": error, "code": "VALIDATION_ERROR"}
                    for error in validation_result.errors
                ],
                max_file_size=upload_service.MAX_VIDEO_SIZE,
                supported_formats=list(upload_service.SUPPORTED_VIDEO_FORMATS),
            ).dict(),
        )

    film_metadata = _parse_json_form(metadata, "metadata")
    project_settings = _parse_json_form(settings_json, "settings")
    use_srt = bool(project_settings.get("use_srt", False))

    estimated_duration = validation_result.duration or 0
    estimated_cost = float(
        billing_service.calculate_cost(estimated_duration / 60)
    )

    skip_billing = settings.SKIP_BILLING or settings.AUTONOMOUS_MODE
    if not skip_billing:
        if not billing_service.has_sufficient_balance(
            db, str(current_user.id), billing_service.calculate_cost(estimated_duration / 60)
        ):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=(
                    f"Insufficient balance. Required: {estimated_cost:.2f} rubles, "
                    f"Available: {current_user.balance:.2f} rubles"
                ),
            )

    try:
        file_path, file_hash = await upload_service.save_video_file(file, current_user.id)

        task = ProcessingTask(
            user_id=current_user.id,
            video_filename=file.filename or "video.mp4",
            video_path=file_path,
            file_hash=file_hash,
            estimated_cost=estimated_cost,
            use_srt=use_srt,
            status="pending",
            progress=0.0,
            current_step="queued",
        )
        db.add(task)
        db.flush()

        title = film_metadata.get("title") or (file.filename or "Без названия")
        if not film_metadata:
            film_metadata = {
                "title": title,
                "production_company": "Не указано",
                "year": 2024,
                "country": "Россия",
                "screenwriters": ["Не указано"],
                "copyright_holders": ["Не указано"],
                "duration": "00:00:00",
                "episodes_count": 1,
                "format": "Digital",
                "color_type": "Цветной",
                "media_carrier": "Файл",
                "original_language": "Русский",
                "audio_language": "Русский",
            }

        project = FilmProject(
            user_id=current_user.id,
            task_id=task.id,
            title=title,
            film_metadata=film_metadata,
            project_settings=project_settings or {
                "timecode_start": "01:00:00:00",
                "standard": "ГФФ",
                "fps": 25.0,
            },
        )
        db.add(project)
        db.commit()
        db.refresh(task)

        # If SRT mode — wait for SRT upload before starting pipeline
        if use_srt:
            logger.info(f"Task {task.id} created in SRT mode — waiting for subtitle upload")
        else:
            try:
                await enqueue_video_processing(
                    task_id=str(task.id),
                    user_id=str(current_user.id),
                    video_path=file_path,
                    use_srt=False,
                    film_metadata=film_metadata,
                    project_settings=project_settings,
                    priority=TaskPriority.NORMAL,
                )
                task.status = "processing"
                db.commit()
            except Exception as e:
                logger.error(f"Failed to enqueue task {task.id}: {e}")
                task.status = "failed"
                task.error_message = f"Failed to enqueue: {e}"
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to start processing: {e}",
                )

        return UploadResponse(
            task_id=task.id,
            filename=file.filename,
            file_size=validation_result.file_size,
            estimated_cost=estimated_cost,
            estimated_duration=estimated_duration / 60,
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {str(e)}",
        )


@router.post("/upload_srt/{task_id}", response_model=SRTUploadResponse)
async def upload_srt(
    task_id: UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload SRT and start (or re-start) processing in SRT mode."""
    task = db.query(ProcessingTask).filter(
        ProcessingTask.id == task_id,
        ProcessingTask.user_id == current_user.id,
    ).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing task not found",
        )

    validation_result = await upload_service.validate_srt_file(file)
    if not validation_result.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SRT validation failed: {validation_result.errors}",
        )

    try:
        srt_path = await upload_service.save_srt_file(file, current_user.id, task_id)
        task.srt_path = srt_path
        task.use_srt = True
        task.status = "processing"
        task.current_step = "queued"
        task.progress = 0.0
        db.commit()

        project = db.query(FilmProject).filter(FilmProject.task_id == task.id).first()
        film_metadata = project.film_metadata if project else None
        project_settings = project.project_settings if project else None

        await enqueue_video_processing(
            task_id=str(task.id),
            user_id=str(current_user.id),
            video_path=task.video_path,
            srt_path=srt_path,
            use_srt=True,
            film_metadata=film_metadata,
            project_settings=project_settings,
            priority=TaskPriority.HIGH,
        )

        return SRTUploadResponse(
            task_id=task.id,
            filename=file.filename or "subtitles.srt",
            scenes_updated=0,
            processing_mode="srt_mode",
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process SRT: {str(e)}",
        )
