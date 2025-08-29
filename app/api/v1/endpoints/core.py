"""
Core API endpoints for task status, montage updates, and file downloads.
"""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
import os
import json

from app.core.auth import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.models.processing_task import ProcessingTask
from app.models.film_project import FilmProject
from app.schemas.processing_task import TaskStatusResponse, ProcessingStep
from app.schemas.film_project import MontageRow, MontageUpdateRequest, SaveProjectRequest
from app.schemas.common import SuccessResponse
from app.services.docx_generator import docx_generator

router = APIRouter()


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed status information for a processing task.
    
    - **task_id**: ID of the processing task
    - Returns current status, progress, and results if completed
    """
    # Get processing task and verify ownership
    task = db.query(ProcessingTask).filter(
        ProcessingTask.id == task_id,
        ProcessingTask.user_id == current_user.id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing task not found"
        )
    
    # Get step description based on current step
    step_descriptions = {
        ProcessingStep.VALIDATION: "Проверка видеофайла и извлечение метаданных",
        ProcessingStep.AUDIO_EXTRACTION: "Извлечение аудиодорожки из видео",
        ProcessingStep.SCENE_DETECTION: "Определение границ сцен в видео",
        ProcessingStep.TRANSCRIPTION: "Транскрипция речи с помощью AI",
        ProcessingStep.DIARIZATION: "Определение говорящих в аудио",
        ProcessingStep.TEXT_PROCESSING: "Обработка и коррекция текста",
        ProcessingStep.FRAME_ANALYSIS: "Анализ ключевых кадров с помощью AI",
        ProcessingStep.MONTAGE_GENERATION: "Создание монтажной таблицы",
        ProcessingStep.DOCUMENT_GENERATION: "Генерация DOCX документа"
    }
    
    current_step_description = None
    if task.current_step:
        try:
            step_enum = ProcessingStep(task.current_step)
            current_step_description = step_descriptions.get(step_enum)
        except ValueError:
            current_step_description = task.current_step
    
    # Calculate ETA based on progress and typical processing times
    eta_seconds = None
    if task.status == "processing" and task.progress > 0:
        # Rough estimate: 2-5 minutes per minute of video
        estimated_total_time = 180  # 3 minutes average
        elapsed_ratio = task.progress
        if elapsed_ratio > 0:
            remaining_ratio = 1.0 - elapsed_ratio
            eta_seconds = int(estimated_total_time * remaining_ratio)
    
    # Parse result if available
    result = None
    if task.result and task.status == "completed":
        if isinstance(task.result, str):
            try:
                result = json.loads(task.result)
            except json.JSONDecodeError:
                result = None
        else:
            result = task.result
    
    return TaskStatusResponse(
        id=task.id,
        status=task.status,
        progress=task.progress,
        current_step=ProcessingStep(task.current_step) if task.current_step else None,
        current_step_description=current_step_description,
        eta_seconds=eta_seconds,
        error_message=task.error_message,
        result=result
    )


@router.patch("/montage/{task_id}", response_model=SuccessResponse)
async def update_montage_rows(
    task_id: UUID,
    update_request: MontageUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update montage rows for a completed processing task.
    
    - **task_id**: ID of the processing task
    - **rows**: Updated montage rows
    - Returns success confirmation and regenerates DOCX
    """
    # Get processing task and verify ownership
    task = db.query(ProcessingTask).filter(
        ProcessingTask.id == task_id,
        ProcessingTask.user_id == current_user.id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing task not found"
        )
    
    if task.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot update montage for task in status: {task.status}"
        )
    
    # Validate montage rows
    try:
        # Convert Pydantic models to dict for storage
        rows_data = [row.dict() for row in update_request.rows]
        
        # Validate row numbering and timecode continuity
        for i, row in enumerate(rows_data):
            if row["number"] != i + 1:
                raise ValueError(f"Row {i + 1} has incorrect number: {row['number']}")
        
        # Update task result
        task.result = rows_data
        task.updated_at = func.now()
        
        # Update or create film project
        film_project = db.query(FilmProject).filter(
            FilmProject.task_id == task_id
        ).first()
        
        if film_project:
            film_project.montage_rows = rows_data
            film_project.updated_at = func.now()
        
        db.commit()
        
        # Regenerate DOCX file in background
        try:
            if film_project and film_project.film_metadata:
                await docx_generator.generate_docx_for_task(task_id, rows_data, film_project.film_metadata)
        except Exception as e:
            # Log error but don't fail the update
            print(f"Warning: Failed to regenerate DOCX for task {task_id}: {e}")
        
        return SuccessResponse(
            message=f"Successfully updated {len(rows_data)} montage rows",
            data={"rows_updated": len(rows_data)}
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update montage rows: {str(e)}"
        )


@router.get("/download/{task_id}")
async def download_docx(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Download the generated DOCX file for a completed processing task.
    
    - **task_id**: ID of the processing task
    - Returns DOCX file as download
    """
    # Get processing task and verify ownership
    task = db.query(ProcessingTask).filter(
        ProcessingTask.id == task_id,
        ProcessingTask.user_id == current_user.id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing task not found"
        )
    
    if task.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot download file for task in status: {task.status}"
        )
    
    # Get film project for metadata
    film_project = db.query(FilmProject).filter(
        FilmProject.task_id == task_id
    ).first()
    
    if not film_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Film project not found for this task"
        )
    
    # Check if DOCX file exists
    docx_filename = f"montage_list_{task_id}.docx"
    docx_path = os.path.join("output", str(current_user.id), docx_filename)
    
    if not os.path.exists(docx_path):
        # Generate DOCX file if it doesn't exist
        try:
            montage_rows = task.result or []
            if isinstance(montage_rows, str):
                montage_rows = json.loads(montage_rows)
            
            docx_path = await docx_generator.generate_docx_for_task(
                task_id, 
                montage_rows, 
                film_project.film_metadata
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate DOCX file: {str(e)}"
            )
    
    # Return file as download
    return FileResponse(
        path=docx_path,
        filename=f"{film_project.title}_montage_list.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )