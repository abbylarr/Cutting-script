"""
Integration tests for pipeline orchestration system.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from pathlib import Path
from datetime import datetime

from app.services.pipeline_orchestrator import (
    PipelineOrchestrator, ProcessingContext, ProcessingError
)
from app.services.task_queue import TaskProgressTracker, TaskInfo, TaskPriority
from app.services.video_processor import VideoMetadata, Scene, ValidationResult
from app.schemas.processing_task import ProcessingStep, TaskStatus


class TestProcessingContext:
    """Test cases for ProcessingContext class."""
    
    def test_context_initialization(self):
        """Test context initialization with required fields."""
        context = ProcessingContext(
            task_id="test-task",
            user_id="test-user",
            video_path="/path/to/video.mp4"
        )
        
        assert context.task_id == "test-task"
        assert context.user_id == "test-user"
        assert context.video_path == "/path/to/video.mp4"
        assert context.use_srt is False
        assert context.partial_results == {}
    
    def test_partial_results_management(self):
        """Test saving and retrieving partial results."""
        context = ProcessingContext(
            task_id="test-task",
            user_id="test-user",
            video_path="/path/to/video.mp4"
        )
        
        # Save partial result
        test_result = {"test": "data"}
        context.save_partial_result("validation", test_result)
        
        # Retrieve partial result
        retrieved = context.get_partial_result("validation")
        assert retrieved == test_result
        
        # Non-existent result
        assert context.get_partial_result("nonexistent") is None


class TestPipelineOrchestrator:
    """Test cases for PipelineOrchestrator class."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked services."""
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
        ):
            return PipelineOrchestrator()
    
    @pytest.fixture
    def mock_progress_tracker(self):
        """Create mock progress tracker."""
        task_info = TaskInfo(
            task_id="test-task",
            user_id="test-user",
            priority=TaskPriority.NORMAL,
            created_at=datetime.utcnow()
        )
        
        tracker = TaskProgressTracker("test-task", task_info)
        tracker.set_total_steps = AsyncMock()
        tracker.start_step = AsyncMock()
        tracker.complete_step = AsyncMock()
        tracker.update_progress = AsyncMock()
        tracker.check_cancellation = MagicMock()
        
        return tracker
    
    @pytest.fixture
    def sample_context(self):
        """Create sample processing context."""
        return ProcessingContext(
            task_id="test-task",
            user_id="test-user",
            video_path="/path/to/test_video.mp4"
        )
    
    @pytest.fixture
    def mock_cache_manager(self):
        """Mock cache manager."""
        with patch('app.services.pipeline_orchestrator.cache_manager') as mock:
            mock.redis_client.get_client = AsyncMock()
            mock_client = AsyncMock()
            mock.redis_client.get_client.return_value = mock_client
            mock_client.setex = AsyncMock()
            yield mock
    
    def test_get_steps_for_context_normal_mode(self, orchestrator):
        """Test step selection for normal processing mode."""
        context = ProcessingContext(
            task_id="test-task",
            user_id="test-user",
            video_path="/path/to/video.mp4",
            use_srt=False
        )
        
        steps = orchestrator._get_steps_for_context(context)
        step_names = [step[0] for step in steps]
        
        # Should include all steps
        assert ProcessingStep.TRANSCRIPTION in step_names
        assert ProcessingStep.DIARIZATION in step_names
        assert ProcessingStep.TEXT_PROCESSING in step_names
        assert len(steps) == len(orchestrator.processing_steps)
    
    def test_get_steps_for_context_srt_mode(self, orchestrator):
        """Test step selection for SRT mode."""
        context = ProcessingContext(
            task_id="test-task",
            user_id="test-user",
            video_path="/path/to/video.mp4",
            use_srt=True
        )
        
        steps = orchestrator._get_steps_for_context(context)
        step_names = [step[0] for step in steps]
        
        # Should skip transcription, diarization, and text processing
        assert ProcessingStep.TRANSCRIPTION not in step_names
        assert ProcessingStep.DIARIZATION not in step_names
        assert ProcessingStep.TEXT_PROCESSING not in step_names
        
        # Should include other steps
        assert ProcessingStep.VALIDATION in step_names
        assert ProcessingStep.SCENE_DETECTION in step_names
    
    def test_calculate_eta(self, orchestrator):
        """Test ETA calculation based on video duration."""
        context = ProcessingContext(
            task_id="test-task",
            user_id="test-user",
            video_path="/path/to/video.mp4"
        )
        
        # No metadata - should return None
        eta = orchestrator._calculate_eta(context, ProcessingStep.VALIDATION)
        assert eta is None
        
        # With metadata
        context.video_metadata = VideoMetadata(
            duration=120.0,  # 2 minutes
            fps=25.0,
            width=1920,
            height=1080,
            codec="h264",
            format="mp4"
        )
        
        eta = orchestrator._calculate_eta(context, ProcessingStep.VALIDATION)
        assert eta is not None
        assert eta >= 10  # Minimum ETA
        
        # Transcription should have higher ETA
        transcription_eta = orchestrator._calculate_eta(context, ProcessingStep.TRANSCRIPTION)
        validation_eta = orchestrator._calculate_eta(context, ProcessingStep.VALIDATION)
        assert transcription_eta > validation_eta
    
    async def test_step_validate_video_success(self, orchestrator, sample_context, mock_progress_tracker):
        """Test successful video validation step."""
        # Mock validation service
        mock_metadata = VideoMetadata(
            duration=60.0, fps=25.0, width=1920, height=1080,
            codec="h264", format="mp4"
        )
        
        orchestrator.video_validator.validate_video = AsyncMock(return_value=ValidationResult(
            is_valid=True,
            metadata=mock_metadata
        ))
        orchestrator.video_validator.check_video_integrity = AsyncMock(return_value=(True, None))
        
        # Mock file existence
        with patch('pathlib.Path.exists', return_value=True):
            result_context = await orchestrator._step_validate_video(sample_context, mock_progress_tracker)
        
        assert result_context.video_metadata == mock_metadata
        mock_progress_tracker.update_progress.assert_called()
    
    async def test_step_validate_video_file_not_found(self, orchestrator, sample_context, mock_progress_tracker):
        """Test video validation with missing file."""
        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(ProcessingError, match="Video file not found"):
                await orchestrator._step_validate_video(sample_context, mock_progress_tracker)
    
    async def test_step_validate_video_invalid_video(self, orchestrator, sample_context, mock_progress_tracker):
        """Test video validation with invalid video."""
        orchestrator.video_validator.validate_video = AsyncMock(return_value=ValidationResult(
            is_valid=False,
            error="Unsupported format"
        ))
        
        with patch('pathlib.Path.exists', return_value=True):
            with pytest.raises(ProcessingError, match="Video validation failed"):
                await orchestrator._step_validate_video(sample_context, mock_progress_tracker)
    
    async def test_step_extract_audio_success(self, orchestrator, sample_context, mock_progress_tracker):
        """Test successful audio extraction step."""
        orchestrator.audio_extractor.extract_audio = AsyncMock(return_value="/path/to/audio.wav")
        
        result_context = await orchestrator._step_extract_audio(sample_context, mock_progress_tracker)
        
        assert result_context.audio_path == "/path/to/audio.wav"
        orchestrator.audio_extractor.extract_audio.assert_called_once()
    
    async def test_step_extract_audio_srt_mode(self, orchestrator, mock_progress_tracker):
        """Test audio extraction step in SRT mode (should skip)."""
        context = ProcessingContext(
            task_id="test-task",
            user_id="test-user",
            video_path="/path/to/video.mp4",
            use_srt=True
        )
        
        result_context = await orchestrator._step_extract_audio(context, mock_progress_tracker)
        
        assert result_context.audio_path is None
        orchestrator.audio_extractor.extract_audio.assert_not_called()
    
    async def test_step_detect_scenes_success(self, orchestrator, sample_context, mock_progress_tracker):
        """Test successful scene detection step."""
        mock_scenes = [
            Scene(start_time=0.0, end_time=10.0, duration=10.0, scene_number=1),
            Scene(start_time=10.0, end_time=20.0, duration=10.0, scene_number=2)
        ]
        
        orchestrator.scene_detector.detect_scenes_with_fallback = AsyncMock(return_value=mock_scenes)
        
        result_context = await orchestrator._step_detect_scenes(sample_context, mock_progress_tracker)
        
        assert result_context.scenes == mock_scenes
        assert len(result_context.scenes) == 2
    
    async def test_step_detect_scenes_no_scenes(self, orchestrator, sample_context, mock_progress_tracker):
        """Test scene detection with no scenes found."""
        orchestrator.scene_detector.detect_scenes_with_fallback = AsyncMock(return_value=[])
        
        with pytest.raises(ProcessingError, match="No scenes detected"):
            await orchestrator._step_detect_scenes(sample_context, mock_progress_tracker)
    
    async def test_step_transcribe_audio_success(self, orchestrator, sample_context, mock_progress_tracker):
        """Test successful audio transcription step."""
        sample_context.audio_path = "/path/to/audio.wav"
        mock_transcription = {"text": "Test transcription", "segments": []}
        
        orchestrator.transcription_service.transcribe_audio = AsyncMock(return_value=mock_transcription)
        
        result_context = await orchestrator._step_transcribe_audio(sample_context, mock_progress_tracker)
        
        assert result_context.transcription_result == mock_transcription
    
    async def test_step_transcribe_audio_srt_mode(self, orchestrator, mock_progress_tracker):
        """Test transcription step in SRT mode (should skip)."""
        context = ProcessingContext(
            task_id="test-task",
            user_id="test-user",
            video_path="/path/to/video.mp4",
            use_srt=True
        )
        
        result_context = await orchestrator._step_transcribe_audio(context, mock_progress_tracker)
        
        assert result_context.transcription_result is None
        orchestrator.transcription_service.transcribe_audio.assert_not_called()
    
    async def test_step_transcribe_audio_no_audio(self, orchestrator, sample_context, mock_progress_tracker):
        """Test transcription step without audio file."""
        # audio_path is None by default
        
        with pytest.raises(ProcessingError, match="Audio file not available"):
            await orchestrator._step_transcribe_audio(sample_context, mock_progress_tracker)
    
    async def test_step_diarize_speakers_success(self, orchestrator, sample_context, mock_progress_tracker):
        """Test successful speaker diarization step."""
        sample_context.audio_path = "/path/to/audio.wav"
        mock_diarization = {"speakers": ["SPEAKER_00", "SPEAKER_01"]}
        
        orchestrator.diarization_service.diarize_audio = AsyncMock(return_value=mock_diarization)
        
        result_context = await orchestrator._step_diarize_speakers(sample_context, mock_progress_tracker)
        
        assert result_context.diarization_result == mock_diarization
    
    async def test_step_diarize_speakers_failure_recoverable(self, orchestrator, sample_context, mock_progress_tracker):
        """Test diarization step with recoverable failure."""
        sample_context.audio_path = "/path/to/audio.wav"
        
        orchestrator.diarization_service.diarize_audio = AsyncMock(side_effect=Exception("HF_TOKEN not available"))
        
        # Should not raise exception, but continue without diarization
        result_context = await orchestrator._step_diarize_speakers(sample_context, mock_progress_tracker)
        
        assert result_context.diarization_result is None
    
    async def test_step_process_text_from_transcription(self, orchestrator, sample_context, mock_progress_tracker):
        """Test text processing from transcription result."""
        sample_context.transcription_result = {"text": "Raw transcription text"}
        
        orchestrator.text_processor.process_text = AsyncMock(return_value="Processed text")
        
        result_context = await orchestrator._step_process_text(sample_context, mock_progress_tracker)
        
        assert result_context.processed_text == "Processed text"
        orchestrator.text_processor.process_text.assert_called_once_with("Raw transcription text")
    
    async def test_step_process_text_from_srt(self, orchestrator, mock_progress_tracker):
        """Test text processing from SRT file."""
        context = ProcessingContext(
            task_id="test-task",
            user_id="test-user",
            video_path="/path/to/video.mp4",
            srt_path="/path/to/subtitles.srt",
            use_srt=True
        )
        
        # Mock SRT file content
        srt_content = """1
00:00:01,000 --> 00:00:03,000
Hello world

2
00:00:04,000 --> 00:00:06,000
This is a test"""
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=srt_content)):
                result_context = await orchestrator._step_process_text(context, mock_progress_tracker)
        
        assert "Hello world This is a test" in result_context.processed_text
    
    async def test_step_process_text_srt_file_not_found(self, orchestrator, mock_progress_tracker):
        """Test text processing with missing SRT file."""
        context = ProcessingContext(
            task_id="test-task",
            user_id="test-user",
            video_path="/path/to/video.mp4",
            srt_path="/path/to/missing.srt",
            use_srt=True
        )
        
        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(ProcessingError, match="SRT file not found"):
                await orchestrator._step_process_text(context, mock_progress_tracker)
    
    async def test_step_analyze_frames_success(self, orchestrator, sample_context, mock_progress_tracker):
        """Test successful frame analysis step."""
        # Setup context with scenes
        sample_context.scenes = [
            Scene(start_time=0.0, end_time=10.0, duration=10.0, scene_number=1)
        ]
        sample_context.processed_text = "Test dialogue"
        
        mock_keyframes = [{"scene": 1, "frames": ["frame1.jpg", "frame2.jpg"]}]
        mock_analysis = [{"scene": 1, "shot_type": "Средний", "description": "Test scene"}]
        
        orchestrator.keyframe_extractor.extract_keyframes_for_scenes = AsyncMock(return_value=mock_keyframes)
        orchestrator.visual_analyzer.analyze_scenes = AsyncMock(return_value=mock_analysis)
        
        result_context = await orchestrator._step_analyze_frames(sample_context, mock_progress_tracker)
        
        assert result_context.keyframes == mock_keyframes
        assert result_context.visual_analysis == mock_analysis
    
    async def test_step_analyze_frames_no_scenes(self, orchestrator, sample_context, mock_progress_tracker):
        """Test frame analysis step without scenes."""
        # scenes is None by default
        
        with pytest.raises(ProcessingError, match="No scenes available"):
            await orchestrator._step_analyze_frames(sample_context, mock_progress_tracker)
    
    async def test_step_generate_montage_success(self, orchestrator, sample_context, mock_progress_tracker):
        """Test successful montage generation step."""
        # Setup context
        sample_context.scenes = [Scene(start_time=0.0, end_time=10.0, duration=10.0, scene_number=1)]
        sample_context.processed_text = "Test dialogue"
        sample_context.audio_path = "/path/to/audio.wav"
        
        mock_dialogue_mapping = [{"scene": 1, "dialogue": "Test dialogue"}]
        mock_music_analysis = [{"scene": 1, "has_music": False}]
        mock_montage_rows = [{"number": 1, "start_timecode": "01:00:00:00"}]
        
        orchestrator.dialogue_mapper.map_dialogue_to_scenes = AsyncMock(return_value=mock_dialogue_mapping)
        orchestrator.music_detector.detect_music_in_scenes = AsyncMock(return_value=mock_music_analysis)
        orchestrator.montage_service.generate_montage_table = AsyncMock(return_value=mock_montage_rows)
        
        result_context = await orchestrator._step_generate_montage(sample_context, mock_progress_tracker)
        
        assert result_context.dialogue_mapping == mock_dialogue_mapping
        assert result_context.music_analysis == mock_music_analysis
        assert result_context.montage_rows == mock_montage_rows
    
    async def test_step_generate_document_success(self, orchestrator, sample_context, mock_progress_tracker):
        """Test successful document generation step."""
        sample_context.montage_rows = [{"number": 1, "start_timecode": "01:00:00:00"}]
        sample_context.video_metadata = VideoMetadata(
            duration=60.0, fps=25.0, width=1920, height=1080,
            codec="h264", format="mp4"
        )
        
        orchestrator.docx_generator.generate_document = AsyncMock(return_value="/path/to/document.docx")
        
        result_context = await orchestrator._step_generate_document(sample_context, mock_progress_tracker)
        
        assert result_context.docx_path == "/path/to/document.docx"
    
    async def test_step_generate_document_no_montage_data(self, orchestrator, sample_context, mock_progress_tracker):
        """Test document generation without montage data."""
        # montage_rows is None by default
        
        with pytest.raises(ProcessingError, match="No montage data available"):
            await orchestrator._step_generate_document(sample_context, mock_progress_tracker)
    
    async def test_execute_step_with_recovery_success(self, orchestrator, sample_context, mock_progress_tracker):
        """Test successful step execution with recovery mechanism."""
        async def mock_step_func(context, tracker):
            context.test_result = "success"
            return context
        
        result_context = await orchestrator._execute_step_with_recovery(
            mock_step_func, sample_context, mock_progress_tracker
        )
        
        assert result_context.test_result == "success"
    
    async def test_execute_step_with_recovery_retry_success(self, orchestrator, sample_context, mock_progress_tracker):
        """Test step execution with retry on failure."""
        call_count = 0
        
        async def mock_step_func(context, tracker):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary failure")
            context.test_result = "success_after_retry"
            return context
        
        result_context = await orchestrator._execute_step_with_recovery(
            mock_step_func, sample_context, mock_progress_tracker
        )
        
        assert result_context.test_result == "success_after_retry"
        assert call_count == 2
    
    async def test_execute_step_with_recovery_max_retries(self, orchestrator, sample_context, mock_progress_tracker):
        """Test step execution failure after max retries."""
        async def mock_step_func(context, tracker):
            raise Exception("Persistent failure")
        
        with pytest.raises(ProcessingError, match="Step failed after 3 attempts"):
            await orchestrator._execute_step_with_recovery(
                mock_step_func, sample_context, mock_progress_tracker
            )
    
    async def test_save_partial_results(self, orchestrator, sample_context, mock_cache_manager):
        """Test saving partial results to Redis."""
        # Setup context with metadata
        sample_context.video_metadata = VideoMetadata(
            duration=60.0, fps=25.0, width=1920, height=1080,
            codec="h264", format="mp4"
        )
        
        await orchestrator._save_partial_results(sample_context, ProcessingStep.VALIDATION)
        
        # Verify Redis call was made
        mock_client = await mock_cache_manager.redis_client.get_client()
        mock_client.setex.assert_called_once()
    
    async def test_save_error_context(self, orchestrator, sample_context, mock_cache_manager):
        """Test saving error context for debugging."""
        test_error = Exception("Test error")
        
        await orchestrator._save_error_context(sample_context, test_error)
        
        # Verify Redis call was made
        mock_client = await mock_cache_manager.redis_client.get_client()
        mock_client.setex.assert_called_once()
        
        # Check that error data was saved
        call_args = mock_client.setex.call_args
        assert "error_context:test-task" in call_args[0][0]
    
    async def test_parse_srt_file_success(self, orchestrator):
        """Test successful SRT file parsing."""
        srt_content = """1
00:00:01,000 --> 00:00:03,000
Hello world

2
00:00:04,000 --> 00:00:06,000
This is a test

3
00:00:07,000 --> 00:00:09,000
Final line"""
        
        with patch('builtins.open', mock_open(read_data=srt_content)):
            result = await orchestrator._parse_srt_file("/path/to/test.srt")
        
        assert "Hello world" in result
        assert "This is a test" in result
        assert "Final line" in result
        # Should not contain timestamps or sequence numbers
        assert "00:00:01,000" not in result
        assert "-->" not in result
    
    async def test_parse_srt_file_failure(self, orchestrator):
        """Test SRT file parsing failure."""
        with patch('builtins.open', side_effect=FileNotFoundError("File not found")):
            with pytest.raises(ProcessingError, match="Failed to parse SRT file"):
                await orchestrator._parse_srt_file("/path/to/missing.srt")


