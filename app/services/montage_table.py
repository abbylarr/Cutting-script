"""
Montage table generation and formatting services.
Combines processed data from scenes, dialogue, and visual analysis into montage tables.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import re

from app.schemas.film_project import MontageRow, ShotType, ProjectSettings
from app.services.video_processor import Scene
from app.services.dialogue_mapping import SceneDialogue, DialogueMappingResult
from app.services.gpt_visual_analysis import SceneAnalysisResult
from app.services.music_detection import MusicDetectionResult

logger = logging.getLogger(__name__)


@dataclass
class ProcessedSceneData:
    """Container for all processed data for a single scene."""
    scene: Scene
    dialogue: Optional[SceneDialogue] = None
    visual_analysis: Optional[SceneAnalysisResult] = None
    has_music: bool = False
    music_confidence: float = 0.0


@dataclass
class MontageTableResult:
    """Result of montage table generation."""
    montage_rows: List[MontageRow]
    total_scenes: int
    processing_time: float
    validation_errors: List[str]
    statistics: Dict[str, Any]


class MontageTableGenerationError(Exception):
    """Raised when montage table generation fails."""
    pass


class TimecodeService:
    """Service for handling timecode conversion and continuity."""
    
    # Standard frame rates for different standards
    STANDARD_FRAME_RATES = {
        "ГФФ": {
            "default": 25.0,
            "supported": [24.0, 25.0, 50.0]
        },
        "Красногорский": {
            "default": 25.0,
            "supported": [24.0, 25.0, 29.97, 30.0, 50.0, 59.94, 60.0]
        }
    }
    
    def __init__(self, project_settings: Optional[ProjectSettings] = None, detected_fps: Optional[float] = None):
        """
        Initialize timecode service with project settings.
        
        Args:
            project_settings: Project settings containing timecode configuration
            detected_fps: Frame rate detected from video file
        """
        if project_settings:
            self.start_time = project_settings.timecode_start
            self.standard = project_settings.standard.value if hasattr(project_settings.standard, 'value') else project_settings.standard
            self.fps = project_settings.fps
        else:
            # Default settings
            self.start_time = "01:00:00:00"
            self.standard = "ГФФ"
            self.fps = 25.0
        
        # Use detected FPS if available and valid
        if detected_fps:
            validated_fps = self._validate_and_adjust_fps(detected_fps, self.standard)
            if validated_fps:
                self.fps = validated_fps
        
        # Parse start time into seconds
        self.start_seconds = self._timecode_to_seconds(self.start_time)
        
        # Calculate frame duration for continuity calculations
        self.frame_duration = 1.0 / self.fps
    
    def _validate_and_adjust_fps(self, detected_fps: float, standard: str) -> Optional[float]:
        """
        Validate and adjust detected frame rate according to standard.
        
        Args:
            detected_fps: Frame rate detected from video
            standard: Timecode standard (ГФФ or Красногорский)
            
        Returns:
            Validated frame rate or None if invalid
        """
        if standard not in self.STANDARD_FRAME_RATES:
            logger.warning(f"Unknown standard: {standard}, using default FPS")
            return None
        
        supported_rates = self.STANDARD_FRAME_RATES[standard]["supported"]
        
        # Find closest supported frame rate
        closest_fps = min(supported_rates, key=lambda x: abs(x - detected_fps))
        
        # Allow small tolerance for frame rate detection errors
        tolerance = 0.1
        if abs(detected_fps - closest_fps) <= tolerance:
            logger.info(f"Using frame rate {closest_fps} fps (detected: {detected_fps})")
            return closest_fps
        
        # If detected FPS is not close to any supported rate, log warning
        logger.warning(f"Detected FPS {detected_fps} not supported for standard {standard}")
        return None
    
    @classmethod
    def detect_frame_rate_from_video(cls, video_path: str) -> Optional[float]:
        """
        Detect frame rate from video file using FFprobe.
        
        Args:
            video_path: Path to video file
            
        Returns:
            Detected frame rate or None if detection fails
        """
        try:
            from app.services.video_processor import VideoValidationService
            
            validation_service = VideoValidationService()
            
            # Use asyncio to run the async method
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                metadata = loop.run_until_complete(
                    validation_service._extract_metadata(video_path)
                )
                return metadata.fps
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Failed to detect frame rate from {video_path}: {e}")
            return None
    
    def _timecode_to_seconds(self, timecode: str) -> float:
        """
        Convert timecode string to seconds.
        
        Args:
            timecode: Timecode in HH:MM:SS:FF format
            
        Returns:
            Time in seconds
        """
        try:
            parts = timecode.split(':')
            if len(parts) != 4:
                raise ValueError(f"Invalid timecode format: {timecode}")
            
            hours, minutes, seconds, frames = map(int, parts)
            
            total_seconds = (
                hours * 3600 +
                minutes * 60 +
                seconds +
                frames / self.fps
            )
            
            return total_seconds
            
        except (ValueError, ZeroDivisionError) as e:
            raise ValueError(f"Invalid timecode: {timecode} - {e}")
    
    def _seconds_to_timecode(self, seconds: float) -> str:
        """
        Convert seconds to timecode string.
        
        Args:
            seconds: Time in seconds
            
        Returns:
            Timecode in HH:MM:SS:FF format
        """
        # Add start time offset
        total_seconds = self.start_seconds + seconds
        
        # Extract components
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        secs = int(total_seconds % 60)
        frames = round((total_seconds % 1) * self.fps)
        
        # Handle frame overflow
        if frames >= self.fps:
            frames = 0
            secs += 1
            if secs >= 60:
                secs = 0
                minutes += 1
                if minutes >= 60:
                    minutes = 0
                    hours += 1
        
        # Format with zero padding
        return f"{hours:02d}:{minutes:02d}:{secs:02d}:{frames:02d}"
    
    def ensure_scene_continuity(self, scenes: List[Scene], preserve_original_timing: bool = False) -> List[Scene]:
        """
        Ensure exactly one frame gap between scenes for continuity.
        
        Args:
            scenes: List of scenes to process
            preserve_original_timing: If True, preserve original scene timing where possible
            
        Returns:
            List of scenes with adjusted timing for continuity
        """
        if len(scenes) <= 1:
            return scenes
        
        adjusted_scenes = [scenes[0]]  # First scene remains unchanged
        
        for i in range(1, len(scenes)):
            prev_scene = adjusted_scenes[i - 1]
            current_scene = scenes[i]
            
            # Adjust start time to be exactly one frame after previous scene end
            adjusted_start = prev_scene.end_time + self.frame_duration
            
            if preserve_original_timing:
                # Try to preserve original duration
                original_duration = current_scene.end_time - current_scene.start_time
                adjusted_end = adjusted_start + original_duration
            else:
                # Use original end time if it doesn't create overlap
                original_end = current_scene.end_time
                min_end = adjusted_start + self.frame_duration  # Minimum scene duration of 1 frame
                adjusted_end = max(original_end, min_end)
            
            # Create adjusted scene
            adjusted_scene = Scene(
                start_time=adjusted_start,
                end_time=adjusted_end,
                duration=adjusted_end - adjusted_start,
                scene_number=current_scene.scene_number
            )
            
            adjusted_scenes.append(adjusted_scene)
        
        return adjusted_scenes
    
    def calculate_scene_timecodes(self, scenes: List[Scene]) -> List[Tuple[str, str]]:
        """
        Calculate start and end timecodes for all scenes.
        
        Args:
            scenes: List of scenes with timing information
            
        Returns:
            List of (start_timecode, end_timecode) tuples
        """
        timecodes = []
        
        for scene in scenes:
            start_tc = self._seconds_to_timecode(scene.start_time)
            end_tc = self._seconds_to_timecode(scene.end_time)
            timecodes.append((start_tc, end_tc))
        
        return timecodes
    
    def adjust_scene_timing_for_frame_accuracy(self, scenes: List[Scene]) -> List[Scene]:
        """
        Adjust scene timing to align with frame boundaries.
        
        Args:
            scenes: List of scenes to adjust
            
        Returns:
            List of scenes with frame-accurate timing
        """
        adjusted_scenes = []
        
        for scene in scenes:
            # Round start and end times to nearest frame
            start_frame = round(scene.start_time * self.fps)
            end_frame = round(scene.end_time * self.fps)
            
            # Ensure minimum scene length of 1 frame
            if end_frame <= start_frame:
                end_frame = start_frame + 1
            
            # Convert back to seconds
            adjusted_start = start_frame / self.fps
            adjusted_end = end_frame / self.fps
            
            adjusted_scene = Scene(
                start_time=adjusted_start,
                end_time=adjusted_end,
                duration=adjusted_end - adjusted_start,
                scene_number=scene.scene_number
            )
            
            adjusted_scenes.append(adjusted_scene)
        
        return adjusted_scenes
    
    def validate_timecode_continuity(self, scenes: List[Scene]) -> List[str]:
        """
        Validate that scenes have proper continuity.
        
        Args:
            scenes: List of scenes to validate
            
        Returns:
            List of validation error messages
        """
        errors = []
        tolerance = self.frame_duration * 0.1  # 10% tolerance
        
        for i in range(1, len(scenes)):
            prev_scene = scenes[i - 1]
            current_scene = scenes[i]
            
            expected_start = prev_scene.end_time + self.frame_duration
            actual_gap = current_scene.start_time - prev_scene.end_time
            
            if abs(actual_gap - self.frame_duration) > tolerance:
                errors.append(
                    f"Scene {i + 1}: Gap of {actual_gap:.3f}s instead of expected {self.frame_duration:.3f}s"
                )
        
        return errors
    
    def validate_timecode_format(self, timecode: str) -> Tuple[bool, Optional[str]]:
        """
        Validate timecode format and values.
        
        Args:
            timecode: Timecode string to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        import re
        
        # Check format
        pattern = re.compile(r'^(\d{2}):(\d{2}):(\d{2}):(\d{2})$')
        match = pattern.match(timecode)
        
        if not match:
            return False, f"Invalid timecode format: {timecode} (expected HH:MM:SS:FF)"
        
        hours, minutes, seconds, frames = map(int, match.groups())
        
        # Validate ranges
        if minutes >= 60:
            return False, f"Invalid minutes: {minutes} (must be 0-59)"
        
        if seconds >= 60:
            return False, f"Invalid seconds: {seconds} (must be 0-59)"
        
        if frames >= self.fps:
            return False, f"Invalid frames: {frames} (must be 0-{int(self.fps)-1} for {self.fps} fps)"
        
        return True, None
    
    def get_timecode_info(self) -> Dict[str, Any]:
        """
        Get information about current timecode configuration.
        
        Returns:
            Dictionary with timecode configuration info
        """
        return {
            "start_time": self.start_time,
            "standard": self.standard,
            "fps": self.fps,
            "frame_duration": self.frame_duration,
            "start_seconds": self.start_seconds,
            "supported_fps": self.STANDARD_FRAME_RATES.get(self.standard, {}).get("supported", [])
        }


