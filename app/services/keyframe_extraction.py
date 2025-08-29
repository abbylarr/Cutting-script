"""
Keyframe extraction service for video analysis.

This service extracts keyframes at specific positions (35% and 70%) from video scenes
using FFmpeg, with frame quality assessment and optimization.
"""

import asyncio
import os
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Keyframe:
    """Represents an extracted keyframe with metadata."""
    scene_index: int
    position_percent: float  # 35.0 or 70.0
    timestamp: float  # seconds
    file_path: str
    quality_score: Optional[float] = None


@dataclass
class Scene:
    """Scene data structure for keyframe extraction."""
    start_time: float
    end_time: float
    duration: float
    
    @property
    def keyframe_35_time(self) -> float:
        """Calculate timestamp for 35% position in scene."""
        return self.start_time + (self.duration * 0.35)
    
    @property
    def keyframe_70_time(self) -> float:
        """Calculate timestamp for 70% position in scene."""
        return self.start_time + (self.duration * 0.70)


class KeyframeExtractionService:
    """Service for extracting keyframes from video scenes using FFmpeg."""
    
    def __init__(self, output_dir: str = "output/keyframes"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    async def extract_keyframes_from_scenes(
        self, 
        video_path: str, 
        scenes: List[Scene],
        task_id: str
    ) -> List[Keyframe]:
        """
        Extract keyframes at 35% and 70% positions for all scenes.
        
        Args:
            video_path: Path to the video file
            scenes: List of scene objects with timing information
            task_id: Unique task identifier for file organization
            
        Returns:
            List of extracted keyframes with metadata
        """
        keyframes = []
        
        # Create task-specific directory
        task_dir = self.output_dir / task_id
        task_dir.mkdir(exist_ok=True)
        
        for i, scene in enumerate(scenes):
            try:
                # Extract keyframes at 35% and 70% positions
                keyframe_35 = await self._extract_single_keyframe(
                    video_path, scene.keyframe_35_time, i, 35.0, task_dir
                )
                keyframe_70 = await self._extract_single_keyframe(
                    video_path, scene.keyframe_70_time, i, 70.0, task_dir
                )
                
                # Assess frame quality
                if keyframe_35:
                    keyframe_35.quality_score = await self._assess_frame_quality(keyframe_35.file_path)
                    keyframes.append(keyframe_35)
                    
                if keyframe_70:
                    keyframe_70.quality_score = await self._assess_frame_quality(keyframe_70.file_path)
                    keyframes.append(keyframe_70)
                    
                logger.info(f"Extracted keyframes for scene {i}: 35% and 70% positions")
                
            except Exception as e:
                logger.error(f"Failed to extract keyframes for scene {i}: {e}")
                continue
                
        return keyframes
    
    async def _extract_single_keyframe(
        self, 
        video_path: str, 
        timestamp: float, 
        scene_index: int, 
        position_percent: float,
        output_dir: Path
    ) -> Optional[Keyframe]:
        """
        Extract a single keyframe at specified timestamp using FFmpeg.
        
        Args:
            video_path: Path to the video file
            timestamp: Time position in seconds
            scene_index: Index of the scene
            position_percent: Position percentage (35.0 or 70.0)
            output_dir: Directory to save the keyframe
            
        Returns:
            Keyframe object or None if extraction failed
        """
        output_filename = f"scene_{scene_index:03d}_{int(position_percent)}pct.jpg"
        output_path = output_dir / output_filename
        
        # FFmpeg command for keyframe extraction with quality optimization
        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-ss", str(timestamp),
            "-vframes", "1",
            "-q:v", "2",  # High quality JPEG
            "-vf", "scale='min(1920,iw)':'min(1080,ih)':force_original_aspect_ratio=decrease",  # Optimize size
            "-y",  # Overwrite output file
            str(output_path)
        ]
        
        try:
            # Run FFmpeg command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"FFmpeg failed for keyframe extraction: {stderr.decode()}")
                return None
                
            if not output_path.exists():
                logger.error(f"Keyframe file not created: {output_path}")
                return None
                
            return Keyframe(
                scene_index=scene_index,
                position_percent=position_percent,
                timestamp=timestamp,
                file_path=str(output_path)
            )
            
        except Exception as e:
            logger.error(f"Error extracting keyframe at {timestamp}s: {e}")
            return None
    
    async def _assess_frame_quality(self, image_path: str) -> float:
        """
        Assess the quality of an extracted frame using image analysis.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Quality score between 0.0 and 1.0 (higher is better)
        """
        try:
            # Use FFmpeg to analyze frame quality metrics
            cmd = [
                "ffmpeg",
                "-i", image_path,
                "-vf", "idet,cropdetect=24:16:0",
                "-f", "null",
                "-"
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # Parse quality metrics from FFmpeg output
            quality_score = self._parse_quality_metrics(stderr.decode())
            
            return quality_score
            
        except Exception as e:
            logger.warning(f"Could not assess frame quality for {image_path}: {e}")
            return 0.5  # Default medium quality score
    
    def _parse_quality_metrics(self, ffmpeg_output: str) -> float:
        """
        Parse quality metrics from FFmpeg output.
        
        Args:
            ffmpeg_output: FFmpeg stderr output containing analysis
            
        Returns:
            Quality score between 0.0 and 1.0
        """
        # Simple quality assessment based on common issues
        quality_score = 1.0
        
        # Check for interlacing (reduces quality)
        if "Interlaced" in ffmpeg_output:
            quality_score -= 0.2
            
        # Check for black borders (may indicate poor framing)
        if "crop=" in ffmpeg_output:
            # Extract crop parameters to assess border size
            import re
            crop_match = re.search(r'crop=(\d+):(\d+):(\d+):(\d+)', ffmpeg_output)
            if crop_match:
                # If significant cropping is detected, slightly reduce quality
                quality_score -= 0.1
        
        # Ensure score stays within bounds
        return max(0.0, min(1.0, quality_score))
    
    async def optimize_keyframe_storage(self, keyframes: List[Keyframe]) -> List[Keyframe]:
        """
        Optimize keyframe images for storage and web display.
        
        Args:
            keyframes: List of keyframes to optimize
            
        Returns:
            List of optimized keyframes
        """
        optimized_keyframes = []
        
        for keyframe in keyframes:
            try:
                # Create optimized version
                optimized_path = await self._create_optimized_image(keyframe.file_path)
                
                if optimized_path:
                    # Update keyframe with optimized path
                    optimized_keyframe = Keyframe(
                        scene_index=keyframe.scene_index,
                        position_percent=keyframe.position_percent,
                        timestamp=keyframe.timestamp,
                        file_path=optimized_path,
                        quality_score=keyframe.quality_score
                    )
                    optimized_keyframes.append(optimized_keyframe)
                else:
                    # Keep original if optimization failed
                    optimized_keyframes.append(keyframe)
                    
            except Exception as e:
                logger.warning(f"Failed to optimize keyframe {keyframe.file_path}: {e}")
                optimized_keyframes.append(keyframe)
                
        return optimized_keyframes
    
    async def _create_optimized_image(self, original_path: str) -> Optional[str]:
        """
        Create an optimized version of the keyframe image.
        
        Args:
            original_path: Path to the original image
            
        Returns:
            Path to optimized image or None if failed
        """
        try:
            original = Path(original_path)
            optimized_path = original.parent / f"{original.stem}_opt{original.suffix}"
            
            # FFmpeg command for image optimization
            cmd = [
                "ffmpeg",
                "-i", str(original),
                "-vf", "scale='min(800,iw)':'min(600,ih)':force_original_aspect_ratio=decrease",
                "-q:v", "3",  # Slightly lower quality for smaller size
                "-y",
                str(optimized_path)
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.communicate()
            
            if process.returncode == 0 and optimized_path.exists():
                return str(optimized_path)
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error creating optimized image: {e}")
            return None
    
    def cleanup_keyframes(self, task_id: str) -> None:
        """
        Clean up keyframe files for a specific task.
        
        Args:
            task_id: Task identifier for cleanup
        """
        try:
            task_dir = self.output_dir / task_id
            if task_dir.exists():
                import shutil
                shutil.rmtree(task_dir)
                logger.info(f"Cleaned up keyframes for task {task_id}")
        except Exception as e:
            logger.error(f"Failed to cleanup keyframes for task {task_id}: {e}")