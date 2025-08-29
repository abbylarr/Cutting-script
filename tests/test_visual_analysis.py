"""
Unit tests for visual analysis and montage assistant prompt system.
"""

import pytest
import json
from unittest.mock import Mock, patch

from app.services.visual_analysis import (
    MontageAssistantPromptSystem,
    VisualAnalysisResult,
    ShotType,
    SpecialTag
)


@pytest.fixture
def prompt_system():
    """Create a MontageAssistantPromptSystem instance."""
    return MontageAssistantPromptSystem()


class TestShotType:
    """Test ShotType enum."""
    
    def test_shot_type_values(self):
        """Test shot type enum values."""
        assert ShotType.DISTANT.value == "Дальний"
        assert ShotType.GENERAL.value == "Общий"
        assert ShotType.MEDIUM.value == "Средний"
        assert ShotType.CLOSE.value == "Крупный"
        assert ShotType.DETAIL.value == "Деталь"


class TestSpecialTag:
    """Test SpecialTag enum."""
    
    def test_special_tag_values(self):
        """Test special tag enum values."""
        assert SpecialTag.DARKENING.value == "ЗТМ"
        assert SpecialTag.TEXT_OVERLAY.value == "НДП"
        assert SpecialTag.OFF_SCREEN_VOICE.value == "ГЗК"


class TestVisualAnalysisResult:
    """Test VisualAnalysisResult dataclass."""
    
    def test_create_basic_result(self):
        """Test creating basic visual analysis result."""
        result = VisualAnalysisResult(
            shot_type=ShotType.MEDIUM,
            description="Человек сидит за столом"
        )
        
        assert result.shot_type == ShotType.MEDIUM
        assert result.description == "Человек сидит за столом"
        assert result.text_in_frame is None
        assert result.special_tags == []
        assert result.confidence_score == 1.0
    
    def test_create_result_with_tags(self):
        """Test creating result with special tags."""
        result = VisualAnalysisResult(
            shot_type=ShotType.CLOSE,
            description="Лицо в темноте",
            text_in_frame="НОВОСТИ",
            special_tags=[SpecialTag.DARKENING, SpecialTag.TEXT_OVERLAY],
            confidence_score=0.8
        )
        
        assert result.shot_type == ShotType.CLOSE
        assert result.text_in_frame == "НОВОСТИ"
        assert len(result.special_tags) == 2
        assert SpecialTag.DARKENING in result.special_tags
        assert SpecialTag.TEXT_OVERLAY in result.special_tags
        assert result.confidence_score == 0.8


