"""
File upload and validation service for video and SRT files.
"""
import os
import hashlib
import mimetypes
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4
import aiofiles
from fastapi import UploadFile, HTTPException

try:
    import magic
except ImportError:  # optional dependency
    magic = None

from app.core.config import settings
from app.schemas.upload import VideoValidationResult, SRTValidationResult
from app.models.processing_task import ProcessingTask
from app.db.base import get_db


class FileUploadService:
    """Service for handling file uploads with security and validation."""
    
    # Supported video formats
    SUPPORTED_VIDEO_FORMATS = {
        'video/mp4', 'video/avi', 'video/mov', 'video/mkv', 
        'video/wmv', 'video/flv', 'video/webm', 'video/m4v',
        'application/octet-stream',  # browsers sometimes send this
    }
    
    SUPPORTED_VIDEO_EXTENSIONS = {
        '.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v'
    }
    
    # Supported SRT formats
    SUPPORTED_SRT_FORMATS = {
        'text/plain', 'application/x-subrip'
    }
    
    # Maximum file sizes
    MAX_VIDEO_SIZE = settings.MAX_FILE_SIZE  # 5GB
    MAX_SRT_SIZE = 10 * 1024 * 1024  # 10MB
    
    def __init__(self):
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(exist_ok=True)
        
    async def validate_video_file(self, file: UploadFile) -> VideoValidationResult:
        """Validate uploaded video file format, size, and integrity."""
        errors = []
        
        # Check file size
        if file.size and file.size > self.MAX_VIDEO_SIZE:
            errors.append(f"File size {file.size} exceeds maximum allowed size {self.MAX_VIDEO_SIZE}")
            
        # Check MIME type
        mime_type = None
        if magic is not None:
            try:
                mime_type = magic.from_buffer(await file.read(1024), mime=True)
                await file.seek(0)
            except Exception:
                await file.seek(0)
                mime_type = None

        if mime_type is None:
            # Fallback: trust extension when python-magic is unavailable
            ext = Path(file.filename or "").suffix.lower()
            mime_type = mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
            if ext not in self.SUPPORTED_VIDEO_EXTENSIONS and mime_type not in self.SUPPORTED_VIDEO_FORMATS:
                errors.append(f"Unsupported video format: {ext or mime_type}")
        elif mime_type not in self.SUPPORTED_VIDEO_FORMATS:
            ext = Path(file.filename or "").suffix.lower()
            if ext not in self.SUPPORTED_VIDEO_EXTENSIONS:
                errors.append(f"Unsupported video format: {mime_type}")
            
        # Basic filename validation
        if not file.filename or not self._is_safe_filename(file.filename):
            errors.append("Invalid or unsafe filename")
            
        if errors:
            return VideoValidationResult(
                is_valid=False,
                file_size=file.size or 0,
                errors=errors
            )
            
        # Save temporary file for detailed validation
        temp_path = await self._save_temp_file(file)
        
        try:
            # Use FFmpeg to validate and extract metadata
            metadata = await self._extract_video_metadata(temp_path)
            
            return VideoValidationResult(
                is_valid=True,
                duration=metadata.get('duration'),
                fps=metadata.get('fps'),
                resolution=metadata.get('resolution'),
                codec=metadata.get('codec'),
                file_size=file.size or 0,
                errors=[]
            )
            
        except Exception as e:
            errors.append(f"Video validation failed: {str(e)}")
            return VideoValidationResult(
                is_valid=False,
                file_size=file.size or 0,
                errors=errors
            )
        finally:
            # Clean up temp file
            if temp_path.exists():
                temp_path.unlink()
                
    async def validate_srt_file(self, file: UploadFile) -> SRTValidationResult:
        """Validate uploaded SRT file format and content."""
        errors = []
        
        # Check file size
        if file.size and file.size > self.MAX_SRT_SIZE:
            errors.append(f"SRT file size {file.size} exceeds maximum allowed size {self.MAX_SRT_SIZE}")
            
        # Check filename extension
        if not file.filename or not file.filename.lower().endswith('.srt'):
            errors.append("File must have .srt extension")
            
        if not self._is_safe_filename(file.filename):
            errors.append("Invalid or unsafe filename")
            
        if errors:
            return SRTValidationResult(
                is_valid=False,
                errors=errors
            )
            
        try:
            # Read and validate SRT content
            content = await file.read()
            await file.seek(0)  # Reset file pointer
            
            # Detect encoding
            encoding = self._detect_encoding(content)
            
            # Parse SRT content
            srt_data = self._parse_srt_content(content.decode(encoding))
            
            return SRTValidationResult(
                is_valid=True,
                subtitle_count=len(srt_data),
                duration=srt_data[-1]['end_time'] if srt_data else 0,
                encoding=encoding,
                errors=[]
            )
            
        except Exception as e:
            errors.append(f"SRT validation failed: {str(e)}")
            return SRTValidationResult(
                is_valid=False,
                errors=errors
            )
            
    async def save_video_file(self, file: UploadFile, user_id: UUID) -> Tuple[str, str]:
        """Save uploaded video file with user isolation and security checks."""
        # Create user-specific directory
        user_dir = self.upload_dir / str(user_id)
        user_dir.mkdir(exist_ok=True)
        
        # Generate secure filename
        file_id = uuid4()
        file_extension = Path(file.filename).suffix.lower()
        secure_filename = f"{file_id}{file_extension}"
        file_path = user_dir / secure_filename
        
        # Perform virus scan (basic implementation)
        await self._scan_file_for_viruses(file)
        
        # Save file with integrity check
        file_hash = await self._save_file_with_hash(file, file_path)
        
        return str(file_path), file_hash
        
    async def save_srt_file(self, file: UploadFile, user_id: UUID, task_id: UUID) -> str:
        """Save uploaded SRT file with user isolation."""
        # Create user-specific directory
        user_dir = self.upload_dir / str(user_id)
        user_dir.mkdir(exist_ok=True)
        
        # Generate secure filename
        secure_filename = f"{task_id}.srt"
        file_path = user_dir / secure_filename
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
            
        return str(file_path)
        
    def _is_safe_filename(self, filename: str) -> bool:
        """Check if filename is safe (no path traversal, etc.)."""
        if not filename:
            return False
            
        # Check for path traversal attempts
        if '..' in filename or '/' in filename or '\\' in filename:
            return False
            
        # Check for null bytes
        if '\x00' in filename:
            return False
            
        # Check length
        if len(filename) > 255:
            return False
            
        return True
        
    async def _save_temp_file(self, file: UploadFile) -> Path:
        """Save file to temporary location for validation."""
        temp_dir = Path("/tmp/filmlist_temp")
        temp_dir.mkdir(exist_ok=True)
        
        temp_path = temp_dir / f"{uuid4()}{Path(file.filename).suffix}"
        
        async with aiofiles.open(temp_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
            
        await file.seek(0)  # Reset file pointer
        return temp_path
        
    async def _extract_video_metadata(self, video_path: Path) -> Dict:
        """Extract video metadata using FFmpeg."""
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json', 
            '-show_format', '-show_streams', str(video_path)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                raise Exception(f"FFprobe failed: {result.stderr}")
                
            import json
            data = json.loads(result.stdout)
            
            # Extract video stream info
            video_stream = next(
                (s for s in data['streams'] if s['codec_type'] == 'video'), 
                None
            )
            
            if not video_stream:
                raise Exception("No video stream found")
                
            metadata = {
                'duration': float(data['format'].get('duration', 0)),
                'fps': eval(video_stream.get('r_frame_rate', '0/1')),
                'resolution': f"{video_stream.get('width', 0)}x{video_stream.get('height', 0)}",
                'codec': video_stream.get('codec_name', 'unknown')
            }
            
            return metadata
            
        except subprocess.TimeoutExpired:
            raise Exception("Video validation timeout")
        except Exception as e:
            raise Exception(f"Failed to extract video metadata: {str(e)}")
            
    async def _scan_file_for_viruses(self, file: UploadFile):
        """Basic virus scanning implementation."""
        # Read first 1MB for basic pattern checking
        chunk = await file.read(1024 * 1024)
        await file.seek(0)
        
        # Basic malware signature detection (simplified)
        suspicious_patterns = [
            b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR',  # EICAR test signature
            b'<script',  # Script injection
            b'javascript:',  # JavaScript injection
        ]
        
        for pattern in suspicious_patterns:
            if pattern in chunk:
                raise HTTPException(
                    status_code=400, 
                    detail="File contains suspicious content"
                )
                
    async def _save_file_with_hash(self, file: UploadFile, file_path: Path) -> str:
        """Save file and calculate hash for integrity verification."""
        hasher = hashlib.sha256()
        
        async with aiofiles.open(file_path, 'wb') as f:
            while chunk := await file.read(8192):
                hasher.update(chunk)
                await f.write(chunk)
                
        return hasher.hexdigest()
        
    def _detect_encoding(self, content: bytes) -> str:
        """Detect text encoding of SRT file."""
        import chardet
        result = chardet.detect(content)
        return result.get('encoding', 'utf-8')
        
    def _parse_srt_content(self, content: str) -> List[Dict]:
        """Parse SRT file content and extract subtitle data."""
        import re
        
        # SRT format regex pattern
        pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\d+\n|\n*$)'
        
        matches = re.findall(pattern, content, re.DOTALL)
        
        subtitles = []
        for match in matches:
            index, start_time, end_time, text = match
            
            # Convert time to seconds
            start_seconds = self._time_to_seconds(start_time)
            end_seconds = self._time_to_seconds(end_time)
            
            subtitles.append({
                'index': int(index),
                'start_time': start_seconds,
                'end_time': end_seconds,
                'text': text.strip().replace('\n', ' ')
            })
            
        return subtitles
        
    def _time_to_seconds(self, time_str: str) -> float:
        """Convert SRT time format to seconds."""
        # Format: HH:MM:SS,mmm
        time_part, ms_part = time_str.split(',')
        h, m, s = map(int, time_part.split(':'))
        ms = int(ms_part)
        
        return h * 3600 + m * 60 + s + ms / 1000.0


