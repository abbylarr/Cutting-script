"""
Unit tests for speaker diarization services.
"""

import asyncio
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from pathlib import Path

# Mock pyannote.audio before importing our services
sys.modules['pyannote'] = MagicMock()
sys.modules['pyannote.audio'] = MagicMock()

from app.services.diarization import (
    PyAnnoteDiarizationService,
    FallbackDiarizationService,
    SpeakerDiarizationService,
    SpeakerSegment,
    DiarizationResult,
    DiarizationError
)


class TestSpeakerSegment:
    """Test SpeakerSegment dataclass."""
    
    def test_speaker_segment_creation(self):
        """Test creating a speaker segment."""
        segment = SpeakerSegment(
            start=0.0,
            end=5.0,
            speaker="SPEAKER_00",
            confidence=0.8
        )
        
        assert segment.start == 0.0
        assert segment.end == 5.0
        assert segment.speaker == "SPEAKER_00"
        assert segment.confidence == 0.8


class TestDiarizationResult:
    """Test DiarizationResult dataclass."""
    
    def test_diarization_result_creation(self):
        """Test creating a diarization result."""
        segments = [
            SpeakerSegment(0.0, 5.0, "SPEAKER_00", 0.8),
            SpeakerSegment(5.0, 10.0, "SPEAKER_01", 0.9)
        ]
        
        result = DiarizationResult(
            segments=segments,
            num_speakers=2,
            total_duration=10.0,
            speaker_labels=["SPEAKER_00", "SPEAKER_01"]
        )
        
        assert len(result.segments) == 2
        assert result.num_speakers == 2
        assert result.total_duration == 10.0
        assert result.speaker_labels == ["SPEAKER_00", "SPEAKER_01"]


