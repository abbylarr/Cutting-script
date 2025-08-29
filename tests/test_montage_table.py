"""
Unit tests for montage table generation and formatting services.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch
from datetime import datetime

from app.services.montage_table import (
    MontageTableAssemblyService,
    TimecodeService,
    ProcessedSceneData,
    MontageTableResult,
    MontageTableGenerationError
)
from app.schemas.film_project import MontageRow, ShotType, ProjectSettings, TimecodeStandard
from app.services.video_processor import Scene
from app.services.dialogue_mapping import SceneDialogue, DialogueSegment, DialogueMappingResult
from app.services.gpt_visual_analysis import SceneAnalysisResult
from app.services.visual_analysis import VisualAnalysisResult, ShotType as VisualShotType, SpecialTag
from app.services.music_detection import MusicDetectionResult, SceneMusicAnalysis


class TestTimecodeService:
    """Test cases for TimecodeService."""
    
    def test_init_with_default_settings(self):
        """Test initialization with default settings."""
        service = TimecodeService()
        
        assert service.start_time == "01:00:00:00"
        assert service.standard == "ГФФ"
        assert service.fps == 25.0
        assert service.start_seconds == 3600.0  # 1 hour
    
    def test_init_with_custom_settings(self):
        """Test initialization with custom project settings."""
        settings = ProjectSettings(
            timecode_start="00:00:00:00",
            standard=TimecodeStandard.KRASNOGORSKY,
            fps=24.0
        )
        
        service = TimecodeService(settings)
        
        assert service.start_time == "00:00:00:00"
        assert service.standard == TimecodeStandard.KRASNOGORSKY
        assert service.fps == 24.0
        assert service.start_seconds == 0.0
    
    def test_timecode_to_seconds(self):
        """Test timecode to seconds conversion."""
        service = TimecodeService()
        
        # Test various timecodes
        assert service._timecode_to_seconds("00:00:00:00") == 0.0
        assert service._timecode_to_seconds("00:00:01:00") == 1.0
        assert service._timecode_to_seconds("00:01:00:00") == 60.0
        assert service._timecode_to_seconds("01:00:00:00") == 3600.0
        assert service._timecode_to_seconds("00:00:00:25") == 1.0  # 25 frames at 25fps
        assert service._timecode_to_seconds("00:00:01:12") == 1.48  # 1s + 12/25s
    
    def test_timecode_to_seconds_invalid(self):
        """Test timecode to seconds conversion with invalid input."""
        service = TimecodeService()
        
        with pytest.raises(ValueError):
            service._timecode_to_seconds("invalid")
        
        with pytest.raises(ValueError):
            service._timecode_to_seconds("00:00:00")  # Missing frames
        
        with pytest.raises(ValueError):
            service._timecode_to_seconds("25:70:00:00")  # Invalid minutes
    
    def test_seconds_to_timecode(self):
        """Test seconds to timecode conversion."""
        # Test with start time 01:00:00:00
        service = TimecodeService()
        
        assert service._seconds_to_timecode(0.0) == "01:00:00:00"
        assert service._seconds_to_timecode(1.0) == "01:00:01:00"
        assert service._seconds_to_timecode(60.0) == "01:01:00:00"
        assert service._seconds_to_timecode(0.04) == "01:00:00:01"  # 1 frame at 25fps
        assert service._seconds_to_timecode(1.48) == "01:00:01:12"  # 1s + 12 frames
    
    def test_seconds_to_timecode_zero_start(self):
        """Test seconds to timecode conversion with zero start time."""
        settings = ProjectSettings(timecode_start="00:00:00:00", fps=25.0)
        service = TimecodeService(settings)
        
        assert service._seconds_to_timecode(0.0) == "00:00:00:00"
        assert service._seconds_to_timecode(1.0) == "00:00:01:00"
        assert service._seconds_to_timecode(3661.0) == "01:01:01:00"
    
    def test_ensure_scene_continuity(self):
        """Test scene continuity adjustment."""
        service = TimecodeService()
        
        # Create test scenes with gaps
        scenes = [
            Scene(start_time=0.0, end_time=5.0, duration=5.0, scene_number=1),
            Scene(start_time=6.0, end_time=10.0, duration=4.0, scene_number=2),
            Scene(start_time=12.0, end_time=15.0, duration=3.0, scene_number=3)
        ]
        
        adjusted_scenes = service.ensure_scene_continuity(scenes)
        
        # First scene should remain unchanged
        assert adjusted_scenes[0].start_time == 0.0
        assert adjusted_scenes[0].end_time == 5.0
        
        # Second scene should start one frame after first scene ends
        frame_duration = 1.0 / 25.0  # 0.04s
        expected_start_2 = 5.0 + frame_duration
        assert abs(adjusted_scenes[1].start_time - expected_start_2) < 0.001
        
        # Third scene should start one frame after second scene ends
        expected_start_3 = adjusted_scenes[1].end_time + frame_duration
        assert abs(adjusted_scenes[2].start_time - expected_start_3) < 0.001
    
    def test_validate_timecode_continuity(self):
        """Test timecode continuity validation."""
        service = TimecodeService()
        frame_duration = 1.0 / 25.0
        
        # Create scenes with proper continuity
        good_scenes = [
            Scene(start_time=0.0, end_time=5.0, duration=5.0, scene_number=1),
            Scene(start_time=5.0 + frame_duration, end_time=10.0, duration=4.96, scene_number=2)
        ]
        
        errors = service.validate_timecode_continuity(good_scenes)
        assert len(errors) == 0
        
        # Create scenes with bad continuity
        bad_scenes = [
            Scene(start_time=0.0, end_time=5.0, duration=5.0, scene_number=1),
            Scene(start_time=6.0, end_time=10.0, duration=4.0, scene_number=2)  # Gap too large
        ]
        
        errors = service.validate_timecode_continuity(bad_scenes)
        assert len(errors) > 0
        assert "Gap of" in errors[0]


class TestMontageTableAssemblyService:
    """Test cases for MontageTableAssemblyService."""
    
    @pytest.fixture
    def service(self):
        """Create service instance for testing."""
        return MontageTableAssemblyService()
    
    @pytest.fixture
    def sample_scenes(self):
        """Create sample scenes for testing."""
        return [
            Scene(start_time=0.0, end_time=5.0, duration=5.0, scene_number=1),
            Scene(start_time=5.04, end_time=10.0, duration=4.96, scene_number=2),
            Scene(start_time=10.04, end_time=15.0, duration=4.96, scene_number=3)
        ]
    
    @pytest.fixture
    def sample_dialogue_result(self):
        """Create sample dialogue mapping result."""
        dialogue_segments = [
            DialogueSegment(
                text="Привет, как дела?",
                speaker="Спикер_1",
                start_time=1.0,
                end_time=3.0
            )
        ]
        
        scene_dialogues = [
            SceneDialogue(
                scene_number=1,
                start_time=0.0,
                end_time=5.0,
                dialogue_segments=dialogue_segments,
                full_text="Спикер_1: Привет, как дела?",
                speakers=["Спикер_1"]
            )
        ]
        
        return DialogueMappingResult(
            scene_dialogues=scene_dialogues,
            total_scenes=3,
            total_dialogue_segments=1,
            unmapped_segments=[],
            processing_time=1.0
        )
    
    @pytest.fixture
    def sample_visual_analysis(self):
        """Create sample visual analysis results."""
        visual_result = VisualAnalysisResult(
            shot_type=VisualShotType.MEDIUM,
            description="Человек говорит в кадре",
            confidence_score=0.9,
            text_in_frame="",
            special_tags=[SpecialTag.OFF_SCREEN_VOICE]
        )
        
        scene_analysis = SceneAnalysisResult(
            scene_index=0,
            scene=Scene(start_time=0.0, end_time=5.0, duration=5.0, scene_number=1),
            keyframes=[],
            visual_analysis=visual_result,
            processing_time=2.0
        )
        
        return [scene_analysis]
    
    @pytest.fixture
    def sample_music_result(self):
        """Create sample music detection result."""
        scene_analyses = [
            SceneMusicAnalysis(
                scene_number=2,  # Second scene (index 1)
                start_time=5.04,
                end_time=10.0,
                has_music=True,
                music_segments=[],
                music_coverage=0.8,
                dominant_music_type="background",
                average_music_confidence=0.8
            )
        ]
        
        return MusicDetectionResult(
            scene_analyses=scene_analyses,
            total_scenes=3,
            scenes_with_music=1,
            total_music_duration=4.0,
            processing_time=1.5
        )
    
    @pytest.mark.asyncio
    async def test_generate_montage_table_basic(self, service, sample_scenes):
        """Test basic montage table generation."""
        result = await service.generate_montage_table(sample_scenes)
        
        assert isinstance(result, MontageTableResult)
        assert len(result.montage_rows) == 3
        assert result.total_scenes == 3
        assert len(result.validation_errors) == 0
        
        # Check first row
        first_row = result.montage_rows[0]
        assert first_row.number == 1
        assert first_row.shot_type == ShotType.MEDIUM  # Default
        assert first_row.start_timecode == "01:00:00:00"  # Default start time
        assert first_row.description != ""
    
    @pytest.mark.asyncio
    async def test_generate_montage_table_with_dialogue(
        self, service, sample_scenes, sample_dialogue_result
    ):
        """Test montage table generation with dialogue."""
        result = await service.generate_montage_table(
            sample_scenes, dialogue_result=sample_dialogue_result
        )
        
        assert len(result.montage_rows) == 3
        
        # First scene should have dialogue
        first_row = result.montage_rows[0]
        assert first_row.dialogue == "Спикер_1: Привет, как дела?"
        assert first_row.speaker == "Спикер_1"
        
        # Other scenes should have empty dialogue
        assert result.montage_rows[1].dialogue == ""
        assert result.montage_rows[2].dialogue == ""
    
    @pytest.mark.asyncio
    async def test_generate_montage_table_with_visual_analysis(
        self, service, sample_scenes, sample_visual_analysis
    ):
        """Test montage table generation with visual analysis."""
        result = await service.generate_montage_table(
            sample_scenes, visual_analysis_results=sample_visual_analysis
        )
        
        assert len(result.montage_rows) == 3
        
        # First scene should have visual analysis data
        first_row = result.montage_rows[0]
        assert first_row.shot_type == ShotType.MEDIUM
        assert first_row.description == "Человек говорит в кадре"
        assert "ГЗК" in first_row.special_tags
    
    @pytest.mark.asyncio
    async def test_generate_montage_table_with_music(
        self, service, sample_scenes, sample_music_result
    ):
        """Test montage table generation with music detection."""
        result = await service.generate_montage_table(
            sample_scenes, music_detection_result=sample_music_result
        )
        
        assert len(result.montage_rows) == 3
        
        # Second scene should have music (index 1)
        second_row = result.montage_rows[1]
        assert second_row.has_music is True
        assert "Музыка" in second_row.special_tags
        
        # Other scenes should not have music
        assert result.montage_rows[0].has_music is False
        assert result.montage_rows[2].has_music is False
    
    @pytest.mark.asyncio
    async def test_generate_montage_table_complete(
        self, service, sample_scenes, sample_dialogue_result, 
        sample_visual_analysis, sample_music_result
    ):
        """Test complete montage table generation with all data."""
        result = await service.generate_montage_table(
            sample_scenes,
            dialogue_result=sample_dialogue_result,
            visual_analysis_results=sample_visual_analysis,
            music_detection_result=sample_music_result
        )
        
        assert len(result.montage_rows) == 3
        assert len(result.validation_errors) == 0
        
        # Check statistics
        stats = result.statistics
        assert stats["total_rows"] == 3
        assert stats["scenes_with_dialogue"] == 1
        assert stats["scenes_with_music"] == 1
        assert stats["unique_speakers"] == 1
        assert "Спикер_1" in stats["speaker_list"]
    
    @pytest.mark.asyncio
    async def test_combine_processed_data(self, service, sample_scenes):
        """Test combining processed data from different sources."""
        processed_scenes = await service._combine_processed_data(
            sample_scenes, None, None, None
        )
        
        assert len(processed_scenes) == 3
        
        for i, scene_data in enumerate(processed_scenes):
            assert scene_data.scene == sample_scenes[i]
            assert scene_data.dialogue is None
            assert scene_data.visual_analysis is None
            assert scene_data.has_music is False
    
    @pytest.mark.asyncio
    async def test_generate_montage_rows(self, service, sample_scenes):
        """Test montage row generation."""
        processed_scenes = [
            ProcessedSceneData(scene=scene) for scene in sample_scenes
        ]
        
        montage_rows = await service._generate_montage_rows(processed_scenes)
        
        assert len(montage_rows) == 3
        
        for i, row in enumerate(montage_rows):
            assert row.number == i + 1
            assert row.shot_type == ShotType.MEDIUM  # Default
            assert row.start_timecode.startswith("01:")  # Default start time
            assert row.end_timecode.startswith("01:")
            assert row.description != ""
    
    def test_convert_shot_type(self, service):
        """Test shot type conversion."""
        # Test with enum
        visual_shot = VisualShotType.CLOSE
        converted = service._convert_shot_type(visual_shot)
        assert converted == ShotType.CLOSE
        
        # Test with string
        converted = service._convert_shot_type("Дальний")
        assert converted == ShotType.DISTANT
        
        # Test with unknown type
        converted = service._convert_shot_type("Unknown")
        assert converted == ShotType.MEDIUM  # Default
    
    @pytest.mark.asyncio
    async def test_generate_scene_description(self, service):
        """Test scene description generation."""
        # Test with visual analysis
        visual_result = VisualAnalysisResult(
            shot_type=VisualShotType.MEDIUM,
            description="Тестовое описание",
            text_in_frame="Надпись на экране"
        )
        
        scene_analysis = SceneAnalysisResult(
            scene_index=0,
            scene=Scene(start_time=0.0, end_time=5.0, duration=5.0, scene_number=1),
            keyframes=[],
            visual_analysis=visual_result
        )
        
        scene_data = ProcessedSceneData(
            scene=Scene(start_time=0.0, end_time=5.0, duration=5.0, scene_number=1),
            visual_analysis=scene_analysis
        )
        
        description = await service._generate_scene_description(scene_data)
        assert "Тестовое описание" in description
        assert "Надпись: Надпись на экране" in description
        
        # Test without visual analysis
        scene_data_no_visual = ProcessedSceneData(
            scene=Scene(start_time=0.0, end_time=5.0, duration=5.0, scene_number=1)
        )
        
        description = await service._generate_scene_description(scene_data_no_visual)
        assert "Сцена 1" in description
    
    @pytest.mark.asyncio
    async def test_validate_montage_rows(self, service):
        """Test montage row validation."""
        # Create valid rows
        valid_rows = [
            MontageRow(
                number=1,
                start_timecode="01:00:00:00",
                end_timecode="01:00:05:00",
                shot_type=ShotType.MEDIUM,
                description="Тестовое описание",
                dialogue=""
            ),
            MontageRow(
                number=2,
                start_timecode="01:00:05:01",
                end_timecode="01:00:10:00",
                shot_type=ShotType.CLOSE,
                description="Другое описание",
                dialogue=""
            )
        ]
        
        errors = await service._validate_montage_rows(valid_rows)
        assert len(errors) == 0
        
        # Create invalid rows
        invalid_rows = [
            MontageRow(
                number=5,  # Wrong number
                start_timecode="invalid",  # Invalid format
                end_timecode="01:00:05:00",
                shot_type=ShotType.MEDIUM,
                description="",  # Empty description
                dialogue=""
            )
        ]
        
        errors = await service._validate_montage_rows(invalid_rows)
        assert len(errors) > 0
        assert any("Incorrect number" in error for error in errors)
        assert any("Invalid start timecode format" in error for error in errors)
        assert any("Missing description" in error for error in errors)
    
    @pytest.mark.asyncio
    async def test_update_montage_rows(self, service):
        """Test montage row updates."""
        original_rows = [
            MontageRow(
                number=1,
                start_timecode="01:00:00:00",
                end_timecode="01:00:05:00",
                shot_type=ShotType.MEDIUM,
                description="Оригинальное описание",
                dialogue="",
                speaker=None
            )
        ]
        
        updates = {
            1: {
                "shot_type": "Крупный",
                "description": "Обновленное описание",
                "speaker": "Новый спикер"
            }
        }
        
        updated_rows = await service.update_montage_rows(original_rows, updates)
        
        assert len(updated_rows) == 1
        assert updated_rows[0].shot_type == ShotType.CLOSE
        assert updated_rows[0].description == "Обновленное описание"
        assert updated_rows[0].speaker == "Новый спикер"
    
    @pytest.mark.asyncio
    async def test_renumber_montage_rows(self, service):
        """Test montage row renumbering."""
        rows = [
            MontageRow(
                number=5,  # Wrong number
                start_timecode="01:00:00:00",
                end_timecode="01:00:05:00",
                shot_type=ShotType.MEDIUM,
                description="Первая строка",
                dialogue=""
            ),
            MontageRow(
                number=10,  # Wrong number
                start_timecode="01:00:05:01",
                end_timecode="01:00:10:00",
                shot_type=ShotType.CLOSE,
                description="Вторая строка",
                dialogue=""
            )
        ]
        
        renumbered_rows = await service.renumber_montage_rows(rows)
        
        assert renumbered_rows[0].number == 1
        assert renumbered_rows[1].number == 2
    
    @pytest.mark.asyncio
    async def test_generate_statistics(self, service, sample_scenes):
        """Test statistics generation."""
        montage_rows = [
            MontageRow(
                number=1,
                start_timecode="01:00:00:00",
                end_timecode="01:00:05:00",
                shot_type=ShotType.MEDIUM,
                description="Описание",
                dialogue="Тестовый диалог",
                speaker="Спикер_1",
                has_music=True,
                special_tags=["ГЗК", "Музыка"]
            ),
            MontageRow(
                number=2,
                start_timecode="01:00:05:01",
                end_timecode="01:00:10:00",
                shot_type=ShotType.CLOSE,
                description="Другое описание",
                dialogue="",
                speaker=None,
                has_music=False,
                special_tags=[]
            )
        ]
        
        processed_scenes = [
            ProcessedSceneData(scene=scene) for scene in sample_scenes[:2]
        ]
        
        stats = await service._generate_statistics(montage_rows, processed_scenes)
        
        assert stats["total_rows"] == 2
        assert stats["scenes_with_dialogue"] == 1
        assert stats["dialogue_coverage"] == 0.5
        assert stats["scenes_with_music"] == 1
        assert stats["music_coverage"] == 0.5
        assert stats["unique_speakers"] == 1
        assert "Спикер_1" in stats["speaker_list"]
        assert stats["shot_type_distribution"]["Средний"] == 1
        assert stats["shot_type_distribution"]["Крупный"] == 1
        assert stats["special_tag_distribution"]["ГЗК"] == 1
        assert stats["special_tag_distribution"]["Музыка"] == 1


class TestMontageTableIntegration:
    """Integration tests for montage table generation."""
    
    @pytest.mark.asyncio
    async def test_full_montage_table_generation_workflow(self):
        """Test complete workflow from scenes to montage table."""
        # Create test data
        scenes = [
            Scene(start_time=0.0, end_time=5.0, duration=5.0, scene_number=1),
            Scene(start_time=5.04, end_time=10.0, duration=4.96, scene_number=2)
        ]
        
        # Create service with custom settings
        settings = ProjectSettings(
            timecode_start="00:00:00:00",
            standard=TimecodeStandard.GFF,
            fps=24.0
        )
        
        service = MontageTableAssemblyService(settings)
        
        # Generate montage table
        result = await service.generate_montage_table(scenes)
        
        # Verify results
        assert len(result.montage_rows) == 2
        assert result.total_scenes == 2
        assert result.processing_time > 0
        
        # Check timecode format with custom FPS
        first_row = result.montage_rows[0]
        assert first_row.start_timecode == "00:00:00:00"
        assert first_row.end_timecode == "00:00:05:00"
        
        # Check continuity
        second_row = result.montage_rows[1]
        # Should start one frame after first scene ends (1/24 = ~0.042s)
        # At 24fps, frame 1 = 00:00:05:01
        assert second_row.start_timecode == "00:00:05:01"
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in montage table generation."""
        service = MontageTableAssemblyService()
        
        # Test with empty scenes
        with pytest.raises(MontageTableGenerationError):
            await service.generate_montage_table([])
        
        # Test with invalid scene data
        invalid_scenes = [
            Scene(start_time=10.0, end_time=5.0, duration=-5.0, scene_number=1)  # Invalid duration
        ]
        
        # Should not raise exception but should have validation errors
        result = await service.generate_montage_table(invalid_scenes)
        assert len(result.validation_errors) > 0