# Global service instance
upload_service = FileUploadService()


class SRTProcessor:
    """Service for processing SRT files and mapping to scenes."""
    
    def __init__(self):
        pass
    
    async def process_srt_with_video(self, srt_path: str, video_path: str) -> Dict:
        """
        Process SRT file and map subtitles to video scenes.
        
        Args:
            srt_path: Path to the SRT file
            video_path: Path to the video file for scene detection
            
        Returns:
            Dict containing processed scenes with dialogue
        """
        # Parse SRT file
        srt_data = await self._load_srt_file(srt_path)
        
        # Get video metadata for scene detection
        video_metadata = await self._get_video_metadata(video_path)
        
        # Detect scenes in video (simplified - would use actual scene detection)
        scenes = await self._detect_video_scenes(video_path)
        
        # Map SRT dialogue to scenes
        mapped_scenes = await self._map_dialogue_to_scenes(srt_data, scenes)
        
        # Detect music in scenes (placeholder implementation)
        scenes_with_music = await self._detect_music_in_scenes(mapped_scenes, video_path)
        
        return {
            'scenes': scenes_with_music,
            'total_duration': video_metadata.get('duration', 0),
            'subtitle_count': len(srt_data),
            'processing_mode': 'srt_mode'
        }
    
    async def _load_srt_file(self, srt_path: str) -> List[Dict]:
        """Load and parse SRT file."""
        async with aiofiles.open(srt_path, 'r', encoding='utf-8') as f:
            content = await f.read()
        
        return upload_service._parse_srt_content(content)
    
    async def _get_video_metadata(self, video_path: str) -> Dict:
        """Get video metadata using FFmpeg."""
        return await upload_service._extract_video_metadata(Path(video_path))
    
    async def _detect_video_scenes(self, video_path: str) -> List[Dict]:
        """
        Detect scenes in video using scene detection.
        This is a simplified implementation - would use python-scenedetect in production.
        """
        # For now, create mock scenes based on SRT timing
        # In production, this would use actual scene detection
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', video_path
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                raise Exception(f"FFprobe failed: {result.stderr}")
                
            import json
            data = json.loads(result.stdout)
            duration = float(data['format'].get('duration', 0))
            
            # Create mock scenes every 30 seconds for demonstration
            scenes = []
            scene_duration = 30.0  # seconds
            scene_count = int(duration / scene_duration) + 1
            
            for i in range(scene_count):
                start_time = i * scene_duration
                end_time = min((i + 1) * scene_duration, duration)
                
                scenes.append({
                    'scene_id': i + 1,
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration': end_time - start_time,
                    'dialogue': [],
                    'has_music': False
                })
            
            return scenes
            
        except Exception as e:
            raise Exception(f"Scene detection failed: {str(e)}")
    
    async def _map_dialogue_to_scenes(self, srt_data: List[Dict], scenes: List[Dict]) -> List[Dict]:
        """
        Map SRT dialogue to video scenes without breaking sentences.
        Implements requirement 5.7 from the design document.
        """
        for scene in scenes:
            scene['dialogue'] = []
            scene['speakers'] = []
        
        for subtitle in srt_data:
            subtitle_start = subtitle['start_time']
            subtitle_end = subtitle['end_time']
            subtitle_text = subtitle['text']
            
            # Find which scene(s) this subtitle overlaps with
            overlapping_scenes = []
            for scene in scenes:
                if (subtitle_start < scene['end_time'] and 
                    subtitle_end > scene['start_time']):
                    overlapping_scenes.append(scene)
            
            if not overlapping_scenes:
                continue
            
            # If subtitle spans multiple scenes, handle sentence boundaries
            if len(overlapping_scenes) == 1:
                # Simple case: subtitle fits in one scene
                scene = overlapping_scenes[0]
                scene['dialogue'].append({
                    'start_time': subtitle_start,
                    'end_time': subtitle_end,
                    'text': subtitle_text,
                    'speaker': self._detect_speaker(subtitle_text)
                })
            else:
                # Complex case: subtitle spans multiple scenes
                # Split at sentence boundaries or use ellipsis
                sentences = self._split_into_sentences(subtitle_text)
                
                if len(sentences) <= len(overlapping_scenes):
                    # Distribute sentences across scenes
                    for i, sentence in enumerate(sentences):
                        if i < len(overlapping_scenes):
                            scene = overlapping_scenes[i]
                            scene['dialogue'].append({
                                'start_time': subtitle_start,
                                'end_time': subtitle_end,
                                'text': sentence.strip(),
                                'speaker': self._detect_speaker(sentence)
                            })
                else:
                    # Use ellipsis for continuation
                    for i, scene in enumerate(overlapping_scenes):
                        if i == 0:
                            # First scene gets text with ellipsis
                            text = subtitle_text + "..."
                        elif i == len(overlapping_scenes) - 1:
                            # Last scene gets ellipsis + text
                            text = "..." + subtitle_text
                        else:
                            # Middle scenes get ellipsis on both sides
                            text = "..." + subtitle_text + "..."
                        
                        scene['dialogue'].append({
                            'start_time': subtitle_start,
                            'end_time': subtitle_end,
                            'text': text,
                            'speaker': self._detect_speaker(subtitle_text)
                        })
        
        return scenes
    
    async def _detect_music_in_scenes(self, scenes: List[Dict], video_path: str) -> List[Dict]:
        """
        Detect music in video scenes.
        This is a placeholder implementation - would use audio analysis in production.
        """
        # For now, randomly mark some scenes as having music
        # In production, this would analyze audio frequency patterns
        import random
        
        for scene in scenes:
            # Simple heuristic: if scene has no dialogue, it might have music
            if not scene['dialogue']:
                scene['has_music'] = random.choice([True, False])
            else:
                # Scenes with dialogue are less likely to have prominent music
                scene['has_music'] = random.choice([True, False]) if random.random() < 0.3 else False
        
        return scenes
    
    def _detect_speaker(self, text: str) -> Optional[str]:
        """
        Detect speaker from subtitle text.
        Simple implementation - looks for speaker indicators.
        """
        # Look for common speaker patterns
        import re
        
        # Pattern: "SPEAKER: text" or "Speaker: text"
        speaker_pattern = r'^([A-ZА-Я][A-ZА-Я\s]+):\s*'
        match = re.match(speaker_pattern, text)
        
        if match:
            return match.group(1).strip()
        
        # Pattern: "(Speaker) text" or "[Speaker] text"
        bracket_pattern = r'^[\(\[]([A-ZА-Я][A-ZА-Я\s]+)[\)\]]\s*'
        match = re.match(bracket_pattern, text)
        
        if match:
            return match.group(1).strip()
        
        return None  # Unknown speaker
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences for proper scene boundary handling."""
        import re
        
        # Simple sentence splitting for Russian and English
        sentence_endings = r'[.!?]+\s+'
        sentences = re.split(sentence_endings, text)
        
        # Filter out empty sentences
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences if sentences else [text]


# Global SRT processor instance
srt_processor = SRTProcessor()