@pytest.mark.asyncio
async def test_integration_full_pipeline_normal_mode():
    """Integration test for complete pipeline execution in normal mode."""
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
        DOCXGeneratorService=MagicMock,
        cache_manager=MagicMock()
    ) as mocks:
        
        orchestrator = PipelineOrchestrator()
        
        # Setup all mocks for successful execution
        mocks['VideoValidationService'].return_value.validate_video = AsyncMock(
            return_value=ValidationResult(
                is_valid=True,
                metadata=VideoMetadata(duration=60.0, fps=25.0, width=1920, height=1080, codec="h264", format="mp4")
            )
        )
        mocks['VideoValidationService'].return_value.check_video_integrity = AsyncMock(return_value=(True, None))
        mocks['AudioExtractionService'].return_value.extract_audio = AsyncMock(return_value="/path/to/audio.wav")
        mocks['SceneDetectionService'].return_value.detect_scenes_with_fallback = AsyncMock(
            return_value=[Scene(start_time=0.0, end_time=10.0, duration=10.0, scene_number=1)]
        )
        mocks['TranscriptionService'].return_value.transcribe_audio = AsyncMock(
            return_value={"text": "Test transcription"}
        )
        mocks['SpeakerDiarizationService'].return_value.diarize_audio = AsyncMock(
            return_value={"speakers": ["SPEAKER_00"]}
        )
        mocks['TextProcessingService'].return_value.process_text = AsyncMock(return_value="Processed text")
        mocks['KeyframeExtractionService'].return_value.extract_keyframes_from_scenes = AsyncMock(
            return_value=[{"scene": 1, "frames": ["frame1.jpg"]}]
        )
        mocks['GPTVisualAnalysisService'].return_value.analyze_scenes = AsyncMock(
            return_value=[{"scene": 1, "shot_type": "Средний"}]
        )
        mocks['DialogueSceneMappingService'].return_value.map_dialogue_to_scenes = AsyncMock(
            return_value=[{"scene": 1, "dialogue": "Test"}]
        )
        mocks['MusicDetectionService'].return_value.detect_music_in_scenes = AsyncMock(
            return_value=[{"scene": 1, "has_music": False}]
        )
        mocks['MontageTableService'].return_value.generate_montage_table = AsyncMock(
            return_value=[{"number": 1, "start_timecode": "01:00:00:00"}]
        )
        mocks['DocumentGeneratorService'].return_value.generate_document = AsyncMock(
            return_value="/path/to/document.docx"
        )
        
        # Mock cache manager
        mocks['cache_manager'].redis_client.get_client = AsyncMock()
        mock_client = AsyncMock()
        mocks['cache_manager'].redis_client.get_client.return_value = mock_client
        mock_client.setex = AsyncMock()
        
        # Create context and progress tracker
        context = ProcessingContext(
            task_id="integration-test",
            user_id="test-user",
            video_path="/path/to/test_video.mp4"
        )
        
        task_info = TaskInfo(
            task_id="integration-test",
            user_id="test-user",
            priority=TaskPriority.NORMAL,
            created_at=datetime.utcnow()
        )
        
        progress_tracker = TaskProgressTracker("integration-test", task_info)
        progress_tracker.set_total_steps = AsyncMock()
        progress_tracker.start_step = AsyncMock()
        progress_tracker.complete_step = AsyncMock()
        progress_tracker.update_progress = AsyncMock()
        progress_tracker.check_cancellation = MagicMock()
        
        # Mock file existence
        with patch('pathlib.Path.exists', return_value=True):
            # Execute pipeline
            result_context = await orchestrator.process_video(progress_tracker, context)
        
        # Verify all steps were executed
        assert result_context.video_metadata is not None
        assert result_context.audio_path == "/path/to/audio.wav"
        assert result_context.scenes is not None
        assert result_context.transcription_result is not None
        assert result_context.processed_text == "Processed text"
        assert result_context.montage_rows is not None
        assert result_context.docx_path == "/path/to/document.docx"
        
        # Verify progress tracking calls
        progress_tracker.set_total_steps.assert_called_once()
        assert progress_tracker.start_step.call_count == len(orchestrator.processing_steps)
        assert progress_tracker.complete_step.call_count == len(orchestrator.processing_steps)


