"""
Visual analysis service for professional montage assistant.

This service provides specialized prompt templates and analysis capabilities
for montage director assistant role with shot type classification and special tags.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ShotType(Enum):
    """Shot type classifications for montage analysis."""
    DISTANT = "Дальний"
    GENERAL = "Общий" 
    MEDIUM = "Средний"
    CLOSE = "Крупный"
    DETAIL = "Деталь"


class SpecialTag(Enum):
    """Special tags for montage analysis."""
    DARKENING = "ЗТМ"  # Затемнение
    TEXT_OVERLAY = "НДП"  # Надписи
    OFF_SCREEN_VOICE = "ГЗК"  # Голос за кадром


@dataclass
class VisualAnalysisResult:
    """Result of visual analysis for a scene."""
    shot_type: ShotType
    description: str
    text_in_frame: Optional[str] = None
    special_tags: List[SpecialTag] = None
    confidence_score: float = 1.0
    
    def __post_init__(self):
        if self.special_tags is None:
            self.special_tags = []


class MontageAssistantPromptSystem:
    """Professional montage assistant prompt system with specialized templates."""
    
    SCENE_ANALYSIS_PROMPT = """Ты — профессиональный ассистент режиссера монтажа. Твоя задача — проанализировать ДВА кадра из одной сцены (35% и 70% от длительности) и создать единое описание сцены в формате JSON длиною в одно предложение без эмоционального окраса. Если ты считаешь, что это архивное изображение или фотография, то отметь это.

**Определения планов:**
- **Дальний:** Человек занимает очень маленькое место в кадре, видна окружающая обстановка
- **Общий:** Человек в полный рост, хорошо видна фигура целиком
- **Средний:** Человек по колени или по пояс, фокус на верхней части тела
- **Крупный:** Голова человека занимает почти весь кадр, детали лица хорошо видны
- **Деталь:** Часть лица, руки или небольшой предмет крупным планом

**Специальные теги:**
- **ЗТМ:** Затемнение - если кадр значительно темнее обычного или есть эффект затемнения
- **НДП:** Надписи - если есть читаемый текст, титры, субтитры или графические элементы с текстом

**Инструкция:**
1. Проанализируй оба кадра как единую сцену
2. Определи основной тип плана по наиболее характерному кадру
3. Опиши действие максимально кратко в одно предложение без эмоционального окраса
4. Укажи читаемый текст, если он присутствует в кадре
5. НЕ добавляй тег "ГЗК" - это будет определено отдельно на основе диалогов

**Формат ответа (строго JSON):**
```json
{
    "shot_type": "Ср.",
    "description": "Краткое описание действия в одно предложение",
    "text_in_frame": "Читаемый текст если есть или null"
}
```

**Примеры правильных ответов:**

Для кадров с человеком за столом:
```json
{
    "shot_type": "Ср.",
    "description": "Мужчина сидит за рабочим столом и работает с документами",
    "text_in_frame": null
}
```

Для кадров с титрами:
```json
{
    "shot_type": "Общ.",
    "description": "Группа людей стоит в офисном помещении",
    "text_in_frame": "НОВОСТИ СЕГОДНЯ"
}
```

