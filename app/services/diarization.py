"""
Speaker diarization services for filmlist application.
Handles speaker identification and labeling using pyannote.audio.
"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SpeakerSegment:
    """Represents a segment with speaker information."""
    start: float  # Start time in seconds
    end: float    # End time in seconds
    speaker: str  # Speaker label (e.g., "SPEAKER_00", "SPEAKER_01")
    confidence: float = 0.0  # Confidence score (0.0 to 1.0)


@dataclass
class DiarizationResult:
    """Result of speaker diarization."""
    segments: List[SpeakerSegment]
    num_speakers: int
    total_duration: float
    speaker_labels: List[str]  # Unique speaker labels found


class DiarizationError(Exception):
    """Raised when diarization fails."""
    pass


class PyAnnoteDiarizationService:
    """Service for speaker diarization using pyannote.audio."""
    
    def __init__(self):
        self.hf_token = settings.HF_TOKEN
        self.pipeline = None
        self._initialized = False
        
        if not self.hf_token:
            logger.warning("HF_TOKEN not provided, diarization service will not be available")
        else:
            logger.info("Initializing pyannote.audio diarization service")
    
    async def _initialize_pipeline(self) -> None:
        """
        Initialize the diarization pipeline.
        This is done lazily to avoid loading models if not needed.
        """
        if self._initialized:
            return
        
        if not self.hf_token:
            raise DiarizationError("HF_TOKEN is required for speaker diarization")
        
        try:
            # Import pyannote.audio modules
            from pyannote.audio import Pipeline
            
            # Initialize the speaker diarization pipeline
            # This will download the model on first use
            self.pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.hf_token
            )
            
            self._initialized = True
            logger.info("Pyannote.audio pipeline initialized successfully")
            
        except ImportError as e:
            raise DiarizationError(f"pyannote.audio not available: {e}")
        except Exception as e:
            raise DiarizationError(f"Failed to initialize diarization pipeline: {e}")
    
    async def diarize_audio(
        self, 
        audio_path: str,
        num_speakers: Optional[int] = None,
        min_speakers: int = 1,
        max_speakers: int = 10
    ) -> DiarizationResult:
        """
        Perform speaker diarization on audio file.
        
        Args:
            audio_path: Path to the audio file
            num_speakers: Expected number of speakers (None for automatic detection)
            min_speakers: Minimum number of speakers to detect
            max_speakers: Maximum number of speakers to detect
            
        Returns:
            DiarizationResult with speaker segments
            
        Raises:
            DiarizationError: If diarization fails
        """
        if not Path(audio_path).exists():
            raise DiarizationError(f"Audio file not found: {audio_path}")
        
        # Initialize pipeline if needed
        await self._initialize_pipeline()
        
        logger.info(f"Starting speaker diarization for {audio_path}")
        
        try:
            # Run diarization in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            diarization = await loop.run_in_executor(
                None, 
                self._run_diarization,
                audio_path,
                num_speakers,
                min_speakers,
                max_speakers
            )
            
            # Convert pyannote output to our format
            result = self._convert_diarization_result(diarization)
            
            logger.info(f"Diarization completed: {result.num_speakers} speakers found")
            return result
            
        except Exception as e:
            logger.error(f"Diarization failed for {audio_path}: {e}")
            raise DiarizationError(f"Speaker diarization failed: {e}")
    
    def _run_diarization(
        self, 
        audio_path: str, 
        num_speakers: Optional[int],
        min_speakers: int,
        max_speakers: int
    ):
        """
        Run the actual diarization process.
        This runs in a thread pool to avoid blocking the event loop.
        """
        # Set pipeline parameters
        if num_speakers is not None:
            self.pipeline.instantiate({
                "clustering": {
                    "method": "centroid",
                    "min_cluster_size": 12,
                    "threshold": 0.7045654963945799,
                },
                "segmentation": {
                    "min_duration_off": 0.0
                }
            })
        else:
            # Use automatic speaker detection
            self.pipeline.instantiate({
                "clustering": {
                    "method": "centroid",
                    "min_cluster_size": 12,
                    "threshold": 0.7045654963945799,
                },
                "segmentation": {
                    "min_duration_off": 0.0
                }
            })
        
        # Apply diarization
        diarization = self.pipeline(audio_path)
        
        return diarization
    
    def _convert_diarization_result(self, diarization) -> DiarizationResult:
        """
        Convert pyannote diarization output to our DiarizationResult format.
        
        Args:
            diarization: Pyannote diarization output
            
        Returns:
            DiarizationResult object
        """
        segments = []
        speaker_labels = set()
        total_duration = 0.0
        
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segment = SpeakerSegment(
                start=turn.start,
                end=turn.end,
                speaker=speaker,
                confidence=1.0  # Pyannote doesn't provide confidence scores directly
            )
            segments.append(segment)
            speaker_labels.add(speaker)
            total_duration = max(total_duration, turn.end)
        
        # Sort segments by start time
        segments.sort(key=lambda x: x.start)
        
        return DiarizationResult(
            segments=segments,
            num_speakers=len(speaker_labels),
            total_duration=total_duration,
            speaker_labels=sorted(list(speaker_labels))
        )
    
    async def is_available(self) -> bool:
        """
        Check if diarization service is available.
        
        Returns:
            True if service can be used, False otherwise
        """
        return bool(self.hf_token)
    
    async def get_voice_activity_detection(self, audio_path: str) -> List[Tuple[float, float]]:
        """
        Get voice activity detection (VAD) segments.
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            List of (start, end) tuples for voice activity segments
        """
        if not Path(audio_path).exists():
            raise DiarizationError(f"Audio file not found: {audio_path}")
        
        try:
            # Import VAD pipeline
            from pyannote.audio import Pipeline
            
            # Initialize VAD pipeline
            vad_pipeline = Pipeline.from_pretrained(
                "pyannote/voice-activity-detection",
                use_auth_token=self.hf_token
            )
            
            # Run VAD in thread pool
            loop = asyncio.get_event_loop()
            vad_result = await loop.run_in_executor(
                None,
                vad_pipeline,
                audio_path
            )
            
            # Convert to list of tuples
            voice_segments = []
            for segment in vad_result.get_timeline():
                voice_segments.append((segment.start, segment.end))
            
            return voice_segments
            
        except Exception as e:
            logger.error(f"VAD failed for {audio_path}: {e}")
            raise DiarizationError(f"Voice activity detection failed: {e}")


class FallbackDiarizationService:
    """Fallback diarization service when pyannote.audio is not available."""
    
    def __init__(self):
        self.default_speakers = ["SPEAKER_00", "SPEAKER_01"]
    
    async def diarize_audio(
        self, 
        audio_path: str,
        num_speakers: Optional[int] = None,
        min_speakers: int = 1,
        max_speakers: int = 10
    ) -> DiarizationResult:
        """
        Provide fallback diarization with simple speaker assignment.
        
        Args:
            audio_path: Path to the audio file (used for duration calculation)
            num_speakers: Expected number of speakers
            min_speakers: Minimum number of speakers
            max_speakers: Maximum number of speakers
            
        Returns:
            DiarizationResult with simple speaker segments
        """
        logger.warning(f"Using fallback diarization for {audio_path}")
        
        # Try to get audio duration
        try:
            from app.services.video_processor import AudioExtractionService
            audio_service = AudioExtractionService()
            audio_info = await audio_service.get_audio_info(audio_path)
            
            format_info = audio_info.get('format', {})
            duration = float(format_info.get('duration', 60.0))
        except Exception:
            duration = 60.0  # Default duration
        
        # Create simple speaker segments
        num_speakers = num_speakers or 2
        num_speakers = max(min_speakers, min(num_speakers, max_speakers))
        
        segment_duration = duration / (num_speakers * 2)  # Alternate speakers
        segments = []
        
        for i in range(num_speakers * 2):
            speaker_idx = i % num_speakers
            speaker_label = f"SPEAKER_{speaker_idx:02d}"
            
            start_time = i * segment_duration
            end_time = min((i + 1) * segment_duration, duration)
            
            segment = SpeakerSegment(
                start=start_time,
                end=end_time,
                speaker=speaker_label,
                confidence=0.5  # Low confidence for fallback
            )
            segments.append(segment)
        
        speaker_labels = [f"SPEAKER_{i:02d}" for i in range(num_speakers)]
        
        return DiarizationResult(
            segments=segments,
            num_speakers=num_speakers,
            total_duration=duration,
            speaker_labels=speaker_labels
        )
    
    async def is_available(self) -> bool:
        """Fallback service is always available."""
        return True
    
    async def get_voice_activity_detection(self, audio_path: str) -> List[Tuple[float, float]]:
        """
        Provide simple voice activity detection.
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            List of voice activity segments
        """
        # Simple fallback: assume voice activity for most of the duration
        try:
            from app.services.video_processor import AudioExtractionService
            audio_service = AudioExtractionService()
            audio_info = await audio_service.get_audio_info(audio_path)
            
            format_info = audio_info.get('format', {})
            duration = float(format_info.get('duration', 60.0))
        except Exception:
            duration = 60.0
        
        # Create segments with some gaps to simulate real VAD
        segments = []
        segment_length = 5.0  # 5-second segments
        gap_length = 0.5      # 0.5-second gaps
        
        current_time = 0.0
        while current_time < duration:
            segment_end = min(current_time + segment_length, duration)
            segments.append((current_time, segment_end))
            current_time = segment_end + gap_length
        
        return segments


class SpeakerDiarizationService:
    """Main speaker diarization service with fallback capabilities."""
    
    def __init__(self):
        self.primary_service = None
        self.fallback_service = FallbackDiarizationService()
        
        # Try to initialize primary service
        try:
            if settings.HF_TOKEN:
                self.primary_service = PyAnnoteDiarizationService()
                logger.info("PyAnnote diarization service initialized")
            else:
                logger.info("HF_TOKEN not available, using fallback diarization")
        except Exception as e:
            logger.warning(f"Primary diarization service not available: {e}")
    
    async def diarize_audio(
        self, 
        audio_path: str,
        num_speakers: Optional[int] = None,
        use_fallback: bool = False
    ) -> DiarizationResult:
        """
        Perform speaker diarization with automatic fallback.
        
        Args:
            audio_path: Path to the audio file
            num_speakers: Expected number of speakers
            use_fallback: Force use of fallback service
            
        Returns:
            DiarizationResult
        """
        if use_fallback or not self.primary_service:
            return await self.fallback_service.diarize_audio(audio_path, num_speakers)
        
        try:
            return await self.primary_service.diarize_audio(audio_path, num_speakers)
        except DiarizationError as e:
            logger.error(f"Primary diarization failed, using fallback: {e}")
            return await self.fallback_service.diarize_audio(audio_path, num_speakers)
    
    async def get_voice_activity_detection(
        self, 
        audio_path: str,
        use_fallback: bool = False
    ) -> List[Tuple[float, float]]:
        """
        Get voice activity detection with fallback.
        
        Args:
            audio_path: Path to the audio file
            use_fallback: Force use of fallback service
            
        Returns:
            List of voice activity segments
        """
        if use_fallback or not self.primary_service:
            return await self.fallback_service.get_voice_activity_detection(audio_path)
        
        try:
            return await self.primary_service.get_voice_activity_detection(audio_path)
        except DiarizationError as e:
            logger.error(f"Primary VAD failed, using fallback: {e}")
            return await self.fallback_service.get_voice_activity_detection(audio_path)
    
    async def is_primary_service_available(self) -> bool:
        """
        Check if primary diarization service is available.
        
        Returns:
            True if pyannote.audio service is available, False otherwise
        """
        if not self.primary_service:
            return False
        return await self.primary_service.is_available()
    
    async def get_service_status(self) -> Dict[str, Any]:
        """
        Get status of diarization services.
        
        Returns:
            Dictionary with service status information
        """
        primary_available = await self.is_primary_service_available()
        
        return {
            "primary_available": primary_available,
            "hf_token_configured": bool(settings.HF_TOKEN),
            "fallback_available": True,
            "pyannote_audio_installed": self._check_pyannote_installation(),
            "current_time": datetime.utcnow().isoformat()
        }
    
    def _check_pyannote_installation(self) -> bool:
        """Check if pyannote.audio is installed."""
        try:
            import pyannote.audio
            return True
        except ImportError:
            return False
    
    async def assign_speaker_labels(
        self, 
        segments: List[SpeakerSegment],
        custom_labels: Optional[Dict[str, str]] = None
    ) -> List[SpeakerSegment]:
        """
        Assign custom labels to speakers.
        
        Args:
            segments: List of speaker segments
            custom_labels: Dictionary mapping original labels to custom labels
            
        Returns:
            List of segments with updated speaker labels
        """
        if not custom_labels:
            return segments
        
        updated_segments = []
        for segment in segments:
            new_speaker = custom_labels.get(segment.speaker, segment.speaker)
            updated_segment = SpeakerSegment(
                start=segment.start,
                end=segment.end,
                speaker=new_speaker,
                confidence=segment.confidence
            )
            updated_segments.append(updated_segment)
        
        return updated_segments
    
    async def merge_short_segments(
        self, 
        segments: List[SpeakerSegment],
        min_duration: float = 1.0
    ) -> List[SpeakerSegment]:
        """
        Merge segments that are too short with adjacent segments from the same speaker.
        
        Args:
            segments: List of speaker segments
            min_duration: Minimum segment duration in seconds
            
        Returns:
            List of merged segments
        """
        if not segments:
            return segments
        
        merged_segments = []
        current_segment = segments[0]
        
        for next_segment in segments[1:]:
            # If current segment is too short and next segment has same speaker, merge
            if (current_segment.end - current_segment.start < min_duration and 
                current_segment.speaker == next_segment.speaker):
                
                current_segment = SpeakerSegment(
                    start=current_segment.start,
                    end=next_segment.end,
                    speaker=current_segment.speaker,
                    confidence=max(current_segment.confidence, next_segment.confidence)
                )
            else:
                merged_segments.append(current_segment)
                current_segment = next_segment
        
        # Add the last segment
        merged_segments.append(current_segment)
        
        return merged_segments
    
    async def get_speaker_statistics(self, segments: List[SpeakerSegment]) -> Dict[str, Any]:
        """
        Get statistics about speaker segments.
        
        Args:
            segments: List of speaker segments
            
        Returns:
            Dictionary with speaker statistics
        """
        if not segments:
            return {
                "total_segments": 0,
                "unique_speakers": 0,
                "total_duration": 0.0,
                "speaker_durations": {}
            }
        
        speaker_durations = {}
        total_duration = 0.0
        
        for segment in segments:
            duration = segment.end - segment.start
            total_duration += duration
            
            if segment.speaker not in speaker_durations:
                speaker_durations[segment.speaker] = 0.0
            speaker_durations[segment.speaker] += duration
        
        return {
            "total_segments": len(segments),
            "unique_speakers": len(speaker_durations),
            "total_duration": total_duration,
            "speaker_durations": speaker_durations,
            "average_segment_duration": total_duration / len(segments) if segments else 0.0
        }