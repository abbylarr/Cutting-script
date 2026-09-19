"""
Video processing services for filmlist application.
Handles video validation, metadata extraction, audio extraction, and scene detection.
"""

import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import timedelta

logger = logging.getLogger(__name__)


@dataclass
class VideoMetadata:
    """Video metadata extracted from FFmpeg probe."""
    duration: float  # seconds
    fps: float
    width: int
    height: int
    codec: str
    format: str
    bitrate: Optional[int] = None
    audio_codec: Optional[str] = None
    audio_channels: Optional[int] = None
    audio_sample_rate: Optional[int] = None


@dataclass
class ValidationResult:
    """Result of video validation."""
    is_valid: bool
    metadata: Optional[VideoMetadata] = None
    error: Optional[str] = None


class VideoValidationError(Exception):
    """Raised when video validation fails."""
    pass


class FFmpegError(Exception):
    """Raised when FFmpeg operations fail."""
    pass


class VideoValidationService:
    """Service for validating videos and extracting metadata using FFmpeg."""
    
    # Supported video formats
    SUPPORTED_FORMATS = {
        'mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv', 'webm', 'm4v'
    }
    
    # Supported video codecs
    SUPPORTED_CODECS = {
        'h264', 'h265', 'hevc', 'vp8', 'vp9', 'av1', 'mpeg4', 'xvid'
    }
    
    # Maximum file size (2GB)
    MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024
    
    # Minimum duration (1 second)
    MIN_DURATION = 1.0
    
    # Maximum duration (4 hours)
    MAX_DURATION = 4 * 60 * 60
    
    def __init__(self):
        self._ffmpeg_available = True
        try:
            self._check_ffmpeg_availability()
        except FFmpegError as e:
            self._ffmpeg_available = False
            logger.warning(f"FFmpeg not available at init: {e}")
    
    def _check_ffmpeg_availability(self) -> None:
        """Check if FFmpeg is available in the system."""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                raise FFmpegError("FFmpeg is not working properly")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            raise FFmpegError(f"FFmpeg is not available: {e}")
    
    async def validate_video(self, video_path: str) -> ValidationResult:
        """
        Validate video file and extract metadata.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            ValidationResult with validation status and metadata
        """
        try:
            # Check if file exists
            path = Path(video_path)
            if not path.exists():
                return ValidationResult(
                    is_valid=False,
                    error="Video file does not exist"
                )
            
            # Check file size
            file_size = path.stat().st_size
            if file_size > self.MAX_FILE_SIZE:
                return ValidationResult(
                    is_valid=False,
                    error=f"File size ({file_size / (1024**3):.1f}GB) exceeds maximum allowed size (2GB)"
                )
            
            if file_size == 0:
                return ValidationResult(
                    is_valid=False,
                    error="Video file is empty"
                )
            
            # Extract metadata using FFprobe
            metadata = await self._extract_metadata(video_path)
            
            # Validate format
            if metadata.format.lower() not in self.SUPPORTED_FORMATS:
                return ValidationResult(
                    is_valid=False,
                    error=f"Unsupported video format: {metadata.format}"
                )
            
            # Validate codec
            codec_normalized = metadata.codec.lower().replace('_', '')
            if codec_normalized not in self.SUPPORTED_CODECS:
                return ValidationResult(
                    is_valid=False,
                    error=f"Unsupported video codec: {metadata.codec}"
                )
            
            # Validate duration
            if metadata.duration < self.MIN_DURATION:
                return ValidationResult(
                    is_valid=False,
                    error=f"Video duration ({metadata.duration:.1f}s) is too short (minimum {self.MIN_DURATION}s)"
                )
            
            if metadata.duration > self.MAX_DURATION:
                return ValidationResult(
                    is_valid=False,
                    error=f"Video duration ({metadata.duration / 3600:.1f}h) is too long (maximum 4h)"
                )
            
            # Validate resolution
            if metadata.width < 320 or metadata.height < 240:
                return ValidationResult(
                    is_valid=False,
                    error=f"Video resolution ({metadata.width}x{metadata.height}) is too low (minimum 320x240)"
                )
            
            # Validate FPS
            if metadata.fps < 1 or metadata.fps > 120:
                return ValidationResult(
                    is_valid=False,
                    error=f"Invalid frame rate: {metadata.fps} fps"
                )
            
            return ValidationResult(
                is_valid=True,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Video validation failed for {video_path}: {e}")
            return ValidationResult(
                is_valid=False,
                error=f"Validation error: {str(e)}"
            )
    
    async def _extract_metadata(self, video_path: str) -> VideoMetadata:
        """
        Extract video metadata using FFprobe.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            VideoMetadata object with extracted information
        """
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            video_path
        ]
        
        try:
            # Run FFprobe asynchronously
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8') if stderr else "Unknown FFprobe error"
                raise FFmpegError(f"FFprobe failed: {error_msg}")
            
            # Parse JSON output
            probe_data = json.loads(stdout.decode('utf-8'))
            
            # Extract format information
            format_info = probe_data.get('format', {})
            duration = float(format_info.get('duration', 0))
            format_name = format_info.get('format_name', '').split(',')[0]
            bitrate = format_info.get('bit_rate')
            
            # Find video stream
            video_stream = None
            audio_stream = None
            
            for stream in probe_data.get('streams', []):
                if stream.get('codec_type') == 'video' and video_stream is None:
                    video_stream = stream
                elif stream.get('codec_type') == 'audio' and audio_stream is None:
                    audio_stream = stream
            
            if not video_stream:
                raise VideoValidationError("No video stream found in file")
            
            # Extract video metadata
            width = int(video_stream.get('width', 0))
            height = int(video_stream.get('height', 0))
            codec = video_stream.get('codec_name', '')
            
            # Calculate FPS
            fps_str = video_stream.get('r_frame_rate', '0/1')
            if '/' in fps_str:
                num, den = fps_str.split('/')
                fps = float(num) / float(den) if float(den) != 0 else 0
            else:
                fps = float(fps_str)
            
            # Extract audio metadata if available
            audio_codec = None
            audio_channels = None
            audio_sample_rate = None
            
            if audio_stream:
                audio_codec = audio_stream.get('codec_name')
                audio_channels = audio_stream.get('channels')
                audio_sample_rate = audio_stream.get('sample_rate')
                if audio_sample_rate:
                    audio_sample_rate = int(audio_sample_rate)
            
            return VideoMetadata(
                duration=duration,
                fps=fps,
                width=width,
                height=height,
                codec=codec,
                format=format_name,
                bitrate=int(bitrate) if bitrate else None,
                audio_codec=audio_codec,
                audio_channels=audio_channels,
                audio_sample_rate=audio_sample_rate
            )
            
        except asyncio.TimeoutError:
            raise FFmpegError("FFprobe operation timed out")
        except json.JSONDecodeError as e:
            raise FFmpegError(f"Failed to parse FFprobe output: {e}")
        except Exception as e:
            raise FFmpegError(f"Metadata extraction failed: {e}")
    
    async def check_video_integrity(self, video_path: str) -> Tuple[bool, Optional[str]]:
        """
        Check video file integrity by attempting to decode a few frames.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        cmd = [
            'ffmpeg',
            '-v', 'error',
            '-i', video_path,
            '-t', '10',  # Check first 10 seconds
            '-f', 'null',
            '-'
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8') if stderr else "Unknown integrity check error"
                return False, f"Video integrity check failed: {error_msg}"
            
            return True, None
            
        except asyncio.TimeoutError:
            return False, "Video integrity check timed out"
        except Exception as e:
            return False, f"Integrity check error: {str(e)}"

class AudioExtractionService:
    """Service for extracting audio from video files using FFmpeg."""
    
    # Audio extraction settings
    AUDIO_FORMAT = 'wav'
    AUDIO_SAMPLE_RATE = 16000  # 16kHz for speech recognition
    AUDIO_CHANNELS = 1  # Mono
    
    def __init__(self):
        self._ffmpeg_available = True
        try:
            self._check_ffmpeg_availability()
        except FFmpegError as e:
            self._ffmpeg_available = False
            logger.warning(f"FFmpeg not available for audio extraction: {e}")
    
    def _check_ffmpeg_availability(self) -> None:
        """Check if FFmpeg is available in the system."""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                raise FFmpegError("FFmpeg is not working properly")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            raise FFmpegError(f"FFmpeg is not available: {e}")
    
    async def extract_audio(self, video_path: str, output_path: Optional[str] = None) -> str:
        """
        Extract audio from video file.
        
        Args:
            video_path: Path to the input video file
            output_path: Optional path for output audio file. If None, generates automatically.
            
        Returns:
            Path to the extracted audio file
            
        Raises:
            FFmpegError: If audio extraction fails
        """
        if output_path is None:
            video_file = Path(video_path)
            output_path = str(video_file.parent / f"{video_file.stem}_audio.{self.AUDIO_FORMAT}")
        
        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vn',  # No video
            '-acodec', 'pcm_s16le',  # PCM 16-bit little-endian
            '-ar', str(self.AUDIO_SAMPLE_RATE),  # Sample rate
            '-ac', str(self.AUDIO_CHANNELS),  # Channels
            '-y',  # Overwrite output file
            output_path
        ]
        
        try:
            logger.info(f"Extracting audio from {video_path} to {output_path}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8') if stderr else "Unknown FFmpeg error"
                raise FFmpegError(f"Audio extraction failed: {error_msg}")
            
            # Verify output file was created
            if not Path(output_path).exists():
                raise FFmpegError("Audio file was not created")
            
            logger.info(f"Audio extraction completed: {output_path}")
            return output_path
            
        except Exception as e:
            # Clean up partial file if it exists
            if Path(output_path).exists():
                try:
                    Path(output_path).unlink()
                except Exception:
                    pass
            
            if isinstance(e, FFmpegError):
                raise
            else:
                raise FFmpegError(f"Audio extraction error: {str(e)}")
    
    async def extract_audio_segment(
        self, 
        video_path: str, 
        start_time: float, 
        duration: float, 
        output_path: Optional[str] = None
    ) -> str:
        """
        Extract audio segment from video file.
        
        Args:
            video_path: Path to the input video file
            start_time: Start time in seconds
            duration: Duration in seconds
            output_path: Optional path for output audio file
            
        Returns:
            Path to the extracted audio segment
        """
        if output_path is None:
            video_file = Path(video_path)
            output_path = str(video_file.parent / f"{video_file.stem}_segment_{start_time:.1f}s.{self.AUDIO_FORMAT}")
        
        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        cmd = [
            'ffmpeg',
            '-ss', str(start_time),  # Start time
            '-i', video_path,
            '-t', str(duration),  # Duration
            '-vn',  # No video
            '-acodec', 'pcm_s16le',
            '-ar', str(self.AUDIO_SAMPLE_RATE),
            '-ac', str(self.AUDIO_CHANNELS),
            '-y',
            output_path
        ]
        
        try:
            logger.info(f"Extracting audio segment from {video_path} ({start_time:.1f}s - {start_time + duration:.1f}s)")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8') if stderr else "Unknown FFmpeg error"
                raise FFmpegError(f"Audio segment extraction failed: {error_msg}")
            
            if not Path(output_path).exists():
                raise FFmpegError("Audio segment file was not created")
            
            return output_path
            
        except Exception as e:
            # Clean up partial file if it exists
            if Path(output_path).exists():
                try:
                    Path(output_path).unlink()
                except Exception:
                    pass
            
            if isinstance(e, FFmpegError):
                raise
            else:
                raise FFmpegError(f"Audio segment extraction error: {str(e)}")
    
    async def get_audio_info(self, audio_path: str) -> Dict:
        """
        Get audio file information.
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            Dictionary with audio information
        """
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            audio_path
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8') if stderr else "Unknown FFprobe error"
                raise FFmpegError(f"Audio info extraction failed: {error_msg}")
            
            return json.loads(stdout.decode('utf-8'))
            
        except asyncio.TimeoutError:
            raise FFmpegError("Audio info extraction timed out")
        except json.JSONDecodeError as e:
            raise FFmpegError(f"Failed to parse audio info: {e}")
        except Exception as e:
            raise FFmpegError(f"Audio info extraction error: {str(e)}")


@dataclass
class Scene:
    """Represents a detected scene in a video."""
    start_time: float  # seconds
    end_time: float    # seconds
    duration: float    # seconds
    scene_number: int
    
    def __post_init__(self):
        """Calculate duration if not provided."""
        if self.duration == 0:
            self.duration = self.end_time - self.start_time

    @property
    def keyframe_35_time(self) -> float:
        return self.start_time + (self.duration * 0.35)

    @property
    def keyframe_70_time(self) -> float:
        return self.start_time + (self.duration * 0.70)


class SceneDetectionService:
    """Service for detecting scenes in video files using python-scenedetect."""
    
    def __init__(self):
        self._scenedetect_available = self._check_scenedetect_availability()
    
    def _check_scenedetect_availability(self) -> bool:
        """Check if scenedetect is available."""
        try:
            import scenedetect  # noqa: F401
            return True
        except ImportError:
            logger.warning(
                "python-scenedetect is not installed; will use time-based scene fallback"
            )
            return False

    async def _fallback_time_based_scenes(
        self,
        video_path: str,
        min_scene_length: float = 2.0,
        chunk_seconds: float = 30.0,
    ) -> List[Scene]:
        """Create evenly spaced scenes when scenedetect is unavailable."""
        duration = 60.0
        try:
            validator = VideoValidationService()
            result = await validator.validate_video(video_path)
            if result.metadata and result.metadata.duration:
                duration = result.metadata.duration
        except Exception as e:
            logger.warning(f"Could not probe video duration for fallback scenes: {e}")

        chunk = max(min_scene_length, chunk_seconds)
        scenes: List[Scene] = []
        start = 0.0
        while start < duration:
            end = min(start + chunk, duration)
            if end - start < min_scene_length * 0.5 and scenes:
                last = scenes[-1]
                scenes[-1] = Scene(
                    start_time=last.start_time,
                    end_time=duration,
                    duration=duration - last.start_time,
                    scene_number=last.scene_number,
                )
                break
            scenes.append(
                Scene(
                    start_time=start,
                    end_time=end,
                    duration=end - start,
                    scene_number=len(scenes) + 1,
                )
            )
            start = end

        if not scenes:
            scenes.append(
                Scene(start_time=0.0, end_time=duration, duration=duration, scene_number=1)
            )
        logger.info(f"Fallback scene detection produced {len(scenes)} scenes")
        return scenes
    
    async def detect_scenes(
        self, 
        video_path: str, 
        threshold: float = 30.0,
        min_scene_length: float = 2.0,
        max_scenes: int = 1000
    ) -> List[Scene]:
        """
        Detect scenes in video using content-aware detection.
        
        Args:
            video_path: Path to the video file
            threshold: Detection sensitivity (lower = more sensitive)
            min_scene_length: Minimum scene length in seconds
            max_scenes: Maximum number of scenes to detect
            
        Returns:
            List of detected scenes
        """
        if not self._scenedetect_available:
            return await self._fallback_time_based_scenes(
                video_path, min_scene_length=min_scene_length
            )

        try:
            # Import scenedetect modules
            from scenedetect import VideoManager, SceneManager
            from scenedetect.detectors import ContentDetector
            
            logger.info(f"Starting scene detection for {video_path}")
            
            # Create video manager
            video_manager = VideoManager([video_path])
            scene_manager = SceneManager()
            
            # Add content detector with specified threshold
            scene_manager.add_detector(ContentDetector(threshold=threshold))
            
            # Start video manager
            video_manager.set_duration()
            video_manager.start()
            
            # Detect scenes
            scene_manager.detect_scenes(frame_source=video_manager)
            
            # Get scene list
            scene_list = scene_manager.get_scene_list()
            
            # Convert to our Scene objects
            scenes = []
            for i, (start_time, end_time) in enumerate(scene_list):
                start_seconds = start_time.get_seconds()
                end_seconds = end_time.get_seconds()
                duration = end_seconds - start_seconds
                
                # Filter out scenes that are too short
                if duration >= min_scene_length:
                    scene = Scene(
                        start_time=start_seconds,
                        end_time=end_seconds,
                        duration=duration,
                        scene_number=len(scenes) + 1
                    )
                    scenes.append(scene)
                    
                    # Limit number of scenes
                    if len(scenes) >= max_scenes:
                        logger.warning(f"Reached maximum scene limit ({max_scenes}), stopping detection")
                        break
            
            # Release video manager
            video_manager.release()
            
            # Post-process scenes to merge very short gaps
            scenes = await self._merge_short_gaps(scenes, min_gap=0.5)
            
            logger.info(f"Detected {len(scenes)} scenes in {video_path}")
            return scenes
            
        except ImportError as e:
            raise ImportError(f"Scene detection dependencies not available: {e}")
        except Exception as e:
            logger.error(f"Scene detection failed for {video_path}: {e}")
            raise Exception(f"Scene detection error: {str(e)}")
    
    async def _merge_short_gaps(self, scenes: List[Scene], min_gap: float = 0.5) -> List[Scene]:
        """
        Merge scenes with very short gaps between them.
        
        Args:
            scenes: List of detected scenes
            min_gap: Minimum gap in seconds to keep scenes separate
            
        Returns:
            List of merged scenes
        """
        if len(scenes) <= 1:
            return scenes
        
        merged_scenes = []
        current_scene = scenes[0]
        
        for next_scene in scenes[1:]:
            gap = next_scene.start_time - current_scene.end_time
            
            if gap < min_gap:
                # Merge scenes
                current_scene = Scene(
                    start_time=current_scene.start_time,
                    end_time=next_scene.end_time,
                    duration=next_scene.end_time - current_scene.start_time,
                    scene_number=current_scene.scene_number
                )
            else:
                # Keep current scene and move to next
                merged_scenes.append(current_scene)
                current_scene = next_scene
        
        # Add the last scene
        merged_scenes.append(current_scene)
        
        # Renumber scenes
        for i, scene in enumerate(merged_scenes):
            scene.scene_number = i + 1
        
        return merged_scenes
    
    async def detect_scenes_with_fallback(
        self, 
        video_path: str,
        primary_threshold: float = 30.0,
        fallback_threshold: float = 20.0,
        min_scene_length: float = 2.0
    ) -> List[Scene]:
        """
        Detect scenes with fallback to more sensitive detection if too few scenes found.
        
        Args:
            video_path: Path to the video file
            primary_threshold: Primary detection threshold
            fallback_threshold: Fallback threshold (more sensitive)
            min_scene_length: Minimum scene length in seconds
            
        Returns:
            List of detected scenes
        """
        try:
            scenes = await self.detect_scenes(
                video_path,
                threshold=primary_threshold,
                min_scene_length=min_scene_length,
            )
        except Exception as e:
            logger.warning(f"Primary scene detection failed ({e}), using time-based fallback")
            return await self._fallback_time_based_scenes(
                video_path, min_scene_length=min_scene_length
            )

        # If too few scenes detected, try more sensitive detection
        if len(scenes) < 3 and self._scenedetect_available:
            logger.info(f"Only {len(scenes)} scenes detected, trying more sensitive detection")
            try:
                scenes = await self.detect_scenes(
                    video_path,
                    threshold=fallback_threshold,
                    min_scene_length=min_scene_length,
                )
            except Exception as e:
                logger.warning(f"Fallback threshold detection failed: {e}")

        if not scenes:
            scenes = await self._fallback_time_based_scenes(
                video_path, min_scene_length=min_scene_length
            )

        return scenes
    
    async def get_scene_statistics(self, scenes: List[Scene]) -> Dict:
        """
        Get statistics about detected scenes.
        
        Args:
            scenes: List of scenes
            
        Returns:
            Dictionary with scene statistics
        """
        if not scenes:
            return {
                'total_scenes': 0,
                'total_duration': 0,
                'average_duration': 0,
                'shortest_scene': 0,
                'longest_scene': 0
            }
        
        durations = [scene.duration for scene in scenes]
        total_duration = sum(durations)
        
        return {
            'total_scenes': len(scenes),
            'total_duration': total_duration,
            'average_duration': total_duration / len(scenes),
            'shortest_scene': min(durations),
            'longest_scene': max(durations),
            'scene_durations': durations
        }