class TestPyAnnoteDiarizationService:
    """Test PyAnnote diarization service."""
    
    @pytest.fixture
    def mock_settings_with_token(self):
        """Mock settings with HF token."""
        with patch('app.services.diarization.settings') as mock_settings:
            mock_settings.HF_TOKEN = "test-hf-token"
            yield mock_settings
    
    @pytest.fixture
    def mock_settings_no_token(self):
        """Mock settings without HF token."""
        with patch('app.services.diarization.settings') as mock_settings:
            mock_settings.HF_TOKEN = None
            yield mock_settings
    
    @pytest.fixture
    def diarization_service(self, mock_settings_with_token):
        """Create diarization service with mocked dependencies."""
        return PyAnnoteDiarizationService()
    
    def test_init_with_token(self, mock_settings_with_token):
        """Test initialization with HF token."""
        service = PyAnnoteDiarizationService()
        assert service.hf_token == "test-hf-token"
        assert not service._initialized
    
    def test_init_without_token(self, mock_settings_no_token):
        """Test initialization without HF token."""
        service = PyAnnoteDiarizationService()
        assert service.hf_token is None
        assert not service._initialized
    
    @pytest.mark.asyncio
    async def test_initialize_pipeline_success(self, diarization_service):
        """Test successful pipeline initialization."""
        mock_pipeline = MagicMock()
        
        with patch('pyannote.audio.Pipeline') as mock_pipeline_class:
            mock_pipeline_class.from_pretrained.return_value = mock_pipeline
            
            await diarization_service._initialize_pipeline()
            
            assert diarization_service._initialized
            assert diarization_service.pipeline == mock_pipeline
            mock_pipeline_class.from_pretrained.assert_called_once_with(
                "pyannote/speaker-diarization-3.1",
                use_auth_token="test-hf-token"
            )
    
    @pytest.mark.asyncio
    async def test_initialize_pipeline_no_token(self):
        """Test pipeline initialization without HF token."""
        with patch('app.services.diarization.settings') as mock_settings:
            mock_settings.HF_TOKEN = None
            service = PyAnnoteDiarizationService()
            
            with pytest.raises(DiarizationError, match="HF_TOKEN is required"):
                await service._initialize_pipeline()
    
    @pytest.mark.asyncio
    async def test_initialize_pipeline_import_error(self, diarization_service):
        """Test pipeline initialization with import error."""
        # Mock the import to raise ImportError
        def mock_import(name, *args, **kwargs):
            if name == 'pyannote.audio':
                raise ImportError("Module not found")
            return __import__(name, *args, **kwargs)
        
        with patch('builtins.__import__', side_effect=mock_import):
            with pytest.raises(DiarizationError, match="pyannote.audio not available"):
                await diarization_service._initialize_pipeline()
    
    @pytest.mark.asyncio
    async def test_diarize_audio_success(self, diarization_service):
        """Test successful audio diarization."""
        # Mock file existence
        with patch('pathlib.Path.exists', return_value=True):
            # Mock pipeline initialization
            mock_pipeline = MagicMock()
            diarization_service.pipeline = mock_pipeline
            diarization_service._initialized = True
            
            # Mock diarization result
            mock_diarization = MagicMock()
            mock_diarization.itertracks.return_value = [
                (MagicMock(start=0.0, end=5.0), None, "SPEAKER_00"),
                (MagicMock(start=5.0, end=10.0), None, "SPEAKER_01")
            ]
            
            # Mock the thread pool execution
            with patch.object(diarization_service, '_run_diarization', return_value=mock_diarization):
                result = await diarization_service.diarize_audio("test_audio.wav")
                
                assert isinstance(result, DiarizationResult)
                assert result.num_speakers == 2
                assert len(result.segments) == 2
                assert result.speaker_labels == ["SPEAKER_00", "SPEAKER_01"]
    
    @pytest.mark.asyncio
    async def test_diarize_audio_file_not_found(self, diarization_service):
        """Test diarization with non-existent file."""
        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(DiarizationError, match="Audio file not found"):
                await diarization_service.diarize_audio("nonexistent.wav")
    
    def test_convert_diarization_result(self, diarization_service):
        """Test conversion of pyannote diarization result."""
        # Mock pyannote diarization output
        mock_diarization = MagicMock()
        mock_diarization.itertracks.return_value = [
            (MagicMock(start=0.0, end=5.0), None, "SPEAKER_00"),
            (MagicMock(start=5.0, end=8.0), None, "SPEAKER_01"),
            (MagicMock(start=8.0, end=12.0), None, "SPEAKER_00")
        ]
        
        result = diarization_service._convert_diarization_result(mock_diarization)
        
        assert isinstance(result, DiarizationResult)
        assert result.num_speakers == 2
        assert len(result.segments) == 3
        assert result.total_duration == 12.0
        assert result.speaker_labels == ["SPEAKER_00", "SPEAKER_01"]
        
        # Check segments are sorted by start time
        for i in range(len(result.segments) - 1):
            assert result.segments[i].start <= result.segments[i + 1].start
    
    @pytest.mark.asyncio
    async def test_is_available_with_token(self, diarization_service):
        """Test availability check with HF token."""
        assert await diarization_service.is_available() is True
    
    @pytest.mark.asyncio
    async def test_is_available_without_token(self):
        """Test availability check without HF token."""
        with patch('app.services.diarization.settings') as mock_settings:
            mock_settings.HF_TOKEN = None
            service = PyAnnoteDiarizationService()
            
            assert await service.is_available() is False
    
    @pytest.mark.asyncio
    async def test_get_voice_activity_detection(self, diarization_service):
        """Test voice activity detection."""
        with patch('pathlib.Path.exists', return_value=True):
            # Mock VAD pipeline
            mock_vad_pipeline = MagicMock()
            mock_vad_result = MagicMock()
            mock_vad_result.get_timeline.return_value = [
                MagicMock(start=0.0, end=3.0),
                MagicMock(start=5.0, end=8.0)
            ]
            mock_vad_pipeline.return_value = mock_vad_result
            
            with patch('pyannote.audio.Pipeline') as mock_pipeline_class:
                mock_pipeline_class.from_pretrained.return_value = mock_vad_pipeline
                
                # Mock thread pool execution
                async def mock_executor(executor, func, *args):
                    return func(*args)
                
                with patch('asyncio.get_event_loop') as mock_loop:
                    mock_loop.return_value.run_in_executor = mock_executor
                    
                    segments = await diarization_service.get_voice_activity_detection("test_audio.wav")
                    
                    assert len(segments) == 2
                    assert segments[0] == (0.0, 3.0)
                    assert segments[1] == (5.0, 8.0)


