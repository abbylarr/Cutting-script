"""
Unit tests for video processing services.
"""
import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import tempfile
import os

from app.services.video_processor import (
    VideoValidationService,
    AudioExtractionService,
    SceneDetectionService,
    VideoMetadata,
    ValidationResult,
    Scene,
    VideoValidationError,
    FFmpegError
)


class TestVideoValidationService:
    """Test cases for VideoValidationService."""
    
    @pytest.fixture
    def validation_service(self):
        """Create a VideoValidationService instance."""
        with patch.object(VideoValidationService, '_check_ffmpeg_availability'):
            return VideoValidationService()
    
    @pytest.fixture
    def sample_metadata(self):
        """Sample video metadata for testing."""
        return VideoMetadata(
            duration=120.5,
            fps=25.0,
            width=1920,
            height=1080,
            codec='h264',
            format='mp4',
            bitrate=5000000,
            audio_codec='aac',
            audio_channels=2,
            audio_sample_rate=48000
        )
    
    @pytest.mark.asyncio
    async def test_validate_video_success(self, validation_service, sample_metadata):
        """Test successful video validation."""
        with patch.object(validation_service, '_extract_metadata', return_value=sample_metadata):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.stat') as mock_stat:
                    mock_stat.return_value.st_size = 100 * 1024 * 1024  # 100MB
                    
                    result = await validation_service.validate_video('/test/video.mp4')
                    
                    assert result.is_valid is True
                    assert result.metadata == sample_metadata
                    assert result.error is None
    
    @pytest.mark.asyncio
    async def test_validate_video_file_not_exists(self, validation_service):
        """Test validation with non-existent file."""
        with patch('pathlib.Path.exists', return_value=False):
            result = await validation_service.validate_video('/nonexistent/video.mp4')
            
            assert result.is_valid is False
            assert "does not exist" in result.error
    
    @pytest.mark.asyncio
    async def test_validate_video_file_too_large(self, validation_service):
        """Test validation with file too large."""
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.stat') as mock_stat:
                mock_stat.return_value.st_size = 3 * 1024 * 1024 * 1024  # 3GB
                
                result = await validation_service.validate_video('/test/large_video.mp4')
                
                assert result.is_valid is False
                assert "exceeds maximum allowed size" in result.error
    
    @pytest.mark.asyncio
    async def test_validate_video_empty_file(self, validation_service):
        """Test validation with empty file."""
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.stat') as mock_stat:
                mock_stat.return_value.st_size = 0
                
                result = await validation_service.validate_video('/test/empty_video.mp4')
                
                assert result.is_valid is False
                assert "empty" in result.error
    
    @pytest.mark.asyncio
    async def test_validate_video_unsupported_format(self, validation_service, sample_metadata):
        """Test validation with unsupported format."""
        sample_metadata.format = 'unsupported'
        
        with patch.object(validation_service, '_extract_metadata', return_value=sample_metadata):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.stat') as mock_stat:
                    mock_stat.return_value.st_size = 100 * 1024 * 1024
                    
                    result = await validation_service.validate_video('/test/video.unsupported')
                    
                    assert result.is_valid is False
                    assert "Unsupported video format" in result.error
    
    @pytest.mark.asyncio
    async def test_validate_video_duration_too_short(self, validation_service, sample_metadata):
        """Test validation with video too short."""
        sample_metadata.duration = 0.5  # Less than 1 second
        
        with patch.object(validation_service, '_extract_metadata', return_value=sample_metadata):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.stat') as mock_stat:
                    mock_stat.return_value.st_size = 100 * 1024 * 1024
                    
                    result = await validation_service.validate_video('/test/short_video.mp4')
                    
                    assert result.is_valid is False
                    assert "too short" in result.error
    
    @pytest.mark.asyncio
    async def test_validate_video_duration_too_long(self, validation_service, sample_metadata):
        """Test validation with video too long."""
        sample_metadata.duration = 5 * 60 * 60  # 5 hours
        
        with patch.object(validation_service, '_extract_metadata', return_value=sample_metadata):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.stat') as mock_stat:
                    mock_stat.return_value.st_size = 100 * 1024 * 1024
                    
                    result = await validation_service.validate_video('/test/long_video.mp4')
                    
                    assert result.is_valid is False
                    assert "too long" in result.error
    
    @pytest.mark.asyncio
    async def test_extract_metadata_success(self, validation_service):
        """Test successful metadata extraction."""
        mock_probe_output = {
            'format': {
                'duration': '120.5',
                'format_name': 'mov,mp4,m4a,3gp,3g2,mj2',
                'bit_rate': '5000000'
            },
            'streams': [
                {
                    'codec_type': 'video',
                    'codec_name': 'h264',
                    'width': 1920,
                    'height': 1080,
                    'r_frame_rate': '25/1'
                },
                {
                    'codec_type': 'audio',
                    'codec_name': 'aac',
                    'channels': 2,
                    'sample_rate': '48000'
                }
            ]
        }
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (
                json.dumps(mock_probe_output).encode('utf-8'),
                b''
            )
            mock_subprocess.return_value = mock_process
            
            metadata = await validation_service._extract_metadata('/test/video.mp4')
            
            assert metadata.duration == 120.5
            assert metadata.fps == 25.0
            assert metadata.width == 1920
            assert metadata.height == 1080
            assert metadata.codec == 'h264'
            assert metadata.format == 'mov'
            assert metadata.bitrate == 5000000
            assert metadata.audio_codec == 'aac'
            assert metadata.audio_channels == 2
            assert metadata.audio_sample_rate == 48000
    
    @pytest.mark.asyncio
    async def test_extract_metadata_no_video_stream(self, validation_service):
        """Test metadata extraction with no video stream."""
        mock_probe_output = {
            'format': {'duration': '120.5'},
            'streams': [
                {
                    'codec_type': 'audio',
                    'codec_name': 'aac'
                }
            ]
        }
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (
                json.dumps(mock_probe_output).encode('utf-8'),
                b''
            )
            mock_subprocess.return_value = mock_process
            
            with pytest.raises(FFmpegError, match="Metadata extraction failed"):
                await validation_service._extract_metadata('/test/audio_only.mp4')
    
    @pytest.mark.asyncio
    async def test_check_video_integrity_success(self, validation_service):
        """Test successful video integrity check."""
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (b'', b'')
            mock_subprocess.return_value = mock_process
            
            is_valid, error = await validation_service.check_video_integrity('/test/video.mp4')
            
            assert is_valid is True
            assert error is None
    
    @pytest.mark.asyncio
    async def test_check_video_integrity_failure(self, validation_service):
        """Test video integrity check failure."""
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 1
            mock_process.communicate.return_value = (b'', b'Error: corrupt video')
            mock_subprocess.return_value = mock_process
            
            is_valid, error = await validation_service.check_video_integrity('/test/corrupt_video.mp4')
            
            assert is_valid is False
            assert "integrity check failed" in error