if __name__ == "__main__":
    pytest.main([__file__])

class TestAdvancedTimecodeService:
    """Test cases for advanced TimecodeService features."""
    
    def test_validate_and_adjust_fps_gff_standard(self):
        """Test FPS validation for ГФФ standard."""
        service = TimecodeService()
        
        # Test exact match
        assert service._validate_and_adjust_fps(25.0, "ГФФ") == 25.0
        assert service._validate_and_adjust_fps(24.0, "ГФФ") == 24.0
        
        # Test close match (within tolerance)
        assert service._validate_and_adjust_fps(24.98, "ГФФ") == 25.0
        assert service._validate_and_adjust_fps(23.95, "ГФФ") == 24.0
        
        # Test unsupported FPS
        assert service._validate_and_adjust_fps(30.0, "ГФФ") is None
        assert service._validate_and_adjust_fps(60.0, "ГФФ") is None
    
    def test_validate_and_adjust_fps_krasnogorsky_standard(self):
        """Test FPS validation for Красногорский standard."""
        service = TimecodeService()
        
        # Test supported rates
        assert service._validate_and_adjust_fps(29.97, "Красногорский") == 29.97
        assert service._validate_and_adjust_fps(30.0, "Красногорский") == 30.0
        assert service._validate_and_adjust_fps(59.94, "Красногорский") == 59.94
        
        # Test close match
        assert service._validate_and_adjust_fps(29.9, "Красногорский") == 29.97
        
        # Test unsupported FPS
        assert service._validate_and_adjust_fps(15.0, "Красногорский") is None
    
    def test_init_with_detected_fps(self):
        """Test initialization with detected FPS."""
        settings = ProjectSettings(
            timecode_start="00:00:00:00",
            standard=TimecodeStandard.GFF,
            fps=25.0
        )
        
        # Test with valid detected FPS
        service = TimecodeService(settings, detected_fps=24.0)
        assert service.fps == 24.0  # Should use detected FPS
        
        # Test with invalid detected FPS
        service = TimecodeService(settings, detected_fps=30.0)
        assert service.fps == 25.0  # Should fall back to settings FPS
    
    def test_ensure_scene_continuity_preserve_timing(self):
        """Test scene continuity with preserved timing."""
        service = TimecodeService()
        
        scenes = [
            Scene(start_time=0.0, end_time=5.0, duration=5.0, scene_number=1),
            Scene(start_time=6.0, end_time=12.0, duration=6.0, scene_number=2)
        ]
        
        # Test with preserve_original_timing=True
        adjusted = service.ensure_scene_continuity(scenes, preserve_original_timing=True)
        
        # First scene unchanged
        assert adjusted[0].start_time == 0.0
        assert adjusted[0].end_time == 5.0
        
        # Second scene should preserve duration
        expected_start = 5.0 + service.frame_duration
        assert abs(adjusted[1].start_time - expected_start) < 0.001
        assert abs(adjusted[1].duration - 6.0) < 0.001  # Original duration preserved
    
    def test_calculate_scene_timecodes(self):
        """Test timecode calculation for scenes."""
        service = TimecodeService()
        
        scenes = [
            Scene(start_time=0.0, end_time=5.0, duration=5.0, scene_number=1),
            Scene(start_time=5.04, end_time=10.0, duration=4.96, scene_number=2)
        ]
        
        timecodes = service.calculate_scene_timecodes(scenes)
        
        assert len(timecodes) == 2
        assert timecodes[0] == ("01:00:00:00", "01:00:05:00")
        assert timecodes[1] == ("01:00:05:01", "01:00:10:00")
    
    def test_adjust_scene_timing_for_frame_accuracy(self):
        """Test frame-accurate timing adjustment."""
        service = TimecodeService()  # 25 fps
        
        # Create scenes with non-frame-accurate timing
        scenes = [
            Scene(start_time=0.123, end_time=5.456, duration=5.333, scene_number=1),
            Scene(start_time=5.789, end_time=10.111, duration=4.322, scene_number=2)
        ]
        
        adjusted = service.adjust_scene_timing_for_frame_accuracy(scenes)
        
        # Check that times are frame-accurate
        for scene in adjusted:
            start_frames = scene.start_time * service.fps
            end_frames = scene.end_time * service.fps
            
            # Should be whole frame numbers
            assert abs(start_frames - round(start_frames)) < 0.001
            assert abs(end_frames - round(end_frames)) < 0.001
    
    def test_validate_timecode_format(self):
        """Test timecode format validation."""
        service = TimecodeService()  # 25 fps
        
        # Valid timecodes
        valid, error = service.validate_timecode_format("01:23:45:12")
        assert valid is True
        assert error is None
        
        valid, error = service.validate_timecode_format("00:00:00:00")
        assert valid is True
        assert error is None
        
        # Invalid format
        valid, error = service.validate_timecode_format("1:23:45:12")
        assert valid is False
        assert "Invalid timecode format" in error
        
        valid, error = service.validate_timecode_format("01:23:45")
        assert valid is False
        assert "Invalid timecode format" in error
        
        # Invalid values
        valid, error = service.validate_timecode_format("01:60:45:12")
        assert valid is False
        assert "Invalid minutes" in error
        
        valid, error = service.validate_timecode_format("01:23:60:12")
        assert valid is False
        assert "Invalid seconds" in error
        
        valid, error = service.validate_timecode_format("01:23:45:25")  # 25 fps, so max frame is 24
        assert valid is False
        assert "Invalid frames" in error
    
    def test_get_timecode_info(self):
        """Test timecode configuration info."""
        settings = ProjectSettings(
            timecode_start="00:00:00:00",
            standard=TimecodeStandard.KRASNOGORSKY,
            fps=29.97
        )
        
        service = TimecodeService(settings)
        info = service.get_timecode_info()
        
        assert info["start_time"] == "00:00:00:00"
        assert info["standard"] == "Красногорский"
        assert info["fps"] == 29.97
        assert info["frame_duration"] == 1.0 / 29.97
        assert info["start_seconds"] == 0.0
        assert 29.97 in info["supported_fps"]
    
    def test_different_fps_calculations(self):
        """Test timecode calculations with different frame rates."""
        # Test 24 fps
        settings_24 = ProjectSettings(
            timecode_start="00:00:00:00",
            standard=TimecodeStandard.GFF,
            fps=24.0
        )
        service_24 = TimecodeService(settings_24)
        
        # 1 second should be 24 frames
        assert service_24._seconds_to_timecode(1.0) == "00:00:01:00"
        assert service_24._seconds_to_timecode(1.0 + 1.0/24) == "00:00:01:01"
        
        # Test 29.97 fps (drop frame)
        settings_2997 = ProjectSettings(
            timecode_start="00:00:00:00",
            standard=TimecodeStandard.KRASNOGORSKY,
            fps=29.97
        )
        service_2997 = TimecodeService(settings_2997)
        
        # 1 second should be approximately 30 frames
        tc = service_2997._seconds_to_timecode(1.0)
        assert tc.startswith("00:00:01:")
        
        # Frame number should be close to 30 (29.97)
        frames = int(tc.split(':')[3])
        assert 29 <= frames <= 30
    
    def test_continuity_with_different_fps(self):
        """Test continuity calculations with different frame rates."""
        # Test with 24 fps
        settings = ProjectSettings(fps=24.0)
        service = TimecodeService(settings)
        
        scenes = [
            Scene(start_time=0.0, end_time=5.0, duration=5.0, scene_number=1),
            Scene(start_time=6.0, end_time=10.0, duration=4.0, scene_number=2)
        ]
        
        adjusted = service.ensure_scene_continuity(scenes)
        
        # Gap should be exactly 1/24 second
        expected_gap = 1.0 / 24.0
        actual_gap = adjusted[1].start_time - adjusted[0].end_time
        assert abs(actual_gap - expected_gap) < 0.001