class TestFallbackDiarizationService:
    """Test fallback diarization service."""
    
    @pytest.fixture
    def fallback_service(self):
        """Create fallback diarization service."""
        return FallbackDiarizationService()
    
    @pytest.mark.asyncio
    async def test_diarize_audio_with_audio_info(self, fallback_service):
        """Test fallback diarization with audio info."""
        with patch('app.services.video_processor.AudioExtractionService') as mock_audio_service:
            # Mock audio info
            mock_service_instance = AsyncMock()
            mock_service_instance.get_audio_info.return_value = {
                'format': {'duration': '20.0'}
            }
            mock_audio_service.return_value = mock_service_instance
            
            result = await fallback_service.diarize_audio("test_audio.wav", num_speakers=3)
            
            assert isinstance(result, DiarizationResult)
            assert result.num_speakers == 3
            assert result.total_duration == 20.0
            assert len(result.segments) == 6  # 3 speakers * 2 segments each
            assert len(result.speaker_labels) == 3
    
    @pytest.mark.asyncio
    async def test_diarize_audio_no_audio_info(self, fallback_service):
        """Test fallback diarization without audio info."""
        with patch('app.services.video_processor.AudioExtractionService', side_effect=Exception("No service")):
            result = await fallback_service.diarize_audio("test_audio.wav")
            
            assert isinstance(result, DiarizationResult)
            assert result.total_duration == 60.0  # Default duration
            assert result.num_speakers == 2  # Default number of speakers
    
    @pytest.mark.asyncio
    async def test_is_available(self, fallback_service):
        """Test fallback service availability."""
        assert await fallback_service.is_available() is True
    
    @pytest.mark.asyncio
    async def test_get_voice_activity_detection(self, fallback_service):
        """Test fallback voice activity detection."""
        with patch('app.services.video_processor.AudioExtractionService') as mock_audio_service:
            mock_service_instance = AsyncMock()
            mock_service_instance.get_audio_info.return_value = {
                'format': {'duration': '15.0'}
            }
            mock_audio_service.return_value = mock_service_instance
            
            segments = await fallback_service.get_voice_activity_detection("test_audio.wav")
            
            assert len(segments) > 0
            # Check that segments don't exceed total duration
            for start, end in segments:
                assert start >= 0.0
                assert end <= 15.0
                assert start < end