class TestAudioExtractionService:
    """Test cases for AudioExtractionService."""
    
    @pytest.fixture
    def audio_service(self):
        """Create an AudioExtractionService instance."""
        with patch.object(AudioExtractionService, '_check_ffmpeg_availability'):
            return AudioExtractionService()
    
    @pytest.mark.asyncio
    async def test_extract_audio_success(self, audio_service):
        """Test successful audio extraction."""
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (b'', b'')
            mock_subprocess.return_value = mock_process
            
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.mkdir'):
                    output_path = await audio_service.extract_audio('/test/video.mp4')
                    
                    assert output_path.endswith('_audio.wav')
                    mock_subprocess.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_extract_audio_failure(self, audio_service):
        """Test audio extraction failure."""
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 1
            mock_process.communicate.return_value = (b'', b'FFmpeg error')
            mock_subprocess.return_value = mock_process
            
            with patch('pathlib.Path.mkdir'):
                with pytest.raises(FFmpegError, match="Audio extraction failed"):
                    await audio_service.extract_audio('/test/video.mp4')
    
    @pytest.mark.asyncio
    async def test_extract_audio_segment_success(self, audio_service):
        """Test successful audio segment extraction."""
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (b'', b'')
            mock_subprocess.return_value = mock_process
            
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.mkdir'):
                    output_path = await audio_service.extract_audio_segment(
                        '/test/video.mp4', 
                        start_time=10.0, 
                        duration=30.0
                    )
                    
                    assert '10.0s' in output_path
                    mock_subprocess.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_audio_info_success(self, audio_service):
        """Test successful audio info extraction."""
        mock_audio_info = {
            'format': {'duration': '60.0'},
            'streams': [{'codec_type': 'audio', 'codec_name': 'pcm_s16le'}]
        }
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (
                json.dumps(mock_audio_info).encode('utf-8'),
                b''
            )
            mock_subprocess.return_value = mock_process
            
            info = await audio_service.get_audio_info('/test/audio.wav')
            
            assert info == mock_audio_info


