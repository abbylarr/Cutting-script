"""
Dialogue-to-scene mapping services for filmlist application.
Handles distribution of dialogue across scenes without breaking sentences.
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from app.services.transcription import TranscriptionSegment, TranscriptionResult
from app.services.diarization import SpeakerSegment, DiarizationResult
from app.services.video_processor import Scene

logger = logging.getLogger(__name__)


@dataclass
class DialogueSegment:
    """Represents a dialogue segment with speaker and timing information."""
    text: str
    speaker: Optional[str]
    start_time: float
    end_time: float
    confidence: float = 1.0
    is_continuation: bool = False  # True if this is a continuation from previous scene
    has_ellipsis_start: bool = False  # True if starts with ellipsis
    has_ellipsis_end: bool = False    # True if ends with ellipsis


@dataclass
class SceneDialogue:
    """Represents dialogue content for a single scene."""
    scene_number: int
    start_time: float
    end_time: float
    dialogue_segments: List[DialogueSegment]
    full_text: str
    speakers: List[str]
    has_music: bool = False


@dataclass
class DialogueMappingResult:
    """Result of dialogue-to-scene mapping."""
    scene_dialogues: List[SceneDialogue]
    total_scenes: int
    total_dialogue_segments: int
    unmapped_segments: List[DialogueSegment]
    processing_time: float


class DialogueMappingError(Exception):
    """Raised when dialogue mapping fails."""
    pass


class SentenceBoundaryDetector:
    """Detects sentence boundaries in Russian text."""
    
    def __init__(self):
        # Russian sentence ending patterns
        self.sentence_endings = re.compile(r'[.!?…]+\s*')
        
        # Abbreviations that shouldn't end sentences
        self.abbreviations = {
            'г.', 'гг.', 'р.', 'руб.', 'коп.', 'см.', 'км.', 'м.', 'мм.',
            'кг.', 'т.', 'л.', 'мл.', 'сек.', 'мин.', 'ч.', 'дн.',
            'др.', 'т.д.', 'т.п.', 'и.т.д.', 'и.т.п.', 'т.е.', 'т.к.',
            'в.т.ч.', 'н.э.', 'до.н.э.', 'г-н', 'г-жа'
        }
    
    def find_sentence_boundaries(self, text: str) -> List[int]:
        """
        Find sentence boundary positions in text.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of character positions where sentences end
        """
        boundaries = []
        
        # Find all potential sentence endings
        for match in self.sentence_endings.finditer(text):
            end_pos = match.end()
            
            # Check if this is a real sentence boundary
            if self._is_sentence_boundary(text, match.start(), end_pos):
                boundaries.append(end_pos)
        
        return boundaries
    
    def _is_sentence_boundary(self, text: str, start_pos: int, end_pos: int) -> bool:
        """
        Check if a potential boundary is a real sentence boundary.
        
        Args:
            text: Full text
            start_pos: Start position of the ending punctuation
            end_pos: End position after punctuation and whitespace
            
        Returns:
            True if this is a sentence boundary
        """
        # Get text before the punctuation
        before_text = text[:start_pos].strip()
        
        # Check if it ends with an abbreviation
        for abbr in self.abbreviations:
            if before_text.lower().endswith(abbr.lower()):
                return False
        
        # Check if next character is uppercase (if there is text after)
        if end_pos < len(text):
            next_char = text[end_pos:end_pos + 1]
            if next_char and not next_char.isupper():
                return False
        
        return True
    
    def split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences.
        
        Args:
            text: Text to split
            
        Returns:
            List of sentences
        """
        boundaries = self.find_sentence_boundaries(text)
        
        if not boundaries:
            return [text.strip()] if text.strip() else []
        
        sentences = []
        start = 0
        
        for boundary in boundaries:
            sentence = text[start:boundary].strip()
            if sentence:
                sentences.append(sentence)
            start = boundary
        
        # Add remaining text if any
        if start < len(text):
            remaining = text[start:].strip()
            if remaining:
                sentences.append(remaining)
        
        return sentences


