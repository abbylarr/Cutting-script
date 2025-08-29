"""
Integration tests for project management API endpoints.
"""
import pytest
import json
from uuid import uuid4
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.user import User
from app.models.processing_task import ProcessingTask
from app.models.film_project import FilmProject


class TestProjectManagementEndpoints:
    """Test project management API endpoints."""
    
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
            result=[
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
            ]
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
            },
            montage_rows=[
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
            ]
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)
        return project
    
    @pytest.fixture
    def auth_headers(self, test_user: User):
        """Create authentication headers."""
        return {"Authorization": "Bearer test_token"}
    
    def test_save_project_changes_success(self, client: TestClient, test_project: FilmProject, auth_headers: dict):
        """Test successful project save."""
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
            }
        ]
        
        with patch('app.core.auth.get_current_user') as mock_auth, \
             patch('app.services.docx_generator.docx_generator.generate_docx_for_task', new_callable=AsyncMock) as mock_docx:
            
            mock_auth.return_value = test_project.user
            mock_docx.return_value = "/output/test.docx"
            
            response = client.post(
                f"/api/v1/projects/save/{test_project.task_id}",
                json={
                    "montage_rows": updated_rows,
                    "regenerate_docx": True
                },
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert "1 montage rows" in data["message"]
            assert data["data"]["rows_saved"] == 1
            assert data["data"]["docx_regenerated"] is True
    
    def test_save_project_changes_without_docx_regeneration(self, client: TestClient, test_project: FilmProject, auth_headers: dict):
        """Test project save without DOCX regeneration."""
        updated_rows = [
            {
                "number": 1,
                "start_timecode": "01:00:00:00",
                "end_timecode": "01:00:05:00",
                "shot_type": "Общий",
                "description": "Сцена без регенерации",
                "dialogue": "",
                "speaker": None,
                "has_music": False,
                "special_tags": []
            }
        ]
        
        with patch('app.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = test_project.user
            
            response = client.post(
                f"/api/v1/projects/save/{test_project.task_id}",
                json={
                    "montage_rows": updated_rows,
                    "regenerate_docx": False
                },
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert data["data"]["docx_regenerated"] is False
    
    def test_list_projects_success(self, client: TestClient, test_project: FilmProject, auth_headers: dict):
        """Test successful project listing."""
        with patch('app.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = test_project.user
            
            response = client.get("/api/v1/projects/", headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            
            assert "items" in data
            assert "total" in data
            assert "page" in data
            assert "size" in data
            assert "pages" in data
            
            assert data["total"] >= 1
            assert len(data["items"]) >= 1
            
            # Check first project
            project_item = data["items"][0]
            assert project_item["id"] == str(test_project.id)
            assert project_item["title"] == test_project.title
            assert project_item["status"] == "completed"
    
    def test_list_projects_with_pagination(self, client: TestClient, db_session: Session, test_user: User, auth_headers: dict):
        """Test project listing with pagination."""
        # Create multiple projects
        for i in range(5):
            task = ProcessingTask(
                user_id=test_user.id,
                status="completed",
                video_filename=f"video_{i}.mp4",
                video_path=f"/uploads/video_{i}.mp4",
                progress=1.0
            )
            db_session.add(task)
            db_session.flush()
            
            project = FilmProject(
                user_id=test_user.id,
                task_id=task.id,
                title=f"Проект {i}",
                film_metadata={
                    "title": f"Фильм {i}",
                    "production_company": "Студия",
                    "year": 2024,
                    "country": "Россия",
                    "screenwriters": ["Автор"],
                    "copyright_holders": ["Правообладатель"],
                    "duration": "01:00:00",
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
        
        with patch('app.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = test_user
            
            # Test first page with size 3
            response = client.get("/api/v1/projects/?page=1&size=3", headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["total"] >= 5
            assert len(data["items"]) == 3
            assert data["page"] == 1
            assert data["size"] == 3
            assert data["pages"] >= 2
    
    def test_list_projects_with_search(self, client: TestClient, db_session: Session, test_user: User, auth_headers: dict):
        """Test project listing with search."""
        # Create projects with different titles
        searchable_task = ProcessingTask(
            user_id=test_user.id,
            status="completed",
            video_filename="searchable.mp4",
            video_path="/uploads/searchable.mp4",
            progress=1.0
        )
        db_session.add(searchable_task)
        db_session.flush()
        
        searchable_project = FilmProject(
            user_id=test_user.id,
            task_id=searchable_task.id,
            title="Уникальный поисковый проект",
            film_metadata={
                "title": "Уникальный фильм",
                "production_company": "Студия",
                "year": 2024,
                "country": "Россия",
                "screenwriters": ["Автор"],
                "copyright_holders": ["Правообладатель"],
                "duration": "01:00:00",
                "episodes_count": 1,
                "format": "Digital",
                "color_type": "Цветной",
                "media_carrier": "HDD",
                "original_language": "Русский",
                "audio_language": "Русский"
            }
        )
        db_session.add(searchable_project)
        db_session.commit()
        
        with patch('app.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = test_user
            
            # Search for unique project
            response = client.get("/api/v1/projects/?search=Уникальный", headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["total"] >= 1
            found_titles = [item["title"] for item in data["items"]]
            assert "Уникальный поисковый проект" in found_titles
    
    def test_get_project_success(self, client: TestClient, test_project: FilmProject, auth_headers: dict):
        """Test successful project retrieval."""
        with patch('app.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = test_project.user
            
            response = client.get(f"/api/v1/projects/{test_project.id}", headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["id"] == str(test_project.id)
            assert data["title"] == test_project.title
            assert data["film_metadata"]["title"] == "Тестовый фильм"
            assert data["montage_rows"] is not None
            assert len(data["montage_rows"]) == 1
    
    def test_get_project_not_found(self, client: TestClient, test_user: User, auth_headers: dict):
        """Test project retrieval for non-existent project."""
        with patch('app.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = test_user
            
            fake_project_id = uuid4()
            response = client.get(f"/api/v1/projects/{fake_project_id}", headers=auth_headers)
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
    
    def test_update_project_success(self, client: TestClient, test_project: FilmProject, auth_headers: dict):
        """Test successful project update."""
        update_data = {
            "title": "Обновленный фильм",
            "film_metadata": {
                "title": "Обновленный фильм",
                "production_company": "Новая студия",
                "year": 2025,
                "country": "Россия",
                "screenwriters": ["Новый автор"],
                "copyright_holders": ["Новый правообладатель"],
                "duration": "02:00:00",
                "episodes_count": 2,
                "format": "4K Digital",
                "color_type": "Цветной",
                "media_carrier": "SSD",
                "original_language": "Русский",
                "audio_language": "Русский"
            }
        }
        
        with patch('app.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = test_project.user
            
            response = client.put(
                f"/api/v1/projects/{test_project.id}",
                json=update_data,
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["title"] == "Обновленный фильм"
            assert data["film_metadata"]["production_company"] == "Новая студия"
            assert data["film_metadata"]["year"] == 2025
    
    def test_update_project_with_montage_rows(self, client: TestClient, test_project: FilmProject, auth_headers: dict):
        """Test project update with montage rows."""
        new_rows = [
            {
                "number": 1,
                "start_timecode": "01:00:00:00",
                "end_timecode": "01:00:03:00",
                "shot_type": "Деталь",
                "description": "Новая сцена",
                "dialogue": "Новый диалог",
                "speaker": "Новый спикер",
                "has_music": False,
                "special_tags": ["ЗТМ"]
            },
            {
                "number": 2,
                "start_timecode": "01:00:03:01",
                "end_timecode": "01:00:08:00",
                "shot_type": "Общий",
                "description": "Вторая новая сцена",
                "dialogue": "",
                "speaker": None,
                "has_music": True,
                "special_tags": []
            }
        ]
        
        update_data = {
            "montage_rows": new_rows
        }
        
        with patch('app.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = test_project.user
            
            response = client.put(
                f"/api/v1/projects/{test_project.id}",
                json=update_data,
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert len(data["montage_rows"]) == 2
            assert data["montage_rows"][0]["shot_type"] == "Деталь"
            assert data["montage_rows"][1]["has_music"] is True
    
    @patch('os.path.exists')
    @patch('os.remove')
    @patch('os.rmdir')
    @patch('os.listdir')
    def test_delete_project_success(self, mock_listdir, mock_rmdir, mock_remove, mock_exists, 
                                  client: TestClient, test_project: FilmProject, auth_headers: dict):
        """Test successful project deletion with file cleanup."""
        mock_exists.return_value = True
        mock_listdir.return_value = []  # Empty directories
        
        with patch('app.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = test_project.user
            
            response = client.delete(f"/api/v1/projects/{test_project.id}", headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert "deleted project" in data["message"].lower()
            assert data["data"]["project_id"] == str(test_project.id)
            
            # Verify file cleanup was attempted
            assert mock_remove.call_count >= 1  # At least video file removal
    
    def test_duplicate_project_success(self, client: TestClient, test_project: FilmProject, auth_headers: dict):
        """Test successful project duplication."""
        with patch('app.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = test_project.user
            
            response = client.post(f"/api/v1/projects/{test_project.id}/duplicate", headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["id"] != str(test_project.id)  # Different ID
            assert data["title"] == f"Copy of {test_project.title}"
            assert data["film_metadata"]["title"] == test_project.film_metadata["title"]
            assert data["montage_rows"] == test_project.montage_rows
    
    def test_duplicate_project_not_found(self, client: TestClient, test_user: User, auth_headers: dict):
        """Test project duplication for non-existent project."""
        with patch('app.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = test_user
            
            fake_project_id = uuid4()
            response = client.post(f"/api/v1/projects/{fake_project_id}/duplicate", headers=auth_headers)
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
    
    def test_unauthorized_project_access(self, client: TestClient, test_project: FilmProject):
        """Test unauthorized access to project endpoints."""
        # Test without authentication
        response = client.get("/api/v1/projects/")
        assert response.status_code == 401
        
        response = client.get(f"/api/v1/projects/{test_project.id}")
        assert response.status_code == 401
        
        response = client.put(f"/api/v1/projects/{test_project.id}", json={})
        assert response.status_code == 401
        
        response = client.delete(f"/api/v1/projects/{test_project.id}")
        assert response.status_code == 401
        
        response = client.post(f"/api/v1/projects/save/{test_project.task_id}", json={"montage_rows": []})
        assert response.status_code == 401
    
    def test_cross_user_project_access_denied(self, client: TestClient, db_session: Session, test_project: FilmProject):
        """Test that users cannot access other users' projects."""
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
            
            # Try to access first user's project
            response = client.get(f"/api/v1/projects/{test_project.id}", 
                                headers={"Authorization": "Bearer token"})
            assert response.status_code == 404
            
            response = client.put(f"/api/v1/projects/{test_project.id}", 
                                json={}, 
                                headers={"Authorization": "Bearer token"})
            assert response.status_code == 404
            
            response = client.delete(f"/api/v1/projects/{test_project.id}", 
                                   headers={"Authorization": "Bearer token"})
            assert response.status_code == 404


class TestProjectValidation:
    """Test project data validation."""
    
    def test_save_project_invalid_montage_rows(self, client: TestClient, test_project: FilmProject, auth_headers: dict):
        """Test project save with invalid montage row data."""
        invalid_rows = [
            {
                "number": 1,
                "start_timecode": "invalid_timecode",  # Invalid format
                "end_timecode": "01:00:05:00",
                "shot_type": "InvalidType",  # Invalid shot type
                "description": "Test",
                "dialogue": "",
                "speaker": None,
                "has_music": False,
                "special_tags": []
            }
        ]
        
        with patch('app.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = test_project.user
            
            response = client.post(
                f"/api/v1/projects/save/{test_project.task_id}",
                json={
                    "montage_rows": invalid_rows,
                    "regenerate_docx": False
                },
                headers=auth_headers
            )
            
            assert response.status_code == 422  # Validation error
    
    def test_update_project_invalid_metadata(self, client: TestClient, test_project: FilmProject, auth_headers: dict):
        """Test project update with invalid metadata."""
        invalid_update = {
            "film_metadata": {
                "title": "",  # Empty title
                "year": 1800,  # Invalid year
                "screenwriters": [],  # Empty list
                "copyright_holders": []  # Empty list
            }
        }
        
        with patch('app.core.auth.get_current_user') as mock_auth:
            mock_auth.return_value = test_project.user
            
            response = client.put(
                f"/api/v1/projects/{test_project.id}",
                json=invalid_update,
                headers=auth_headers
            )
            
            assert response.status_code == 422  # Validation error