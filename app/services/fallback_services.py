"""
Fallback services for when external APIs are unavailable.
Provides graceful degradation with test data and local processing.
"""

import asyncio
import random
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from app.core.logging import get_logger
from app.core.exceptions import ProcessingError, ErrorCode

logger = get_logger("fallback_services")


class FallbackVisualAnalysisService:
    """Fallback visual analysis service when GPT vision is unavailable."""
    
    def __init__(self):
        self.shot_types = ["Д.", "О.", "Ср.", "Кр.", "Дет."]
        self.sample_descriptions = [
            "Персонаж находится в помещении",
            "Диалог между двумя персонажами",
            "Крупный план лица персонажа",
            "Общий план интерьера",
            "Деталь предмета на столе",
            "Персонаж идет по коридору",
            "Разговор в офисе",
            "Вид из окна",
            "Персонаж работает за компьютером",
            "Встреча в конференц-зале"
        ]
    
    async def analyze_scene_frames(
        self, 
        frame1_path: str, 
        frame2_path: str, 
        dialogue: str = ""
    ) -> Dict[str, Any]:
        """
        Provide fallback visual analysis using rule-based logic.
        
        Args:
            frame1_path: Path to first keyframe
            frame2_path: Path to second keyframe
            dialogue: Scene dialogue text
            
        Returns:
            Analysis result in expected format
        """
        logger.warning(
            "Using fallback visual analysis service",
            extra={
                "frame1": frame1_path,
                "frame2": frame2_path,
                "dialogue_length": len(dialogue) if dialogue else 0
            }
        )
        
        # Simulate processing delay
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        # Generate fallback analysis based on available information
        shot_type = self._determine_shot_type(dialogue)
        description = self._generate_description(dialogue)
        text_in_frame = self._detect_text_in_frame(dialogue)
        
        return {
            "shot_type": shot_type,
            "description": description,
            "text_in_frame": text_in_frame
        }
    
    def _determine_shot_type(self, dialogue: str) -> str:
        """Determine shot type based on dialogue characteristics."""
        if not dialogue:
            return random.choice(self.shot_types)
        
        dialogue_lower = dialogue.lower()
        
        # Rule-based shot type determination
        if any(word in dialogue_lower for word in ["крупный", "лицо", "глаза", "взгляд"]):
            return "Кр."
        elif any(word in dialogue_lower for word in ["деталь", "предмет", "рука", "документ"]):
            return "Дет."
        elif any(word in dialogue_lower for word in ["общий", "комната", "зал", "помещение"]):
            return "О."
        elif any(word in dialogue_lower for word in ["дальний", "здание", "улица", "пейзаж"]):
            return "Д."
        else:
            return "Ср."  # Default to medium shot
    
    def _generate_description(self, dialogue: str) -> str:
        """Generate scene description based on dialogue content."""
        if not dialogue:
            return random.choice(self.sample_descriptions)
        
        dialogue_lower = dialogue.lower()
        
        # Rule-based description generation
        if any(word in dialogue_lower for word in ["офис", "работа", "компьютер"]):
            return "Персонаж работает в офисе"
        elif any(word in dialogue_lower for word in ["встреча", "совещание", "переговоры"]):
            return "Деловая встреча в офисе"
        elif any(word in dialogue_lower for word in ["дом", "квартира", "кухня"]):
            return "Сцена в домашней обстановке"
        elif any(word in dialogue_lower for word in ["улица", "дорога", "машина"]):
            return "Сцена на улице"
        elif any(word in dialogue_lower for word in ["телефон", "звонок"]):
            return "Персонаж разговаривает по телефону"
        else:
            # Generate based on dialogue length and content
            if len(dialogue) > 100:
                return "Продолжительный диалог между персонажами"
            elif len(dialogue) > 50:
                return "Разговор между персонажами"
            else:
                return "Короткая реплика персонажа"
    
    def _detect_text_in_frame(self, dialogue: str) -> str:
        """Detect if there might be text in frame based on dialogue."""
        dialogue_lower = dialogue.lower() if dialogue else ""
        
        # Look for indicators of on-screen text
        text_indicators = [
            "надпись", "текст", "заголовок", "название", "вывеска",
            "документ", "письмо", "сообщение", "email", "смс"
        ]
        
        if any(indicator in dialogue_lower for indicator in text_indicators):
            return "Текст на экране"
        
        return ""


