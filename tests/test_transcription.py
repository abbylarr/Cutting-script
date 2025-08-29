"""
Unit tests for transcription services.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from pathlib import Path

from app.services.transcription import (
    WhisperTranscriptionService,
    FallbackTranscriptionService,
    TranscriptionService,
    TranscriptionResult,
    TranscriptionSegment,
    TranscriptionError,
    RateLimitError,
    RetryHandler
)


class TestRetryHandler:
    """Test retry handler functionality."""
    
    @pytest.mark.asyncio
    async def test_successful_execution_no_retry(self):
        """Test successful execution without retries."""
        retry_handler = RetryHandler(max_retries=3, base_delay=0.1)
        
        async def success_func():
            return "success"
        
        result = await retry_handler.with_exponential_backoff(success_func)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_retry_on_rate_limit_error(self):
        """Test retry logic on rate limit errors."""
        retry_handler = RetryHandler(max_retries=3, base_delay=0.1)
        
        call_count = 0
        
        async def rate_limit_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                from openai import RateLimitError
                raise RateLimitError("Rate limit exceeded, try again in 1 seconds")
            return "success"
        
        with patch('openai.RateLimitError', Exception):
            result = await retry_handler.with_exponential_backoff(rate_limit_func)
            assert result == "success"
            assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test behavior when max retries are exceeded."""
        retry_handler = RetryHandler(max_retries=2, base_delay=0.1)
        
        async def always_fail_func():
            from openai import RateLimitError
            raise RateLimitError("Rate limit exceeded")
        
        with patch('openai.RateLimitError', Exception):
            with pytest.raises(RateLimitError):
                await retry_handler.with_exponential_backoff(always_fail_func)
    
    def test_parse_retry_delay(self):
        """Test parsing retry delay from error messages."""
        retry_handler = RetryHandler()
        
        # Test various error message formats
        assert retry_handler._parse_retry_delay("try again in 5 seconds") == 5.0
        assert retry_handler._parse_retry_delay("retry after 10.5 seconds") == 10.5
        assert retry_handler._parse_retry_delay("please wait 2 seconds") == 2.0
        assert retry_handler._parse_retry_delay("no delay mentioned") is None


