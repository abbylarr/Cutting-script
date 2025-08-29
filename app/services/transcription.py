"""
Speech transcription services for filmlist application.
Handles OpenAI Whisper API integration with retry logic and fallback mechanisms.
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

import openai
from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionSegment:
    """Represents a segment of transcribed text with timing information."""
    id: int
    seek: float
    start: float
    end: float
    text: str
    tokens: List[int]
    temperature: float
    avg_logprob: float
    compression_ratio: float
    no_speech_prob: float


@dataclass
class TranscriptionResult:
    """Result of audio transcription."""
    text: str
    language: str
    duration: float
    segments: List[TranscriptionSegment]
    task: str = "transcribe"


class TranscriptionError(Exception):
    """Raised when transcription fails."""
    pass


class RateLimitError(Exception):
    """Raised when API rate limit is exceeded."""
    pass


class RetryHandler:
    """Handles retry logic with exponential backoff for API calls."""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
    
    async def with_exponential_backoff(self, func, *args, **kwargs) -> Any:
        """
        Execute function with exponential backoff retry logic.
        
        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If all retries are exhausted
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except openai.RateLimitError as e:
                last_exception = e
                if attempt == self.max_retries - 1:
                    raise RateLimitError(f"Rate limit exceeded after {self.max_retries} attempts: {e}")
                
                # Parse retry delay from error message
                delay = self._parse_retry_delay(str(e)) or (self.base_delay * (2 ** attempt))
                logger.warning(f"Rate limit hit, retrying in {delay:.1f}s (attempt {attempt + 1}/{self.max_retries})")
                await asyncio.sleep(delay)
                
            except (openai.APIError, openai.APIConnectionError) as e:
                last_exception = e
                if attempt == self.max_retries - 1:
                    raise TranscriptionError(f"API error after {self.max_retries} attempts: {e}")
                
                delay = self.base_delay * (2 ** attempt)
                logger.warning(f"API error, retrying in {delay:.1f}s (attempt {attempt + 1}/{self.max_retries}): {e}")
                await asyncio.sleep(delay)
                
            except Exception as e:
                # For other exceptions, don't retry
                raise TranscriptionError(f"Transcription failed: {e}")
        
        # This should never be reached, but just in case
        raise TranscriptionError(f"All retries exhausted. Last error: {last_exception}")
    
    def _parse_retry_delay(self, error_message: str) -> Optional[float]:
        """
        Parse retry delay from OpenAI error messages.
        
        Args:
            error_message: Error message from OpenAI API
            
        Returns:
            Delay in seconds if found, None otherwise
        """
        # Look for patterns like "try again in X seconds" or "retry after X seconds"
        patterns = [
            r'try again in (\d+(?:\.\d+)?) seconds?',
            r'retry after (\d+(?:\.\d+)?) seconds?',
            r'please wait (\d+(?:\.\d+)?) seconds?'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, error_message, re.IGNORECASE)
            if match:
                return float(match.group(1))
        
        return None


