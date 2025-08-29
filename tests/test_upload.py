"""
Tests for file upload functionality.
"""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from fastapi import UploadFile
from fastapi.testclient import TestClient
import io

from app.main import app
from app.services.upload import FileUploadService
from app.schemas.upload import VideoValidationResult, SRTValidationResult


class TestFileUploadService:
    """Test cases for FileUploadService."""
    
    @pytest.fixture
    def upload_service(self):
        """Create upload service instance for testing."""
        return FileUploadService()
    
    @pytest.fixture
    def mock_video_file(self):
        """Create mock video file for testing."""
        content = b"fake video content for testing"
        file = UploadFile(
            filename="test_video.mp4",
            file=io.BytesIO(content),
            size=len(content)
        )
        return file
    
    @pytest.fixture
    def mock_srt_file(self):
        """Create mock SRT file for testing."""
        srt_content = """1
00:00:01,000 --> 00:00:03,000
Первая реплика

2
00:00:04,000 --> 00:00:06,000
Вторая реплика
"""
        content = srt_content.encode('utf-8')
        file = UploadFile(
            filename="test_subtitles.srt",
            file=io.BytesIO(content),
            size=len(content)
        )
        return file
    
    @pytest.mark.asyncio
    async def test_validate_video_file_success(self, upload_service, mock_video_file):
        """Test successful video file validation."""
        with patch('magic.from_buffer', return_value='video/mp4'), \
             patch.object(upload_service, '_save_temp_file') as mock_save, \
             patch.object(upload_service, '_extract_video_metadata') as mock_extract:
            
            mock_save.return_value = Path("/tmp/test_video.mp4")
            mock_extract.return_value = {
                'duration': 120.0,
                'fps': 30.0,
                'resolution': '1920x1080',
                'codec': 'h264'
            }
            
            result = await upload_service.validate_video_file(mock_video_file)
            
            assert result.is_valid is True
            assert result.duration == 120.0
            assert result.fps == 30.0
            assert result.resolution == '1920x1080'
            assert result.codec == 'h264'
            assert len(result.errors) == 0
    
    @pytest.mark.asyncio
    async def test_validate_video_file_unsupported_format(self, upload_service, mock_video_file):
        """Test video validation with unsupported format."""
        with patch('magic.from_buffer', return_value='text/plain'):
            result = await upload_service.validate_video_file(mock_video_file)
            
            assert result.is_valid is False
            assert "Unsupported video format" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_validate_video_file_too_large(self, upload_service):
        """Test video validation with file too large."""
        large_file = UploadFile(
            filename="large_video.mp4",
            file=io.BytesIO(b"content"),
            size=upload_service.MAX_VIDEO_SIZE + 1
        )
        
        result = await upload_service.validate_video_file(large_file)
        
        assert result.is_valid is False
        assert "exceeds maximum allowed size" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_validate_srt_file_success(self, upload_service, mock_srt_file):
        """Test successful SRT file validation."""
        result = await upload_service.validate_srt_file(mock_srt_file)
        
        assert result.is_valid is True
        assert result.subtitle_count == 2
        assert result.duration == 6.0  # Last subtitle ends at 6 seconds
        assert result.encoding == 'utf-8'
        assert len(result.errors) == 0
    
    @pytest.mark.asyncio
    async def test_validate_srt_file_wrong_extension(self, upload_service):
        """Test SRT validation with wrong file extension."""
        wrong_file = UploadFile(
            filename="subtitles.txt",
            file=io.BytesIO(b"content"),
            size=100
        )
        
        result = await upload_service.validate_srt_file(wrong_file)
        
        assert result.is_valid is False
        assert "must have .srt extension" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_validate_srt_file_too_large(self, upload_service):
        """Test SRT validation with file too large."""
        large_srt = UploadFile(
            filename="large.srt",
            file=io.BytesIO(b"content"),
            size=upload_service.MAX_SRT_SIZE + 1
        )
        
        result = await upload_service.validate_srt_file(large_srt)
        
        assert result.is_valid is False
        assert "exceeds maximum allowed size" in result.errors[0]
    
    def test_is_safe_filename(self, upload_service):
        """Test filename safety validation."""
        # Safe filenames
        assert upload_service._is_safe_filename("video.mp4") is True
        assert upload_service._is_safe_filename("my_video_2023.avi") is True
        
        # Unsafe filenames
        assert upload_service._is_safe_filename("../../../etc/passwd") is False
        assert upload_service._is_safe_filename("video/with/path.mp4") is False
        assert upload_service._is_safe_filename("video\\with\\backslash.mp4") is False
        assert upload_service._is_safe_filename("video\x00null.mp4") is False
        assert upload_service._is_safe_filename("") is False
        assert upload_service._is_safe_filename("a" * 300) is False  # Too long
    
    def test_parse_srt_content(self, upload_service):
        """Test SRT content parsing."""
        srt_content = """1
00:00:01,500 --> 00:00:04,000
Первая строка субтитров

2
00:00:05,200 --> 00:00:08,300
Вторая строка
с переносом

3
00:00:10,000 --> 00:00:12,500
Третья строка"""
        
        result = upload_service._parse_srt_content(srt_content)
        
        assert len(result) == 3
        assert result[0]['index'] == 1
        assert result[0]['start_time'] == 1.5
        assert result[0]['end_time'] == 4.0
        assert result[0]['text'] == "Первая строка субтитров"
        
        assert result[1]['text'] == "Вторая строка с переносом"
        assert result[2]['start_time'] == 10.0
    
    def test_time_to_seconds(self, upload_service):
        """Test SRT time format conversion."""
        assert upload_service._time_to_seconds("00:00:01,500") == 1.5
        assert upload_service._time_to_seconds("00:01:30,250") == 90.25
        assert upload_service._time_to_seconds("01:23:45,678") == 5025.678
    
    @pytest.mark.asyncio
    async def test_scan_file_for_viruses_clean(self, upload_service, mock_video_file):
        """Test virus scanning with clean file."""
        # Should not raise exception for clean file
        await upload_service._scan_file_for_viruses(mock_video_file)
    
    @pytest.mark.asyncio
    async def test_scan_file_for_viruses_suspicious(self, upload_service):
        """Test virus scanning with suspicious content."""
        suspicious_file = UploadFile(
            filename="malware.exe",
            file=io.BytesIO(b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR"),
            size=100
        )
        
        with pytest.raises(Exception) as exc_info:
            await upload_service._scan_file_for_viruses(suspicious_file)
        
        assert "suspicious content" in str(exc_info.value)


class TestUploadEndpoints:
    """Test cases for upload API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        """Mock authentication headers."""
        return {"Authorization": "Bearer test_token"}
    
    def test_upload_video_unauthorized(self, client):
        """Test video upload without authentication."""
        with tempfile.NamedTemporaryFile(suffix=".mp4") as tmp_file:
            tmp_file.write(b"fake video content")
            tmp_file.seek(0)
            
            response = client.post(
                "/api/v1/upload/upload",
                files={"file": ("test.mp4", tmp_file, "video/mp4")}
            )
            
            assert response.status_code == 401
    
    @patch('app.api.v1.endpoints.upload.get_current_user')
    @patch('app.api.v1.endpoints.upload.check_upload_rate_limit')
    @patch('app.api.v1.endpoints.upload.upload_service.validate_video_file')
    @patch('app.api.v1.endpoints.upload.billing_service.calculate_cost')
    @patch('app.api.v1.endpoints.upload.billing_service.has_sufficient_balance')
    def test_upload_video_success(self, mock_balance, mock_cost, mock_validate, 
                                 mock_rate_limit, mock_user, client):
        """Test successful video upload."""
        # Setup mocks
        mock_user.return_value = Mock(id="user123", balance=1000.0)
        mock_rate_limit.return_value = {"allowed": True}
        mock_validate.return_value = VideoValidationResult(
            is_valid=True,
            duration=120.0,
            file_size=1000000,
            errors=[]
        )
        mock_cost.return_value = 150.0
        mock_balance.return_value = True
        
        with tempfile.NamedTemporaryFile(suffix=".mp4") as tmp_file:
            tmp_file.write(b"fake video content")
            tmp_file.seek(0)
            
            with patch('app.api.v1.endpoints.upload.upload_service.save_video_file') as mock_save, \
                 patch('app.api.v1.endpoints.upload.get_db') as mock_db:
                
                mock_save.return_value = ("/path/to/video.mp4", "hash123")
                mock_db_session = Mock()
                mock_db.return_value = mock_db_session
                
                response = client.post(
                    "/api/v1/upload/upload",
                    files={"file": ("test.mp4", tmp_file, "video/mp4")},
                    headers={"Authorization": "Bearer test_token"}
                )
                
                assert response.status_code == 200
                data = response.json()
                assert "task_id" in data
                assert data["filename"] == "test.mp4"
                assert data["estimated_cost"] == 150.0
    
    @patch('app.api.v1.endpoints.upload.get_current_user')
    @patch('app.api.v1.endpoints.upload.check_upload_rate_limit')
    def test_upload_video_rate_limited(self, mock_rate_limit, mock_user, client):
        """Test video upload with rate limiting."""
        mock_user.return_value = Mock(id="user123")
        mock_rate_limit.return_value = {"allowed": False, "retry_after": 3600}
        
        with tempfile.NamedTemporaryFile(suffix=".mp4") as tmp_file:
            tmp_file.write(b"fake video content")
            tmp_file.seek(0)
            
            response = client.post(
                "/api/v1/upload/upload",
                files={"file": ("test.mp4", tmp_file, "video/mp4")},
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 429
            assert "rate limit exceeded" in response.json()["detail"]
    
    @patch('app.api.v1.endpoints.upload.get_current_user')
    @patch('app.api.v1.endpoints.upload.check_upload_rate_limit')
    @patch('app.api.v1.endpoints.upload.upload_service.validate_video_file')
    def test_upload_video_validation_failed(self, mock_validate, mock_rate_limit, mock_user, client):
        """Test video upload with validation failure."""
        mock_user.return_value = Mock(id="user123")
        mock_rate_limit.return_value = {"allowed": True}
        mock_validate.return_value = VideoValidationResult(
            is_valid=False,
            file_size=1000000,
            errors=["Unsupported format"]
        )
        
        with tempfile.NamedTemporaryFile(suffix=".mp4") as tmp_file:
            tmp_file.write(b"fake video content")
            tmp_file.seek(0)
            
            response = client.post(
                "/api/v1/upload/upload",
                files={"file": ("test.mp4", tmp_file, "video/mp4")},
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 400
            assert "validation failed" in response.json()["detail"]["error"]
    
    def test_get_upload_limits(self, client):
        """Test getting upload limits endpoint."""
        with patch('app.api.v1.endpoints.upload.get_current_user') as mock_user, \
             patch('app.api.v1.endpoints.upload.check_upload_rate_limit') as mock_rate_limit:
            
            mock_user.return_value = Mock(id="user123")
            mock_rate_limit.return_value = {"allowed": True, "remaining": 5}
            
            response = client.get(
                "/api/v1/upload/limits",
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "max_video_size" in data
            assert "supported_video_formats" in data
            assert "rate_limit" in data

class TestSRTProcessor:
    """Test cases for SRT processing functionality."""
    
    @pytest.fixture
    def srt_processor(self):
        """Create SRT processor instance for testing."""
        from app.services.upload import SRTProcessor
        return SRTProcessor()
    
    @pytest.fixture
    def sample_srt_data(self):
        """Sample SRT data for testing."""
        return [
            {
                'index': 1,
                'start_time': 1.0,
                'end_time': 3.0,
                'text': 'Первая реплика персонажа'
            },
            {
                'index': 2,
                'start_time': 4.0,
                'end_time': 6.0,
                'text': 'ИВАН: Вторая реплика с указанием спикера'
            },
            {
                'index': 3,
                'start_time': 25.0,
                'end_time': 28.0,
                'text': 'Реплика во второй сцене'
            }
        ]
    
    @pytest.fixture
    def sample_scenes(self):
        """Sample video scenes for testing."""
        return [
            {
                'scene_id': 1,
                'start_time': 0.0,
                'end_time': 30.0,
                'duration': 30.0,
                'dialogue': [],
                'has_music': False
            },
            {
                'scene_id': 2,
                'start_time': 30.0,
                'end_time': 60.0,
                'duration': 30.0,
                'dialogue': [],
                'has_music': False
            }
        ]
    
    def test_detect_speaker(self, srt_processor):
        """Test speaker detection from subtitle text."""
        # Test speaker with colon
        assert srt_processor._detect_speaker("ИВАН: Привет, как дела?") == "ИВАН"
        assert srt_processor._detect_speaker("МАРИЯ: Хорошо, спасибо") == "МАРИЯ"
        
        # Test speaker in brackets
        assert srt_processor._detect_speaker("(ПЕТР) Что происходит?") == "ПЕТР"
        assert srt_processor._detect_speaker("[АННА] Не знаю") == "АННА"
        
        # Test no speaker
        assert srt_processor._detect_speaker("Просто текст без спикера") is None
        assert srt_processor._detect_speaker("обычная реплика") is None
    
    def test_split_into_sentences(self, srt_processor):
        """Test sentence splitting functionality."""
        # Single sentence
        result = srt_processor._split_into_sentences("Это одно предложение.")
        assert result == ["Это одно предложение."]
        
        # Multiple sentences
        result = srt_processor._split_into_sentences("Первое предложение. Второе предложение! Третье предложение?")
        assert len(result) == 3
        assert result[0] == "Первое предложение"
        assert result[1] == "Второе предложение"
        assert result[2] == "Третье предложение?"
        
        # No sentence endings
        result = srt_processor._split_into_sentences("Текст без окончаний")
        assert result == ["Текст без окончаний"]
    
    @pytest.mark.asyncio
    async def test_map_dialogue_to_scenes(self, srt_processor, sample_srt_data, sample_scenes):
        """Test mapping dialogue to video scenes."""
        result = await srt_processor._map_dialogue_to_scenes(sample_srt_data, sample_scenes)
        
        # Check that dialogue was mapped to correct scenes
        scene1 = result[0]
        scene2 = result[1]
        
        # First scene should have first two subtitles
        assert len(scene1['dialogue']) == 2
        assert scene1['dialogue'][0]['text'] == 'Первая реплика персонажа'
        assert scene1['dialogue'][1]['text'] == 'ИВАН: Вторая реплика с указанием спикера'
        assert scene1['dialogue'][1]['speaker'] == 'ИВАН'
        
        # Second scene should have the third subtitle
        assert len(scene2['dialogue']) == 0  # subtitle at 25s is still in first scene (0-30s)
    
    @pytest.mark.asyncio
    async def test_load_srt_file(self, srt_processor):
        """Test loading SRT file from disk."""
        # Create temporary SRT file
        srt_content = """1
00:00:01,000 --> 00:00:03,000
Тестовая реплика

2
00:00:04,500 --> 00:00:06,000
СПИКЕР: Вторая реплика
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as f:
            f.write(srt_content)
            temp_path = f.name
        
        try:
            result = await srt_processor._load_srt_file(temp_path)
            
            assert len(result) == 2
            assert result[0]['text'] == 'Тестовая реплика'
            assert result[1]['text'] == 'СПИКЕР: Вторая реплика'
            assert result[0]['start_time'] == 1.0
            assert result[1]['start_time'] == 4.5
            
        finally:
            os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_detect_video_scenes_mock(self, srt_processor):
        """Test video scene detection with mocked FFprobe."""
        with patch('subprocess.run') as mock_run:
            # Mock FFprobe response
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = '{"format": {"duration": "120.0"}}'
            
            result = await srt_processor._detect_video_scenes("/fake/video/path.mp4")
            
            # Should create scenes every 30 seconds for 120 second video
            assert len(result) == 5  # 0-30, 30-60, 60-90, 90-120, 120-120
            assert result[0]['start_time'] == 0.0
            assert result[0]['end_time'] == 30.0
            assert result[1]['start_time'] == 30.0
            assert result[1]['end_time'] == 60.0
    
    @pytest.mark.asyncio
    async def test_process_srt_with_video_integration(self, srt_processor):
        """Test full SRT processing integration."""
        # Create temporary SRT file
        srt_content = """1
00:00:01,000 --> 00:00:03,000
Начало фильма

2
00:00:35,000 --> 00:00:37,000
Вторая сцена
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as f:
            f.write(srt_content)
            srt_path = f.name
        
        try:
            with patch.object(srt_processor, '_get_video_metadata') as mock_metadata, \
                 patch.object(srt_processor, '_detect_video_scenes') as mock_scenes:
                
                mock_metadata.return_value = {'duration': 60.0}
                mock_scenes.return_value = [
                    {
                        'scene_id': 1,
                        'start_time': 0.0,
                        'end_time': 30.0,
                        'duration': 30.0,
                        'dialogue': [],
                        'has_music': False
                    },
                    {
                        'scene_id': 2,
                        'start_time': 30.0,
                        'end_time': 60.0,
                        'duration': 30.0,
                        'dialogue': [],
                        'has_music': False
                    }
                ]
                
                result = await srt_processor.process_srt_with_video(srt_path, "/fake/video.mp4")
                
                assert result['processing_mode'] == 'srt_mode'
                assert result['total_duration'] == 60.0
                assert result['subtitle_count'] == 2
                assert len(result['scenes']) == 2
                
                # Check dialogue mapping
                scenes = result['scenes']
                assert len(scenes[0]['dialogue']) == 1  # First subtitle in first scene
                assert len(scenes[1]['dialogue']) == 1  # Second subtitle in second scene
                
        finally:
            os.unlink(srt_path)