class TestSceneDetectionService:
    """Test cases for SceneDetectionService."""
    
    @pytest.fixture
    def scene_service(self):
        """Create a SceneDetectionService instance."""
        with patch.object(SceneDetectionService, '_check_scenedetect_availability'):
            return SceneDetectionService()
    
    @pytest.fixture
    def sample_scenes(self):
        """Sample scenes for testing."""
        return [
            Scene(start_time=0.0, end_time=10.0, duration=10.0, scene_number=1),
            Scene(start_time=10.0, end_time=25.0, duration=15.0, scene_number=2),
            Scene(start_time=25.0, end_time=40.0, duration=15.0, scene_number=3),
        ]
    
    @pytest.mark.asyncio
    async def test_detect_scenes_success(self, scene_service):
        """Test successful scene detection."""
        # Mock scenedetect classes
        mock_scene_list = [
            (Mock(get_seconds=Mock(return_value=0.0)), Mock(get_seconds=Mock(return_value=10.0))),
            (Mock(get_seconds=Mock(return_value=10.0)), Mock(get_seconds=Mock(return_value=25.0))),
            (Mock(get_seconds=Mock(return_value=25.0)), Mock(get_seconds=Mock(return_value=40.0))),
        ]
        
        with patch('scenedetect.VideoManager') as mock_vm:
            with patch('scenedetect.SceneManager') as mock_sm:
                with patch('scenedetect.detectors.ContentDetector'):
                    mock_vm_instance = Mock()
                    mock_sm_instance = Mock()
                    mock_sm_instance.get_scene_list.return_value = mock_scene_list
                    
                    mock_vm.return_value = mock_vm_instance
                    mock_sm.return_value = mock_sm_instance
                    
                    scenes = await scene_service.detect_scenes('/test/video.mp4')
                    
                    assert len(scenes) == 3
                    assert scenes[0].start_time == 0.0
                    assert scenes[0].end_time == 10.0
                    assert scenes[0].duration == 10.0
                    assert scenes[0].scene_number == 1
    
    @pytest.mark.asyncio
    async def test_detect_scenes_filter_short(self, scene_service):
        """Test scene detection with short scene filtering."""
        # Mock scene list with one short scene
        mock_scene_list = [
            (Mock(get_seconds=Mock(return_value=0.0)), Mock(get_seconds=Mock(return_value=10.0))),
            (Mock(get_seconds=Mock(return_value=10.0)), Mock(get_seconds=Mock(return_value=11.0))),  # 1 second - too short
            (Mock(get_seconds=Mock(return_value=11.0)), Mock(get_seconds=Mock(return_value=25.0))),
        ]
        
        with patch('scenedetect.VideoManager') as mock_vm:
            with patch('scenedetect.SceneManager') as mock_sm:
                with patch('scenedetect.detectors.ContentDetector'):
                    mock_vm_instance = Mock()
                    mock_sm_instance = Mock()
                    mock_sm_instance.get_scene_list.return_value = mock_scene_list
                    
                    mock_vm.return_value = mock_vm_instance
                    mock_sm.return_value = mock_sm_instance
                    
                    scenes = await scene_service.detect_scenes('/test/video.mp4', min_scene_length=2.0)
                    
                    # Should filter out the 1-second scene
                    assert len(scenes) == 2
                    assert scenes[0].duration == 10.0
                    assert scenes[1].duration == 14.0  # 25 - 11
    
    @pytest.mark.asyncio
    async def test_merge_short_gaps(self, scene_service):
        """Test merging scenes with short gaps."""
        scenes = [
            Scene(start_time=0.0, end_time=10.0, duration=10.0, scene_number=1),
            Scene(start_time=10.2, end_time=20.0, duration=9.8, scene_number=2),  # 0.2s gap
            Scene(start_time=25.0, end_time=35.0, duration=10.0, scene_number=3),  # 5s gap
        ]
        
        merged = await scene_service._merge_short_gaps(scenes, min_gap=0.5)
        
        # First two scenes should be merged due to short gap
        assert len(merged) == 2
        assert merged[0].start_time == 0.0
        assert merged[0].end_time == 20.0
        assert merged[0].duration == 20.0
        assert merged[1].start_time == 25.0
        assert merged[1].end_time == 35.0
    
    @pytest.mark.asyncio
    async def test_detect_scenes_with_fallback(self, scene_service):
        """Test scene detection with fallback to more sensitive detection."""
        # First call returns few scenes, second call returns more
        mock_scene_list_few = [
            (Mock(get_seconds=Mock(return_value=0.0)), Mock(get_seconds=Mock(return_value=40.0))),
        ]
        
        mock_scene_list_many = [
            (Mock(get_seconds=Mock(return_value=0.0)), Mock(get_seconds=Mock(return_value=10.0))),
            (Mock(get_seconds=Mock(return_value=10.0)), Mock(get_seconds=Mock(return_value=25.0))),
            (Mock(get_seconds=Mock(return_value=25.0)), Mock(get_seconds=Mock(return_value=40.0))),
        ]
        
        with patch.object(scene_service, 'detect_scenes') as mock_detect:
            # First call returns 1 scene, second call returns 3 scenes
            mock_detect.side_effect = [
                [Scene(start_time=0.0, end_time=40.0, duration=40.0, scene_number=1)],
                [
                    Scene(start_time=0.0, end_time=10.0, duration=10.0, scene_number=1),
                    Scene(start_time=10.0, end_time=25.0, duration=15.0, scene_number=2),
                    Scene(start_time=25.0, end_time=40.0, duration=15.0, scene_number=3),
                ]
            ]
            
            scenes = await scene_service.detect_scenes_with_fallback('/test/video.mp4')
            
            # Should use fallback result with 3 scenes
            assert len(scenes) == 3
            assert mock_detect.call_count == 2
    
    @pytest.mark.asyncio
    async def test_get_scene_statistics(self, scene_service, sample_scenes):
        """Test scene statistics calculation."""
        stats = await scene_service.get_scene_statistics(sample_scenes)
        
        assert stats['total_scenes'] == 3
        assert stats['total_duration'] == 40.0  # 10 + 15 + 15
        assert stats['average_duration'] == 40.0 / 3
        assert stats['shortest_scene'] == 10.0
        assert stats['longest_scene'] == 15.0
        assert len(stats['scene_durations']) == 3
    
    @pytest.mark.asyncio
    async def test_get_scene_statistics_empty(self, scene_service):
        """Test scene statistics with empty scene list."""
        stats = await scene_service.get_scene_statistics([])
        
        assert stats['total_scenes'] == 0
        assert stats['total_duration'] == 0
        assert stats['average_duration'] == 0
        assert stats['shortest_scene'] == 0
        assert stats['longest_scene'] == 0


class TestSceneDataClass:
    """Test cases for Scene dataclass."""
    
    def test_scene_post_init_calculates_duration(self):
        """Test that Scene calculates duration in __post_init__."""
        scene = Scene(start_time=10.0, end_time=25.0, duration=0, scene_number=1)
        
        assert scene.duration == 15.0
    
    def test_scene_post_init_preserves_duration(self):
        """Test that Scene preserves provided duration."""
        scene = Scene(start_time=10.0, end_time=25.0, duration=12.0, scene_number=1)
        
        assert scene.duration == 12.0


if __name__ == "__main__":
    pytest.main([__file__])