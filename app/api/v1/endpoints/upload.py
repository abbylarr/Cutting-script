"""
File upload endpoints for video and SRT files.
"""
from typing import Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.cache import check_upload_rate_limit
from app.db.base import get_db
from app.models.user import User
from app.models.processing_task import ProcessingTask
from app.schemas.upload import (
    UploadResponse, SRTUploadResponse, UploadError, 
    VideoValidationResult, SRTValidationResult
)
from app.services.upload import upload_service
from app.services.billing import billing_service

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload_video(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload video file for processing.
    
    - **file**: Video file to upload (MP4, AVI, MOV, MKV, etc.)
    - Returns task_id for tracking processing status
    """
    # Check upload rate limit
    rate_limit_result = await check_upload_rate_limit(str(current_user.id))
    if not rate_limit_result["allowed"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Upload rate limit exceeded. Try again in {rate_limit_result['retry_after']} seconds"
        )
    
    # Validate video file
    validation_result = await upload_service.validate_video_file(file)
    
    if not validation_result.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=UploadError(
                error="Video validation failed",
                details=[{"field": "file", "message": error, "code": "VALIDATION_ERROR"} 
                        for error in validation_result.errors],
                max_file_size=upload_service.MAX_VIDEO_SIZE,
                supported_formats=list(upload_service.SUPPORTED_VIDEO_FORMATS)
            ).dict()
        )
    
    # Calculate estimated cost and check user balance
    estimated_duration = validation_result.duration or 0
    estimated_cost = await billing_service.calculate_cost(estimated_duration / 60)  # Convert to minutes
    
    if not await billing_service.has_sufficient_balance(current_user.id, estimated_cost):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient balance. Required: {estimated_cost:.2f} rubles, Available: {current_user.balance:.2f} rubles"
        )
    
    try:
        # Save video file with user isolation
        file_path, file_hash = await upload_service.save_video_file(file, current_user.id)
        
        # Create processing task
        task = ProcessingTask(
            user_id=current_user.id,
            video_filename=file.filename,
            video_path=file_path,
            file_hash=file_hash,
            estimated_cost=estimated_cost,
            status="pending"
        )
        
        db.add(task)
        db.commit()
        db.refresh(task)
        
        return UploadResponse(
            task_id=task.id,
            filename=file.filename,
            file_size=validation_result.file_size,
            estimated_cost=estimated_cost,
            estimated_duration=estimated_duration / 60  # Convert to minutes
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {str(e)}"
        )


@router.post("/upload_srt/{task_id}", response_model=SRTUploadResponse)
async def upload_srt(
    task_id: UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload SRT file for existing processing task.
    
    - **task_id**: ID of the processing task to update
    - **file**: SRT subtitle file
    - Returns updated task information
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
    
    if task.status not in ["pending", "completed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot upload SRT for task in status: {task.status}"
        )
    
    # Validate SRT file
    validation_result = await upload_service.validate_srt_file(file)
    
    if not validation_result.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=UploadError(
                error="SRT validation failed",
                details=[{"field": "file", "message": error, "code": "VALIDATION_ERROR"} 
                        for error in validation_result.errors]
            ).dict()
        )
    
    try:
        # Save SRT file
        srt_path = await upload_service.save_srt_file(file, current_user.id, task_id)
        
        # Process SRT with video to create scene mapping
        from app.services.upload import srt_processor
        processing_result = await srt_processor.process_srt_with_video(srt_path, task.video_path)
        
        # Update task with SRT information and processing results
        task.srt_path = srt_path
        task.use_srt = True
        task.status = "completed"  # Mark as completed since SRT processing is done
        task.result = processing_result  # Store the processed scenes
        task.progress = 1.0
        task.current_step = "SRT processing completed"
        
        db.commit()
        
        return SRTUploadResponse(
            task_id=task.id,
            filename=file.filename,
            scenes_updated=len(processing_result.get('scenes', [])),
            processing_mode="srt_mode"
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save SRT file: {str(e)}"
        )


@router.get("/validate/video")
async def validate_video_endpoint(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
) -> VideoValidationResult:
    """
    Validate video file without uploading.
    
    - **file**: Video file to validate
    - Returns validation result with metadata
    """
    return await upload_service.validate_video_file(file)


@router.get("/validate/srt")
async def validate_srt_endpoint(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
) -> SRTValidationResult:
    """
    Validate SRT file without uploading.
    
    - **file**: SRT file to validate
    - Returns validation result with subtitle information
    """
    return await upload_service.validate_srt_file(file)


@router.get("/limits")
async def get_upload_limits(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get upload limits and supported formats for current user.
    """
    rate_limit_result = await check_upload_rate_limit(str(current_user.id))
    
    return {
        "max_video_size": upload_service.MAX_VIDEO_SIZE,
        "max_srt_size": upload_service.MAX_SRT_SIZE,
        "supported_video_formats": list(upload_service.SUPPORTED_VIDEO_FORMATS),
        "supported_srt_formats": list(upload_service.SUPPORTED_SRT_FORMATS),
        "rate_limit": {
            "allowed": rate_limit_result["allowed"],
            "remaining": rate_limit_result.get("remaining", 0),
            "retry_after": rate_limit_result.get("retry_after", 0)
        }
    }