Для темных кадров:
```json
{
    "shot_type": "Кр.",
    "description": "Лицо человека в условиях слабого освещения",
    "text_in_frame": null
}
```"""

    SHOT_TYPE_DEFINITIONS = {
        ShotType.DISTANT: {
            "abbreviation": "Дал.",
            "description": "Человек занимает очень маленькое место в кадре, видна окружающая обстановка",
            "keywords": ["далекий", "панорама", "общий план", "окружение", "пейзаж"]
        },
        ShotType.GENERAL: {
            "abbreviation": "Общ.",
            "description": "Человек в полный рост, хорошо видна фигура целиком",
            "keywords": ["полный рост", "фигура", "общий", "весь человек"]
        },
        ShotType.MEDIUM: {
            "abbreviation": "Ср.",
            "description": "Человек по колени или по пояс, фокус на верхней части тела",
            "keywords": ["по пояс", "по колени", "средний", "торс", "верхняя часть"]
        },
        ShotType.CLOSE: {
            "abbreviation": "Кр.",
            "description": "Голова человека занимает почти весь кадр, детали лица хорошо видны",
            "keywords": ["голова", "лицо", "крупный", "портрет", "детали лица"]
        },
        ShotType.DETAIL: {
            "abbreviation": "Дет.",
            "description": "Часть лица, руки или небольшой предмет крупным планом",
            "keywords": ["деталь", "часть лица", "руки", "предмет", "макро"]
        }
    }

    SPECIAL_TAG_DEFINITIONS = {
        SpecialTag.DARKENING: {
            "abbreviation": "ЗТМ",
            "description": "Затемнение - кадр значительно темнее обычного или есть эффект затемнения",
            "detection_keywords": ["темный", "темной", "темная", "затемнение", "слабое освещение", "слабого освещения", "тень", "темнота"]
        },
        SpecialTag.TEXT_OVERLAY: {
            "abbreviation": "НДП",
            "description": "Надписи - читаемый текст, титры, субтитры или графические элементы с текстом",
            "detection_keywords": ["текст", "надпись", "титры", "субтитры", "графика"]
        },
        SpecialTag.OFF_SCREEN_VOICE: {
            "abbreviation": "ГЗК",
            "description": "Голос за кадром - персонаж говорит, но не виден в кадре",
            "detection_keywords": ["голос за кадром", "закадровый", "не виден", "говорит"]
        }
    }

    def __init__(self):
        """Initialize the montage assistant prompt system."""
        pass

    def get_scene_analysis_prompt(self) -> str:
        """
        Get the complete scene analysis prompt for GPT-5-mini.
        
        Returns:
            Formatted prompt string for visual analysis
        """
        return self.SCENE_ANALYSIS_PROMPT

    def get_shot_type_definition(self, shot_type: ShotType) -> Dict[str, Any]:
        """
        Get definition and metadata for a specific shot type.
        
        Args:
            shot_type: The shot type to get definition for
            
        Returns:
            Dictionary with abbreviation, description, and keywords
        """
        return self.SHOT_TYPE_DEFINITIONS.get(shot_type, {})

    def get_all_shot_types(self) -> Dict[ShotType, Dict[str, Any]]:
        """
        Get all shot type definitions.
        
        Returns:
            Dictionary mapping shot types to their definitions
        """
        return self.SHOT_TYPE_DEFINITIONS.copy()

    def get_special_tag_definition(self, tag: SpecialTag) -> Dict[str, Any]:
        """
        Get definition and metadata for a specific special tag.
        
        Args:
            tag: The special tag to get definition for
            
        Returns:
            Dictionary with abbreviation, description, and detection keywords
        """
        return self.SPECIAL_TAG_DEFINITIONS.get(tag, {})

    def get_all_special_tags(self) -> Dict[SpecialTag, Dict[str, Any]]:
        """
        Get all special tag definitions.
        
        Returns:
            Dictionary mapping special tags to their definitions
        """
        return self.SPECIAL_TAG_DEFINITIONS.copy()

    def parse_shot_type_from_response(self, response_text: str) -> Optional[ShotType]:
        """
        Parse shot type from GPT response text.
        
        Args:
            response_text: The response text containing shot type abbreviation
            
        Returns:
            Parsed ShotType or None if not found
        """
        # Create mapping from abbreviations to shot types
        abbrev_to_type = {
            definition["abbreviation"]: shot_type 
            for shot_type, definition in self.SHOT_TYPE_DEFINITIONS.items()
        }
        
        # Look for abbreviations in response
        for abbrev, shot_type in abbrev_to_type.items():
            if abbrev in response_text:
                return shot_type
                
        return None

    def detect_special_tags_from_description(self, description: str, text_in_frame: Optional[str] = None) -> List[SpecialTag]:
        """
        Detect special tags based on description and text content.
        
        Args:
            description: Scene description text
            text_in_frame: Text detected in frame (if any)
            
        Returns:
            List of detected special tags
        """
        detected_tags = []
        
        # Check for text overlay tag
        if text_in_frame and text_in_frame.strip():
            detected_tags.append(SpecialTag.TEXT_OVERLAY)
        
        # Check for darkening tag based on keywords
        darkening_keywords = self.SPECIAL_TAG_DEFINITIONS[SpecialTag.DARKENING]["detection_keywords"]
        description_lower = description.lower()
        
        if any(keyword in description_lower for keyword in darkening_keywords):
            detected_tags.append(SpecialTag.DARKENING)
            
        return detected_tags

    def detect_off_screen_voice(self, dialogue: str, visual_description: str) -> bool:
        """
        Detect if there's an off-screen voice (ГЗК) based on dialogue and visual analysis.
        
        Args:
            dialogue: Dialogue text for the scene
            visual_description: Visual description of the scene
            
        Returns:
            True if off-screen voice is detected
        """
        if not dialogue or not dialogue.strip():
            return False
            
        # Keywords that suggest no visible speaker
        no_speaker_keywords = [
            "не виден", "за кадром", "закадровый", "голос", "без персонажа",
            "пустой", "без людей", "только объекты", "интерьер без людей"
        ]
        
        visual_lower = visual_description.lower()
        
        # If dialogue exists but visual suggests no visible speaker
        if any(keyword in visual_lower for keyword in no_speaker_keywords):
            return True
            
        # Additional logic: if dialogue is present but description doesn't mention speaking/talking
        speaking_keywords = ["говорит", "произносит", "речь", "диалог", "беседа", "разговор"]
        has_speaking_visual = any(keyword in visual_lower for keyword in speaking_keywords)
        
        # If there's dialogue but no visual indication of speaking
        if dialogue.strip() and not has_speaking_visual:
            return True
            
        return False

    def validate_json_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """
        Validate and parse JSON response from GPT analysis.
        
        Args:
            response_text: Raw response text from GPT
            
        Returns:
            Parsed JSON dictionary or None if invalid
        """
        try:
            # Extract JSON from response (handle cases where there's extra text)
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                logger.error("No JSON found in response")
                return None
                
            json_text = response_text[json_start:json_end]
            parsed = json.loads(json_text)
            
            # Validate required fields
            required_fields = ["shot_type", "description"]
            for field in required_fields:
                if field not in parsed:
                    logger.error(f"Missing required field: {field}")
                    return None
                    
            # Validate shot_type format
            shot_type = parsed.get("shot_type", "")
            if not self.parse_shot_type_from_response(shot_type):
                logger.warning(f"Invalid shot type: {shot_type}")
                
            return parsed
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error validating JSON: {e}")
            return None

    def create_analysis_result(
        self, 
        json_response: Dict[str, Any], 
        dialogue: Optional[str] = None
    ) -> VisualAnalysisResult:
        """
        Create a VisualAnalysisResult from validated JSON response.
        
        Args:
            json_response: Validated JSON response from GPT
            dialogue: Optional dialogue text for ГЗК detection
            
        Returns:
            VisualAnalysisResult object
        """
        # Parse shot type
        shot_type_text = json_response.get("shot_type", "")
        shot_type = self.parse_shot_type_from_response(shot_type_text)
        
        if not shot_type:
            # Default to medium shot if parsing fails
            shot_type = ShotType.MEDIUM
            logger.warning(f"Could not parse shot type '{shot_type_text}', defaulting to Medium")
        
        description = json_response.get("description", "")
        text_in_frame = json_response.get("text_in_frame")
        
        # Detect special tags
        special_tags = self.detect_special_tags_from_description(description, text_in_frame)
        
        # Check for off-screen voice if dialogue is provided
        if dialogue and self.detect_off_screen_voice(dialogue, description):
            special_tags.append(SpecialTag.OFF_SCREEN_VOICE)
        
        return VisualAnalysisResult(
            shot_type=shot_type,
            description=description,
            text_in_frame=text_in_frame,
            special_tags=special_tags,
            confidence_score=1.0
        )

    def format_analysis_for_montage(self, analysis: VisualAnalysisResult) -> Dict[str, Any]:
        """
        Format analysis result for montage table integration.
        
        Args:
            analysis: VisualAnalysisResult to format
            
        Returns:
            Dictionary formatted for montage table
        """
        # Get shot type abbreviation
        shot_def = self.get_shot_type_definition(analysis.shot_type)
        shot_abbrev = shot_def.get("abbreviation", analysis.shot_type.value)
        
        # Format special tags
        tag_abbreviations = []
        for tag in analysis.special_tags:
            tag_def = self.get_special_tag_definition(tag)
            if tag_def:
                tag_abbreviations.append(tag_def["abbreviation"])
        
        # Combine shot type with tags
        type_with_tags = shot_abbrev
        if tag_abbreviations:
            type_with_tags += f" ({', '.join(tag_abbreviations)})"
        
        return {
            "shot_type": type_with_tags,
            "description": analysis.description,
            "text_in_frame": analysis.text_in_frame,
            "special_tags": [tag.value for tag in analysis.special_tags],
            "confidence_score": analysis.confidence_score
        }

    def generate_test_scenarios(self) -> List[Dict[str, Any]]:
        """
        Generate test scenarios for various scene types.
        
        Returns:
            List of test scenario dictionaries
        """
        return [
            {
                "name": "office_meeting_medium_shot",
                "description": "Мужчина сидит за рабочим столом и работает с документами",
                "expected_shot_type": ShotType.MEDIUM,
                "expected_tags": [],
                "text_in_frame": None
            },
            {
                "name": "news_broadcast_with_titles",
                "description": "Группа людей стоит в офисном помещении",
                "expected_shot_type": ShotType.GENERAL,
                "expected_tags": [SpecialTag.TEXT_OVERLAY],
                "text_in_frame": "НОВОСТИ СЕГОДНЯ"
            },
            {
                "name": "dark_close_up",
                "description": "Лицо человека в условиях слабого освещения",
                "expected_shot_type": ShotType.CLOSE,
                "expected_tags": [SpecialTag.DARKENING],
                "text_in_frame": None
            },
            {
                "name": "landscape_distant_shot",
                "description": "Человек идет по дороге среди деревьев",
                "expected_shot_type": ShotType.DISTANT,
                "expected_tags": [],
                "text_in_frame": None
            },
            {
                "name": "hand_detail_shot",
                "description": "Крупным планом руки человека держат документ",
                "expected_shot_type": ShotType.DETAIL,
                "expected_tags": [],
                "text_in_frame": None
            },
            {
                "name": "off_screen_voice_scenario",
                "description": "Пустой офис без людей",
                "expected_shot_type": ShotType.GENERAL,
                "expected_tags": [SpecialTag.OFF_SCREEN_VOICE],
                "text_in_frame": None,
                "dialogue": "Добро пожаловать в нашу компанию"
            }
        ]