class TestMontageAssistantPromptSystem:
    """Test MontageAssistantPromptSystem functionality."""
    
    def test_get_scene_analysis_prompt(self, prompt_system):
        """Test getting scene analysis prompt."""
        prompt = prompt_system.get_scene_analysis_prompt()
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "профессиональный ассистент режиссера монтажа" in prompt
        assert "Дальний:" in prompt
        assert "Общий:" in prompt
        assert "Средний:" in prompt
        assert "Крупный:" in prompt
        assert "Деталь:" in prompt
        assert "ЗТМ:" in prompt
        assert "НДП:" in prompt
    
    def test_get_shot_type_definition(self, prompt_system):
        """Test getting shot type definitions."""
        medium_def = prompt_system.get_shot_type_definition(ShotType.MEDIUM)
        
        assert medium_def["abbreviation"] == "Ср."
        assert "по пояс" in medium_def["description"]
        assert "средний" in medium_def["keywords"]
        
        close_def = prompt_system.get_shot_type_definition(ShotType.CLOSE)
        assert close_def["abbreviation"] == "Кр."
        assert "голова" in close_def["description"].lower()
    
    def test_get_all_shot_types(self, prompt_system):
        """Test getting all shot type definitions."""
        all_types = prompt_system.get_all_shot_types()
        
        assert len(all_types) == 5
        assert ShotType.DISTANT in all_types
        assert ShotType.GENERAL in all_types
        assert ShotType.MEDIUM in all_types
        assert ShotType.CLOSE in all_types
        assert ShotType.DETAIL in all_types
        
        # Verify each has required fields
        for shot_type, definition in all_types.items():
            assert "abbreviation" in definition
            assert "description" in definition
            assert "keywords" in definition
    
    def test_get_special_tag_definition(self, prompt_system):
        """Test getting special tag definitions."""
        darkening_def = prompt_system.get_special_tag_definition(SpecialTag.DARKENING)
        
        assert darkening_def["abbreviation"] == "ЗТМ"
        assert "затемнение" in darkening_def["description"].lower()
        assert "темный" in darkening_def["detection_keywords"]
        
        text_def = prompt_system.get_special_tag_definition(SpecialTag.TEXT_OVERLAY)
        assert text_def["abbreviation"] == "НДП"
        assert "надписи" in text_def["description"].lower()
    
    def test_get_all_special_tags(self, prompt_system):
        """Test getting all special tag definitions."""
        all_tags = prompt_system.get_all_special_tags()
        
        assert len(all_tags) == 3
        assert SpecialTag.DARKENING in all_tags
        assert SpecialTag.TEXT_OVERLAY in all_tags
        assert SpecialTag.OFF_SCREEN_VOICE in all_tags
        
        # Verify each has required fields
        for tag, definition in all_tags.items():
            assert "abbreviation" in definition
            assert "description" in definition
            assert "detection_keywords" in definition
    
    def test_parse_shot_type_from_response_success(self, prompt_system):
        """Test successful shot type parsing from response."""
        test_cases = [
            ("Ср.", ShotType.MEDIUM),
            ("Кр.", ShotType.CLOSE),
            ("Общ.", ShotType.GENERAL),
            ("Дал.", ShotType.DISTANT),
            ("Дет.", ShotType.DETAIL)
        ]
        
        for response_text, expected_type in test_cases:
            result = prompt_system.parse_shot_type_from_response(response_text)
            assert result == expected_type
    
    def test_parse_shot_type_from_response_in_json(self, prompt_system):
        """Test parsing shot type from JSON response."""
        json_response = '{"shot_type": "Ср.", "description": "Test"}'
        
        result = prompt_system.parse_shot_type_from_response(json_response)
        assert result == ShotType.MEDIUM
    
    def test_parse_shot_type_from_response_not_found(self, prompt_system):
        """Test shot type parsing when not found."""
        result = prompt_system.parse_shot_type_from_response("Invalid text")
        assert result is None
    
    def test_detect_special_tags_text_overlay(self, prompt_system):
        """Test detecting text overlay special tag."""
        tags = prompt_system.detect_special_tags_from_description(
            "Человек говорит", 
            "НОВОСТИ СЕГОДНЯ"
        )
        
        assert SpecialTag.TEXT_OVERLAY in tags
    
    def test_detect_special_tags_darkening(self, prompt_system):
        """Test detecting darkening special tag."""
        tags = prompt_system.detect_special_tags_from_description(
            "Лицо человека в условиях слабого освещения"
        )
        
        assert SpecialTag.DARKENING in tags
    
    def test_detect_special_tags_multiple(self, prompt_system):
        """Test detecting multiple special tags."""
        tags = prompt_system.detect_special_tags_from_description(
            "Темный кадр с человеком",
            "BREAKING NEWS"
        )
        
        assert SpecialTag.DARKENING in tags
        assert SpecialTag.TEXT_OVERLAY in tags
        assert len(tags) == 2
    
    def test_detect_special_tags_none(self, prompt_system):
        """Test when no special tags are detected."""
        tags = prompt_system.detect_special_tags_from_description(
            "Обычный кадр с человеком"
        )
        
        assert len(tags) == 0
    
    def test_detect_off_screen_voice_no_dialogue(self, prompt_system):
        """Test off-screen voice detection with no dialogue."""
        result = prompt_system.detect_off_screen_voice("", "Человек говорит")
        assert result is False
        
        result = prompt_system.detect_off_screen_voice(None, "Человек говорит")
        assert result is False
    
    def test_detect_off_screen_voice_with_speaker_visible(self, prompt_system):
        """Test off-screen voice detection with visible speaker."""
        result = prompt_system.detect_off_screen_voice(
            "Привет, как дела?",
            "Человек говорит в микрофон"
        )
        assert result is False
    
    def test_detect_off_screen_voice_no_visible_speaker(self, prompt_system):
        """Test off-screen voice detection with no visible speaker."""
        result = prompt_system.detect_off_screen_voice(
            "Добро пожаловать в программу",
            "Пустой офис без людей"
        )
        assert result is True
        
        result = prompt_system.detect_off_screen_voice(
            "Голос диктора",
            "Интерьер без людей"
        )
        assert result is True
    
    def test_detect_off_screen_voice_dialogue_without_speaking_visual(self, prompt_system):
        """Test off-screen voice when dialogue exists but no speaking visual cues."""
        result = prompt_system.detect_off_screen_voice(
            "Текст диалога",
            "Человек сидит за столом"  # No speaking keywords
        )
        assert result is True
    
    def test_validate_json_response_success(self, prompt_system):
        """Test successful JSON response validation."""
        valid_json = '''
        {
            "shot_type": "Ср.",
            "description": "Человек сидит за столом",
            "text_in_frame": null
        }
        '''
        
        result = prompt_system.validate_json_response(valid_json)
        
        assert result is not None
        assert result["shot_type"] == "Ср."
        assert result["description"] == "Человек сидит за столом"
        assert result["text_in_frame"] is None
    
    def test_validate_json_response_with_extra_text(self, prompt_system):
        """Test JSON validation with extra text around JSON."""
        response_with_extra = '''
        Вот мой анализ кадра:
        
        {
            "shot_type": "Кр.",
            "description": "Лицо человека крупным планом"
        }
        
        Надеюсь, это поможет!
        '''
        
        result = prompt_system.validate_json_response(response_with_extra)
        
        assert result is not None
        assert result["shot_type"] == "Кр."
        assert result["description"] == "Лицо человека крупным планом"
    
    def test_validate_json_response_invalid_json(self, prompt_system):
        """Test JSON validation with invalid JSON."""
        invalid_json = '{"shot_type": "Ср.", "description": "Test"'  # Missing closing brace
        
        result = prompt_system.validate_json_response(invalid_json)
        assert result is None
    
    def test_validate_json_response_missing_required_fields(self, prompt_system):
        """Test JSON validation with missing required fields."""
        missing_fields = '{"shot_type": "Ср."}'  # Missing description
        
        result = prompt_system.validate_json_response(missing_fields)
        assert result is None
    
    def test_validate_json_response_no_json(self, prompt_system):
        """Test JSON validation with no JSON content."""
        no_json = "This is just plain text without JSON"
        
        result = prompt_system.validate_json_response(no_json)
        assert result is None
    
    def test_create_analysis_result_basic(self, prompt_system):
        """Test creating analysis result from JSON response."""
        json_response = {
            "shot_type": "Ср.",
            "description": "Человек работает за компьютером",
            "text_in_frame": None
        }
        
        result = prompt_system.create_analysis_result(json_response)
        
        assert result.shot_type == ShotType.MEDIUM
        assert result.description == "Человек работает за компьютером"
        assert result.text_in_frame is None
        assert len(result.special_tags) == 0
    
    def test_create_analysis_result_with_text(self, prompt_system):
        """Test creating analysis result with text in frame."""
        json_response = {
            "shot_type": "Общ.",
            "description": "Группа людей в офисе",
            "text_in_frame": "НОВОСТИ"
        }
        
        result = prompt_system.create_analysis_result(json_response)
        
        assert result.shot_type == ShotType.GENERAL
        assert result.text_in_frame == "НОВОСТИ"
        assert SpecialTag.TEXT_OVERLAY in result.special_tags
    
    def test_create_analysis_result_with_dialogue_gzk(self, prompt_system):
        """Test creating analysis result with off-screen voice detection."""
        json_response = {
            "shot_type": "Общ.",
            "description": "Пустой офис без людей",
            "text_in_frame": None
        }
        
        result = prompt_system.create_analysis_result(
            json_response, 
            dialogue="Добро пожаловать в нашу компанию"
        )
        
        assert result.shot_type == ShotType.GENERAL
        assert SpecialTag.OFF_SCREEN_VOICE in result.special_tags
    
    def test_create_analysis_result_invalid_shot_type(self, prompt_system):
        """Test creating analysis result with invalid shot type."""
        json_response = {
            "shot_type": "Invalid",
            "description": "Test description",
            "text_in_frame": None
        }
        
        result = prompt_system.create_analysis_result(json_response)
        
        # Should default to medium shot
        assert result.shot_type == ShotType.MEDIUM
        assert result.description == "Test description"
    
    def test_format_analysis_for_montage_basic(self, prompt_system):
        """Test formatting analysis for montage table."""
        analysis = VisualAnalysisResult(
            shot_type=ShotType.MEDIUM,
            description="Человек за столом",
            confidence_score=0.9
        )
        
        formatted = prompt_system.format_analysis_for_montage(analysis)
        
        assert formatted["shot_type"] == "Ср."
        assert formatted["description"] == "Человек за столом"
        assert formatted["text_in_frame"] is None
        assert formatted["special_tags"] == []
        assert formatted["confidence_score"] == 0.9
    
    def test_format_analysis_for_montage_with_tags(self, prompt_system):
        """Test formatting analysis with special tags."""
        analysis = VisualAnalysisResult(
            shot_type=ShotType.CLOSE,
            description="Темное лицо",
            text_in_frame="NEWS",
            special_tags=[SpecialTag.DARKENING, SpecialTag.TEXT_OVERLAY]
        )
        
        formatted = prompt_system.format_analysis_for_montage(analysis)
        
        assert formatted["shot_type"] == "Кр. (ЗТМ, НДП)"
        assert formatted["text_in_frame"] == "NEWS"
        assert "ЗТМ" in formatted["special_tags"]
        assert "НДП" in formatted["special_tags"]
    
    def test_generate_test_scenarios(self, prompt_system):
        """Test generating test scenarios."""
        scenarios = prompt_system.generate_test_scenarios()
        
        assert len(scenarios) > 0
        
        # Check first scenario structure
        scenario = scenarios[0]
        assert "name" in scenario
        assert "description" in scenario
        assert "expected_shot_type" in scenario
        assert "expected_tags" in scenario
        
        # Find and test specific scenarios
        office_scenario = next(
            (s for s in scenarios if s["name"] == "office_meeting_medium_shot"), 
            None
        )
        assert office_scenario is not None
        assert office_scenario["expected_shot_type"] == ShotType.MEDIUM
        
        news_scenario = next(
            (s for s in scenarios if s["name"] == "news_broadcast_with_titles"), 
            None
        )
        assert news_scenario is not None
        assert SpecialTag.TEXT_OVERLAY in news_scenario["expected_tags"]
        
        dark_scenario = next(
            (s for s in scenarios if s["name"] == "dark_close_up"), 
            None
        )
        assert dark_scenario is not None
        assert dark_scenario["expected_shot_type"] == ShotType.CLOSE
        assert SpecialTag.DARKENING in dark_scenario["expected_tags"]