class TestWhisperTranscriptionService:
    """Test OpenAI Whisper transcription service."""
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings with API key."""
        with patch('app.services.transcription.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = "test-api-key"
            yield mock_settings
    
    @pytest.fixture
    def transcription_service(self, mock_settings):
        """Create transcription service with mocked dependencies."""
        with patch('app.services.transcription.AsyncOpenAI'):
            return WhisperTranscriptionService()
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_success(self, transcription_service):
        """Test successful audio transcription."""
        # Mock file operations
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.stat') as mock_stat, \
             patch('builtins.open', mock_open(read_data=b'audio data')):
            
            mock_stat.return_value.st_size = 1024 * 1024  # 1MB
            
            # Mock OpenAI response
            mock_response = MagicMock()
            mock_response.model_dump.return_value = {
                "text": "Тестовая транскрипция",
                "language": "ru",
                "duration": 10.5,
                "task": "transcribe",
                "segments": [
                    {
                        "id": 0,
                        "seek": 0.0,
                        "start": 0.0,
                        "end": 10.5,
                        "text": "Тестовая транскрипция",
                        "tokens": [1, 2, 3],
                        "temperature": 0.0,
                        "avg_logprob": -0.5,
                        "compression_ratio": 1.2,
                        "no_speech_prob": 0.1
                    }
                ]
            }
            
            transcription_service.client.audio.transcriptions.create = AsyncMock(return_value=mock_response)
            
            result = await transcription_service.transcribe_audio("test_audio.wav")
            
            assert isinstance(result, TranscriptionResult)
            assert result.text == "Тестовая транскрипция"
            assert result.language == "ru"
            assert result.duration == 10.5
            assert len(result.segments) == 1
            assert result.segments[0].text == "Тестовая транскрипция"
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_file_not_found(self, transcription_service):
        """Test transcription with non-existent file."""
        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(TranscriptionError, match="Audio file not found"):
                await transcription_service.transcribe_audio("nonexistent.wav")
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_file_too_large(self, transcription_service):
        """Test transcription with file exceeding size limit."""
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.stat') as mock_stat:
            
            mock_stat.return_value.st_size = 30 * 1024 * 1024  # 30MB (exceeds 25MB limit)
            
            with pytest.raises(TranscriptionError, match="Audio file too large"):
                await transcription_service.transcribe_audio("large_audio.wav")
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_with_rate_limit(self, transcription_service):
        """Test transcription with rate limit handling."""
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.stat') as mock_stat, \
             patch('builtins.open', mock_open(read_data=b'audio data')):
            
            mock_stat.return_value.st_size = 1024 * 1024  # 1MB
            
            # Mock rate limit error then success
            call_count = 0
            
            async def mock_create(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    from openai import RateLimitError
                    raise RateLimitError("Rate limit exceeded, try again in 1 seconds")
                
                mock_response = MagicMock()
                mock_response.model_dump.return_value = {
                    "text": "Success after retry",
                    "language": "ru",
                    "duration": 5.0,
                    "segments": []
                }
                return mock_response
            
            transcription_service.client.audio.transcriptions.create = mock_create
            
            with patch('openai.RateLimitError', Exception):
                result = await transcription_service.transcribe_audio("test_audio.wav")
                assert result.text == "Success after retry"
                assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_transcribe_multiple_segments(self, transcription_service):
        """Test transcribing multiple audio segments."""
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.stat') as mock_stat, \
             patch('builtins.open', mock_open(read_data=b'audio data')):
            
            mock_stat.return_value.st_size = 1024 * 1024  # 1MB
            
            # Mock successful responses
            mock_response = MagicMock()
            mock_response.model_dump.return_value = {
                "text": "Segment text",
                "language": "ru",
                "duration": 5.0,
                "segments": []
            }
            
            transcription_service.client.audio.transcriptions.create = AsyncMock(return_value=mock_response)
            
            segments = ["segment1.wav", "segment2.wav", "segment3.wav"]
            results = await transcription_service.transcribe_audio_segments(segments)
            
            assert len(results) == 3
            for result in results:
                assert isinstance(result, TranscriptionResult)
                assert result.text == "Segment text"
    
    def test_get_transcription_cost(self, transcription_service):
        """Test transcription cost calculation."""
        # Test 1 minute
        cost_1min = asyncio.run(transcription_service.get_transcription_cost(60.0))
        assert cost_1min == 0.006
        
        # Test 2.5 minutes
        cost_2_5min = asyncio.run(transcription_service.get_transcription_cost(150.0))
        assert cost_2_5min == 0.015


class TestFallbackTranscriptionService:
    """Test fallback transcription service."""
    
    @pytest.fixture
    def fallback_service(self):
        """Create fallback transcription service."""
        return FallbackTranscriptionService()
    
    @pytest.mark.asyncio
    async def test_fallback_transcription(self, fallback_service):
        """Test fallback transcription functionality."""
        with patch('app.services.video_processor.AudioExtractionService') as mock_audio_service:
            # Mock audio info
            mock_service_instance = AsyncMock()
            mock_service_instance.get_audio_info.return_value = {
                'format': {'duration': '30.0'}
            }
            mock_audio_service.return_value = mock_service_instance
            
            result = await fallback_service.transcribe_audio("test_audio.wav")
            
            assert isinstance(result, TranscriptionResult)
            assert result.language == "ru"
            assert result.duration == 30.0
            assert len(result.segments) == len(fallback_service.fallback_texts)
            assert "Тестовая транскрипция" in result.text
    
    @pytest.mark.asyncio
    async def test_fallback_transcription_no_audio_info(self, fallback_service):
        """Test fallback transcription when audio info is unavailable."""
        with patch('app.services.video_processor.AudioExtractionService', side_effect=Exception("No audio service")):
            result = await fallback_service.transcribe_audio("test_audio.wav")
            
            assert isinstance(result, TranscriptionResult)
            assert result.duration == 60.0  # Default duration
            assert len(result.segments) > 0


class TestTranscriptionService:
    """Test main transcription service with fallback."""
    
    @pytest.fixture
    def mock_settings_with_key(self):
        """Mock settings with API key."""
        with patch('app.services.transcription.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = "test-api-key"
            yield mock_settings
    
    @pytest.fixture
    def mock_settings_no_key(self):
        """Mock settings without API key."""
        with patch('app.services.transcription.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = ""
            yield mock_settings
    
    @pytest.mark.asyncio
    async def test_transcription_service_with_primary(self, mock_settings_with_key):
        """Test transcription service with primary service available."""
        with patch('app.services.transcription.AsyncOpenAI'):
            service = TranscriptionService()
            
            assert service.primary_service is not None
            assert await service.is_primary_service_available() is True
    
    @pytest.mark.asyncio
    async def test_transcription_service_without_primary(self, mock_settings_no_key):
        """Test transcription service without primary service."""
        service = TranscriptionService()
        
        assert service.primary_service is None
        assert await service.is_primary_service_available() is False
    
    @pytest.mark.asyncio
    async def test_transcription_with_fallback_forced(self, mock_settings_with_key):
        """Test transcription with forced fallback."""
        with patch('app.services.transcription.AsyncOpenAI'):
            service = TranscriptionService()
            
            with patch.object(service.fallback_service, 'transcribe_audio') as mock_fallback:
                mock_result = TranscriptionResult(
                    text="Fallback result",
                    language="ru",
                    duration=10.0,
                    segments=[]
                )
                mock_fallback.return_value = mock_result
                
                result = await service.transcribe_audio("test.wav", use_fallback=True)
                
                assert result.text == "Fallback result"
                mock_fallback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_transcription_primary_fails_fallback_used(self, mock_settings_with_key):
        """Test automatic fallback when primary service fails."""
        with patch('app.services.transcription.AsyncOpenAI'):
            service = TranscriptionService()
            
            # Mock primary service to fail
            with patch.object(service.primary_service, 'transcribe_audio', side_effect=TranscriptionError("API failed")), \
                 patch.object(service.fallback_service, 'transcribe_audio') as mock_fallback:
                
                mock_result = TranscriptionResult(
                    text="Fallback after failure",
                    language="ru",
                    duration=10.0,
                    segments=[]
                )
                mock_fallback.return_value = mock_result
                
                result = await service.transcribe_audio("test.wav")
                
                assert result.text == "Fallback after failure"
                mock_fallback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_service_status(self, mock_settings_with_key):
        """Test service status reporting."""
        with patch('app.services.transcription.AsyncOpenAI'):
            service = TranscriptionService()
            
            status = await service.get_service_status()
            
            assert isinstance(status, dict)
            assert "primary_available" in status
            assert "openai_api_key_configured" in status
            assert "fallback_available" in status
            assert "current_time" in status
            assert status["fallback_available"] is True


@pytest.mark.asyncio
async def test_transcription_integration():
    """Integration test for transcription service."""
    # This test would require actual audio files and API keys
    # For now, we'll test the service initialization and basic functionality
    
    with patch('app.services.transcription.settings') as mock_settings:
        mock_settings.OPENAI_API_KEY = ""
        
        service = TranscriptionService()
        
        # Should fall back to fallback service
        assert service.primary_service is None
        
        # Test status
        status = await service.get_service_status()
        assert status["primary_available"] is False
        assert status["fallback_available"] is True