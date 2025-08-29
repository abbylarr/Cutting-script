# Developer Guide - Filmlist

Руководство для разработчиков по расширению и поддержке системы Filmlist.

## 📋 Содержание

- [Архитектура системы](#архитектура-системы)
- [Добавление новых функций](#добавление-новых-функций)
- [Работа с пайплайном обработки](#работа-с-пайплайном-обработки)
- [API разработка](#api-разработка)
- [База данных](#база-данных)
- [Тестирование](#тестирование)
- [Развертывание](#развертывание)
- [Лучшие практики](#лучшие-практики)

## 🏗 Архитектура системы

### Общая архитектура

Filmlist построен по принципу микросервисной архитектуры с четким разделением ответственности:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   API Gateway   │    │   Processing    │
│   (React)       │◄──►│   (FastAPI)     │◄──►│   Pipeline      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Database      │    │   External      │
                       │   (PostgreSQL)  │    │   Services      │
                       └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Cache         │    │   File Storage  │
                       │   (Redis)       │    │   (Local/S3)    │
                       └─────────────────┘    └─────────────────┘
```

### Ключевые компоненты

#### 1. API Gateway (`app/main.py`)
- Центральная точка входа для всех HTTP запросов
- Маршрутизация к соответствующим эндпоинтам
- Middleware для аутентификации, CORS, логирования
- Обработка ошибок и валидация

#### 2. Processing Pipeline (`app/services/`)
- Асинхронная обработка видеофайлов
- Модульная архитектура с возможностью замены компонентов
- Отслеживание прогресса и обработка ошибок
- Fallback механизмы для внешних сервисов

#### 3. Data Layer (`app/models/`, `app/db/`)
- SQLAlchemy ORM для работы с PostgreSQL
- Миграции через Alembic
- Кэширование через Redis
- Типизированные схемы данных

## 🔧 Добавление новых функций

### 1. Создание нового API эндпоинта

#### Шаг 1: Создайте Pydantic схему
```python
# app/schemas/new_feature.py
from pydantic import BaseModel
from typing import Optional

class NewFeatureRequest(BaseModel):
    name: str
    description: Optional[str] = None
    
class NewFeatureResponse(BaseModel):
    id: str
    name: str
    status: str
```

#### Шаг 2: Создайте модель базы данных
```python
# app/models/new_feature.py
from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
import uuid

class NewFeature(Base):
    __tablename__ = "new_features"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
```

#### Шаг 3: Создайте сервис
```python
# app/services/new_feature.py
from typing import List, Optional
from app.models.new_feature import NewFeature
from app.schemas.new_feature import NewFeatureRequest
from sqlalchemy.orm import Session

class NewFeatureService:
    def __init__(self, db: Session):
        self.db = db
    
    async def create_feature(self, request: NewFeatureRequest) -> NewFeature:
        feature = NewFeature(
            name=request.name,
            description=request.description
        )
        self.db.add(feature)
        self.db.commit()
        self.db.refresh(feature)
        return feature
    
    async def get_features(self) -> List[NewFeature]:
        return self.db.query(NewFeature).all()
```

#### Шаг 4: Создайте эндпоинт
```python
# app/api/v1/endpoints/new_feature.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.services.new_feature import NewFeatureService
from app.schemas.new_feature import NewFeatureRequest, NewFeatureResponse

router = APIRouter()

@router.post("/", response_model=NewFeatureResponse)
async def create_feature(
    request: NewFeatureRequest,
    db: Session = Depends(get_db)
):
    service = NewFeatureService(db)
    feature = await service.create_feature(request)
    return NewFeatureResponse(
        id=str(feature.id),
        name=feature.name,
        status="created"
    )

@router.get("/", response_model=List[NewFeatureResponse])
async def get_features(db: Session = Depends(get_db)):
    service = NewFeatureService(db)
    features = await service.get_features()
    return [
        NewFeatureResponse(
            id=str(f.id),
            name=f.name,
            status="active"
        ) for f in features
    ]
```

#### Шаг 5: Зарегистрируйте роутер
```python
# app/api/v1/api.py
from app.api.v1.endpoints import new_feature

api_router.include_router(
    new_feature.router, 
    prefix="/new-feature", 
    tags=["new-feature"]
)
```

### 2. Создание миграции базы данных

```bash
# Создайте миграцию
alembic revision --autogenerate -m "Add new_feature table"

# Примените миграцию
alembic upgrade head
```

### 3. Добавление тестов

```python
# tests/test_new_feature.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_feature():
    response = client.post(
        "/api/v1/new-feature/",
        json={"name": "Test Feature", "description": "Test description"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Feature"
    assert data["status"] == "created"

def test_get_features():
    response = client.get("/api/v1/new-feature/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

## 🎬 Работа с пайплайном обработки

### Архитектура пайплайна

Пайплайн обработки состоит из последовательных этапов:

```python
# app/services/pipeline_orchestrator.py
class ProcessingPipeline:
    def __init__(self):
        self.steps = [
            VideoValidationStep(),
            AudioExtractionStep(),
            SceneDetectionStep(),
            TranscriptionStep(),
            DiarizationStep(),
            TextProcessingStep(),
            KeyframeExtractionStep(),
            VisualAnalysisStep(),
            MontageTableGenerationStep(),
            DocumentGenerationStep()
        ]
    
    async def process(self, task_id: str, video_path: str) -> ProcessingResult:
        context = ProcessingContext(task_id=task_id, video_path=video_path)
        
        for step in self.steps:
            try:
                context = await step.execute(context)
                await self.update_progress(task_id, step.name, step.progress)
            except Exception as e:
                await self.handle_error(task_id, step.name, e)
                raise
        
        return context.result
```

### Добавление нового этапа обработки

#### 1. Создайте базовый класс этапа
```python
# app/services/processing/base_step.py
from abc import ABC, abstractmethod
from typing import Any

class ProcessingStep(ABC):
    def __init__(self, name: str):
        self.name = name
        self.progress = 0.0
    
    @abstractmethod
    async def execute(self, context: ProcessingContext) -> ProcessingContext:
        pass
    
    async def validate_input(self, context: ProcessingContext) -> bool:
        return True
    
    async def cleanup(self, context: ProcessingContext):
        pass
```

#### 2. Реализуйте новый этап
```python
# app/services/processing/new_step.py
from app.services.processing.base_step import ProcessingStep
from app.core.logging import get_logger

logger = get_logger(__name__)

class NewProcessingStep(ProcessingStep):
    def __init__(self):
        super().__init__("new_processing_step")
    
    async def execute(self, context: ProcessingContext) -> ProcessingContext:
        logger.info(f"Starting {self.name} for task {context.task_id}")
        
        # Валидация входных данных
        if not await self.validate_input(context):
            raise ValueError("Invalid input for new processing step")
        
        try:
            # Основная логика обработки
            result = await self.process_data(context.data)
            
            # Обновление контекста
            context.add_result(self.name, result)
            self.progress = 1.0
            
            logger.info(f"Completed {self.name} for task {context.task_id}")
            return context
            
        except Exception as e:
            logger.error(f"Error in {self.name}: {e}")
            raise
        finally:
            await self.cleanup(context)
    
    async def process_data(self, data: Any) -> Any:
        # Реализуйте логику обработки
        pass
    
    async def validate_input(self, context: ProcessingContext) -> bool:
        # Проверьте необходимые данные в контексте
        return hasattr(context, 'video_path')
```

#### 3. Зарегистрируйте этап в пайплайне
```python
# app/services/pipeline_orchestrator.py
from app.services.processing.new_step import NewProcessingStep

class ProcessingPipeline:
    def __init__(self):
        self.steps = [
            # ... существующие этапы
            NewProcessingStep(),
            # ... остальные этапы
        ]
```

### Обработка ошибок и fallback

```python
# app/services/processing/error_handling.py
class ProcessingErrorHandler:
    def __init__(self):
        self.fallback_services = FallbackServices()
    
    async def handle_step_error(
        self, 
        step_name: str, 
        error: Exception, 
        context: ProcessingContext
    ) -> ProcessingContext:
        logger.error(f"Error in step {step_name}: {error}")
        
        # Попытка использовать fallback сервис
        if step_name == "transcription" and isinstance(error, OpenAIError):
            logger.info("Using fallback transcription service")
            result = await self.fallback_services.get_transcription(
                context.audio_path
            )
            context.add_result("transcription", result)
            return context
        
        # Если fallback недоступен, пропустить этап
        if step_name in ["diarization", "visual_analysis"]:
            logger.warning(f"Skipping optional step {step_name}")
            context.add_result(step_name, None)
            return context
        
        # Для критических этапов - прервать обработку
        raise error
```

## 🌐 API разработка

### Структура API

API организован по версиям и функциональным группам:

```
/api/v1/
├── auth/          # Аутентификация и авторизация
├── upload/        # Загрузка файлов
├── processing/    # Управление задачами обработки
├── projects/      # Управление проектами
├── billing/       # Биллинг и платежи
└── admin/         # Административные функции
```

### Middleware и зависимости

#### Аутентификация
```python
# app/api/deps.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from app.core.auth import verify_token
from app.models.user import User

security = HTTPBearer()

async def get_current_user(token: str = Depends(security)) -> User:
    try:
        payload = verify_token(token.credentials)
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
        # Получить пользователя из базы данных
        user = await get_user_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        return user
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
```

#### Rate Limiting
```python
# app/core/rate_limiting.py
from fastapi import HTTPException, Request
from app.core.redis import get_redis
import time

class RateLimiter:
    def __init__(self, calls: int, period: int):
        self.calls = calls
        self.period = period
    
    async def __call__(self, request: Request):
        redis = await get_redis()
        client_ip = request.client.host
        key = f"rate_limit:{client_ip}"
        
        current = await redis.get(key)
        if current is None:
            await redis.setex(key, self.period, 1)
        else:
            current = int(current)
            if current >= self.calls:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded"
                )
            await redis.incr(key)

# Использование
rate_limiter = RateLimiter(calls=10, period=60)  # 10 запросов в минуту

@router.post("/upload")
async def upload_file(
    file: UploadFile,
    _: None = Depends(rate_limiter)
):
    pass
```

### Валидация и сериализация

#### Кастомные валидаторы
```python
# app/schemas/validators.py
from pydantic import validator
import magic

class FileUploadSchema(BaseModel):
    filename: str
    content_type: str
    size: int
    
    @validator('content_type')
    def validate_content_type(cls, v):
        allowed_types = [
            'video/mp4', 'video/avi', 'video/mov', 
            'video/mkv', 'video/webm'
        ]
        if v not in allowed_types:
            raise ValueError('Unsupported file type')
        return v
    
    @validator('size')
    def validate_size(cls, v):
        max_size = 5 * 1024 * 1024 * 1024  # 5GB
        if v > max_size:
            raise ValueError('File too large')
        return v
    
    @validator('filename')
    def validate_filename(cls, v):
        if not v or len(v) > 255:
            raise ValueError('Invalid filename')
        return v
```

## 🗄 База данных

### Модели данных

#### Базовый класс модели
```python
# app/db/base_model.py
from sqlalchemy import Column, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

class BaseModel(Base):
    __abstract__ = True
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
```

#### Связи между моделями
```python
# app/models/relationships.py
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

class User(BaseModel):
    __tablename__ = "users"
    
    # Связь один-ко-многим с проектами
    projects = relationship("FilmProject", back_populates="user")
    
    # Связь один-ко-многим с задачами
    tasks = relationship("ProcessingTask", back_populates="user")

class FilmProject(BaseModel):
    __tablename__ = "film_projects"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    user = relationship("User", back_populates="projects")
    
    # Связь один-к-одному с задачей обработки
    task_id = Column(UUID(as_uuid=True), ForeignKey("processing_tasks.id"))
    task = relationship("ProcessingTask", back_populates="project")
```

### Миграции

#### Создание сложной миграции
```python
# alembic/versions/xxx_add_indexes.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Создание индексов для производительности
    op.create_index(
        'idx_processing_tasks_status_created', 
        'processing_tasks', 
        ['status', 'created_at']
    )
    
    # Создание частичного индекса
    op.execute("""
        CREATE INDEX idx_active_tasks 
        ON processing_tasks (user_id, created_at) 
        WHERE status IN ('pending', 'processing')
    """)
    
    # Создание полнотекстового поиска
    op.execute("""
        ALTER TABLE film_projects 
        ADD COLUMN search_vector tsvector
    """)
    
    op.execute("""
        CREATE INDEX idx_film_projects_search 
        ON film_projects 
        USING gin(search_vector)
    """)

def downgrade():
    op.drop_index('idx_processing_tasks_status_created')
    op.execute("DROP INDEX idx_active_tasks")
    op.execute("DROP INDEX idx_film_projects_search")
    op.drop_column('film_projects', 'search_vector')
```

### Оптимизация запросов

#### Использование eager loading
```python
# app/services/project_service.py
from sqlalchemy.orm import joinedload, selectinload

class ProjectService:
    async def get_project_with_details(self, project_id: str) -> FilmProject:
        return self.db.query(FilmProject)\
            .options(
                joinedload(FilmProject.user),
                selectinload(FilmProject.task).joinedload(ProcessingTask.result)
            )\
            .filter(FilmProject.id == project_id)\
            .first()
    
    async def get_user_projects_optimized(self, user_id: str) -> List[FilmProject]:
        # Используем подзапрос для оптимизации
        subquery = self.db.query(ProcessingTask.id)\
            .filter(ProcessingTask.status == 'completed')\
            .subquery()
        
        return self.db.query(FilmProject)\
            .join(subquery, FilmProject.task_id == subquery.c.id)\
            .filter(FilmProject.user_id == user_id)\
            .all()
```

## 🧪 Тестирование

### Структура тестов

```
tests/
├── unit/              # Модульные тесты
│   ├── services/      # Тесты сервисов
│   ├── models/        # Тесты моделей
│   └── utils/         # Тесты утилит
├── integration/       # Интеграционные тесты
│   ├── api/           # Тесты API
│   ├── database/      # Тесты БД
│   └── external/      # Тесты внешних сервисов
├── e2e/              # End-to-end тесты
├── performance/      # Тесты производительности
└── fixtures/         # Тестовые данные
```

### Фикстуры и моки

#### Базовые фикстуры
```python
# tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.main import app

@pytest.fixture(scope="session")
def test_db():
    engine = create_engine("sqlite:///./test.db")
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session(test_db):
    SessionLocal = sessionmaker(bind=test_db)
    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture
def test_client():
    with TestClient(app) as client:
        yield client

@pytest.fixture
def mock_openai_api():
    with patch('app.services.transcription.openai') as mock:
        mock.Audio.transcribe.return_value = {
            "text": "Test transcription",
            "segments": []
        }
        yield mock
```

#### Тестирование сервисов
```python
# tests/unit/services/test_video_processor.py
import pytest
from unittest.mock import Mock, patch
from app.services.video_processor import VideoProcessor

class TestVideoProcessor:
    @pytest.fixture
    def video_processor(self):
        return VideoProcessor()
    
    @pytest.mark.asyncio
    async def test_validate_video_success(self, video_processor):
        # Arrange
        video_path = "test_video.mp4"
        
        with patch('app.services.video_processor.ffmpeg') as mock_ffmpeg:
            mock_ffmpeg.probe.return_value = {
                "streams": [{"codec_type": "video"}]
            }
            
            # Act
            result = await video_processor.validate_video(video_path)
            
            # Assert
            assert result.is_valid is True
            assert result.duration > 0
    
    @pytest.mark.asyncio
    async def test_extract_audio_creates_file(self, video_processor, tmp_path):
        # Arrange
        video_path = str(tmp_path / "test.mp4")
        expected_audio_path = str(tmp_path / "test.wav")
        
        with patch('app.services.video_processor.ffmpeg') as mock_ffmpeg:
            # Act
            audio_path = await video_processor.extract_audio(video_path)
            
            # Assert
            assert audio_path == expected_audio_path
            mock_ffmpeg.input.assert_called_once_with(video_path)
```

### Интеграционные тесты

```python
# tests/integration/api/test_upload_endpoint.py
import pytest
from fastapi.testclient import TestClient
from io import BytesIO

class TestUploadEndpoint:
    def test_upload_video_success(self, test_client, mock_openai_api):
        # Arrange
        video_content = b"fake video content"
        files = {"file": ("test.mp4", BytesIO(video_content), "video/mp4")}
        
        # Act
        response = test_client.post("/api/v1/upload", files=files)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "pending"
    
    def test_upload_invalid_file_type(self, test_client):
        # Arrange
        files = {"file": ("test.txt", BytesIO(b"text"), "text/plain")}
        
        # Act
        response = test_client.post("/api/v1/upload", files=files)
        
        # Assert
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]
```

### Тесты производительности

```python
# tests/performance/test_processing_performance.py
import pytest
import time
from app.services.video_processor import VideoProcessor

class TestProcessingPerformance:
    @pytest.mark.performance
    def test_video_processing_time(self, large_video_file):
        # Arrange
        processor = VideoProcessor()
        start_time = time.time()
        
        # Act
        result = processor.process_video(large_video_file)
        
        # Assert
        processing_time = time.time() - start_time
        assert processing_time < 300  # Должно завершиться за 5 минут
        assert result.success is True
    
    @pytest.mark.performance
    def test_concurrent_processing(self, multiple_video_files):
        # Тест обработки нескольких файлов одновременно
        import asyncio
        
        async def process_all():
            tasks = [
                VideoProcessor().process_video(video) 
                for video in multiple_video_files
            ]
            return await asyncio.gather(*tasks)
        
        start_time = time.time()
        results = asyncio.run(process_all())
        total_time = time.time() - start_time
        
        # Проверяем, что параллельная обработка эффективнее
        assert total_time < len(multiple_video_files) * 60  # Меньше минуты на файл
        assert all(r.success for r in results)
```

## 🚀 Развертывание

### CI/CD Pipeline

#### GitHub Actions
```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      
      redis:
        image: redis:6
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Run tests
      run: |
        pytest --cov=app --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
  
  build:
    needs: test
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Build Docker image
      run: |
        docker build -t filmlist:${{ github.sha }} .
    
    - name: Push to registry
      if: github.ref == 'refs/heads/main'
      run: |
        echo ${{ secrets.DOCKER_PASSWORD }} | docker login -u ${{ secrets.DOCKER_USERNAME }} --password-stdin
        docker push filmlist:${{ github.sha }}
  
  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - name: Deploy to production
      run: |
        # Скрипт развертывания на production сервер
        ssh ${{ secrets.PRODUCTION_HOST }} "cd /app && docker-compose pull && docker-compose up -d"
```

### Мониторинг и логирование

#### Prometheus метрики
```python
# app/core/metrics.py
from prometheus_client import Counter, Histogram, Gauge
import time

# Метрики для мониторинга
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration')
PROCESSING_TASKS = Gauge('processing_tasks_active', 'Active processing tasks')
PROCESSING_DURATION = Histogram('processing_duration_seconds', 'Processing duration', ['step'])

class MetricsMiddleware:
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            start_time = time.time()
            
            # Обработка запроса
            await self.app(scope, receive, send)
            
            # Запись метрик
            duration = time.time() - start_time
            REQUEST_COUNT.labels(
                method=scope["method"], 
                endpoint=scope["path"]
            ).inc()
            REQUEST_DURATION.observe(duration)
        else:
            await self.app(scope, receive, send)
```

#### Структурированное логирование
```python
# app/core/logging.py
import structlog
import logging
from typing import Any, Dict

def configure_logging():
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

class ContextLogger:
    def __init__(self, logger_name: str):
        self.logger = structlog.get_logger(logger_name)
        self.context = {}
    
    def add_context(self, **kwargs):
        self.context.update(kwargs)
        return self
    
    def info(self, message: str, **kwargs):
        self.logger.info(message, **{**self.context, **kwargs})
    
    def error(self, message: str, **kwargs):
        self.logger.error(message, **{**self.context, **kwargs})
```

## 📝 Лучшие практики

### Код

1. **Следуйте PEP 8** и используйте автоматическое форматирование
2. **Типизация**: Используйте type hints везде
3. **Документация**: Документируйте все публичные методы
4. **Тестирование**: Покрытие тестами должно быть > 80%
5. **Безопасность**: Валидируйте все входные данные

### API Design

1. **RESTful принципы**: Используйте правильные HTTP методы и коды ответов
2. **Версионирование**: Всегда версионируйте API
3. **Пагинация**: Реализуйте пагинацию для списков
4. **Rate Limiting**: Ограничивайте частоту запросов
5. **Документация**: Поддерживайте актуальную OpenAPI документацию

### База данных

1. **Миграции**: Всегда используйте миграции для изменений схемы
2. **Индексы**: Создавайте индексы для часто используемых запросов
3. **Транзакции**: Используйте транзакции для связанных операций
4. **Бэкапы**: Регулярно создавайте бэкапы
5. **Мониторинг**: Отслеживайте производительность запросов

### Безопасность

1. **Аутентификация**: Используйте JWT токены с коротким временем жизни
2. **Авторизация**: Проверяйте права доступа на каждом эндпоинте
3. **Валидация**: Валидируйте и санитизируйте все входные данные
4. **HTTPS**: Используйте HTTPS в production
5. **Секреты**: Храните секреты в переменных окружения

### Производительность

1. **Кэширование**: Кэшируйте часто запрашиваемые данные
2. **Асинхронность**: Используйте async/await для I/O операций
3. **Пулы соединений**: Используйте пулы для БД и внешних сервисов
4. **Мониторинг**: Отслеживайте метрики производительности
5. **Профилирование**: Регулярно профилируйте критические участки кода

---

Это руководство поможет вам эффективно разрабатывать и поддерживать систему Filmlist. При возникновении вопросов обращайтесь к команде разработки или создавайте Issue в репозитории.