class TestIntegrationScenarios:
    """Integration tests for complete analysis scenarios."""
    
    def test_complete_analysis_workflow(self, prompt_system):
        """Test complete analysis workflow from JSON to formatted result."""
        # Simulate GPT response
        gpt_response = '''
        {
            "shot_type": "Ср.",
            "description": "Мужчина в темной комнате работает за компьютером",
            "text_in_frame": "LIVE"
        }
        '''
        
        # Validate JSON
        json_data = prompt_system.validate_json_response(gpt_response)
        assert json_data is not None
        
        # Create analysis result
        analysis = prompt_system.create_analysis_result(json_data)
        assert analysis.shot_type == ShotType.MEDIUM
        assert SpecialTag.DARKENING in analysis.special_tags
        assert SpecialTag.TEXT_OVERLAY in analysis.special_tags
        
        # Format for montage
        formatted = prompt_system.format_analysis_for_montage(analysis)
        assert "ЗТМ" in formatted["shot_type"]
        assert "НДП" in formatted["shot_type"]
        assert formatted["text_in_frame"] == "LIVE"
    
    def test_off_screen_voice_complete_workflow(self, prompt_system):
        """Test complete workflow with off-screen voice detection."""
        gpt_response = '''
        {
            "shot_type": "Общ.",
            "description": "Пустая комната с мебелью",
            "text_in_frame": null
        }
        '''
        
        dialogue = "Добро пожаловать в нашу передачу"
        
        json_data = prompt_system.validate_json_response(gpt_response)
        analysis = prompt_system.create_analysis_result(json_data, dialogue)
        
        assert analysis.shot_type == ShotType.GENERAL
        assert SpecialTag.OFF_SCREEN_VOICE in analysis.special_tags
        
        formatted = prompt_system.format_analysis_for_montage(analysis)
        assert "ГЗК" in formatted["shot_type"]
        assert "ГЗК" in formatted["special_tags"]