class TestMontageTableWithAdvancedTimecode:
    """Test montage table generation with advanced timecode features."""
    
    @pytest.mark.asyncio
    async def test_montage_table_with_custom_fps(self):
        """Test montage table generation with custom frame rate."""
        # Create scenes
        scenes = [
            Scene(start_time=0.0, end_time=2.0, duration=2.0, scene_number=1),
            Scene(start_time=2.5, end_time=4.5, duration=2.0, scene_number=2)
        ]
        
        # Create service with 24 fps
        settings = ProjectSettings(
            timecode_start="00:00:00:00",
            standard=TimecodeStandard.GFF,
            fps=24.0
        )
        
        service = MontageTableAssemblyService(settings)
        result = await service.generate_montage_table(scenes)
        
        # Check that timecodes use 24 fps
        first_row = result.montage_rows[0]
        assert first_row.start_timecode == "00:00:00:00"
        assert first_row.end_timecode == "00:00:02:00"
        
        # Check continuity with 24 fps frame gap
        second_row = result.montage_rows[1]
        # Should start 1 frame after first scene ends (1/24 = ~0.042s)
        assert second_row.start_timecode == "00:00:02:01"
    
    @pytest.mark.asyncio
    async def test_montage_table_with_frame_accurate_timing(self):
        """Test montage table with frame-accurate timing adjustment."""
        # Create scenes with non-frame-accurate timing
        scenes = [
            Scene(start_time=0.123, end_time=2.456, duration=2.333, scene_number=1),
            Scene(start_time=3.789, end_time=5.111, duration=1.322, scene_number=2)
        ]
        
        settings = ProjectSettings(fps=25.0)
        service = MontageTableAssemblyService(settings)
        
        # The service should automatically adjust for frame accuracy
        result = await service.generate_montage_table(scenes)
        
        # Verify that all timecodes are frame-accurate
        for row in result.montage_rows:
            # Parse timecodes and verify frame accuracy
            start_parts = row.start_timecode.split(':')
            end_parts = row.end_timecode.split(':')
            
            # Frames should be valid (0-24 for 25fps)
            start_frames = int(start_parts[3])
            end_frames = int(end_parts[3])
            
            assert 0 <= start_frames < 25
            assert 0 <= end_frames < 25
    
    @pytest.mark.asyncio
    async def test_montage_table_validation_with_advanced_timecode(self):
        """Test montage table validation with advanced timecode features."""
        scenes = [
            Scene(start_time=0.0, end_time=5.0, duration=5.0, scene_number=1),
            Scene(start_time=5.04, end_time=10.0, duration=4.96, scene_number=2)
        ]
        
        settings = ProjectSettings(
            timecode_start="01:00:00:00",
            standard=TimecodeStandard.GFF,
            fps=25.0
        )
        
        service = MontageTableAssemblyService(settings)
        result = await service.generate_montage_table(scenes)
        
        # Should have no validation errors with proper continuity
        assert len(result.validation_errors) == 0
        
        # Verify timecode format
        for row in result.montage_rows:
            valid_start, _ = service.timecode_service.validate_timecode_format(row.start_timecode)
            valid_end, _ = service.timecode_service.validate_timecode_format(row.end_timecode)
            
            assert valid_start is True
            assert valid_end is True


if __name__ == "__main__":
    pytest.main([__file__])