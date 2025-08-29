"""
Unit tests for keyframe extraction service.
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import subprocess

from app.services.keyframe_extraction import (
    KeyframeExtractionService, 
    Keyframe, 
    Scene
)


@pytest.fixture
def temp_output_dir():
    """Create a temporary directory for test outputs."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def keyframe_service(temp_output_dir):
    """Create a keyframe extraction service with temporary output directory."""
    return KeyframeExtractionService(output_dir=temp_output_dir)


@pytest.fixture
def sample_scenes():
    """Create sample scenes for testing."""
    return [
        Scene(start_time=0.0, end_time=10.0, duration=10.0),
        Scene(start_time=10.0, end_time=25.0, duration=15.0),
        Scene(start_time=25.0, end_time=30.0, duration=5.0)
    ]


class TestScene:
    """Test Scene data structure."""
    
    def test_scene_keyframe_positions(self):
        """Test keyframe position calculations."""
        scene = Scene(start_time=10.0, end_time=30.0, duration=20.0)
        
        assert scene.keyframe_35_time == 17.0  # 10 + (20 * 0.35)
        assert scene.keyframe_70_time == 24.0  # 10 + (20 * 0.70)
    
    def test_scene_short_duration(self):
        """Test keyframe positions for short scenes."""
        scene = Scene(start_time=0.0, end_time=2.0, duration=2.0)
        
        assert scene.keyframe_35_time == 0.7   # 0 + (2 * 0.35)
        assert scene.keyframe_70_time == 1.4   # 0 + (2 * 0.70)


