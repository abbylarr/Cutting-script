"""
File upload-related Pydantic schemas for API validation.
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from uuid import UUID


class UploadResponse(BaseModel):
    task_id: UUID = Field(..., description="Task ID for tracking upload processing")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    estimated_cost: float = Field(..., description="Estimated processing cost in rubles")
    estimated_duration: float = Field(..., description="Estimated processing duration in minutes")


class SRTUploadResponse(BaseModel):
    task_id: UUID = Field(..., description="Task ID that was updated")
    filename: str = Field(..., description="SRT filename")
    scenes_updated: int = Field(..., description="Number of scenes updated with SRT data")
    processing_mode: str = Field("srt_mode", description="Processing mode after SRT upload")


class FileValidationError(BaseModel):
    field: str = Field(..., description="Field that failed validation")
    message: str = Field(..., description="Validation error message")
    code: str = Field(..., description="Error code")


class UploadError(BaseModel):
    error: str = Field(..., description="Error message")
    details: Optional[List[FileValidationError]] = None
    max_file_size: Optional[int] = Field(None, description="Maximum allowed file size in bytes")
    supported_formats: Optional[List[str]] = Field(None, description="List of supported file formats")


class VideoValidationResult(BaseModel):
    is_valid: bool = Field(..., description="Whether video file is valid")
    duration: Optional[float] = Field(None, description="Video duration in seconds")
    fps: Optional[float] = Field(None, description="Frames per second")
    resolution: Optional[str] = Field(None, description="Video resolution (e.g., 1920x1080)")
    codec: Optional[str] = Field(None, description="Video codec")
    file_size: int = Field(..., description="File size in bytes")
    errors: List[str] = Field([], description="List of validation errors if any")


class SRTValidationResult(BaseModel):
    is_valid: bool = Field(..., description="Whether SRT file is valid")
    subtitle_count: Optional[int] = Field(None, description="Number of subtitles found")
    duration: Optional[float] = Field(None, description="Total duration covered by subtitles")
    encoding: Optional[str] = Field(None, description="File encoding detected")
    errors: List[str] = Field([], description="List of validation errors if any")