class WhisperTranscriptionService:
    """Service for transcribing audio using OpenAI Whisper API."""
    
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required for transcription service")
        
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.retry_handler = RetryHandler(max_retries=3, base_delay=1.0)
        
        # Whisper API settings
        self.model = "whisper-1"
        self.language = "ru"  # Russian language
        self.response_format = "verbose_json"  # Get detailed timing information
        self.temperature = 0.0  # Deterministic output
    
    async def transcribe_audio(
        self, 
        audio_path: str, 
        language: Optional[str] = None,
        prompt: Optional[str] = None
    ) -> TranscriptionResult:
        """
        Transcribe audio file using OpenAI Whisper API.
        
        Args:
            audio_path: Path to the audio file
            language: Language code (defaults to Russian)
            prompt: Optional prompt to guide transcription
            
        Returns:
            TranscriptionResult with transcribed text and timing information
            
        Raises:
            TranscriptionError: If transcription fails
            RateLimitError: If rate limit is exceeded
        """
        if not Path(audio_path).exists():
            raise TranscriptionError(f"Audio file not found: {audio_path}")
        
        # Check file size (Whisper API has 25MB limit)
        file_size = Path(audio_path).stat().st_size
        max_size = 25 * 1024 * 1024  # 25MB
        if file_size > max_size:
            raise TranscriptionError(f"Audio file too large: {file_size / (1024**2):.1f}MB (max 25MB)")
        
        language = language or self.language
        
        logger.info(f"Starting transcription for {audio_path} (language: {language})")
        
        try:
            # Use retry handler for the transcription call
            result = await self.retry_handler.with_exponential_backoff(
                self._transcribe_with_client,
                audio_path,
                language,
                prompt
            )
            
            logger.info(f"Transcription completed for {audio_path}")
            return result
            
        except Exception as e:
            logger.error(f"Transcription failed for {audio_path}: {e}")
            raise
    
    async def _transcribe_with_client(
        self, 
        audio_path: str, 
        language: str, 
        prompt: Optional[str]
    ) -> TranscriptionResult:
        """
        Internal method to perform transcription with OpenAI client.
        
        Args:
            audio_path: Path to the audio file
            language: Language code
            prompt: Optional prompt
            
        Returns:
            TranscriptionResult
        """
        with open(audio_path, "rb") as audio_file:
            # Prepare transcription parameters
            transcription_params = {
                "file": audio_file,
                "model": self.model,
                "language": language,
                "response_format": self.response_format,
                "temperature": self.temperature
            }
            
            # Add prompt if provided
            if prompt:
                transcription_params["prompt"] = prompt
            
            # Call OpenAI Whisper API
            response = await self.client.audio.transcriptions.create(**transcription_params)
        
        # Parse response based on format
        if self.response_format == "verbose_json":
            return self._parse_verbose_response(response)
        else:
            # Simple text response
            return TranscriptionResult(
                text=response.text,
                language=language,
                duration=0.0,
                segments=[]
            )
    
    def _parse_verbose_response(self, response) -> TranscriptionResult:
        """
        Parse verbose JSON response from Whisper API.
        
        Args:
            response: API response object
            
        Returns:
            TranscriptionResult with detailed information
        """
        # Convert response to dict if needed
        if hasattr(response, 'model_dump'):
            data = response.model_dump()
        else:
            data = response
        
        # Parse segments
        segments = []
        for seg_data in data.get("segments", []):
            segment = TranscriptionSegment(
                id=seg_data.get("id", 0),
                seek=seg_data.get("seek", 0.0),
                start=seg_data.get("start", 0.0),
                end=seg_data.get("end", 0.0),
                text=seg_data.get("text", ""),
                tokens=seg_data.get("tokens", []),
                temperature=seg_data.get("temperature", 0.0),
                avg_logprob=seg_data.get("avg_logprob", 0.0),
                compression_ratio=seg_data.get("compression_ratio", 0.0),
                no_speech_prob=seg_data.get("no_speech_prob", 0.0)
            )
            segments.append(segment)
        
        return TranscriptionResult(
            text=data.get("text", ""),
            language=data.get("language", "ru"),
            duration=data.get("duration", 0.0),
            segments=segments,
            task=data.get("task", "transcribe")
        )
    
    async def transcribe_audio_segments(
        self, 
        audio_segments: List[str], 
        language: Optional[str] = None
    ) -> List[TranscriptionResult]:
        """
        Transcribe multiple audio segments concurrently.
        
        Args:
            audio_segments: List of paths to audio segment files
            language: Language code (defaults to Russian)
            
        Returns:
            List of TranscriptionResult objects
        """
        language = language or self.language
        
        # Create transcription tasks
        tasks = [
            self.transcribe_audio(segment_path, language)
            for segment_path in audio_segments
        ]
        
        # Execute with limited concurrency to avoid rate limits
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent requests
        
        async def transcribe_with_semaphore(task):
            async with semaphore:
                return await task
        
        # Wait for all transcriptions to complete
        results = await asyncio.gather(
            *[transcribe_with_semaphore(task) for task in tasks],
            return_exceptions=True
        )
        
        # Process results and handle exceptions
        transcription_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Transcription failed for segment {i}: {result}")
                # Create empty result for failed transcription
                transcription_results.append(TranscriptionResult(
                    text="",
                    language=language,
                    duration=0.0,
                    segments=[]
                ))
            else:
                transcription_results.append(result)
        
        return transcription_results
    
    async def get_transcription_cost(self, audio_duration: float) -> float:
        """
        Calculate estimated cost for transcription.
        
        Args:
            audio_duration: Duration of audio in seconds
            
        Returns:
            Estimated cost in USD
        """
        # OpenAI Whisper pricing: $0.006 per minute
        cost_per_minute = 0.006
        duration_minutes = audio_duration / 60.0
        return duration_minutes * cost_per_minute


class FallbackTranscriptionService:
    """Fallback transcription service for when OpenAI API is unavailable."""
    
    def __init__(self):
        self.fallback_texts = [
            "Тестовая транскрипция для демонстрации работы системы.",
            "Это пример текста, который используется когда OpenAI API недоступен.",
            "Система продолжает работать с тестовыми данными.",
            "Автоматическая транскрипция временно недоступна."
        ]
    
    async def transcribe_audio(
        self, 
        audio_path: str, 
        language: Optional[str] = None
    ) -> TranscriptionResult:
        """
        Provide fallback transcription when OpenAI API is unavailable.
        
        Args:
            audio_path: Path to the audio file (used for duration calculation)
            language: Language code (ignored in fallback)
            
        Returns:
            TranscriptionResult with test data
        """
        logger.warning(f"Using fallback transcription for {audio_path}")
        
        # Try to get audio duration from file
        try:
            from app.services.video_processor import AudioExtractionService
            audio_service = AudioExtractionService()
            audio_info = await audio_service.get_audio_info(audio_path)
            
            format_info = audio_info.get('format', {})
            duration = float(format_info.get('duration', 60.0))
        except Exception:
            # Default duration if we can't get it from file
            duration = 60.0
        
        # Create test segments
        segment_duration = duration / len(self.fallback_texts)
        segments = []
        
        for i, text in enumerate(self.fallback_texts):
            start_time = i * segment_duration
            end_time = (i + 1) * segment_duration
            
            segment = TranscriptionSegment(
                id=i,
                seek=start_time,
                start=start_time,
                end=end_time,
                text=text,
                tokens=[],
                temperature=0.0,
                avg_logprob=-0.5,
                compression_ratio=1.0,
                no_speech_prob=0.1
            )
            segments.append(segment)
        
        full_text = " ".join(self.fallback_texts)
        
        return TranscriptionResult(
            text=full_text,
            language="ru",
            duration=duration,
            segments=segments,
            task="transcribe"
        )


