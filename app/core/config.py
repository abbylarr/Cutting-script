"""
Configuration settings for the filmlist application.
"""
import os
from typing import List, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Filmlist"
    
    # Database Configuration
    DATABASE_URL: str = "postgresql://filmlist:filmlist@localhost/filmlist"
    
    # Redis Configuration
    REDIS_URL: str = "redis://localhost:6379"
    
    # External API Keys
    OPENAI_API_KEY: str
    HF_TOKEN: Optional[str] = None
    
    # File Storage
    UPLOAD_DIR: str = "uploads"
    OUTPUT_DIR: str = "output"
    MAX_FILE_SIZE: int = 5 * 1024 * 1024 * 1024  # 5GB
    
    # Processing Configuration
    RATE_PER_MINUTE: float = 75.0  # рублей за минуту
    MIN_SCENE_LENGTH: float = 2.0  # минимальная длительность сцены в секундах
    
    # CORS Configuration
    BACKEND_CORS_ORIGINS: Optional[List[str]] = ["http://localhost:3000", "http://localhost:8000"]
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    
    # Development Configuration
    DEBUG: bool = False
    RELOAD: bool = False
    
    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v):
        if v is None:
            return ["http://localhost:3000", "http://localhost:8000"]
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()