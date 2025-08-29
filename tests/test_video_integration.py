"""
Integration tests for video processing services.
"""
import pytest
from unittest.mock import patch, AsyncMock
from app.services.video_processor import (
    VideoValidationService,
    AudioExtractionService,
    SceneDetectionService,
    VideoMetadata
)


class TestVideoProcessingIntegration:
    """Integration tests for video processing pipeline."""
    
    @pytest.mark.asyncio
    async def test_video_processing_pipeline_integration(self):
        """Test that all video processing services can work together."""
        
        # Mock video metadata
        mock_metadata = VideoMetadata(
            duration=120.0,
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
        
        # Test video validation service
        with patch.object(VideoValidationService, '_check_ffmpeg_availability'):
            validation_service = VideoValidationService()
            
            with patch.object(validation_service, '_extract_metadata', return_value=mock_metadata):
                with patch('pathlib.Path.exists', return_value=True):
                    with patch('pathlib.Path.stat') as mock_stat:
                        mock_stat.return_value.st_size = 100 * 1024 * 1024  # 100MB
                        
                        result = await validation_service.validate_video('/test/video.mp4')
                        assert result.is_valid is True
                        assert result.metadata.duration == 120.0
        
        # Test audio extraction service
        with patch.object(AudioExtractionService, '_check_ffmpeg_availability'):
            audio_service = AudioExtractionService()
            
            with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                mock_process = AsyncMock()
                mock_process.returncode = 0
                mock_process.communicate.return_value = (b'', b'')
                mock_subprocess.return_value = mock_process
                
                with patch('pathlib.Path.exists', return_value=True):
                    with patch('pathlib.Path.mkdir'):
                        audio_path = await audio_service.extract_audio('/test/video.mp4')
                        assert audio_path.endswith('_audio.wav')
        
        # Test scene detection service (without OpenCV dependencies)
        with patch.object(SceneDetectionService, '_check_scenedetect_availability'):
            scene_service = SceneDetectionService()
            
            # Test scene statistics with mock data
            from app.services.video_processor import Scene
            mock_scenes = [
                Scene(start_time=0.0, end_time=30.0, duration=30.0, scene_number=1),
                Scene(start_time=30.0, end_time=60.0, duration=30.0, scene_number=2),
                Scene(start_time=60.0, end_time=120.0, duration=60.0, scene_number=3),
            ]
            
            stats = await scene_service.get_scene_statistics(mock_scenes)
            assert stats['total_scenes'] == 3
            assert stats['total_duration'] == 120.0
            assert stats['average_duration'] == 40.0
    
    @pytest.mark.asyncio
    async def test_error_handling_integration(self):
        """Test error handling across services."""
        
        # Test validation service error handling
        with patch.object(VideoValidationService, '_check_ffmpeg_availability'):
            validation_service = VideoValidationService()
            
            # Test with non-existent file
            with patch('pathlib.Path.exists', return_value=False):
                result = await validation_service.validate_video('/nonexistent/video.mp4')
                assert result.is_valid is False
                assert "does not exist" in result.error
        
        # Test audio service error handling
        with patch.object(AudioExtractionService, '_check_ffmpeg_availability'):
            audio_service = AudioExtractionService()
            
            with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                mock_process = AsyncMock()
                mock_process.returncode = 1
                mock_process.communicate.return_value = (b'', b'FFmpeg error')
                mock_subprocess.return_value = mock_process
                
                with patch('pathlib.Path.mkdir'):
                    from app.services.video_processor import FFmpegError
                    with pytest.raises(FFmpegError):
                        await audio_service.extract_audio('/test/video.mp4')


if __name__ == "__main__":
    pytest.main([__file__])