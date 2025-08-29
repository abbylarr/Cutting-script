"""
Processing task-related Pydantic schemas for API validation.
"""
from typing import Optional, List, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import UUID
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingStep(str, Enum):
    VALIDATION = "video_validation"
    AUDIO_EXTRACTION = "audio_extraction"
    SCENE_DETECTION = "scene_detection"
    TRANSCRIPTION = "transcription"
    DIARIZATION = "speaker_diarization"
    TEXT_PROCESSING = "text_processing"
    FRAME_ANALYSIS = "frame_analysis"
    MONTAGE_GENERATION = "montage_generation"
    DOCUMENT_GENERATION = "document_generation"


class TaskCreate(BaseModel):
    video_filename: str = Field(..., description="Original filename of the uploaded video")
    use_srt: bool = Field(False, description="Whether to use SRT file instead of auto-transcription")


class TaskResponse(BaseModel):
    id: UUID
    user_id: UUID
    status: TaskStatus
    video_filename: str
    progress: float = Field(..., ge=0.0, le=1.0, description="Progress from 0.0 to 1.0")
    current_step: Optional[ProcessingStep] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskStatusResponse(BaseModel):
    id: UUID
    status: TaskStatus
    progress: float = Field(..., ge=0.0, le=1.0)
    current_step: Optional[ProcessingStep] = None
    current_step_description: Optional[str] = None
    eta_seconds: Optional[int] = None
    error_message: Optional[str] = None
    result: Optional[List[Dict[str, Any]]] = None  # Montage rows when completed


class TaskProgressUpdate(BaseModel):
    progress: float = Field(..., ge=0.0, le=1.0)
    current_step: ProcessingStep
    step_description: Optional[str] = None
    eta_seconds: Optional[int] = None


class TaskError(BaseModel):
    task_id: UUID
    error_message: str
    error_code: Optional[str] = None
    step: Optional[ProcessingStep] = None