"""
Simple tests for project management API endpoints logic.
"""
import pytest
import json
from uuid import uuid4
from unittest.mock import patch, MagicMock

from app.schemas.film_project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, 
    SaveProjectRequest, FilmMetadata, ProjectSettings,
    MontageRow, ShotType, TimecodeStandard, ColorType
)


class TestProjectSchemas:
    """Test project-related schema validation."""
    
    def test_film_metadata_validation(self):
        """Test film metadata schema validation."""
        valid_metadata = FilmMetadata(
            title="Test Film",
            production_company="Test Studio",
            year=2024,
            country="Russia",
            screenwriters=["Author 1", "Author 2"],
            copyright_holders=["Holder 1"],
            duration="01:30:00",
            episodes_count=1,
            format="Digital",
            color_type=ColorType.COLOR,
            media_carrier="HDD",
            original_language="Русский",
            audio_language="Русский"
        )
        
        assert valid_metadata.title == "Test Film"
        assert valid_metadata.year == 2024
        assert valid_metadata.color_type == ColorType.COLOR
        assert len(valid_metadata.screenwriters) == 2
        assert valid_metadata.episodes_count == 1
    
    def test_project_settings_validation(self):
        """Test project settings schema validation."""
        settings = ProjectSettings(
            timecode_start="01:00:00:00",
            standard=TimecodeStandard.GFF,
            fps=25.0
        )
        
        assert settings.timecode_start == "01:00:00:00"
        assert settings.standard == TimecodeStandard.GFF
        assert settings.fps == 25.0
        
        # Test alternative settings
        alt_settings = ProjectSettings(
            timecode_start="00:00:00:00",
            standard=TimecodeStandard.KRASNOGORSKY,
            fps=29.97
        )
        
        assert alt_settings.timecode_start == "00:00:00:00"
        assert alt_settings.standard == TimecodeStandard.KRASNOGORSKY
        assert alt_settings.fps == 29.97
    
    def test_project_create_validation(self):
        """Test project creation schema validation."""
        film_metadata = FilmMetadata(
            title="New Project",
            production_company="Studio",
            year=2024,
            country="Russia",
            screenwriters=["Writer"],
            copyright_holders=["Owner"],
            duration="02:00:00",
            episodes_count=1,
            format="4K",
            color_type=ColorType.COLOR,
            media_carrier="SSD",
            original_language="Русский",
            audio_language="Русский"
        )
        
        project_create = ProjectCreate(
            title="New Project",
            film_metadata=film_metadata
        )
        
        assert project_create.title == "New Project"
        assert project_create.film_metadata.title == "New Project"
        assert project_create.project_settings is None  # Optional field
    
    def test_project_update_validation(self):
        """Test project update schema validation."""
        # Test partial update
        update = ProjectUpdate(title="Updated Title")
        assert update.title == "Updated Title"
        assert update.film_metadata is None
        assert update.project_settings is None
        assert update.montage_rows is None
        
        # Test update with montage rows
        rows = [
            MontageRow(
                number=1,
                start_timecode="01:00:00:00",
                end_timecode="01:00:05:00",
                shot_type=ShotType.MEDIUM,
                description="Updated scene",
                dialogue="Updated dialogue",
                speaker="Speaker",
                has_music=False,
                special_tags=[]
            )
        ]
        
        update_with_rows = ProjectUpdate(montage_rows=rows)
        assert len(update_with_rows.montage_rows) == 1
        assert update_with_rows.montage_rows[0].description == "Updated scene"
    
    def test_save_project_request_validation(self):
        """Test save project request validation."""
        rows = [
            MontageRow(
                number=1,
                start_timecode="01:00:00:00",
                end_timecode="01:00:05:00",
                shot_type=ShotType.CLOSE,
                description="Scene to save",
                dialogue="Dialogue to save",
                speaker="Actor",
                has_music=True,
                special_tags=["НДП", "ЗТМ"]
            )
        ]
        
        save_request = SaveProjectRequest(
            montage_rows=rows,
            regenerate_docx=True
        )
        
        assert len(save_request.montage_rows) == 1
        assert save_request.regenerate_docx is True
        assert save_request.montage_rows[0].has_music is True
        assert "НДП" in save_request.montage_rows[0].special_tags
        
        # Test without DOCX regeneration
        save_request_no_docx = SaveProjectRequest(
            montage_rows=rows,
            regenerate_docx=False
        )
        
        assert save_request_no_docx.regenerate_docx is False