class TestSpeakerDiarizationService:
    """Test main speaker diarization service."""
    
    @pytest.fixture
    def mock_settings_with_token(self):
        """Mock settings with HF token."""
        with patch('app.services.diarization.settings') as mock_settings:
            mock_settings.HF_TOKEN = "test-hf-token"
            yield mock_settings
    
    @pytest.fixture
    def mock_settings_no_token(self):
        """Mock settings without HF token."""
        with patch('app.services.diarization.settings') as mock_settings:
            mock_settings.HF_TOKEN = None
            yield mock_settings
    
    @pytest.mark.asyncio
    async def test_diarization_service_with_primary(self, mock_settings_with_token):
        """Test diarization service with primary service available."""
        with patch('app.services.diarization.PyAnnoteDiarizationService'):
            service = SpeakerDiarizationService()
            
            assert service.primary_service is not None
    
    @pytest.mark.asyncio
    async def test_diarization_service_without_primary(self, mock_settings_no_token):
        """Test diarization service without primary service."""
        service = SpeakerDiarizationService()
        
        assert service.primary_service is None
    
    @pytest.mark.asyncio
    async def test_diarize_audio_with_fallback_forced(self, mock_settings_with_token):
        """Test diarization with forced fallback."""
        with patch('app.services.diarization.PyAnnoteDiarizationService'):
            service = SpeakerDiarizationService()
            
            with patch.object(service.fallback_service, 'diarize_audio') as mock_fallback:
                mock_result = DiarizationResult(
                    segments=[],
                    num_speakers=2,
                    total_duration=10.0,
                    speaker_labels=["SPEAKER_00", "SPEAKER_01"]
                )
                mock_fallback.return_value = mock_result
                
                result = await service.diarize_audio("test.wav", use_fallback=True)
                
                assert result.num_speakers == 2
                mock_fallback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_diarize_audio_primary_fails_fallback_used(self, mock_settings_with_token):
        """Test automatic fallback when primary service fails."""
        with patch('app.services.diarization.PyAnnoteDiarizationService') as mock_primary_class:
            mock_primary = AsyncMock()
            mock_primary.diarize_audio.side_effect = DiarizationError("Primary failed")
            mock_primary_class.return_value = mock_primary
            
            service = SpeakerDiarizationService()
            
            with patch.object(service.fallback_service, 'diarize_audio') as mock_fallback:
                mock_result = DiarizationResult(
                    segments=[],
                    num_speakers=1,
                    total_duration=5.0,
                    speaker_labels=["SPEAKER_00"]
                )
                mock_fallback.return_value = mock_result
                
                result = await service.diarize_audio("test.wav")
                
                assert result.num_speakers == 1
                mock_fallback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_assign_speaker_labels(self, mock_settings_no_token):
        """Test assigning custom speaker labels."""
        service = SpeakerDiarizationService()
        
        segments = [
            SpeakerSegment(0.0, 5.0, "SPEAKER_00", 0.8),
            SpeakerSegment(5.0, 10.0, "SPEAKER_01", 0.9),
            SpeakerSegment(10.0, 15.0, "SPEAKER_00", 0.7)
        ]
        
        custom_labels = {
            "SPEAKER_00": "Alice",
            "SPEAKER_01": "Bob"
        }
        
        updated_segments = await service.assign_speaker_labels(segments, custom_labels)
        
        assert len(updated_segments) == 3
        assert updated_segments[0].speaker == "Alice"
        assert updated_segments[1].speaker == "Bob"
        assert updated_segments[2].speaker == "Alice"
    
    @pytest.mark.asyncio
    async def test_merge_short_segments(self, mock_settings_no_token):
        """Test merging short segments."""
        service = SpeakerDiarizationService()
        
        segments = [
            SpeakerSegment(0.0, 0.5, "SPEAKER_00", 0.8),  # Short segment
            SpeakerSegment(0.5, 5.0, "SPEAKER_00", 0.9),  # Same speaker
            SpeakerSegment(5.0, 5.3, "SPEAKER_01", 0.7),  # Short segment
            SpeakerSegment(5.3, 10.0, "SPEAKER_02", 0.8)  # Different speaker
        ]
        
        merged_segments = await service.merge_short_segments(segments, min_duration=1.0)
        
        # First two segments should be merged (same speaker, first is short)
        # Third segment should remain separate (different speaker from fourth)
        assert len(merged_segments) == 3
        assert merged_segments[0].start == 0.0
        assert merged_segments[0].end == 5.0
        assert merged_segments[0].speaker == "SPEAKER_00"
    
    @pytest.mark.asyncio
    async def test_get_speaker_statistics(self, mock_settings_no_token):
        """Test getting speaker statistics."""
        service = SpeakerDiarizationService()
        
        segments = [
            SpeakerSegment(0.0, 5.0, "SPEAKER_00", 0.8),   # 5 seconds
            SpeakerSegment(5.0, 8.0, "SPEAKER_01", 0.9),   # 3 seconds
            SpeakerSegment(8.0, 12.0, "SPEAKER_00", 0.7)   # 4 seconds
        ]
        
        stats = await service.get_speaker_statistics(segments)
        
        assert stats["total_segments"] == 3
        assert stats["unique_speakers"] == 2
        assert stats["total_duration"] == 12.0
        assert stats["speaker_durations"]["SPEAKER_00"] == 9.0  # 5 + 4
        assert stats["speaker_durations"]["SPEAKER_01"] == 3.0
        assert stats["average_segment_duration"] == 4.0  # 12 / 3
    
    @pytest.mark.asyncio
    async def test_get_service_status(self, mock_settings_with_token):
        """Test service status reporting."""
        with patch('app.services.diarization.PyAnnoteDiarizationService') as mock_primary_class:
            mock_primary = AsyncMock()
            mock_primary.is_available.return_value = True
            mock_primary_class.return_value = mock_primary
            
            service = SpeakerDiarizationService()
            
            with patch.object(service, '_check_pyannote_installation', return_value=True):
                status = await service.get_service_status()
                
                assert isinstance(status, dict)
                assert "primary_available" in status
                assert "hf_token_configured" in status
                assert "fallback_available" in status
                assert "pyannote_audio_installed" in status
                assert "current_time" in status
                assert status["fallback_available"] is True
    
    def test_check_pyannote_installation_success(self, mock_settings_no_token):
        """Test checking pyannote installation when available."""
        service = SpeakerDiarizationService()
        
        with patch.dict('sys.modules', {'pyannote.audio': MagicMock()}):
            assert service._check_pyannote_installation() is True
    
    def test_check_pyannote_installation_failure(self, mock_settings_no_token):
        """Test checking pyannote installation when not available."""
        service = SpeakerDiarizationService()
        
        with patch.dict('sys.modules', {'pyannote.audio': None}):
            assert service._check_pyannote_installation() is False


@pytest.mark.asyncio
async def test_diarization_integration():
    """Integration test for diarization service."""
    # This test would require actual audio files and HF tokens
    # For now, we'll test the service initialization and basic functionality
    
    with patch('app.services.diarization.settings') as mock_settings:
        mock_settings.HF_TOKEN = None
        
        service = SpeakerDiarizationService()
        
        # Should fall back to fallback service
        assert service.primary_service is None
        
        # Test status
        status = await service.get_service_status()
        assert status["primary_available"] is False
        assert status["fallback_available"] is True