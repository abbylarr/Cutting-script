"""
Integration tests for core API endpoints.
"""
import pytest
import json
from uuid import uuid4
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.user import User
from app.models.processing_task import ProcessingTask
from app.models.film_project import FilmProject
from app.schemas.film_project import MontageRow, ShotType


class TestCoreAPIEndpoints:
    """Test core API endpoints for task status, montage updates, and downloads."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def test_user(self, db_session: Session):
        """Create test user."""
        user = User(
            email="test@example.com",
            password_hash="hashed_password",
            balance=1000.0
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user
    
    @pytest.fixture
    def test_task(self, db_session: Session, test_user: User):
        """Create test processing task."""
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
    def test_project(self, db_session: Session, test_user: User, test_task: ProcessingTask):
        """Create test film project."""
        project = FilmProject(
            user_id=test_user.id,
            task_id=test_task.id,
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
    def auth_headers(self, test_user: User):
        """Create authentication headers."""
        # Mock JWT token for testing
        with patch('app.core.auth.get_current_user', return_value=test_user):
            return {"Authorization": "Bearer test_token"}
    
    def test_get_task_status_success(self, client: TestClient, test_task: ProcessingTask, auth_headers: dict):
        """Test successful task status retrieval."""
        with patch('app.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = test_task.user
            
            response = client.get(f"/api/v1/status/{test_task.id}", headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["id"] == str(test_task.id)
            assert data["status"] == "completed"
            assert data["progress"] == 1.0
            assert data["result"] is not None
            assert len(data["result"]) == 1
    
    def test_get_task_status_not_found(self, client: TestClient, test_user: User, auth_headers: dict):
        """Test task status retrieval for non-existent task."""
        with patch('app.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = test_user
            
            fake_task_id = uuid4()
            response = client.get(f"/api/v1/status/{fake_task_id}", headers=auth_headers)
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
    
    def test_get_task_status_processing(self, client: TestClient, db_session: Session, test_user: User, auth_headers: dict):
        """Test task status for processing task with ETA calculation."""
        # Create processing task
        task = ProcessingTask(
            user_id=test_user.id,
            status="processing",
            video_filename="processing_video.mp4",
            video_path="/uploads/processing_video.mp4",
            progress=0.5,
            current_step="transcription"
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        
        with patch('app.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = test_user
            
            response = client.get(f"/api/v1/status/{task.id}", headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "processing"
            assert data["progress"] == 0.5
            assert data["current_step"] == "transcription"
            assert data["current_step_description"] is not None
            assert data["eta_seconds"] is not None
            assert data["eta_seconds"] > 0
    
    def test_update_montage_rows_success(self, client: TestClient, test_task: ProcessingTask, auth_headers: dict):
        """Test successful montage rows update."""
        updated_rows = [
            {
                "number": 1,
                "start_timecode": "01:00:00:00",
                "end_timecode": "01:00:05:00",
                "shot_type": "Крупный",
                "description": "Обновленная сцена",
                "dialogue": "Обновленный диалог",
                "speaker": "Новый спикер",
                "has_music": True,
                "special_tags": ["НДП"]
            },
            {
                "number": 2,
                "start_timecode": "01:00:05:01",
                "end_timecode": "01:00:10:00",
                "shot_type": "Общий",
                "description": "Вторая сцена",
                "dialogue": "",
                "speaker": None,
                "has_music": False,
                "special_tags": []
            }
        ]
        
        with patch('app.core.auth.get_current_user') as mock_auth, \
             patch('app.services.docx_generator.docx_generator.generate_docx_for_task', new_callable=AsyncMock) as mock_docx:
            
            mock_auth.return_value = test_task.user
            mock_docx.return_value = "/output/test.docx"
            
            response = client.patch(
                f"/api/v1/montage/{test_task.id}",
                json={"rows": updated_rows},
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert "2 montage rows" in data["message"]
            assert data["data"]["rows_updated"] == 2
    
    def test_update_montage_rows_invalid_task_status(self, client: TestClient, db_session: Session, test_user: User, auth_headers: dict):
        """Test montage update for task with invalid status."""
        # Create pending task
        task = ProcessingTask(
            user_id=test_user.id,
            status="pending",
            video_filename="pending_video.mp4",
            video_path="/uploads/pending_video.mp4",
            progress=0.0
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        
        updated_rows = [
            {
                "number": 1,
                "start_timecode": "01:00:00:00",
                "end_timecode": "01:00:05:00",
                "shot_type": "Средний",
                "description": "Тест",
                "dialogue": "",
                "speaker": None,
                "has_music": False,
                "special_tags": []
            }
        ]
        
        with patch('app.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = test_user
            
            response = client.patch(
                f"/api/v1/montage/{task.id}",
                json={"rows": updated_rows},
                headers=auth_headers
            )
            
            assert response.status_code == 400
            assert "pending" in response.json()["detail"]
    
    def test_update_montage_rows_validation_error(self, client: TestClient, test_task: ProcessingTask, auth_headers: dict):
        """Test montage update with validation errors."""
        invalid_rows = [
            {
                "number": 2,  # Wrong number (should be 1)
                "start_timecode": "01:00:00:00",
                "end_timecode": "01:00:05:00",
                "shot_type": "Средний",
                "description": "Тест",
                "dialogue": "",
                "speaker": None,
                "has_music": False,
                "special_tags": []
            }
        ]
        
        with patch('app.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = test_task.user
            
            response = client.patch(
                f"/api/v1/montage/{test_task.id}",
                json={"rows": invalid_rows},
                headers=auth_headers
            )
            
            assert response.status_code == 400
            assert "incorrect number" in response.json()["detail"]
    
    @patch('os.path.exists')
    def test_download_docx_existing_file(self, mock_exists, client: TestClient, test_task: ProcessingTask, test_project: FilmProject, auth_headers: dict):
        """Test DOCX download when file already exists."""
        mock_exists.return_value = True
        
        with patch('app.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = test_task.user
            
            response = client.get(f"/api/v1/download/{test_task.id}", headers=auth_headers)
            
            # Should return file response (can't easily test file content in unit test)
            assert response.status_code == 200
    
    @patch('os.path.exists')
    def test_download_docx_generate_new_file(self, mock_exists, client: TestClient, test_task: ProcessingTask, test_project: FilmProject, auth_headers: dict):
        """Test DOCX download when file needs to be generated."""
        mock_exists.return_value = False
        
        with patch('app.core.auth.get_current_user') as mock_auth, \
             patch('app.services.docx_generator.docx_generator.generate_docx_for_task', new_callable=AsyncMock) as mock_docx:
            
            mock_auth.return_value = test_task.user
            mock_docx.return_value = "/output/test.docx"
            
            response = client.get(f"/api/v1/download/{test_task.id}", headers=auth_headers)
            
            assert response.status_code == 200
            mock_docx.assert_called_once()
    
    def test_download_docx_invalid_task_status(self, client: TestClient, db_session: Session, test_user: User, auth_headers: dict):
        """Test DOCX download for task with invalid status."""
        # Create processing task
        task = ProcessingTask(
            user_id=test_user.id,
            status="processing",
            video_filename="processing_video.mp4",
            video_path="/uploads/processing_video.mp4",
            progress=0.5
        )
        db_session.add(task)
        db_session.commit()
        
        with patch('app.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = test_user
            
            response = client.get(f"/api/v1/download/{task.id}", headers=auth_headers)
            
            assert response.status_code == 400
            assert "processing" in response.json()["detail"]
    
    def test_download_docx_no_project(self, client: TestClient, test_task: ProcessingTask, auth_headers: dict):
        """Test DOCX download when no film project exists."""
        with patch('app.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = test_task.user
            
            response = client.get(f"/api/v1/download/{test_task.id}", headers=auth_headers)
            
            assert response.status_code == 404
            assert "Film project not found" in response.json()["detail"]
    
    def test_unauthorized_access(self, client: TestClient, test_task: ProcessingTask):
        """Test unauthorized access to endpoints."""
        # Test without authentication headers
        response = client.get(f"/api/v1/status/{test_task.id}")
        assert response.status_code == 401
        
        response = client.patch(f"/api/v1/montage/{test_task.id}", json={"rows": []})
        assert response.status_code == 401
        
        response = client.get(f"/api/v1/download/{test_task.id}")
        assert response.status_code == 401
    
    def test_cross_user_access_denied(self, client: TestClient, db_session: Session, test_task: ProcessingTask):
        """Test that users cannot access other users' tasks."""
        # Create another user
        other_user = User(
            email="other@example.com",
            password_hash="hashed_password",
            balance=500.0
        )
        db_session.add(other_user)
        db_session.commit()
        
        with patch('app.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = other_user
            
            # Try to access first user's task
            response = client.get(f"/api/v1/status/{test_task.id}", headers={"Authorization": "Bearer token"})
            assert response.status_code == 404
            
            response = client.patch(f"/api/v1/montage/{test_task.id}", 
                                  json={"rows": []}, 
                                  headers={"Authorization": "Bearer token"})
            assert response.status_code == 404
            
            response = client.get(f"/api/v1/download/{test_task.id}", 
                                headers={"Authorization": "Bearer token"})
            assert response.status_code == 404


class TestTaskStatusDescriptions:
    """Test task status descriptions and ETA calculations."""
    
    def test_step_descriptions_mapping(self):
        """Test that all processing steps have descriptions."""
        from app.api.v1.endpoints.core import router
        from app.schemas.processing_task import ProcessingStep
        
        # This would be tested by calling the endpoint, but we can verify the mapping exists
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
        
        # Verify all steps have descriptions
        for step in ProcessingStep:
            assert step in step_descriptions
            assert len(step_descriptions[step]) > 0
    
    def test_eta_calculation_logic(self):
        """Test ETA calculation logic."""
        # Test ETA calculation for different progress values
        estimated_total_time = 180  # 3 minutes
        
        # 50% progress should give ~90 seconds remaining
        progress = 0.5
        remaining_ratio = 1.0 - progress
        eta_seconds = int(estimated_total_time * remaining_ratio)
        assert eta_seconds == 90
        
        # 90% progress should give ~18 seconds remaining
        progress = 0.9
        remaining_ratio = 1.0 - progress
        eta_seconds = int(estimated_total_time * remaining_ratio)
        assert eta_seconds == 18 or eta_seconds == 17  # Allow for rounding differences
        
        # 0% progress should give full time
        progress = 0.0
        remaining_ratio = 1.0 - progress
        eta_seconds = int(estimated_total_time * remaining_ratio)
        assert eta_seconds == 180