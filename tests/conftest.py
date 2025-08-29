"""
Test configuration and fixtures.
"""
import pytest
import tempfile
import os
import json
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base, get_db
from app.core.config import settings
from app.models.user import User
from app.models.processing_task import ProcessingTask
from app.models.film_project import FilmProject
from app.schemas.film_project import MontageRow, ShotType


# Test database URL (use file-based SQLite for tests)
TEST_DATABASE_URL = "sqlite:///./test_filmlist.db"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client():
    """Create a test client with database override."""
    # Create tables for each test
    Base.metadata.create_all(bind=engine)
    
    def override_get_db():
        """Override database dependency for testing."""
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    
    # Clean up tables after each test
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user_data():
    """Test user data for registration."""
    return {
        "email": "test@example.com",
        "password": "testpassword123"
    }


@pytest.fixture
def test_user(db_session):
    """Create a test user in the database."""
    user = User(
        email="test@example.com",
        password_hash="$2b$12$hashed_password",
        balance=1000.0
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_processing_task(db_session, test_user):
    """Create a test processing task."""
    task = ProcessingTask(
        user_id=test_user.id,
        status="completed",
        video_filename="test_video.mp4",
        video_path="/uploads/test_video.mp4",
        progress=1.0,
        current_step="document_generation",
        result=json.dumps([
            {
                "number": 1,
                "start_timecode": "01:00:00:00",
                "end_timecode": "01:00:05:00",
                "shot_type": "Средний",
                "description": "Тестовая сцена",
                "dialogue": "Тестовый диалог",
                "speaker": "Спикер 1",
                "has_music": False,
                "special_tags": []
            }
        ])
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


@pytest.fixture
def test_film_project(db_session, test_user, test_processing_task):
    """Create a test film project."""
    project = FilmProject(
        user_id=test_user.id,
        task_id=test_processing_task.id,
        title="Тестовый фильм",
        film_metadata={
            "title": "Тестовый фильм",
            "production_company": "Тестовая студия",
            "year": 2024,
            "country": "Россия",
            "screenwriters": ["Автор 1"],
            "copyright_holders": ["Правообладатель 1"],
            "duration": "01:30:00",
            "episodes_count": 1,
            "format": "Digital",
            "color_type": "Цветной",
            "media_carrier": "HDD",
            "original_language": "Русский",
            "audio_language": "Русский"
        }
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.fixture
def sample_montage_rows():
    """Sample montage rows for testing."""
    return [
        MontageRow(
            number=1,
            start_timecode="01:00:00:00",
            end_timecode="01:00:05:00",
            shot_type=ShotType.MEDIUM,
            description="Первая сцена",
            dialogue="Привет, как дела?",
            speaker="Спикер 1",
            has_music=False,
            special_tags=[]
        ),
        MontageRow(
            number=2,
            start_timecode="01:00:05:01",
            end_timecode="01:00:10:00",
            shot_type=ShotType.CLOSE,
            description="Вторая сцена",
            dialogue="Все хорошо, спасибо!",
            speaker="Спикер 2",
            has_music=True,
            special_tags=["НДП"]
        )
    ]


@pytest.fixture
def temp_video_file():
    """Create a temporary video file for testing."""
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
        # Write minimal MP4 header for testing
        f.write(b'\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom')
        f.write(b'\x00' * 1000)  # Add some content
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def temp_audio_file():
    """Create a temporary audio file for testing."""
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        # Write minimal WAV header
        f.write(b'RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00')
        f.write(b'\x01\x00\x02\x00\x44\xac\x00\x00\x10\xb1\x02\x00')
        f.write(b'\x04\x00\x10\x00data\x00\x08\x00\x00')
        f.write(b'\x00' * 2048)  # Add some audio data
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def temp_srt_file():
    """Create a temporary SRT file for testing."""
    srt_content = """1
00:00:00,000 --> 00:00:05,000
Первая реплика диалога

2
00:00:05,000 --> 00:00:10,000
Вторая реплика диалога

3
00:00:10,000 --> 00:00:15,000
Третья реплика диалога
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as f:
        f.write(srt_content)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response for testing."""
    return {
        "text": "Тестовая транскрипция аудио файла.",
        "segments": [
            {
                "start": 0.0,
                "end": 5.0,
                "text": "Первая часть транскрипции"
            },
            {
                "start": 5.0,
                "end": 10.0,
                "text": "Вторая часть транскрипции"
            }
        ]
    }


@pytest.fixture
def mock_scene_list():
    """Mock scene detection results."""
    return [
        {"start_time": 0.0, "end_time": 10.0, "duration": 10.0, "scene_number": 1},
        {"start_time": 10.0, "end_time": 25.0, "duration": 15.0, "scene_number": 2},
        {"start_time": 25.0, "end_time": 40.0, "duration": 15.0, "scene_number": 3}
    ]


@pytest.fixture
def mock_visual_analysis_response():
    """Mock GPT visual analysis response."""
    return {
        "shot_type": "Ср.",
        "description": "Человек сидит за столом и говорит",
        "text_in_frame": ""
    }


@pytest.fixture
def temp_directory():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture(autouse=True)
def mock_redis():
    """Mock Redis for all tests."""
    with patch('app.core.redis.cache_manager') as mock_cache:
        mock_redis_client = AsyncMock()
        mock_cache.redis_client.get_client.return_value = mock_redis_client
        mock_redis_client.get.return_value = None
        mock_redis_client.set.return_value = True
        mock_redis_client.setex.return_value = True
        mock_redis_client.delete.return_value = True
        mock_redis_client.exists.return_value = False
        mock_redis_client.ping.return_value = True
        yield mock_cache


@pytest.fixture
def mock_ffmpeg_success():
    """Mock successful FFmpeg subprocess calls."""
    with patch('asyncio.create_subprocess_exec') as mock_subprocess:
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b'', b'')
        mock_subprocess.return_value = mock_process
        yield mock_subprocess


@pytest.fixture
def mock_file_operations():
    """Mock file system operations."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.mkdir'), \
         patch('pathlib.Path.unlink'), \
         patch('os.path.exists', return_value=True), \
         patch('os.makedirs'), \
         patch('os.remove'):
        yield


# Event loop fixture for async tests
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()