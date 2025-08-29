"""
End-to-end integration tests for complete video processing workflows.
"""
import pytest
import asyncio
import tempfile
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.user import User
from app.models.processing_task import ProcessingTask
from app.models.film_project import FilmProject
from app.schemas.processing_task import TaskStatus, ProcessingStep
from app.services.pipeline_orchestrator import PipelineOrchestrator, ProcessingContext
from app.services.task_queue import TaskQueue, TaskInfo, TaskPriority


class TestEndToEndWorkflows:
    """Test complete end-to-end workflows."""
    
    @pytest.fixture
    def authenticated_client(self, client: TestClient, test_user: User):
        """Create authenticated test client."""
        # Mock authentication
        with patch('app.core.auth.get_current_user', return_value=test_user):
            yield client
    
    @pytest.fixture
    def mock_all_services(self):
        """Mock all external services for E2E tests."""
        with patch.multiple(
            'app.services.pipeline_orchestrator',
            VideoValidationService=MagicMock,
            AudioExtractionService=MagicMock,
            SceneDetectionService=MagicMock,
            TranscriptionService=MagicMock,
            SpeakerDiarizationService=MagicMock,
            TextProcessingService=MagicMock,
            KeyframeExtractionService=MagicMock,
            GPTVisualAnalysisService=MagicMock,
            DialogueSceneMappingService=MagicMock,
            MusicDetectionService=MagicMock,
            MontageTableAssemblyService=MagicMock,
            DOCXGeneratorService=MagicMock
        ) as mocks:
            # Setup successful responses for all services
            self._setup_successful_mocks(mocks)
            yield mocks
    
    def _setup_successful_mocks(self, mocks):
        """Setup all mocks for successful processing."""
        from app.services.video_processor import VideoMetadata, ValidationResult, Scene
        
        # Video validation
        mocks['VideoValidationService'].return_value.validate_video = AsyncMock(
            return_value=ValidationResult(
                is_valid=True,
                metadata=VideoMetadata(
                    duration=120.0, fps=25.0, width=1920, height=1080,
                    codec="h264", format="mp4", bitrate=5000000,
                    audio_codec="aac", audio_channels=2, audio_sample_rate=48000
                )
            )
        )
        mocks['VideoValidationService'].return_value.check_video_integrity = AsyncMock(
            return_value=(True, None)
        )
        
        # Audio extraction
        mocks['AudioExtractionService'].return_value.extract_audio = AsyncMock(
            return_value="/tmp/test_audio.wav"
        )
        
        # Scene detection
        mocks['SceneDetectionService'].return_value.detect_scenes_with_fallback = AsyncMock(
            return_value=[
                Scene(start_time=0.0, end_time=30.0, duration=30.0, scene_number=1),
                Scene(start_time=30.0, end_time=60.0, duration=30.0, scene_number=2),
                Scene(start_time=60.0, end_time=120.0, duration=60.0, scene_number=3)
            ]
        )
        
        # Transcription
        mocks['TranscriptionService'].return_value.transcribe_audio = AsyncMock(
            return_value={
                "text": "Привет, как дела? Все хорошо, спасибо. Что планируем делать сегодня?",
                "segments": [
                    {"start": 0.0, "end": 5.0, "text": "Привет, как дела?"},
                    {"start": 35.0, "end": 40.0, "text": "Все хорошо, спасибо."},
                    {"start": 65.0, "end": 70.0, "text": "Что планируем делать сегодня?"}
                ]
            }
        )
        
        # Diarization
        mocks['SpeakerDiarizationService'].return_value.diarize_audio = AsyncMock(
            return_value={
                "speakers": ["SPEAKER_00", "SPEAKER_01"],
                "segments": [
                    {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"},
                    {"start": 35.0, "end": 40.0, "speaker": "SPEAKER_01"},
                    {"start": 65.0, "end": 70.0, "speaker": "SPEAKER_00"}
                ]
            }
        )
        
        # Text processing
        mocks['TextProcessingService'].return_value.process_text = AsyncMock(
            return_value="Привет, как дела? Все хорошо, спасибо. Что планируем делать сегодня?"
        )
        
        # Keyframe extraction
        mocks['KeyframeExtractionService'].return_value.extract_keyframes_for_scenes = AsyncMock(
            return_value=[
                {"scene": 1, "frames": ["/tmp/scene1_35.jpg", "/tmp/scene1_70.jpg"]},
                {"scene": 2, "frames": ["/tmp/scene2_35.jpg", "/tmp/scene2_70.jpg"]},
                {"scene": 3, "frames": ["/tmp/scene3_35.jpg", "/tmp/scene3_70.jpg"]}
            ]
        )
        
        # Visual analysis
        mocks['GPTVisualAnalysisService'].return_value.analyze_scenes = AsyncMock(
            return_value=[
                {"scene": 1, "shot_type": "Ср.", "description": "Человек говорит в камеру", "text_in_frame": ""},
                {"scene": 2, "shot_type": "Кр.", "description": "Крупный план лица", "text_in_frame": ""},
                {"scene": 3, "shot_type": "Общ.", "description": "Общий план комнаты", "text_in_frame": ""}
            ]
        )
        
        # Dialogue mapping
        mocks['DialogueSceneMappingService'].return_value.map_dialogue_to_scenes = AsyncMock(
            return_value=[
                {"scene": 1, "dialogue": "Привет, как дела?", "speaker": "SPEAKER_00"},
                {"scene": 2, "dialogue": "Все хорошо, спасибо.", "speaker": "SPEAKER_01"},
                {"scene": 3, "dialogue": "Что планируем делать сегодня?", "speaker": "SPEAKER_00"}
            ]
        )
        
        # Music detection
        mocks['MusicDetectionService'].return_value.detect_music_in_scenes = AsyncMock(
            return_value=[
                {"scene": 1, "has_music": False},
                {"scene": 2, "has_music": True},
                {"scene": 3, "has_music": False}
            ]
        )
        
        # Montage table assembly
        mocks['MontageTableAssemblyService'].return_value.generate_montage_table = AsyncMock(
            return_value=[
                {
                    "number": 1,
                    "start_timecode": "01:00:00:00",
                    "end_timecode": "01:00:30:00",
                    "shot_type": "Ср.",
                    "description": "Человек говорит в камеру",
                    "dialogue": "Привет, как дела?",
                    "speaker": "SPEAKER_00",
                    "has_music": False,
                    "special_tags": []
                },
                {
                    "number": 2,
                    "start_timecode": "01:00:30:01",
                    "end_timecode": "01:01:00:00",
                    "shot_type": "Кр.",
                    "description": "Крупный план лица",
                    "dialogue": "Все хорошо, спасибо.",
                    "speaker": "SPEAKER_01",
                    "has_music": True,
                    "special_tags": []
                },
                {
                    "number": 3,
                    "start_timecode": "01:01:00:01",
                    "end_timecode": "01:02:00:00",
                    "shot_type": "Общ.",
                    "description": "Общий план комнаты",
                    "dialogue": "Что планируем делать сегодня?",
                    "speaker": "SPEAKER_00",
                    "has_music": False,
                    "special_tags": []
                }
            ]
        )
        
        # Document generation
        mocks['DOCXGeneratorService'].return_value.generate_docx_for_task = AsyncMock(
            return_value="/tmp/test_montage.docx"
        )
    
    @pytest.mark.asyncio
    async def test_complete_video_upload_and_processing_workflow(
        self, authenticated_client: TestClient, test_user: User, 
        temp_video_file: str, mock_all_services, db_session: Session
    ):
        """Test complete workflow from video upload to document generation."""
        
        # Mock file operations
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.mkdir'), \
             patch('shutil.move'), \
             patch('app.services.task_queue.task_queue') as mock_task_queue:
            
            # Mock task queue
            mock_task_queue.add_task = AsyncMock()
            mock_task_queue.process_tasks = AsyncMock()
            
            # Step 1: Upload video file
            with open(temp_video_file, 'rb') as f:
                upload_response = authenticated_client.post(
                    "/api/v1/upload",
                    files={"file": ("test_video.mp4", f, "video/mp4")},
                    data={
                        "title": "Тестовый фильм",
                        "production_company": "Тестовая студия",
                        "year": "2024",
                        "country": "Россия",
                        "screenwriters": "Автор 1",
                        "copyright_holders": "Правообладатель 1",
                        "duration": "02:00:00",
                        "episodes_count": "1",
                        "format": "Digital",
                        "color_type": "Цветной",
                        "media_carrier": "HDD",
                        "original_language": "Русский",
                        "audio_language": "Русский",
                        "timecode_start": "01:00:00:00",
                        "standard": "ГФФ"
                    }
                )
            
            assert upload_response.status_code == 201
            upload_data = upload_response.json()
            task_id = upload_data["task_id"]
            
            # Verify task was created in database
            task = db_session.query(ProcessingTask).filter(
                ProcessingTask.id == task_id
            ).first()
            assert task is not None
            assert task.status == TaskStatus.PENDING
            assert task.user_id == test_user.id
            
            # Verify film project was created
            project = db_session.query(FilmProject).filter(
                FilmProject.task_id == task_id
            ).first()
            assert project is not None
            assert project.title == "Тестовый фильм"
            
            # Step 2: Simulate task processing
            with patch('app.services.pipeline_orchestrator.cache_manager') as mock_cache:
                mock_cache.redis_client.get_client = AsyncMock()
                mock_client = AsyncMock()
                mock_cache.redis_client.get_client.return_value = mock_client
                mock_client.setex = AsyncMock()
                
                # Create orchestrator and process
                orchestrator = PipelineOrchestrator()
                context = ProcessingContext(
                    task_id=str(task_id),
                    user_id=str(test_user.id),
                    video_path=f"/uploads/{task_id}/test_video.mp4"
                )
                
                # Mock progress tracker
                task_info = TaskInfo(
                    task_id=str(task_id),
                    user_id=str(test_user.id),
                    priority=TaskPriority.NORMAL,
                    created_at=task.created_at
                )
                
                from app.services.task_queue import TaskProgressTracker
                progress_tracker = TaskProgressTracker(str(task_id), task_info)
                progress_tracker.set_total_steps = AsyncMock()
                progress_tracker.start_step = AsyncMock()
                progress_tracker.complete_step = AsyncMock()
                progress_tracker.update_progress = AsyncMock()
                progress_tracker.check_cancellation = MagicMock(return_value=False)
                
                # Process the video
                result_context = await orchestrator.process_video(progress_tracker, context)
                
                # Update task status in database
                task.status = TaskStatus.COMPLETED
                task.progress = 1.0
                task.result = json.dumps(result_context.montage_rows)
                db_session.commit()
            
            # Step 3: Check task status
            status_response = authenticated_client.get(f"/api/v1/status/{task_id}")
            assert status_response.status_code == 200
            status_data = status_response.json()
            
            assert status_data["status"] == "completed"
            assert status_data["progress"] == 1.0
            assert len(status_data["result"]) == 3  # 3 montage rows
            
            # Step 4: Download generated document
            with patch('os.path.exists', return_value=True), \
                 patch('fastapi.responses.FileResponse') as mock_file_response:
                
                download_response = authenticated_client.get(f"/api/v1/download/{task_id}")
                assert download_response.status_code == 200
            
            # Step 5: Update montage rows
            updated_rows = [
                {
                    "number": 1,
                    "start_timecode": "01:00:00:00",
                    "end_timecode": "01:00:30:00",
                    "shot_type": "Кр.",  # Changed from Ср.
                    "description": "Обновленное описание",  # Changed
                    "dialogue": "Привет, как дела?",
                    "speaker": "Главный герой",  # Changed speaker name
                    "has_music": False,
                    "special_tags": []
                },
                {
                    "number": 2,
                    "start_timecode": "01:00:30:01",
                    "end_timecode": "01:01:00:00",
                    "shot_type": "Кр.",
                    "description": "Крупный план лица",
                    "dialogue": "Все хорошо, спасибо.",
                    "speaker": "Второй персонаж",  # Changed speaker name
                    "has_music": True,
                    "special_tags": ["НДП"]  # Added special tag
                },
                {
                    "number": 3,
                    "start_timecode": "01:01:00:01",
                    "end_timecode": "01:02:00:00",
                    "shot_type": "Общ.",
                    "description": "Общий план комнаты",
                    "dialogue": "Что планируем делать сегодня?",
                    "speaker": "Главный герой",
                    "has_music": False,
                    "special_tags": []
                }
            ]
            
            with patch('app.services.docx_generator.docx_generator.generate_docx_for_task', 
                      new_callable=AsyncMock) as mock_docx:
                mock_docx.return_value = "/tmp/updated_montage.docx"
                
                update_response = authenticated_client.patch(
                    f"/api/v1/montage/{task_id}",
                    json={"rows": updated_rows}
                )
                
                assert update_response.status_code == 200
                update_data = update_response.json()
                assert update_data["success"] is True
                assert update_data["data"]["rows_updated"] == 3
            
            # Step 6: Save project
            save_response = authenticated_client.post(f"/api/v1/save/{task_id}")
            assert save_response.status_code == 200
            save_data = save_response.json()
            assert save_data["success"] is True
    
    @pytest.mark.asyncio
    async def test_srt_upload_workflow(
        self, authenticated_client: TestClient, test_user: User,
        temp_video_file: str, temp_srt_file: str, mock_all_services, db_session: Session
    ):
        """Test workflow with SRT file upload."""
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.mkdir'), \
             patch('shutil.move'), \
             patch('app.services.task_queue.task_queue') as mock_task_queue:
            
            mock_task_queue.add_task = AsyncMock()
            
            # Step 1: Upload video file (normal upload first)
            with open(temp_video_file, 'rb') as f:
                upload_response = authenticated_client.post(
                    "/api/v1/upload",
                    files={"file": ("test_video.mp4", f, "video/mp4")},
                    data={
                        "title": "Тестовый фильм с SRT",
                        "production_company": "Тестовая студия",
                        "year": "2024",
                        "country": "Россия"
                    }
                )
            
            assert upload_response.status_code == 201
            task_id = upload_response.json()["task_id"]
            
            # Step 2: Upload SRT file
            with open(temp_srt_file, 'rb') as f:
                srt_response = authenticated_client.post(
                    f"/api/v1/upload_srt/{task_id}",
                    files={"file": ("subtitles.srt", f, "text/plain")}
                )
            
            assert srt_response.status_code == 200
            srt_data = srt_response.json()
            assert srt_data["success"] is True
            assert "SRT file uploaded" in srt_data["message"]
            
            # Verify task was updated for SRT mode
            task = db_session.query(ProcessingTask).filter(
                ProcessingTask.id == task_id
            ).first()
            assert task.srt_path is not None
            
            # Step 3: Process with SRT mode
            with patch('app.services.pipeline_orchestrator.cache_manager') as mock_cache:
                mock_cache.redis_client.get_client = AsyncMock()
                mock_client = AsyncMock()
                mock_cache.redis_client.get_client.return_value = mock_client
                mock_client.setex = AsyncMock()
                
                orchestrator = PipelineOrchestrator()
                context = ProcessingContext(
                    task_id=str(task_id),
                    user_id=str(test_user.id),
                    video_path=f"/uploads/{task_id}/test_video.mp4",
                    srt_path=f"/uploads/{task_id}/subtitles.srt",
                    use_srt=True
                )
                
                # Mock progress tracker
                task_info = TaskInfo(
                    task_id=str(task_id),
                    user_id=str(test_user.id),
                    priority=TaskPriority.NORMAL,
                    created_at=task.created_at
                )
                
                from app.services.task_queue import TaskProgressTracker
                progress_tracker = TaskProgressTracker(str(task_id), task_info)
                progress_tracker.set_total_steps = AsyncMock()
                progress_tracker.start_step = AsyncMock()
                progress_tracker.complete_step = AsyncMock()
                progress_tracker.update_progress = AsyncMock()
                progress_tracker.check_cancellation = MagicMock(return_value=False)
                
                # Process should skip transcription and diarization
                result_context = await orchestrator.process_video(progress_tracker, context)
                
                # Verify SRT mode results
                assert result_context.transcription_result is None  # Should be skipped
                assert result_context.diarization_result is None   # Should be skipped
                assert result_context.processed_text is not None   # Should come from SRT
                assert result_context.montage_rows is not None
    
    @pytest.mark.asyncio
    async def test_error_recovery_workflow(
        self, authenticated_client: TestClient, test_user: User,
        temp_video_file: str, db_session: Session
    ):
        """Test error recovery and fallback mechanisms."""
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.mkdir'), \
             patch('shutil.move'), \
             patch('app.services.task_queue.task_queue') as mock_task_queue:
            
            mock_task_queue.add_task = AsyncMock()
            
            # Upload video
            with open(temp_video_file, 'rb') as f:
                upload_response = authenticated_client.post(
                    "/api/v1/upload",
                    files={"file": ("test_video.mp4", f, "video/mp4")},
                    data={"title": "Error Test Video"}
                )
            
            task_id = upload_response.json()["task_id"]
            
            # Mock services with failures and fallbacks
            with patch.multiple(
                'app.services.pipeline_orchestrator',
                VideoValidationService=MagicMock,
                AudioExtractionService=MagicMock,
                SceneDetectionService=MagicMock,
                TranscriptionService=MagicMock,
                SpeakerDiarizationService=MagicMock,
                TextProcessingService=MagicMock,
                KeyframeExtractionService=MagicMock,
                GPTVisualAnalysisService=MagicMock,
                DialogueSceneMappingService=MagicMock,
                MusicDetectionService=MagicMock,
                MontageTableAssemblyService=MagicMock,
                DOCXGeneratorService=MagicMock
            ) as mocks:
                
                from app.services.video_processor import VideoMetadata, ValidationResult, Scene
                
                # Setup validation success
                mocks['VideoValidationService'].return_value.validate_video = AsyncMock(
                    return_value=ValidationResult(
                        is_valid=True,
                        metadata=VideoMetadata(
                            duration=60.0, fps=25.0, width=1920, height=1080,
                            codec="h264", format="mp4"
                        )
                    )
                )
                mocks['VideoValidationService'].return_value.check_video_integrity = AsyncMock(
                    return_value=(True, None)
                )
                
                # Audio extraction success
                mocks['AudioExtractionService'].return_value.extract_audio = AsyncMock(
                    return_value="/tmp/audio.wav"
                )
                
                # Scene detection success
                mocks['SceneDetectionService'].return_value.detect_scenes_with_fallback = AsyncMock(
                    return_value=[Scene(start_time=0.0, end_time=60.0, duration=60.0, scene_number=1)]
                )
                
                # Transcription fails first, then succeeds (retry mechanism)
                call_count = 0
                async def failing_transcription(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if call_count == 1:
                        raise Exception("OpenAI API rate limit")
                    return {"text": "Fallback transcription"}
                
                mocks['TranscriptionService'].return_value.transcribe_audio = AsyncMock(
                    side_effect=failing_transcription
                )
                
                # Diarization fails (should continue without it)
                mocks['SpeakerDiarizationService'].return_value.diarize_audio = AsyncMock(
                    side_effect=Exception("HF_TOKEN not available")
                )
                
                # Text processing success
                mocks['TextProcessingService'].return_value.process_text = AsyncMock(
                    return_value="Processed fallback text"
                )
                
                # Continue with other successful services
                mocks['KeyframeExtractionService'].return_value.extract_keyframes_for_scenes = AsyncMock(
                    return_value=[{"scene": 1, "frames": ["frame1.jpg"]}]
                )
                
                mocks['GPTVisualAnalysisService'].return_value.analyze_scenes = AsyncMock(
                    return_value=[{"scene": 1, "shot_type": "Ср.", "description": "Test scene"}]
                )
                
                mocks['DialogueSceneMappingService'].return_value.map_dialogue_to_scenes = AsyncMock(
                    return_value=[{"scene": 1, "dialogue": "Fallback text", "speaker": None}]
                )
                
                mocks['MusicDetectionService'].return_value.detect_music_in_scenes = AsyncMock(
                    return_value=[{"scene": 1, "has_music": False}]
                )
                
                mocks['MontageTableAssemblyService'].return_value.generate_montage_table = AsyncMock(
                    return_value=[{
                        "number": 1,
                        "start_timecode": "01:00:00:00",
                        "end_timecode": "01:01:00:00",
                        "shot_type": "Ср.",
                        "description": "Test scene",
                        "dialogue": "Fallback text",
                        "speaker": None,
                        "has_music": False,
                        "special_tags": []
                    }]
                )
                
                mocks['DOCXGeneratorService'].return_value.generate_docx_for_task = AsyncMock(
                    return_value="/tmp/fallback_document.docx"
                )
                
                # Process with error recovery
                with patch('app.services.pipeline_orchestrator.cache_manager') as mock_cache:
                    mock_cache.redis_client.get_client = AsyncMock()
                    mock_client = AsyncMock()
                    mock_cache.redis_client.get_client.return_value = mock_client
                    mock_client.setex = AsyncMock()
                    
                    orchestrator = PipelineOrchestrator()
                    context = ProcessingContext(
                        task_id=str(task_id),
                        user_id=str(test_user.id),
                        video_path=f"/uploads/{task_id}/test_video.mp4"
                    )
                    
                    task_info = TaskInfo(
                        task_id=str(task_id),
                        user_id=str(test_user.id),
                        priority=TaskPriority.NORMAL,
                        created_at=db_session.query(ProcessingTask).filter(
                            ProcessingTask.id == task_id
                        ).first().created_at
                    )
                    
                    from app.services.task_queue import TaskProgressTracker
                    progress_tracker = TaskProgressTracker(str(task_id), task_info)
                    progress_tracker.set_total_steps = AsyncMock()
                    progress_tracker.start_step = AsyncMock()
                    progress_tracker.complete_step = AsyncMock()
                    progress_tracker.update_progress = AsyncMock()
                    progress_tracker.check_cancellation = MagicMock(return_value=False)
                    
                    # Should complete successfully despite failures
                    result_context = await orchestrator.process_video(progress_tracker, context)
                    
                    # Verify recovery worked
                    assert result_context.transcription_result["text"] == "Fallback transcription"
                    assert result_context.diarization_result is None  # Failed but continued
                    assert result_context.processed_text == "Processed fallback text"
                    assert result_context.montage_rows is not None
                    assert len(result_context.montage_rows) == 1
    
    @pytest.mark.asyncio
    async def test_concurrent_processing_workflow(
        self, authenticated_client: TestClient, db_session: Session
    ):
        """Test concurrent processing of multiple videos."""
        
        # Create multiple users
        users = []
        for i in range(3):
            user = User(
                email=f"user{i}@example.com",
                password_hash="$2b$12$hashed_password",
                balance=2000.0
            )
            db_session.add(user)
            users.append(user)
        db_session.commit()
        
        # Mock all services for successful processing
        with patch.multiple(
            'app.services.pipeline_orchestrator',
            VideoValidationService=MagicMock,
            AudioExtractionService=MagicMock,
            SceneDetectionService=MagicMock,
            TranscriptionService=MagicMock,
            SpeakerDiarizationService=MagicMock,
            TextProcessingService=MagicMock,
            KeyframeExtractionService=MagicMock,
            GPTVisualAnalysisService=MagicMock,
            DialogueSceneMappingService=MagicMock,
            MusicDetectionService=MagicMock,
            MontageTableAssemblyService=MagicMock,
            DOCXGeneratorService=MagicMock
        ) as mocks:
            
            self._setup_successful_mocks(mocks)
            
            # Create tasks for each user
            tasks = []
            for i, user in enumerate(users):
                with patch('app.core.auth.get_current_user', return_value=user):
                    with patch('pathlib.Path.exists', return_value=True), \
                         patch('pathlib.Path.mkdir'), \
                         patch('shutil.move'):
                        
                        # Create temporary video file
                        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
                            f.write(b'\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom')
                            f.write(b'\x00' * 1000)
                            temp_path = f.name
                        
                        try:
                            with open(temp_path, 'rb') as f:
                                upload_response = authenticated_client.post(
                                    "/api/v1/upload",
                                    files={"file": (f"video{i}.mp4", f, "video/mp4")},
                                    data={"title": f"Concurrent Video {i}"}
                                )
                            
                            assert upload_response.status_code == 201
                            task_id = upload_response.json()["task_id"]
                            tasks.append((task_id, user))
                        
                        finally:
                            Path(temp_path).unlink(missing_ok=True)
            
            # Process all tasks concurrently
            async def process_task(task_id, user):
                with patch('app.services.pipeline_orchestrator.cache_manager') as mock_cache:
                    mock_cache.redis_client.get_client = AsyncMock()
                    mock_client = AsyncMock()
                    mock_cache.redis_client.get_client.return_value = mock_client
                    mock_client.setex = AsyncMock()
                    
                    orchestrator = PipelineOrchestrator()
                    context = ProcessingContext(
                        task_id=str(task_id),
                        user_id=str(user.id),
                        video_path=f"/uploads/{task_id}/video.mp4"
                    )
                    
                    task_info = TaskInfo(
                        task_id=str(task_id),
                        user_id=str(user.id),
                        priority=TaskPriority.NORMAL,
                        created_at=db_session.query(ProcessingTask).filter(
                            ProcessingTask.id == task_id
                        ).first().created_at
                    )
                    
                    from app.services.task_queue import TaskProgressTracker
                    progress_tracker = TaskProgressTracker(str(task_id), task_info)
                    progress_tracker.set_total_steps = AsyncMock()
                    progress_tracker.start_step = AsyncMock()
                    progress_tracker.complete_step = AsyncMock()
                    progress_tracker.update_progress = AsyncMock()
                    progress_tracker.check_cancellation = MagicMock(return_value=False)
                    
                    return await orchestrator.process_video(progress_tracker, context)
            
            # Run all tasks concurrently
            results = await asyncio.gather(*[
                process_task(task_id, user) for task_id, user in tasks
            ])
            
            # Verify all tasks completed successfully
            assert len(results) == 3
            for result in results:
                assert result.montage_rows is not None
                assert len(result.montage_rows) == 3
                assert result.docx_path is not None
            
            # Verify all tasks in database are completed
            for task_id, user in tasks:
                task = db_session.query(ProcessingTask).filter(
                    ProcessingTask.id == task_id
                ).first()
                assert task is not None
                # Note: Task status would be updated by the actual task queue processor
    
    def test_api_error_handling(self, authenticated_client: TestClient, test_user: User):
        """Test API error handling for various scenarios."""
        
        # Test invalid task ID format
        response = authenticated_client.get("/api/v1/status/invalid-uuid")
        assert response.status_code == 422  # Validation error
        
        # Test non-existent task
        from uuid import uuid4
        fake_task_id = uuid4()
        response = authenticated_client.get(f"/api/v1/status/{fake_task_id}")
        assert response.status_code == 404
        
        # Test unauthorized access (no auth header)
        client = TestClient(app)
        response = client.get(f"/api/v1/status/{fake_task_id}")
        assert response.status_code == 401
        
        # Test invalid file upload
        response = authenticated_client.post(
            "/api/v1/upload",
            files={"file": ("test.txt", b"not a video", "text/plain")},
            data={"title": "Invalid File"}
        )
        assert response.status_code == 400
        
        # Test missing required fields
        with tempfile.NamedTemporaryFile(suffix='.mp4') as f:
            f.write(b'\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom')
            f.flush()
            
            with open(f.name, 'rb') as video_file:
                response = authenticated_client.post(
                    "/api/v1/upload",
                    files={"file": ("test.mp4", video_file, "video/mp4")},
                    data={}  # Missing required title
                )
                assert response.status_code == 422  # Validation error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])