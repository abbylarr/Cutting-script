"""
Test data fixtures and factories for comprehensive testing.
"""
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
from uuid import uuid4

from app.schemas.film_project import MontageRow, ShotType
from app.schemas.processing_task import ProcessingStep, TaskStatus


class TestDataFactory:
    """Factory for creating test data."""
    
    @staticmethod
    def create_film_metadata(title: str = "Тестовый фильм") -> Dict[str, Any]:
        """Create film metadata for testing."""
        return {
            "title": title,
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
            "subtitle_language": "Русский",
            "audio_language": "Русский"
        }
    
    @staticmethod
    def create_montage_rows(count: int = 3) -> List[Dict[str, Any]]:
        """Create montage rows for testing."""
        rows = []
        
        shot_types = ["Дальний", "Общий", "Средний", "Крупный", "Деталь"]
        dialogues = [
            "Привет, как дела?",
            "Все хорошо, спасибо за вопрос.",
            "Что планируем делать сегодня?",
            "Давайте обсудим наши планы.",
            "Это очень интересная идея."
        ]
        descriptions = [
            "Человек входит в комнату",
            "Крупный план лица персонажа",
            "Общий план интерьера",
            "Диалог между персонажами",
            "Финальная сцена эпизода"
        ]
        
        for i in range(count):
            start_seconds = i * 30
            end_seconds = (i + 1) * 30
            
            # Convert to timecode format
            start_timecode = f"01:00:{start_seconds//60:02d}:{start_seconds%60:02d}"
            end_timecode = f"01:00:{end_seconds//60:02d}:{end_seconds%60:02d}"
            
            row = {
                "number": i + 1,
                "start_timecode": start_timecode,
                "end_timecode": end_timecode,
                "shot_type": shot_types[i % len(shot_types)],
                "description": descriptions[i % len(descriptions)],
                "dialogue": dialogues[i % len(dialogues)] if i % 2 == 0 else "",
                "speaker": f"SPEAKER_{i % 2:02d}" if i % 2 == 0 else None,
                "has_music": i % 3 == 1,  # Every third row has music
                "special_tags": ["НДП"] if i % 4 == 2 else []  # Some rows have special tags
            }
            rows.append(row)
        
        return rows
    
    @staticmethod
    def create_video_metadata() -> Dict[str, Any]:
        """Create video metadata for testing."""
        return {
            "duration": 180.0,  # 3 minutes
            "fps": 25.0,
            "width": 1920,
            "height": 1080,
            "codec": "h264",
            "format": "mp4",
            "bitrate": 5000000,
            "audio_codec": "aac",
            "audio_channels": 2,
            "audio_sample_rate": 48000
        }
    
    @staticmethod
    def create_scene_list(count: int = 5) -> List[Dict[str, Any]]:
        """Create scene list for testing."""
        scenes = []
        current_time = 0.0
        
        for i in range(count):
            duration = 30.0 + (i * 10.0)  # Varying durations
            scene = {
                "start_time": current_time,
                "end_time": current_time + duration,
                "duration": duration,
                "scene_number": i + 1
            }
            scenes.append(scene)
            current_time += duration
        
        return scenes
    
    @staticmethod
    def create_transcription_result() -> Dict[str, Any]:
        """Create transcription result for testing."""
        return {
            "text": "Привет, как дела? Все хорошо, спасибо. Что планируем делать сегодня? Давайте обсудим наши планы.",
            "segments": [
                {"start": 0.0, "end": 5.0, "text": "Привет, как дела?"},
                {"start": 30.0, "end": 35.0, "text": "Все хорошо, спасибо."},
                {"start": 60.0, "end": 65.0, "text": "Что планируем делать сегодня?"},
                {"start": 90.0, "end": 95.0, "text": "Давайте обсудим наши планы."}
            ]
        }
    
    @staticmethod
    def create_diarization_result() -> Dict[str, Any]:
        """Create diarization result for testing."""
        return {
            "speakers": ["SPEAKER_00", "SPEAKER_01"],
            "segments": [
                {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"},
                {"start": 30.0, "end": 35.0, "speaker": "SPEAKER_01"},
                {"start": 60.0, "end": 65.0, "speaker": "SPEAKER_00"},
                {"start": 90.0, "end": 95.0, "speaker": "SPEAKER_01"}
            ]
        }
    
    @staticmethod
    def create_visual_analysis_result() -> List[Dict[str, Any]]:
        """Create visual analysis result for testing."""
        return [
            {
                "scene": 1,
                "shot_type": "Ср.",
                "description": "Человек сидит за столом и говорит",
                "text_in_frame": ""
            },
            {
                "scene": 2,
                "shot_type": "Кр.",
                "description": "Крупный план лица персонажа",
                "text_in_frame": ""
            },
            {
                "scene": 3,
                "shot_type": "Общ.",
                "description": "Общий план комнаты с мебелью",
                "text_in_frame": "НОВОСТИ"
            },
            {
                "scene": 4,
                "shot_type": "Ср.",
                "description": "Два человека в диалоге",
                "text_in_frame": ""
            },
            {
                "scene": 5,
                "shot_type": "Деталь",
                "description": "Крупный план руки на клавиатуре",
                "text_in_frame": ""
            }
        ]
    
    @staticmethod
    def create_keyframes_result() -> List[Dict[str, Any]]:
        """Create keyframes extraction result for testing."""
        return [
            {"scene": 1, "frames": ["/tmp/scene1_35.jpg", "/tmp/scene1_70.jpg"]},
            {"scene": 2, "frames": ["/tmp/scene2_35.jpg", "/tmp/scene2_70.jpg"]},
            {"scene": 3, "frames": ["/tmp/scene3_35.jpg", "/tmp/scene3_70.jpg"]},
            {"scene": 4, "frames": ["/tmp/scene4_35.jpg", "/tmp/scene4_70.jpg"]},
            {"scene": 5, "frames": ["/tmp/scene5_35.jpg", "/tmp/scene5_70.jpg"]}
        ]
    
    @staticmethod
    def create_dialogue_mapping_result() -> List[Dict[str, Any]]:
        """Create dialogue mapping result for testing."""
        return [
            {"scene": 1, "dialogue": "Привет, как дела?", "speaker": "SPEAKER_00"},
            {"scene": 2, "dialogue": "Все хорошо, спасибо.", "speaker": "SPEAKER_01"},
            {"scene": 3, "dialogue": "", "speaker": None},  # No dialogue
            {"scene": 4, "dialogue": "Что планируем делать сегодня?", "speaker": "SPEAKER_00"},
            {"scene": 5, "dialogue": "Давайте обсудим наши планы.", "speaker": "SPEAKER_01"}
        ]
    
    @staticmethod
    def create_music_analysis_result() -> List[Dict[str, Any]]:
        """Create music analysis result for testing."""
        return [
            {"scene": 1, "has_music": False, "confidence": 0.1},
            {"scene": 2, "has_music": True, "confidence": 0.8},
            {"scene": 3, "has_music": False, "confidence": 0.2},
            {"scene": 4, "has_music": False, "confidence": 0.1},
            {"scene": 5, "has_music": True, "confidence": 0.7}
        ]
    
    @staticmethod
    def create_processing_context_data() -> Dict[str, Any]:
        """Create complete processing context data for testing."""
        return {
            "task_id": str(uuid4()),
            "user_id": str(uuid4()),
            "video_path": "/uploads/test_video.mp4",
            "audio_path": "/tmp/test_audio.wav",
            "srt_path": None,
            "use_srt": False,
            "video_metadata": TestDataFactory.create_video_metadata(),
            "scenes": TestDataFactory.create_scene_list(),
            "transcription_result": TestDataFactory.create_transcription_result(),
            "diarization_result": TestDataFactory.create_diarization_result(),
            "processed_text": "Привет, как дела? Все хорошо, спасибо. Что планируем делать сегодня? Давайте обсудим наши планы.",
            "keyframes": TestDataFactory.create_keyframes_result(),
            "visual_analysis": TestDataFactory.create_visual_analysis_result(),
            "dialogue_mapping": TestDataFactory.create_dialogue_mapping_result(),
            "music_analysis": TestDataFactory.create_music_analysis_result(),
            "montage_rows": TestDataFactory.create_montage_rows(),
            "docx_path": "/tmp/test_montage.docx"
        }
    
    @staticmethod
    def create_srt_content() -> str:
        """Create SRT file content for testing."""
        return """1
00:00:00,000 --> 00:00:05,000
Привет, как дела?

2
00:00:30,000 --> 00:00:35,000
Все хорошо, спасибо.

3
00:01:00,000 --> 00:01:05,000
Что планируем делать сегодня?

4
00:01:30,000 --> 00:01:35,000
Давайте обсудим наши планы.

5
00:02:00,000 --> 00:02:05,000
Это очень интересная идея.
"""
    
    @staticmethod
    def create_error_scenarios() -> List[Dict[str, Any]]:
        """Create various error scenarios for testing."""
        return [
            {
                "name": "openai_rate_limit",
                "error": "Rate limit exceeded. Please try again in 60 seconds.",
                "service": "transcription",
                "recoverable": True
            },
            {
                "name": "openai_api_key_invalid",
                "error": "Invalid API key provided",
                "service": "transcription",
                "recoverable": False
            },
            {
                "name": "hf_token_missing",
                "error": "HF_TOKEN environment variable not set",
                "service": "diarization",
                "recoverable": True
            },
            {
                "name": "ffmpeg_not_found",
                "error": "FFmpeg not found in system PATH",
                "service": "video_processing",
                "recoverable": False
            },
            {
                "name": "insufficient_balance",
                "error": "Insufficient balance for processing",
                "service": "billing",
                "recoverable": False
            },
            {
                "name": "file_not_found",
                "error": "Video file not found",
                "service": "file_system",
                "recoverable": False
            },
            {
                "name": "corrupted_video",
                "error": "Video file is corrupted or unreadable",
                "service": "video_validation",
                "recoverable": False
            }
        ]


class MockDataProvider:
    """Provider for mock data and responses."""
    
    @staticmethod
    def get_openai_transcription_response() -> Dict[str, Any]:
        """Get mock OpenAI transcription response."""
        return {
            "text": TestDataFactory.create_transcription_result()["text"],
            "segments": TestDataFactory.create_transcription_result()["segments"]
        }
    
    @staticmethod
    def get_openai_visual_analysis_response() -> Dict[str, Any]:
        """Get mock OpenAI visual analysis response."""
        return {
            "shot_type": "Ср.",
            "description": "Человек сидит за столом и говорит в камеру",
            "text_in_frame": ""
        }
    
    @staticmethod
    def get_ffmpeg_probe_response() -> str:
        """Get mock FFmpeg probe JSON response."""
        metadata = TestDataFactory.create_video_metadata()
        return json.dumps({
            "format": {
                "duration": str(metadata["duration"]),
                "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
                "bit_rate": str(metadata["bitrate"])
            },
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": metadata["codec"],
                    "width": metadata["width"],
                    "height": metadata["height"],
                    "r_frame_rate": f"{int(metadata['fps'])}/1"
                },
                {
                    "codec_type": "audio",
                    "codec_name": metadata["audio_codec"],
                    "channels": metadata["audio_channels"],
                    "sample_rate": str(metadata["audio_sample_rate"])
                }
            ]
        })
    
    @staticmethod
    def get_pyannote_diarization_response() -> Dict[str, Any]:
        """Get mock pyannote.audio diarization response."""
        return TestDataFactory.create_diarization_result()
    
    @staticmethod
    def get_sbp_payment_response() -> Dict[str, Any]:
        """Get mock СБП payment response."""
        return {
            "payment_id": f"sbp_{uuid4().hex[:8]}",
            "status": "pending",
            "qr_code": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "amount": 750.0,
            "expires_at": (datetime.utcnow() + timedelta(minutes=15)).isoformat()
        }


# Export commonly used test data
TEST_FILM_METADATA = TestDataFactory.create_film_metadata()
TEST_MONTAGE_ROWS = TestDataFactory.create_montage_rows()
TEST_VIDEO_METADATA = TestDataFactory.create_video_metadata()
TEST_SCENE_LIST = TestDataFactory.create_scene_list()
TEST_TRANSCRIPTION = TestDataFactory.create_transcription_result()
TEST_DIARIZATION = TestDataFactory.create_diarization_result()
TEST_VISUAL_ANALYSIS = TestDataFactory.create_visual_analysis_result()
TEST_SRT_CONTENT = TestDataFactory.create_srt_content()
TEST_ERROR_SCENARIOS = TestDataFactory.create_error_scenarios()