class TestProjectEnums:
    """Test project-related enums."""
    
    def test_timecode_standard_enum(self):
        """Test timecode standard enum values."""
        assert TimecodeStandard.GFF.value == "ГФФ"
        assert TimecodeStandard.KRASNOGORSKY.value == "Красногорский"
        
        # Test that we can create from string values
        gff_from_str = TimecodeStandard("ГФФ")
        assert gff_from_str == TimecodeStandard.GFF
        
        krasno_from_str = TimecodeStandard("Красногорский")
        assert krasno_from_str == TimecodeStandard.KRASNOGORSKY
    
    def test_color_type_enum(self):
        """Test color type enum values."""
        assert ColorType.COLOR.value == "Цветной"
        assert ColorType.BLACK_WHITE.value == "Черно-белый"
        
        # Test creation from string values
        color_from_str = ColorType("Цветной")
        assert color_from_str == ColorType.COLOR
        
        bw_from_str = ColorType("Черно-белый")
        assert bw_from_str == ColorType.BLACK_WHITE
    
    def test_shot_type_enum(self):
        """Test shot type enum values."""
        expected_values = {
            ShotType.DISTANT: "Дальний",
            ShotType.GENERAL: "Общий",
            ShotType.MEDIUM: "Средний", 
            ShotType.CLOSE: "Крупный",
            ShotType.DETAIL: "Деталь"
        }
        
        for shot_type, expected_value in expected_values.items():
            assert shot_type.value == expected_value
            
            # Test creation from string
            from_str = ShotType(expected_value)
            assert from_str == shot_type


class TestProjectDataHandling:
    """Test project data handling and serialization."""
    
    def test_montage_rows_serialization(self):
        """Test montage rows JSON serialization."""
        rows = [
            {
                "number": 1,
                "start_timecode": "01:00:00:00",
                "end_timecode": "01:00:05:00",
                "shot_type": "Средний",
                "description": "Test scene",
                "dialogue": "Test dialogue",
                "speaker": "Speaker 1",
                "has_music": False,
                "special_tags": ["НДП"]
            },
            {
                "number": 2,
                "start_timecode": "01:00:05:01",
                "end_timecode": "01:00:10:00",
                "shot_type": "Общий",
                "description": "Second scene",
                "dialogue": "",
                "speaker": None,
                "has_music": True,
                "special_tags": []
            }
        ]
        
        # Test serialization
        json_str = json.dumps(rows, ensure_ascii=False)
        assert isinstance(json_str, str)
        assert "Средний" in json_str
        assert "НДП" in json_str
        
        # Test deserialization
        parsed_rows = json.loads(json_str)
        assert len(parsed_rows) == 2
        assert parsed_rows[0]["shot_type"] == "Средний"
        assert parsed_rows[1]["has_music"] is True
        assert parsed_rows[0]["special_tags"] == ["НДП"]
    
    def test_film_metadata_serialization(self):
        """Test film metadata JSON serialization."""
        metadata = {
            "title": "Тестовый фильм",
            "production_company": "Тестовая студия",
            "year": 2024,
            "country": "Россия",
            "screenwriters": ["Автор 1", "Автор 2"],
            "copyright_holders": ["Правообладатель 1"],
            "duration": "01:30:00",
            "episodes_count": 1,
            "format": "Digital",
            "color_type": "Цветной",
            "media_carrier": "HDD",
            "original_language": "Русский",
            "audio_language": "Русский"
        }
        
        # Test serialization
        json_str = json.dumps(metadata, ensure_ascii=False)
        assert "Тестовый фильм" in json_str
        assert "Россия" in json_str
        
        # Test deserialization
        parsed_metadata = json.loads(json_str)
        assert parsed_metadata["title"] == "Тестовый фильм"
        assert parsed_metadata["year"] == 2024
        assert len(parsed_metadata["screenwriters"]) == 2
    
    def test_project_settings_serialization(self):
        """Test project settings JSON serialization."""
        settings = {
            "timecode_start": "01:00:00:00",
            "standard": "ГФФ",
            "fps": 25.0
        }
        
        # Test serialization
        json_str = json.dumps(settings, ensure_ascii=False)
        assert "ГФФ" in json_str
        assert "01:00:00:00" in json_str
        
        # Test deserialization
        parsed_settings = json.loads(json_str)
        assert parsed_settings["standard"] == "ГФФ"
        assert parsed_settings["fps"] == 25.0