class FallbackDiarizationService:
    """Fallback speaker diarization when pyannote.audio is unavailable."""
    
    def __init__(self):
        self.speaker_names = ["Спикер 1", "Спикер 2", "Спикер 3", "Спикер 4"]
    
    async def diarize_audio(
        self, 
        audio_path: str, 
        transcription_segments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Provide fallback speaker diarization using simple heuristics.
        
        Args:
            audio_path: Path to audio file
            transcription_segments: Transcription segments with timing
            
        Returns:
            Diarization result with speaker assignments
        """
        logger.warning(
            "Using fallback diarization service",
            extra={
                "audio_path": audio_path,
                "segments_count": len(transcription_segments)
            }
        )
        
        # Simulate processing delay
        await asyncio.sleep(random.uniform(1.0, 2.0))
        
        # Simple rule-based speaker assignment
        speaker_segments = []
        current_speaker = 0
        
        for i, segment in enumerate(transcription_segments):
            # Change speaker based on simple heuristics
            if i > 0:
                # Change speaker if there's a significant pause
                prev_segment = transcription_segments[i - 1]
                gap = segment.get("start", 0) - prev_segment.get("end", 0)
                
                if gap > 2.0:  # 2 second gap
                    current_speaker = (current_speaker + 1) % len(self.speaker_names)
                
                # Change speaker for questions
                text = segment.get("text", "").strip()
                if text.endswith("?"):
                    current_speaker = (current_speaker + 1) % len(self.speaker_names)
            
            speaker_segments.append({
                "start": segment.get("start", 0),
                "end": segment.get("end", 0),
                "speaker": self.speaker_names[current_speaker],
                "text": segment.get("text", "")
            })
        
        return {
            "segments": speaker_segments,
            "speakers": list(set(seg["speaker"] for seg in speaker_segments)),
            "method": "fallback_heuristic"
        }


class FallbackTextProcessingService:
    """Fallback text processing when GPT is unavailable."""
    
    def __init__(self):
        self.common_corrections = {
            # Common Russian transcription errors
            "ну ": "",  # Remove filler words
            " ну ": " ",
            "эээ": "",
            "ммм": "",
            "ааа": "",
            "  ": " ",  # Multiple spaces to single space
        }
    
    async def process_text(self, text: str) -> str:
        """
        Provide basic text processing without AI.
        
        Args:
            text: Raw transcribed text
            
        Returns:
            Processed text with basic corrections
        """
        logger.warning(
            "Using fallback text processing service",
            extra={"text_length": len(text)}
        )
        
        # Simulate processing delay
        await asyncio.sleep(random.uniform(0.2, 0.5))
        
        if not text:
            return text
        
        processed_text = text
        
        # Apply basic corrections
        for old, new in self.common_corrections.items():
            processed_text = processed_text.replace(old, new)
        
        # Basic capitalization
        sentences = processed_text.split(". ")
        capitalized_sentences = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence:
                # Capitalize first letter
                sentence = sentence[0].upper() + sentence[1:] if len(sentence) > 1 else sentence.upper()
                capitalized_sentences.append(sentence)
        
        processed_text = ". ".join(capitalized_sentences)
        
        # Ensure proper ending punctuation
        if processed_text and not processed_text.endswith((".", "!", "?")):
            processed_text += "."
        
        return processed_text


class FallbackMusicDetectionService:
    """Fallback music detection using simple audio analysis."""
    
    async def detect_music_in_scene(
        self, 
        audio_path: str, 
        start_time: float, 
        end_time: float
    ) -> bool:
        """
        Provide basic music detection fallback.
        
        Args:
            audio_path: Path to audio file
            start_time: Scene start time in seconds
            end_time: Scene end time in seconds
            
        Returns:
            True if music is likely present, False otherwise
        """
        logger.warning(
            "Using fallback music detection service",
            extra={
                "audio_path": audio_path,
                "start_time": start_time,
                "end_time": end_time
            }
        )
        
        # Simulate processing delay
        await asyncio.sleep(random.uniform(0.3, 0.8))
        
        # Simple heuristic: assume music in longer scenes without dialogue
        scene_duration = end_time - start_time
        
        # If scene is longer than 10 seconds, there might be music
        if scene_duration > 10:
            return random.choice([True, False])  # 50% chance
        
        # Shorter scenes less likely to have music
        return random.random() < 0.2  # 20% chance


class FallbackServiceManager:
    """Manager for all fallback services."""
    
    def __init__(self):
        self.visual_analysis = FallbackVisualAnalysisService()
        self.diarization = FallbackDiarizationService()
        self.text_processing = FallbackTextProcessingService()
        self.music_detection = FallbackMusicDetectionService()
        
        logger.info("Fallback service manager initialized")
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Get status of all fallback services."""
        return {
            "visual_analysis": {
                "available": True,
                "type": "rule_based",
                "capabilities": ["shot_type", "description", "text_detection"]
            },
            "diarization": {
                "available": True,
                "type": "heuristic",
                "max_speakers": len(self.diarization.speaker_names)
            },
            "text_processing": {
                "available": True,
                "type": "basic_corrections",
                "corrections_count": len(self.text_processing.common_corrections)
            },
            "music_detection": {
                "available": True,
                "type": "duration_based",
                "accuracy": "low"
            },
            "status": "ready",
            "last_updated": datetime.utcnow().isoformat()
        }


# Global fallback service manager instance
fallback_services = FallbackServiceManager()