class DialogueSceneMappingService:
    """Service for mapping dialogue to scenes without breaking sentences."""
    
    def __init__(self):
        self.sentence_detector = SentenceBoundaryDetector()
        
        # Configuration for ellipsis insertion
        self.ellipsis_threshold = 0.5  # seconds - minimum gap to add ellipsis
        self.max_sentence_split_gap = 2.0  # seconds - max gap to allow sentence splitting
    
    async def map_dialogue_to_scenes(
        self,
        scenes: List[Scene],
        transcription_result: TranscriptionResult,
        diarization_result: Optional[DiarizationResult] = None
    ) -> DialogueMappingResult:
        """
        Map dialogue segments to scenes without breaking sentences.
        
        Args:
            scenes: List of detected scenes
            transcription_result: Transcription with timing information
            diarization_result: Optional speaker diarization result
            
        Returns:
            DialogueMappingResult with mapped dialogue
            
        Raises:
            DialogueMappingError: If mapping fails
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            logger.info(f"Starting dialogue mapping for {len(scenes)} scenes")
            
            # Prepare dialogue segments from transcription and diarization
            dialogue_segments = await self._prepare_dialogue_segments(
                transcription_result, diarization_result
            )
            
            # Map segments to scenes
            scene_dialogues = await self._map_segments_to_scenes(
                scenes, dialogue_segments
            )
            
            # Process sentence boundaries and add ellipses
            scene_dialogues = await self._process_sentence_boundaries(
                scene_dialogues
            )
            
            # Generate full text for each scene
            for scene_dialogue in scene_dialogues:
                scene_dialogue.full_text = self._generate_scene_text(scene_dialogue)
                scene_dialogue.speakers = self._extract_speakers(scene_dialogue)
            
            # Find unmapped segments
            unmapped_segments = await self._find_unmapped_segments(
                dialogue_segments, scene_dialogues
            )
            
            processing_time = asyncio.get_event_loop().time() - start_time
            
            logger.info(f"Dialogue mapping completed: {len(scene_dialogues)} scenes processed")
            
            return DialogueMappingResult(
                scene_dialogues=scene_dialogues,
                total_scenes=len(scenes),
                total_dialogue_segments=len(dialogue_segments),
                unmapped_segments=unmapped_segments,
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(f"Dialogue mapping failed: {e}")
            raise DialogueMappingError(f"Failed to map dialogue to scenes: {e}")
    
    async def _prepare_dialogue_segments(
        self,
        transcription_result: TranscriptionResult,
        diarization_result: Optional[DiarizationResult] = None
    ) -> List[DialogueSegment]:
        """
        Prepare dialogue segments from transcription and diarization data.
        
        Args:
            transcription_result: Transcription with segments
            diarization_result: Optional diarization result
            
        Returns:
            List of DialogueSegment objects
        """
        dialogue_segments = []
        
        # Create speaker mapping if diarization is available
        speaker_map = {}
        if diarization_result:
            speaker_map = self._create_speaker_timeline(diarization_result.segments)
        
        # Process each transcription segment
        for segment in transcription_result.segments:
            # Find speaker for this segment
            speaker = self._find_speaker_for_segment(
                segment, speaker_map
            ) if speaker_map else None
            
            # Create dialogue segment
            dialogue_segment = DialogueSegment(
                text=segment.text.strip(),
                speaker=speaker,
                start_time=segment.start,
                end_time=segment.end,
                confidence=1.0 - segment.no_speech_prob
            )
            
            if dialogue_segment.text:  # Only add non-empty segments
                dialogue_segments.append(dialogue_segment)
        
        return dialogue_segments
    
    def _create_speaker_timeline(self, speaker_segments: List[SpeakerSegment]) -> Dict[float, str]:
        """
        Create a timeline mapping time to speaker.
        
        Args:
            speaker_segments: List of speaker segments
            
        Returns:
            Dictionary mapping time to speaker
        """
        speaker_map = {}
        
        for segment in speaker_segments:
            # Sample the segment at regular intervals
            duration = segment.end - segment.start
            sample_interval = min(0.1, duration / 10)  # Sample every 0.1s or 10 times per segment
            
            current_time = segment.start
            while current_time <= segment.end:
                speaker_map[current_time] = segment.speaker
                current_time += sample_interval
        
        return speaker_map
    
    def _find_speaker_for_segment(
        self,
        segment: TranscriptionSegment,
        speaker_map: Dict[float, str]
    ) -> Optional[str]:
        """
        Find the most likely speaker for a transcription segment.
        
        Args:
            segment: Transcription segment
            speaker_map: Timeline mapping time to speaker
            
        Returns:
            Speaker label or None
        """
        if not speaker_map:
            return None
        
        # Sample speaker at multiple points in the segment
        segment_duration = segment.end - segment.start
        sample_points = max(3, int(segment_duration * 2))  # At least 3 samples
        
        speaker_votes = {}
        
        for i in range(sample_points):
            sample_time = segment.start + (i * segment_duration / (sample_points - 1))
            
            # Find closest speaker in timeline
            closest_time = min(speaker_map.keys(), key=lambda t: abs(t - sample_time))
            speaker = speaker_map[closest_time]
            
            speaker_votes[speaker] = speaker_votes.get(speaker, 0) + 1
        
        # Return speaker with most votes
        if speaker_votes:
            return max(speaker_votes.items(), key=lambda x: x[1])[0]
        
        return None
    
    async def _map_segments_to_scenes(
        self,
        scenes: List[Scene],
        dialogue_segments: List[DialogueSegment]
    ) -> List[SceneDialogue]:
        """
        Map dialogue segments to scenes based on timing.
        
        Args:
            scenes: List of scenes
            dialogue_segments: List of dialogue segments
            
        Returns:
            List of SceneDialogue objects
        """
        scene_dialogues = []
        
        for scene in scenes:
            # Find segments that overlap with this scene
            scene_segments = []
            
            for segment in dialogue_segments:
                # Check if segment overlaps with scene
                if self._segments_overlap(segment, scene):
                    scene_segments.append(segment)
            
            # Create scene dialogue
            scene_dialogue = SceneDialogue(
                scene_number=scene.scene_number,
                start_time=scene.start_time,
                end_time=scene.end_time,
                dialogue_segments=scene_segments,
                full_text="",  # Will be generated later
                speakers=[]    # Will be extracted later
            )
            
            scene_dialogues.append(scene_dialogue)
        
        return scene_dialogues
    
    def _segments_overlap(self, segment: DialogueSegment, scene: Scene) -> bool:
        """
        Check if a dialogue segment overlaps with a scene.
        
        Args:
            segment: Dialogue segment
            scene: Scene
            
        Returns:
            True if they overlap
        """
        # Check for any time overlap
        return not (segment.end_time <= scene.start_time or segment.start_time >= scene.end_time)
    
    async def _process_sentence_boundaries(
        self,
        scene_dialogues: List[SceneDialogue]
    ) -> List[SceneDialogue]:
        """
        Process sentence boundaries and add ellipses where sentences are split.
        
        Args:
            scene_dialogues: List of scene dialogues
            
        Returns:
            Updated scene dialogues with proper sentence handling
        """
        for i, scene_dialogue in enumerate(scene_dialogues):
            if not scene_dialogue.dialogue_segments:
                continue
            
            # Combine all text in the scene
            full_scene_text = " ".join(
                segment.text for segment in scene_dialogue.dialogue_segments
            )
            
            # Check for sentence boundaries at scene transitions
            if i > 0:  # Not the first scene
                scene_dialogue = await self._handle_scene_start_boundary(
                    scene_dialogue, scene_dialogues[i - 1]
                )
            
            if i < len(scene_dialogues) - 1:  # Not the last scene
                scene_dialogue = await self._handle_scene_end_boundary(
                    scene_dialogue, scene_dialogues[i + 1]
                )
        
        return scene_dialogues
    
    async def _handle_scene_start_boundary(
        self,
        current_scene: SceneDialogue,
        previous_scene: SceneDialogue
    ) -> SceneDialogue:
        """
        Handle sentence boundaries at the start of a scene.
        
        Args:
            current_scene: Current scene dialogue
            previous_scene: Previous scene dialogue
            
        Returns:
            Updated current scene dialogue
        """
        if not current_scene.dialogue_segments or not previous_scene.dialogue_segments:
            return current_scene
        
        # Get first segment of current scene
        first_segment = current_scene.dialogue_segments[0]
        
        # Get last segment of previous scene
        last_segment = previous_scene.dialogue_segments[-1]
        
        # Check if we're in the middle of a sentence
        if self._is_sentence_continuation(last_segment.text, first_segment.text):
            # Add ellipsis to indicate continuation
            first_segment.is_continuation = True
            first_segment.has_ellipsis_start = True
            
            # Modify the text to start with ellipsis
            if not first_segment.text.startswith('...'):
                first_segment.text = '...' + first_segment.text
        
        return current_scene
    
    async def _handle_scene_end_boundary(
        self,
        current_scene: SceneDialogue,
        next_scene: SceneDialogue
    ) -> SceneDialogue:
        """
        Handle sentence boundaries at the end of a scene.
        
        Args:
            current_scene: Current scene dialogue
            next_scene: Next scene dialogue
            
        Returns:
            Updated current scene dialogue
        """
        if not current_scene.dialogue_segments or not next_scene.dialogue_segments:
            return current_scene
        
        # Get last segment of current scene
        last_segment = current_scene.dialogue_segments[-1]
        
        # Get first segment of next scene
        first_segment = next_scene.dialogue_segments[0]
        
        # Check if sentence continues to next scene
        if self._is_sentence_continuation(last_segment.text, first_segment.text):
            # Add ellipsis to indicate continuation
            last_segment.has_ellipsis_end = True
            
            # Modify the text to end with ellipsis
            if not last_segment.text.rstrip().endswith('...'):
                last_segment.text = last_segment.text.rstrip() + '...'
        
        return current_scene
    
    def _is_sentence_continuation(self, text1: str, text2: str) -> bool:
        """
        Check if text2 is a continuation of a sentence from text1.
        
        Args:
            text1: First text (end of previous segment/scene)
            text2: Second text (start of next segment/scene)
            
        Returns:
            True if text2 continues a sentence from text1
        """
        # Clean texts
        text1 = text1.strip()
        text2 = text2.strip()
        
        if not text1 or not text2:
            return False
        
        # Check if text1 ends with sentence-ending punctuation
        if re.search(r'[.!?…]+\s*$', text1):
            return False
        
        # Check if text2 starts with uppercase (new sentence)
        if text2[0].isupper():
            # Could still be continuation if text1 doesn't end properly
            # Check if text1 ends with comma, dash, or no punctuation
            if re.search(r'[,-]?\s*$', text1):
                return True
        
        # If text2 starts with lowercase, likely continuation
        if text2[0].islower():
            return True
        
        return False
    
    def _generate_scene_text(self, scene_dialogue: SceneDialogue) -> str:
        """
        Generate full text for a scene from its dialogue segments.
        
        Args:
            scene_dialogue: Scene dialogue object
            
        Returns:
            Full text for the scene
        """
        if not scene_dialogue.dialogue_segments:
            return ""
        
        # Group segments by speaker
        speaker_texts = {}
        
        for segment in scene_dialogue.dialogue_segments:
            speaker = segment.speaker or "Неизвестный"
            
            if speaker not in speaker_texts:
                speaker_texts[speaker] = []
            
            speaker_texts[speaker].append(segment.text)
        
        # Format text with speaker labels
        formatted_parts = []
        
        for speaker, texts in speaker_texts.items():
            combined_text = " ".join(texts)
            if combined_text.strip():
                formatted_parts.append(f"{speaker}: {combined_text}")
        
        return " ".join(formatted_parts)
    
    def _extract_speakers(self, scene_dialogue: SceneDialogue) -> List[str]:
        """
        Extract unique speakers from scene dialogue.
        
        Args:
            scene_dialogue: Scene dialogue object
            
        Returns:
            List of unique speaker names
        """
        speakers = set()
        
        for segment in scene_dialogue.dialogue_segments:
            if segment.speaker:
                speakers.add(segment.speaker)
        
        return sorted(list(speakers))
    
    async def _find_unmapped_segments(
        self,
        all_segments: List[DialogueSegment],
        scene_dialogues: List[SceneDialogue]
    ) -> List[DialogueSegment]:
        """
        Find dialogue segments that weren't mapped to any scene.
        
        Args:
            all_segments: All dialogue segments
            scene_dialogues: Scene dialogues with mapped segments
            
        Returns:
            List of unmapped segments
        """
        mapped_segments = set()
        
        # Collect all mapped segments
        for scene_dialogue in scene_dialogues:
            for segment in scene_dialogue.dialogue_segments:
                # Use start time as unique identifier
                mapped_segments.add(segment.start_time)
        
        # Find unmapped segments
        unmapped = []
        for segment in all_segments:
            if segment.start_time not in mapped_segments:
                unmapped.append(segment)
        
        return unmapped
    
    async def update_speaker_labels(
        self,
        scene_dialogues: List[SceneDialogue],
        speaker_mapping: Dict[str, str]
    ) -> List[SceneDialogue]:
        """
        Update speaker labels in scene dialogues.
        
        Args:
            scene_dialogues: List of scene dialogues
            speaker_mapping: Dictionary mapping old labels to new labels
            
        Returns:
            Updated scene dialogues
        """
        for scene_dialogue in scene_dialogues:
            # Update segments
            for segment in scene_dialogue.dialogue_segments:
                if segment.speaker and segment.speaker in speaker_mapping:
                    segment.speaker = speaker_mapping[segment.speaker]
            
            # Regenerate full text and speakers list
            scene_dialogue.full_text = self._generate_scene_text(scene_dialogue)
            scene_dialogue.speakers = self._extract_speakers(scene_dialogue)
        
        return scene_dialogues
    
    async def get_dialogue_statistics(
        self,
        scene_dialogues: List[SceneDialogue]
    ) -> Dict[str, Any]:
        """
        Get statistics about dialogue mapping.
        
        Args:
            scene_dialogues: List of scene dialogues
            
        Returns:
            Dictionary with statistics
        """
        total_segments = sum(len(sd.dialogue_segments) for sd in scene_dialogues)
        total_speakers = set()
        scenes_with_dialogue = 0
        total_dialogue_duration = 0.0
        
        for scene_dialogue in scene_dialogues:
            if scene_dialogue.dialogue_segments:
                scenes_with_dialogue += 1
                
                for segment in scene_dialogue.dialogue_segments:
                    if segment.speaker:
                        total_speakers.add(segment.speaker)
                    total_dialogue_duration += segment.end_time - segment.start_time
        
        return {
            "total_scenes": len(scene_dialogues),
            "scenes_with_dialogue": scenes_with_dialogue,
            "total_dialogue_segments": total_segments,
            "unique_speakers": len(total_speakers),
            "total_dialogue_duration": total_dialogue_duration,
            "average_segments_per_scene": total_segments / len(scene_dialogues) if scene_dialogues else 0,
            "dialogue_coverage": scenes_with_dialogue / len(scene_dialogues) if scene_dialogues else 0
        }