class MontageTableAssemblyService:
    """Service for assembling montage tables from processed data."""
    
    def __init__(self, project_settings: Optional[ProjectSettings] = None):
        """
        Initialize montage table assembly service.
        
        Args:
            project_settings: Project settings for timecode configuration
        """
        self.timecode_service = TimecodeService(project_settings)
        self.project_settings = project_settings
    
    async def generate_montage_table(
        self,
        scenes: List[Scene],
        dialogue_result: Optional[DialogueMappingResult] = None,
        visual_analysis_results: Optional[List[SceneAnalysisResult]] = None,
        music_detection_result: Optional[MusicDetectionResult] = None
    ) -> MontageTableResult:
        """
        Generate complete montage table from processed data.
        
        Args:
            scenes: List of detected scenes
            dialogue_result: Optional dialogue mapping result
            visual_analysis_results: Optional visual analysis results
            music_detection_result: Optional music detection result
            
        Returns:
            MontageTableResult with generated montage rows
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            logger.info(f"Generating montage table for {len(scenes)} scenes")
            
            # Ensure scene continuity
            scenes = self.timecode_service.ensure_scene_continuity(scenes)
            
            # Validate continuity
            validation_errors = self.timecode_service.validate_timecode_continuity(scenes)
            
            # Combine all processed data
            processed_scenes = await self._combine_processed_data(
                scenes, dialogue_result, visual_analysis_results, music_detection_result
            )
            
            # Generate montage rows
            montage_rows = await self._generate_montage_rows(processed_scenes)
            
            # Validate montage rows
            row_validation_errors = await self._validate_montage_rows(montage_rows)
            validation_errors.extend(row_validation_errors)
            
            # Generate statistics
            statistics = await self._generate_statistics(montage_rows, processed_scenes)
            
            processing_time = asyncio.get_event_loop().time() - start_time
            
            logger.info(f"Montage table generation completed: {len(montage_rows)} rows")
            
            return MontageTableResult(
                montage_rows=montage_rows,
                total_scenes=len(scenes),
                processing_time=processing_time,
                validation_errors=validation_errors,
                statistics=statistics
            )
            
        except Exception as e:
            logger.error(f"Montage table generation failed: {e}")
            raise MontageTableGenerationError(f"Failed to generate montage table: {e}")
    
    async def _combine_processed_data(
        self,
        scenes: List[Scene],
        dialogue_result: Optional[DialogueMappingResult],
        visual_analysis_results: Optional[List[SceneAnalysisResult]],
        music_detection_result: Optional[MusicDetectionResult]
    ) -> List[ProcessedSceneData]:
        """
        Combine all processed data for each scene.
        
        Args:
            scenes: List of scenes
            dialogue_result: Optional dialogue mapping result
            visual_analysis_results: Optional visual analysis results
            music_detection_result: Optional music detection result
            
        Returns:
            List of ProcessedSceneData objects
        """
        processed_scenes = []
        
        # Create mappings for quick lookup
        dialogue_map = {}
        if dialogue_result:
            for scene_dialogue in dialogue_result.scene_dialogues:
                dialogue_map[scene_dialogue.scene_number - 1] = scene_dialogue
        
        visual_analysis_map = {}
        if visual_analysis_results:
            for analysis in visual_analysis_results:
                visual_analysis_map[analysis.scene_index] = analysis
        
        music_map = {}
        if music_detection_result:
            for scene_analysis in music_detection_result.scene_analyses:
                # Convert scene_number to 0-based index
                scene_index = scene_analysis.scene_number - 1
                music_map[scene_index] = scene_analysis
        
        # Combine data for each scene
        for i, scene in enumerate(scenes):
            dialogue = dialogue_map.get(i)
            visual_analysis = visual_analysis_map.get(i)
            
            # Get music information
            has_music = False
            music_confidence = 0.0
            if i in music_map:
                music_analysis = music_map[i]
                has_music = music_analysis.has_music
                music_confidence = music_analysis.average_music_confidence
            
            processed_scene = ProcessedSceneData(
                scene=scene,
                dialogue=dialogue,
                visual_analysis=visual_analysis,
                has_music=has_music,
                music_confidence=music_confidence
            )
            
            processed_scenes.append(processed_scene)
        
        return processed_scenes
    
    async def _generate_montage_rows(
        self, 
        processed_scenes: List[ProcessedSceneData]
    ) -> List[MontageRow]:
        """
        Generate montage rows from processed scene data.
        
        Args:
            processed_scenes: List of processed scene data
            
        Returns:
            List of MontageRow objects
        """
        montage_rows = []
        
        for i, scene_data in enumerate(processed_scenes):
            scene = scene_data.scene
            
            # Generate timecodes
            start_timecode = self.timecode_service._seconds_to_timecode(scene.start_time)
            end_timecode = self.timecode_service._seconds_to_timecode(scene.end_time)
            
            # Extract shot type from visual analysis
            shot_type = ShotType.MEDIUM  # Default
            if scene_data.visual_analysis:
                shot_type = self._convert_shot_type(
                    scene_data.visual_analysis.visual_analysis.shot_type
                )
            
            # Generate description
            description = await self._generate_scene_description(scene_data)
            
            # Extract dialogue
            dialogue = ""
            speaker = None
            if scene_data.dialogue and scene_data.dialogue.dialogue_segments:
                dialogue = scene_data.dialogue.full_text
                # Get primary speaker (most dialogue)
                speaker_counts = {}
                for segment in scene_data.dialogue.dialogue_segments:
                    if segment.speaker:
                        speaker_counts[segment.speaker] = speaker_counts.get(segment.speaker, 0) + len(segment.text)
                
                if speaker_counts:
                    speaker = max(speaker_counts.items(), key=lambda x: x[1])[0]
            
            # Extract special tags
            special_tags = []
            if scene_data.visual_analysis:
                for tag in scene_data.visual_analysis.visual_analysis.special_tags:
                    special_tags.append(tag.value)
            
            # Add music tag if detected
            if scene_data.has_music:
                if "Музыка" not in special_tags:
                    special_tags.append("Музыка")
            
            # Create montage row
            montage_row = MontageRow(
                number=i + 1,
                start_timecode=start_timecode,
                end_timecode=end_timecode,
                shot_type=shot_type,
                description=description,
                dialogue=dialogue,
                speaker=speaker,
                has_music=scene_data.has_music,
                special_tags=special_tags
            )
            
            montage_rows.append(montage_row)
        
        return montage_rows
    
    def _convert_shot_type(self, visual_shot_type) -> ShotType:
        """
        Convert visual analysis shot type to schema shot type.
        
        Args:
            visual_shot_type: Shot type from visual analysis
            
        Returns:
            ShotType enum value
        """
        # Map visual analysis shot types to schema shot types
        shot_type_mapping = {
            "Дальний": ShotType.DISTANT,
            "Общий": ShotType.GENERAL,
            "Средний": ShotType.MEDIUM,
            "Крупный": ShotType.CLOSE,
            "Деталь": ShotType.DETAIL
        }
        
        if hasattr(visual_shot_type, 'value'):
            shot_type_str = visual_shot_type.value
        else:
            shot_type_str = str(visual_shot_type)
        
        return shot_type_mapping.get(shot_type_str, ShotType.MEDIUM)
    
    async def _generate_scene_description(self, scene_data: ProcessedSceneData) -> str:
        """
        Generate scene description from available data.
        
        Args:
            scene_data: Processed scene data
            
        Returns:
            Scene description string
        """
        # Use visual analysis description if available
        if scene_data.visual_analysis and scene_data.visual_analysis.visual_analysis.description:
            description = scene_data.visual_analysis.visual_analysis.description
            
            # Add text in frame if available
            if scene_data.visual_analysis.visual_analysis.text_in_frame:
                text_in_frame = scene_data.visual_analysis.visual_analysis.text_in_frame
                if text_in_frame.strip() and text_in_frame.lower() != "нет":
                    description += f" Надпись: {text_in_frame}"
            
            return description
        
        # Fallback to basic description
        duration = scene_data.scene.duration
        scene_num = scene_data.scene.scene_number
        
        description = f"Сцена {scene_num}"
        
        # Add duration info for very long or short scenes
        if duration > 30:
            description += f" (длительная сцена {duration:.1f}с)"
        elif duration < 2:
            description += f" (короткая сцена {duration:.1f}с)"
        
        return description
    
    async def _validate_montage_rows(self, montage_rows: List[MontageRow]) -> List[str]:
        """
        Validate generated montage rows for consistency and completeness.
        
        Args:
            montage_rows: List of montage rows to validate
            
        Returns:
            List of validation error messages
        """
        errors = []
        
        if not montage_rows:
            errors.append("No montage rows generated")
            return errors
        
        # Check row numbering
        for i, row in enumerate(montage_rows):
            expected_number = i + 1
            if row.number != expected_number:
                errors.append(f"Row {i + 1}: Incorrect number {row.number}, expected {expected_number}")
        
        # Check timecode format and continuity
        timecode_pattern = re.compile(r'^\d{2}:\d{2}:\d{2}:\d{2}$')
        
        for i, row in enumerate(montage_rows):
            # Validate timecode format
            if not timecode_pattern.match(row.start_timecode):
                errors.append(f"Row {i + 1}: Invalid start timecode format: {row.start_timecode}")
            
            if not timecode_pattern.match(row.end_timecode):
                errors.append(f"Row {i + 1}: Invalid end timecode format: {row.end_timecode}")
            
            # Check that end time is after start time
            try:
                start_seconds = self.timecode_service._timecode_to_seconds(row.start_timecode)
                end_seconds = self.timecode_service._timecode_to_seconds(row.end_timecode)
                
                if end_seconds <= start_seconds:
                    errors.append(f"Row {i + 1}: End time must be after start time")
                    
            except ValueError as e:
                errors.append(f"Row {i + 1}: Timecode validation error: {e}")
        
        # Check for required fields
        for i, row in enumerate(montage_rows):
            if not row.description.strip():
                errors.append(f"Row {i + 1}: Missing description")
            
            if not isinstance(row.shot_type, ShotType):
                errors.append(f"Row {i + 1}: Invalid shot type: {row.shot_type}")
        
        return errors
    
    async def _generate_statistics(
        self, 
        montage_rows: List[MontageRow], 
        processed_scenes: List[ProcessedSceneData]
    ) -> Dict[str, Any]:
        """
        Generate statistics about the montage table.
        
        Args:
            montage_rows: Generated montage rows
            processed_scenes: Processed scene data
            
        Returns:
            Dictionary with statistics
        """
        if not montage_rows:
            return {}
        
        # Count shot types
        shot_type_counts = {}
        for row in montage_rows:
            shot_type = row.shot_type.value
            shot_type_counts[shot_type] = shot_type_counts.get(shot_type, 0) + 1
        
        # Count special tags
        special_tag_counts = {}
        for row in montage_rows:
            for tag in row.special_tags:
                special_tag_counts[tag] = special_tag_counts.get(tag, 0) + 1
        
        # Count scenes with dialogue
        scenes_with_dialogue = sum(1 for row in montage_rows if row.dialogue.strip())
        
        # Count scenes with music
        scenes_with_music = sum(1 for row in montage_rows if row.has_music)
        
        # Count unique speakers
        unique_speakers = set()
        for row in montage_rows:
            if row.speaker:
                unique_speakers.add(row.speaker)
        
        # Calculate total duration
        total_duration = 0.0
        for scene_data in processed_scenes:
            total_duration += scene_data.scene.duration
        
        return {
            "total_rows": len(montage_rows),
            "total_duration": total_duration,
            "average_scene_duration": total_duration / len(montage_rows),
            "shot_type_distribution": shot_type_counts,
            "special_tag_distribution": special_tag_counts,
            "scenes_with_dialogue": scenes_with_dialogue,
            "dialogue_coverage": scenes_with_dialogue / len(montage_rows),
            "scenes_with_music": scenes_with_music,
            "music_coverage": scenes_with_music / len(montage_rows),
            "unique_speakers": len(unique_speakers),
            "speaker_list": sorted(list(unique_speakers))
        }
    
    async def update_montage_rows(
        self, 
        montage_rows: List[MontageRow], 
        updates: Dict[int, Dict[str, Any]]
    ) -> List[MontageRow]:
        """
        Update specific montage rows with new data.
        
        Args:
            montage_rows: Current montage rows
            updates: Dictionary mapping row numbers to update data
            
        Returns:
            Updated montage rows
        """
        updated_rows = montage_rows.copy()
        
        for row_number, update_data in updates.items():
            if 1 <= row_number <= len(updated_rows):
                row_index = row_number - 1
                row = updated_rows[row_index]
                
                # Update fields if provided
                if "shot_type" in update_data:
                    if isinstance(update_data["shot_type"], str):
                        # Convert string to ShotType enum
                        shot_type_map = {
                            "Дальний": ShotType.DISTANT,
                            "Общий": ShotType.GENERAL,
                            "Средний": ShotType.MEDIUM,
                            "Крупный": ShotType.CLOSE,
                            "Деталь": ShotType.DETAIL
                        }
                        row.shot_type = shot_type_map.get(update_data["shot_type"], row.shot_type)
                    else:
                        row.shot_type = update_data["shot_type"]
                
                if "description" in update_data:
                    row.description = update_data["description"]
                
                if "dialogue" in update_data:
                    row.dialogue = update_data["dialogue"]
                
                if "speaker" in update_data:
                    row.speaker = update_data["speaker"]
                
                if "special_tags" in update_data:
                    row.special_tags = update_data["special_tags"]
                
                if "has_music" in update_data:
                    row.has_music = update_data["has_music"]
        
        return updated_rows
    
    async def renumber_montage_rows(self, montage_rows: List[MontageRow]) -> List[MontageRow]:
        """
        Renumber montage rows to ensure sequential numbering.
        
        Args:
            montage_rows: Montage rows to renumber
            
        Returns:
            Renumbered montage rows
        """
        for i, row in enumerate(montage_rows):
            row.number = i + 1
        
        return montage_rows
    
    def format_content_column(self, row: MontageRow) -> str:
        """
        Format column 5: Содержание (описание) плана, титры
        
        Args:
            row: Montage row
            
        Returns:
            Formatted content string
        """
        content = row.description
        
        # Добавляем специальные теги к описанию
        if row.special_tags:
            tags_text = ", ".join(row.special_tags)
            content = f"{content}. {tags_text}"
        
        return content
    
    def format_audio_column(self, row: MontageRow) -> str:
        """
        Format column 6: Монологи, разговоры, песни, субтитры. Музыка.
        
        Args:
            row: Montage row
            
        Returns:
            Formatted audio content string
        """
        audio_parts = []
        
        # Добавляем диалоги
        if row.dialogue:
            audio_parts.append(row.dialogue)
        
        # Добавляем музыку
        if row.has_music:
            audio_parts.append("Музыка")
        
        return ". ".join(audio_parts)
    
    def export_to_standard_format(self, montage_rows: List[MontageRow]) -> List[Dict[str, str]]:
        """
        Export montage rows to standard 6-column format.
        
        Args:
            montage_rows: List of montage rows
            
        Returns:
            List of dictionaries with standard column names
        """
        standard_rows = []
        
        for row in montage_rows:
            standard_row = {
                "№ плана": str(row.number),
                "Начальный тайм-код плана": row.start_timecode,
                "Конечный тайм-код плана": row.end_timecode,
                "Вид плана": row.shot_type.value,
                "Содержание (описание) плана, титры": self.format_content_column(row),
                "Монологи, разговоры, песни, субтитры. Музыка.": self.format_audio_column(row)
            }
            standard_rows.append(standard_row)
        
        return standard_rows