class TranscriptionService:
    """Main transcription service with fallback capabilities and health monitoring."""
    
    def __init__(self):
        self.primary_service = None
        self.fallback_service = FallbackTranscriptionService()
        
        # Try to initialize primary service
        try:
            self.primary_service = WhisperTranscriptionService()
            logger.info("OpenAI Whisper transcription service initialized")
        except ValueError as e:
            logger.warning(f"OpenAI service not available: {e}")
    
    async def transcribe_audio(
        self, 
        audio_path: str, 
        language: Optional[str] = None,
        use_fallback: bool = False
    ) -> TranscriptionResult:
        """
        Transcribe audio with automatic fallback based on service health.
        
        Args:
            audio_path: Path to the audio file
            language: Language code (defaults to Russian)
            use_fallback: Force use of fallback service
            
        Returns:
            TranscriptionResult
        """
        # Import health monitor here to avoid circular imports
        from app.core.health_monitor import health_monitor
        
        # Check if we should use fallback
        if use_fallback or not self.primary_service:
            logger.info("Using fallback transcription service")
            return await self.fallback_service.transcribe_audio(audio_path, language)
        
        # Use health monitor to determine service availability
        async with health_monitor.with_fallback("openai") as fallback:
            if fallback.should_use_fallback():
                logger.warning("OpenAI service unhealthy, using fallback transcription")
                return await self.fallback_service.transcribe_audio(audio_path, language)
            
            try:
                # Try primary service
                result = await self.primary_service.transcribe_audio(audio_path, language)
                logger.info(f"Transcription completed successfully using OpenAI")
                return result
                
            except (TranscriptionError, RateLimitError) as e:
                logger.error(f"Primary transcription failed: {e}")
                
                # If service is degraded, we might still try fallback
                if fallback.is_service_degraded():
                    logger.info("Service degraded, using fallback transcription")
                    return await self.fallback_service.transcribe_audio(audio_path, language)
                
                # Re-raise the exception if service should be healthy
                raise
    
    async def transcribe_audio_with_retry(
        self,
        audio_path: str,
        language: Optional[str] = None,
        max_retries: int = 2,
        retry_delay: float = 5.0
    ) -> TranscriptionResult:
        """
        Transcribe audio with retry logic and automatic fallback.
        
        Args:
            audio_path: Path to the audio file
            language: Language code (defaults to Russian)
            max_retries: Maximum number of retries
            retry_delay: Delay between retries in seconds
            
        Returns:
            TranscriptionResult
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return await self.transcribe_audio(audio_path, language)
                
            except (TranscriptionError, RateLimitError) as e:
                last_exception = e
                
                if attempt < max_retries:
                    logger.warning(
                        f"Transcription attempt {attempt + 1} failed, retrying in {retry_delay}s: {e}"
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 1.5  # Exponential backoff
                else:
                    logger.error(f"All transcription attempts failed, using fallback")
                    return await self.fallback_service.transcribe_audio(audio_path, language)
        
        # This should never be reached, but just in case
        return await self.fallback_service.transcribe_audio(audio_path, language)
    
    async def is_primary_service_available(self) -> bool:
        """
        Check if primary transcription service is available.
        
        Returns:
            True if OpenAI service is available, False otherwise
        """
        if not self.primary_service:
            return False
        
        # Check health monitor status
        from app.core.health_monitor import health_monitor
        return health_monitor.is_service_healthy("openai")
    
    async def get_service_status(self) -> Dict[str, Any]:
        """
        Get detailed status of transcription services.
        
        Returns:
            Dictionary with service status information
        """
        from app.core.health_monitor import health_monitor
        
        openai_info = health_monitor.get_service_info("openai")
        
        return {
            "primary_service": {
                "available": self.primary_service is not None,
                "health_status": openai_info["status"] if openai_info else "unknown",
                "last_check": openai_info["last_check"] if openai_info else None,
                "success_rate": openai_info["success_rate"] if openai_info else 0,
                "average_response_time": openai_info["average_response_time"] if openai_info else 0
            },
            "fallback_service": {
                "available": True,
                "type": "test_data"
            },
            "configuration": {
                "openai_api_key_configured": bool(settings.OPENAI_API_KEY),
                "model": "whisper-1",
                "language": "ru"
            },
            "current_time": datetime.utcnow().isoformat()
        }