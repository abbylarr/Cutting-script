"""
Film project-related Pydantic schemas for API validation.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import UUID
from enum import Enum


class TimecodeStandard(str, Enum):
    GFF = "ГФФ"
    KRASNOGORSKY = "Красногорский"


class ShotType(str, Enum):
    DISTANT = "Дальний"
    GENERAL = "Общий"
    MEDIUM = "Средний"
    CLOSE = "Крупный"
    DETAIL = "Деталь"


class ColorType(str, Enum):
    COLOR = "Цветной"
    BLACK_WHITE = "Черно-белый"


class FilmMetadata(BaseModel):
    title: str = Field(..., description="Film title")
    production_company: str = Field(..., description="Production company name")
    year: int = Field(..., ge=1900, le=2100, description="Production year")
    country: str = Field(..., description="Country of production")
    screenwriters: List[str] = Field(..., description="List of screenwriters")
    copyright_holders: List[str] = Field(..., description="List of copyright holders")
    duration: str = Field(..., description="Film duration in HH:MM:SS format")
    episodes_count: int = Field(1, ge=1, description="Number of episodes")
    format: str = Field(..., description="Film format (e.g., 35mm, Digital)")
    color_type: ColorType = Field(..., description="Color type")
    media_carrier: str = Field(..., description="Media carrier type")
    original_language: str = Field("Русский", description="Original language")
    subtitle_language: Optional[str] = Field(None, description="Subtitle language")
    audio_language: str = Field("Русский", description="Audio language")


class ProjectSettings(BaseModel):
    timecode_start: str = Field("01:00:00:00", pattern=r"^\d{2}:\d{2}:\d{2}:\d{2}$", 
                               description="Timecode start point")
    standard: TimecodeStandard = Field(TimecodeStandard.GFF, description="Timecode standard")
    fps: float = Field(25.0, gt=0, description="Frame rate for timecode calculations")


class MontageRow(BaseModel):
    number: int = Field(..., ge=1, description="Row number in montage table")
    start_timecode: str = Field(..., pattern=r"^\d{2}:\d{2}:\d{2}:\d{2}$", 
                               description="Start timecode in HH:MM:SS:FF format")
    end_timecode: str = Field(..., pattern=r"^\d{2}:\d{2}:\d{2}:\d{2}$", 
                             description="End timecode in HH:MM:SS:FF format")
    shot_type: ShotType = Field(..., description="Type of shot/plan")
    description: str = Field(..., description="Scene description")
    dialogue: str = Field("", description="Dialogue or text in scene")
    speaker: Optional[str] = Field(None, description="Speaker name if applicable")
    has_music: bool = Field(False, description="Whether scene contains music")
    special_tags: List[str] = Field([], description="Special tags like ЗТМ, НДП, ГЗК")


class ProjectCreate(BaseModel):
    title: str = Field(..., description="Project title")
    film_metadata: FilmMetadata
    project_settings: Optional[ProjectSettings] = None


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    film_metadata: Optional[FilmMetadata] = None
    project_settings: Optional[ProjectSettings] = None
    montage_rows: Optional[List[MontageRow]] = None


class ProjectResponse(BaseModel):
    id: UUID
    user_id: UUID
    task_id: UUID
    title: str
    film_metadata: FilmMetadata
    project_settings: Optional[ProjectSettings] = None
    montage_rows: Optional[List[MontageRow]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    status: str  # Based on associated task status

    class Config:
        from_attributes = True


class MontageUpdateRequest(BaseModel):
    rows: List[MontageRow] = Field(..., description="Updated montage rows")


class SaveProjectRequest(BaseModel):
    montage_rows: List[MontageRow] = Field(..., description="Montage rows to save")
    regenerate_docx: bool = Field(True, description="Whether to regenerate DOCX file")