@pytest.mark.asyncio
async def test_integration_full_pipeline_srt_mode():
    """Integration test for complete pipeline execution in SRT mode."""
    with patch.multiple(
        'app.services.pipeline_orchestrator',
        VideoValidationService=MagicMock,
        AudioExtractionService=MagicMock,
        SceneDetectionService=MagicMock,
        KeyframeExtractionService=MagicMock,
        GPTVisualAnalysisService=MagicMock,
        DialogueSceneMappingService=MagicMock,
        MusicDetectionService=MagicMock,
        MontageTableAssemblyService=MagicMock,
        DOCXGeneratorService=MagicMock,
        cache_manager=MagicMock()
    ) as mocks:
        
        orchestrator = PipelineOrchestrator()
        
        # Setup mocks for SRT mode (skip transcription services)
        mocks['VideoValidationService'].return_value.validate_video = AsyncMock(
            return_value=ValidationResult(
                is_valid=True,
                metadata=VideoMetadata(duration=60.0, fps=25.0, width=1920, height=1080, codec="h264", format="mp4")
            )
        )
        mocks['VideoValidationService'].return_value.check_video_integrity = AsyncMock(return_value=(True, None))
        mocks['SceneDetectionService'].return_value.detect_scenes_with_fallback = AsyncMock(
            return_value=[Scene(start_time=0.0, end_time=10.0, duration=10.0, scene_number=1)]
        )
        mocks['KeyframeExtractionService'].return_value.extract_keyframes_from_scenes = AsyncMock(
            return_value=[{"scene": 1, "frames": ["frame1.jpg"]}]
        )
        mocks['GPTVisualAnalysisService'].return_value.analyze_scenes = AsyncMock(
            return_value=[{"scene": 1, "shot_type": "Средний"}]
        )
        mocks['DialogueSceneMappingService'].return_value.map_dialogue_to_scenes = AsyncMock(
            return_value=[{"scene": 1, "dialogue": "SRT text"}]
        )
        mocks['MusicDetectionService'].return_value.detect_music_in_scenes = AsyncMock(
            return_value=[{"scene": 1, "has_music": False}]
        )
        mocks['MontageTableService'].return_value.generate_montage_table = AsyncMock(
            return_value=[{"number": 1, "start_timecode": "01:00:00:00"}]
        )
        mocks['DocumentGeneratorService'].return_value.generate_document = AsyncMock(
            return_value="/path/to/document.docx"
        )
        
        # Mock cache manager
        mocks['cache_manager'].redis_client.get_client = AsyncMock()
        mock_client = AsyncMock()
        mocks['cache_manager'].redis_client.get_client.return_value = mock_client
        mock_client.setex = AsyncMock()
        
        # Create SRT mode context
        context = ProcessingContext(
            task_id="srt-test",
            user_id="test-user",
            video_path="/path/to/test_video.mp4",
            srt_path="/path/to/subtitles.srt",
            use_srt=True
        )
        
        task_info = TaskInfo(
            task_id="srt-test",
            user_id="test-user",
            priority=TaskPriority.NORMAL,
            created_at=datetime.utcnow()
        )
        
        progress_tracker = TaskProgressTracker("srt-test", task_info)
        progress_tracker.set_total_steps = AsyncMock()
        progress_tracker.start_step = AsyncMock()
        progress_tracker.complete_step = AsyncMock()
        progress_tracker.update_progress = AsyncMock()
        progress_tracker.check_cancellation = MagicMock()
        
        # Mock SRT file
        srt_content = "1\n00:00:01,000 --> 00:00:03,000\nTest SRT content"
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=srt_content)):
                # Execute pipeline
                result_context = await orchestrator.process_video(progress_tracker, context)
        
        # Verify SRT mode execution
        assert result_context.video_metadata is not None
        assert result_context.audio_path is None  # Should be None in SRT mode
        assert result_context.transcription_result is None  # Should be None in SRT mode
        assert result_context.processed_text is not None  # Should have SRT text
        assert result_context.montage_rows is not None
        assert result_context.docx_path == "/path/to/document.docx"
        
        # Verify fewer steps were executed (no transcription/diarization)
        expected_steps = len([s for s in orchestrator.processing_steps 
                            if s[0] not in [ProcessingStep.TRANSCRIPTION, ProcessingStep.DIARIZATION, ProcessingStep.TEXT_PROCESSING]])
        progress_tracker.set_total_steps.assert_called_once_with(expected_steps)