class TestProjectValidationRules:
    """Test project validation business rules."""
    
    def test_year_validation_range(self):
        """Test year validation range."""
        # Valid years
        valid_years = [1900, 2000, 2024, 2100]
        
        for year in valid_years:
            metadata = FilmMetadata(
                title="Test",
                production_company="Studio",
                year=year,
                country="Country",
                screenwriters=["Author"],
                copyright_holders=["Holder"],
                duration="01:00:00",
                episodes_count=1,
                format="Digital",
                color_type=ColorType.COLOR,
                media_carrier="HDD",
                original_language="Language",
                audio_language="Language"
            )
            assert metadata.year == year
    
    def test_episodes_count_validation(self):
        """Test episodes count validation."""
        # Valid episode counts
        valid_counts = [1, 5, 10, 100]
        
        for count in valid_counts:
            metadata = FilmMetadata(
                title="Test",
                production_company="Studio", 
                year=2024,
                country="Country",
                screenwriters=["Author"],
                copyright_holders=["Holder"],
                duration="01:00:00",
                episodes_count=count,
                format="Digital",
                color_type=ColorType.COLOR,
                media_carrier="HDD",
                original_language="Language",
                audio_language="Language"
            )
            assert metadata.episodes_count == count
    
    def test_timecode_pattern_validation(self):
        """Test timecode pattern validation."""
        valid_timecodes = [
            "00:00:00:00",
            "01:00:00:00", 
            "23:59:59:29"
        ]
        
        for timecode in valid_timecodes:
            settings = ProjectSettings(
                timecode_start=timecode,
                standard=TimecodeStandard.GFF,
                fps=25.0
            )
            assert settings.timecode_start == timecode
    
    def test_fps_validation(self):
        """Test FPS validation."""
        valid_fps_values = [23.976, 24.0, 25.0, 29.97, 30.0, 50.0, 59.94, 60.0]
        
        for fps in valid_fps_values:
            settings = ProjectSettings(
                timecode_start="01:00:00:00",
                standard=TimecodeStandard.GFF,
                fps=fps
            )
            assert settings.fps == fps
    
    def test_montage_row_numbering(self):
        """Test montage row numbering validation."""
        # Test sequential numbering
        rows = []
        for i in range(1, 6):  # Numbers 1-5
            row = MontageRow(
                number=i,
                start_timecode=f"01:00:{i:02d}:00",
                end_timecode=f"01:00:{i+4:02d}:00",
                shot_type=ShotType.MEDIUM,
                description=f"Scene {i}",
                dialogue=f"Dialogue {i}",
                speaker=f"Speaker {i}",
                has_music=False,
                special_tags=[]
            )
            rows.append(row)
        
        # Verify sequential numbering
        for i, row in enumerate(rows):
            assert row.number == i + 1
        
        # Test that we can create a save request with these rows
        save_request = SaveProjectRequest(
            montage_rows=rows,
            regenerate_docx=True
        )
        
        assert len(save_request.montage_rows) == 5
        assert save_request.montage_rows[0].number == 1
        assert save_request.montage_rows[-1].number == 5


if __name__ == "__main__":
    pytest.main([__file__])