class TestKeyframeExtractionService:
    """Test KeyframeExtractionService functionality."""
    
    @pytest.mark.asyncio
    async def test_extract_keyframes_from_scenes_success(self, keyframe_service, sample_scenes):
        """Test successful keyframe extraction from scenes."""
        video_path = "test_video.mp4"
        task_id = "test_task_123"
        
        # Mock the single keyframe extraction
        with patch.object(keyframe_service, '_extract_single_keyframe') as mock_extract:
            # Mock successful extractions
            mock_extract.side_effect = [
                Keyframe(0, 35.0, 3.5, "/path/to/scene_000_35pct.jpg"),
                Keyframe(0, 70.0, 7.0, "/path/to/scene_000_70pct.jpg"),
                Keyframe(1, 35.0, 15.25, "/path/to/scene_001_35pct.jpg"),
                Keyframe(1, 70.0, 20.5, "/path/to/scene_001_70pct.jpg"),
                Keyframe(2, 35.0, 26.75, "/path/to/scene_002_35pct.jpg"),
                Keyframe(2, 70.0, 28.5, "/path/to/scene_002_70pct.jpg")
            ]
            
            # Mock quality assessment
            with patch.object(keyframe_service, '_assess_frame_quality', return_value=0.8):
                keyframes = await keyframe_service.extract_keyframes_from_scenes(
                    video_path, sample_scenes, task_id
                )
        
        assert len(keyframes) == 6  # 2 keyframes per scene * 3 scenes
        assert all(kf.quality_score == 0.8 for kf in keyframes)
        
        # Verify extraction calls
        assert mock_extract.call_count == 6
    
    @pytest.mark.asyncio
    async def test_extract_keyframes_with_failures(self, keyframe_service, sample_scenes):
        """Test keyframe extraction with some failures."""
        video_path = "test_video.mp4"
        task_id = "test_task_456"
        
        with patch.object(keyframe_service, '_extract_single_keyframe') as mock_extract:
            # Mock mixed success/failure
            mock_extract.side_effect = [
                Keyframe(0, 35.0, 3.5, "/path/to/scene_000_35pct.jpg"),
                None,  # Failed extraction
                Keyframe(1, 35.0, 15.25, "/path/to/scene_001_35pct.jpg"),
                Keyframe(1, 70.0, 20.5, "/path/to/scene_001_70pct.jpg"),
                None,  # Failed extraction
                Keyframe(2, 70.0, 28.5, "/path/to/scene_002_70pct.jpg")
            ]
            
            with patch.object(keyframe_service, '_assess_frame_quality', return_value=0.7):
                keyframes = await keyframe_service.extract_keyframes_from_scenes(
                    video_path, sample_scenes, task_id
                )
        
        assert len(keyframes) == 4  # Only successful extractions
        assert all(kf.quality_score == 0.7 for kf in keyframes)
    
    @pytest.mark.asyncio
    async def test_extract_single_keyframe_success(self, keyframe_service, temp_output_dir):
        """Test successful single keyframe extraction."""
        video_path = "test_video.mp4"
        timestamp = 15.5
        scene_index = 2
        position_percent = 35.0
        output_dir = Path(temp_output_dir) / "test_task"
        output_dir.mkdir()
        
        # Mock FFmpeg subprocess
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"", b"")
        
        expected_output = output_dir / "scene_002_35pct.jpg"
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch.object(Path, 'exists', return_value=True):
                keyframe = await keyframe_service._extract_single_keyframe(
                    video_path, timestamp, scene_index, position_percent, output_dir
                )
        
        assert keyframe is not None
        assert keyframe.scene_index == 2
        assert keyframe.position_percent == 35.0
        assert keyframe.timestamp == 15.5
        assert keyframe.file_path == str(expected_output)
    
    @pytest.mark.asyncio
    async def test_extract_single_keyframe_ffmpeg_failure(self, keyframe_service, temp_output_dir):
        """Test keyframe extraction with FFmpeg failure."""
        video_path = "test_video.mp4"
        timestamp = 15.5
        scene_index = 2
        position_percent = 70.0
        output_dir = Path(temp_output_dir) / "test_task"
        output_dir.mkdir()
        
        # Mock FFmpeg failure
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"Error: Invalid input")
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            keyframe = await keyframe_service._extract_single_keyframe(
                video_path, timestamp, scene_index, position_percent, output_dir
            )
        
        assert keyframe is None
    
    @pytest.mark.asyncio
    async def test_extract_single_keyframe_file_not_created(self, keyframe_service, temp_output_dir):
        """Test keyframe extraction when output file is not created."""
        video_path = "test_video.mp4"
        timestamp = 15.5
        scene_index = 1
        position_percent = 35.0
        output_dir = Path(temp_output_dir) / "test_task"
        output_dir.mkdir()
        
        # Mock successful FFmpeg but file not created
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"", b"")
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch.object(Path, 'exists', return_value=False):
                keyframe = await keyframe_service._extract_single_keyframe(
                    video_path, timestamp, scene_index, position_percent, output_dir
                )
        
        assert keyframe is None
    
    @pytest.mark.asyncio
    async def test_assess_frame_quality_success(self, keyframe_service):
        """Test frame quality assessment."""
        image_path = "/path/to/test_frame.jpg"
        
        # Mock FFmpeg quality analysis
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"", b"Progressive scan detected")
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            quality = await keyframe_service._assess_frame_quality(image_path)
        
        assert 0.0 <= quality <= 1.0
        assert quality == 1.0  # No quality issues detected
    
    @pytest.mark.asyncio
    async def test_assess_frame_quality_with_issues(self, keyframe_service):
        """Test frame quality assessment with detected issues."""
        image_path = "/path/to/test_frame.jpg"
        
        # Mock FFmpeg output with quality issues
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (
            b"", 
            b"Interlaced video detected\ncrop=1920:1080:0:0"
        )
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            quality = await keyframe_service._assess_frame_quality(image_path)
        
        assert quality < 1.0  # Quality reduced due to interlacing
        assert quality >= 0.0
    
    @pytest.mark.asyncio
    async def test_assess_frame_quality_failure(self, keyframe_service):
        """Test frame quality assessment with FFmpeg failure."""
        image_path = "/path/to/test_frame.jpg"
        
        # Mock FFmpeg failure
        with patch('asyncio.create_subprocess_exec', side_effect=Exception("FFmpeg error")):
            quality = await keyframe_service._assess_frame_quality(image_path)
        
        assert quality == 0.5  # Default quality score on failure
    
    def test_parse_quality_metrics_clean_output(self, keyframe_service):
        """Test parsing quality metrics from clean FFmpeg output."""
        clean_output = "Progressive scan detected\nNo issues found"
        
        quality = keyframe_service._parse_quality_metrics(clean_output)
        
        assert quality == 1.0
    
    def test_parse_quality_metrics_with_interlacing(self, keyframe_service):
        """Test parsing quality metrics with interlacing detected."""
        interlaced_output = "Interlaced video detected\nTFF detected"
        
        quality = keyframe_service._parse_quality_metrics(interlaced_output)
        
        assert quality == 0.8  # 1.0 - 0.2 for interlacing
    
    def test_parse_quality_metrics_with_cropping(self, keyframe_service):
        """Test parsing quality metrics with cropping detected."""
        crop_output = "crop=1920:1080:10:10 detected"
        
        quality = keyframe_service._parse_quality_metrics(crop_output)
        
        assert quality == 0.9  # 1.0 - 0.1 for cropping
    
    def test_parse_quality_metrics_multiple_issues(self, keyframe_service):
        """Test parsing quality metrics with multiple issues."""
        issues_output = "Interlaced video detected\ncrop=1920:1080:20:20"
        
        quality = keyframe_service._parse_quality_metrics(issues_output)
        
        assert abs(quality - 0.7) < 0.001  # 1.0 - 0.2 - 0.1 for both issues (with floating point tolerance)
    
    @pytest.mark.asyncio
    async def test_optimize_keyframe_storage_success(self, keyframe_service):
        """Test successful keyframe storage optimization."""
        keyframes = [
            Keyframe(0, 35.0, 3.5, "/path/to/scene_000_35pct.jpg", 0.8),
            Keyframe(0, 70.0, 7.0, "/path/to/scene_000_70pct.jpg", 0.9)
        ]
        
        with patch.object(keyframe_service, '_create_optimized_image') as mock_optimize:
            mock_optimize.side_effect = [
                "/path/to/scene_000_35pct_opt.jpg",
                "/path/to/scene_000_70pct_opt.jpg"
            ]
            
            optimized = await keyframe_service.optimize_keyframe_storage(keyframes)
        
        assert len(optimized) == 2
        assert optimized[0].file_path == "/path/to/scene_000_35pct_opt.jpg"
        assert optimized[1].file_path == "/path/to/scene_000_70pct_opt.jpg"
        assert optimized[0].quality_score == 0.8
        assert optimized[1].quality_score == 0.9
    
    @pytest.mark.asyncio
    async def test_optimize_keyframe_storage_with_failures(self, keyframe_service):
        """Test keyframe optimization with some failures."""
        keyframes = [
            Keyframe(0, 35.0, 3.5, "/path/to/scene_000_35pct.jpg", 0.8),
            Keyframe(0, 70.0, 7.0, "/path/to/scene_000_70pct.jpg", 0.9)
        ]
        
        with patch.object(keyframe_service, '_create_optimized_image') as mock_optimize:
            mock_optimize.side_effect = [
                "/path/to/scene_000_35pct_opt.jpg",
                None  # Optimization failed
            ]
            
            optimized = await keyframe_service.optimize_keyframe_storage(keyframes)
        
        assert len(optimized) == 2
        assert optimized[0].file_path == "/path/to/scene_000_35pct_opt.jpg"  # Optimized
        assert optimized[1].file_path == "/path/to/scene_000_70pct.jpg"     # Original kept
    
    @pytest.mark.asyncio
    async def test_create_optimized_image_success(self, keyframe_service, temp_output_dir):
        """Test successful image optimization."""
        original_path = Path(temp_output_dir) / "test_frame.jpg"
        original_path.touch()  # Create empty file
        
        # Mock successful FFmpeg optimization
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"", b"")
        
        expected_optimized = original_path.parent / "test_frame_opt.jpg"
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch.object(Path, 'exists', return_value=True):
                result = await keyframe_service._create_optimized_image(str(original_path))
        
        assert result == str(expected_optimized)
    
    @pytest.mark.asyncio
    async def test_create_optimized_image_failure(self, keyframe_service, temp_output_dir):
        """Test image optimization failure."""
        original_path = Path(temp_output_dir) / "test_frame.jpg"
        original_path.touch()
        
        # Mock FFmpeg failure
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"Error")
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result = await keyframe_service._create_optimized_image(str(original_path))
        
        assert result is None
    
    def test_cleanup_keyframes_success(self, keyframe_service, temp_output_dir):
        """Test successful keyframe cleanup."""
        task_id = "test_task_cleanup"
        task_dir = Path(temp_output_dir) / task_id
        task_dir.mkdir()
        
        # Create some test files
        (task_dir / "scene_001_35pct.jpg").touch()
        (task_dir / "scene_001_70pct.jpg").touch()
        
        assert task_dir.exists()
        
        keyframe_service.cleanup_keyframes(task_id)
        
        assert not task_dir.exists()
    
    def test_cleanup_keyframes_nonexistent_task(self, keyframe_service):
        """Test cleanup for non-existent task (should not raise error)."""
        task_id = "nonexistent_task"
        
        # Should not raise an exception
        keyframe_service.cleanup_keyframes(task_id)


@pytest.mark.integration
class TestKeyframeExtractionIntegration:
    """Integration tests for keyframe extraction with real FFmpeg."""
    
    @pytest.mark.asyncio
    async def test_extract_keyframes_with_test_video(self, keyframe_service):
        """Test keyframe extraction with a real test video (if available)."""
        # This test would require a real test video file
        # Skip if FFmpeg is not available
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"], 
                capture_output=True, 
                check=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("FFmpeg not available for integration test")
        
        # Test would continue with actual video processing
        # For now, just verify FFmpeg is available
        assert "ffmpeg version" in result.stdout.decode().lower()