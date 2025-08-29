"""
Processing pipeline orchestration service.
Coordinates all video processing steps with progress tracking and error recovery.
"""
import asyncio
import logging
import traceback
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
import json

from app.services.task_queue import TaskProgressTracker
from app.services.video_processor import (
    VideoValidationService, AudioExtractionService, SceneDetectionService,
    VideoMetadata, Scene, ValidationResult
)
from app.services.transcription import TranscriptionService
from app.services.diarization import SpeakerDiarizationService
from app.services.text_processing import TextProcessingService
from app.services.keyframe_extraction import KeyframeExtractionService
from app.services.gpt_visual_analysis import GPTVisualAnalysisService
from app.services.dialogue_mapping import DialogueSceneMappingService
from app.services.music_detection import MusicDetectionService
from app.services.montage_table import MontageTableAssemblyService
from app.services.docx_generator import DOCXGeneratorService
from app.schemas.processing_task import ProcessingStep
from app.core.redis import cache_manager


logger = logging.getLogger(__name__)


@dataclass
class ProcessingContext:
    """Context object that holds all processing data and intermediate results."""
    task_id: str
    user_id: str
    video_path: str
    srt_path: Optional[str] = None
    use_srt: bool = False
    
    # Processing results
    video_metadata: Optional[VideoMetadata] = None
    audio_path: Optional[str] = None
    scenes: Optional[List[Scene]] = None
    transcription_result: Optional[Dict] = None
    diarization_result: Optional[Dict] = None
    processed_text: Optional[str] = None
    keyframes: Optional[List[Dict]] = None
    visual_analysis: Optional[List[Dict]] = None
    dialogue_mapping: Optional[List[Dict]] = None
    music_analysis: Optional[List[Dict]] = None
    montage_rows: Optional[List[Dict]] = None
    docx_path: Optional[str] = None
    
    # Processing settings
    timecode_start: str = "01:00:00:00"
    standard: str = "ГФФ"
    
    # Error recovery
    partial_results: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.partial_results is None:
            self.partial_results = {}
    
    def save_partial_result(self, step: str, result: Any):
        """Save partial result for error recovery."""
        self.partial_results[step] = result
    
    def get_partial_result(self, step: str) -> Optional[Any]:
        """Get saved partial result."""
        return self.partial_results.get(step)


class ProcessingError(Exception):
    """Base exception for processing errors."""
    def __init__(self, message: str, step: Optional[ProcessingStep] = None, recoverable: bool = False):
        super().__init__(message)
        self.step = step
        self.recoverable = recoverable


class PipelineOrchestrator:
    """
    Orchestrates the complete video processing pipeline.
    Manages step-by-step execution, progress tracking, and error recovery.
    """
    
    def __init__(self):
        # Initialize all services
        self.video_validator = VideoValidationService()
        self.audio_extractor = AudioExtractionService()
        self.scene_detector = SceneDetectionService()
        self.transcription_service = TranscriptionService()
        self.diarization_service = SpeakerDiarizationService()
        self.text_processor = TextProcessingService()
        self.keyframe_extractor = KeyframeExtractionService()
        self.visual_analyzer = GPTVisualAnalysisService()
        self.dialogue_mapper = DialogueSceneMappingService()
        self.music_detector = MusicDetectionService()
        self.montage_service = MontageTableAssemblyService()
        self.docx_generator = DOCXGeneratorService()
        
        # Define processing steps
        self.processing_steps = [
            (ProcessingStep.VALIDATION, self._step_validate_video),
            (ProcessingStep.AUDIO_EXTRACTION, self._step_extract_audio),
            (ProcessingStep.SCENE_DETECTION, self._step_detect_scenes),
            (ProcessingStep.TRANSCRIPTION, self._step_transcribe_audio),
            (ProcessingStep.DIARIZATION, self._step_diarize_speakers),
            (ProcessingStep.TEXT_PROCESSING, self._step_process_text),
            (ProcessingStep.FRAME_ANALYSIS, self._step_analyze_frames),
            (ProcessingStep.MONTAGE_GENERATION, self._step_generate_montage),
            (ProcessingStep.DOCUMENT_GENERATION, self._step_generate_document)
        ]
        
        # Step descriptions for progress tracking
        self.step_descriptions = {
            ProcessingStep.VALIDATION: "Проверка видеофайла и извлечение метаданных",
            ProcessingStep.AUDIO_EXTRACTION: "Извлечение аудиодорожки из видео",
            ProcessingStep.SCENE_DETECTION: "Определение границ сцен в видео",
            ProcessingStep.TRANSCRIPTION: "Транскрипция речи с помощью AI",
            ProcessingStep.DIARIZATION: "Определение спикеров в аудио",
            ProcessingStep.TEXT_PROCESSING: "Обработка и коррекция текста",
            ProcessingStep.FRAME_ANALYSIS: "Анализ ключевых кадров с помощью AI",
            ProcessingStep.MONTAGE_GENERATION: "Создание монтажной таблицы",
            ProcessingStep.DOCUMENT_GENERATION: "Генерация итогового документа"
        }
        
        # ETA estimates per step (in seconds, for 1 minute of video)
        self.step_eta_base = {
            ProcessingStep.VALIDATION: 5,
            ProcessingStep.AUDIO_EXTRACTION: 10,
            ProcessingStep.SCENE_DETECTION: 30,
            ProcessingStep.TRANSCRIPTION: 60,
            ProcessingStep.DIARIZATION: 45,
            ProcessingStep.TEXT_PROCESSING: 15,
            ProcessingStep.FRAME_ANALYSIS: 90,
            ProcessingStep.MONTAGE_GENERATION: 10,
            ProcessingStep.DOCUMENT_GENERATION: 5
        }
    
    async def process_video(self, progress_tracker: TaskProgressTracker, context: ProcessingContext) -> ProcessingContext:
        """
        Execute the complete video processing pipeline.
        
        Args:
            progress_tracker: Progress tracking helper
            context: Processing context with input data
            
        Returns:
            Updated context with processing results
        """
        logger.info(f"Starting video processing pipeline for task {context.task_id}")
        
        # Set total steps for progress calculation
        steps_to_execute = self._get_steps_for_context(context)
        await progress_tracker.set_total_steps(len(steps_to_execute))
        
        try:
            # Execute each processing step
            for step, step_func in steps_to_execute:
                # Check for cancellation
                progress_tracker.check_cancellation()
                
                # Calculate ETA
                eta_seconds = self._calculate_eta(context, step)
                
                # Start step
                await progress_tracker.start_step(
                    step, 
                    self.step_descriptions.get(step, step.value),
                    eta_seconds
                )
                
                # Execute step with error recovery
                try:
                    context = await self._execute_step_with_recovery(step_func, context, progress_tracker)
                    
                    # Save partial result for recovery
                    await self._save_partial_results(context, step)
                    
                except ProcessingError as e:
                    if e.recoverable:
                        logger.warning(f"Recoverable error in step {step.value}: {e}")
                        # Try to continue with partial results
                        context = await self._recover_from_error(context, step, e)
                    else:
                        logger.error(f"Unrecoverable error in step {step.value}: {e}")
                        raise
                
                # Complete step
                await progress_tracker.complete_step()
                
                logger.info(f"Completed step {step.value} for task {context.task_id}")
            
            logger.info(f"Video processing pipeline completed for task {context.task_id}")
            return context
            
        except Exception as e:
            logger.error(f"Pipeline execution failed for task {context.task_id}: {e}")
            logger.error(traceback.format_exc())
            
            # Save partial results for debugging
            await self._save_error_context(context, e)
            
            raise ProcessingError(f"Pipeline execution failed: {str(e)}")
    
    def _get_steps_for_context(self, context: ProcessingContext) -> List[tuple]:
        """Get the list of steps to execute based on context."""
        if context.use_srt:
            # Skip transcription and diarization when using SRT
            return [
                (step, func) for step, func in self.processing_steps
                if step not in [ProcessingStep.TRANSCRIPTION, ProcessingStep.DIARIZATION, ProcessingStep.TEXT_PROCESSING]
            ]
        else:
            return self.processing_steps
    
    def _calculate_eta(self, context: ProcessingContext, current_step: ProcessingStep) -> Optional[int]:
        """Calculate ETA for current step based on video duration."""
        if not context.video_metadata:
            return None
        
        video_duration_minutes = context.video_metadata.duration / 60
        base_eta = self.step_eta_base.get(current_step, 30)
        
        # Scale ETA based on video duration
        eta_seconds = int(base_eta * video_duration_minutes)
        
        # Add some variance for different video types
        if current_step == ProcessingStep.TRANSCRIPTION:
            # Transcription time varies more with audio complexity
            eta_seconds = int(eta_seconds * 1.5)
        elif current_step == ProcessingStep.FRAME_ANALYSIS:
            # Visual analysis depends on scene count
            if context.scenes:
                eta_seconds = int(len(context.scenes) * 10)  # ~10 seconds per scene
        
        return max(10, eta_seconds)  # Minimum 10 seconds
    
    async def _execute_step_with_recovery(
        self, 
        step_func: Callable, 
        context: ProcessingContext, 
        progress_tracker: TaskProgressTracker
    ) -> ProcessingContext:
        """Execute a step with retry logic and error recovery."""
        max_retries = 3
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                return await step_func(context, progress_tracker)
            
            except Exception as e:
                if attempt == max_retries - 1:
                    # Last attempt failed
                    raise ProcessingError(
                        f"Step failed after {max_retries} attempts: {str(e)}",
                        recoverable=False
                    )
                
                logger.warning(f"Step attempt {attempt + 1} failed: {e}, retrying in {retry_delay}s")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
        
        return context
    
    async def _recover_from_error(
        self, 
        context: ProcessingContext, 
        failed_step: ProcessingStep, 
        error: ProcessingError
    ) -> ProcessingContext:
        """Attempt to recover from a processing error."""
        logger.info(f"Attempting recovery from error in step {failed_step.value}")
        
        # Try to load partial results from previous successful run
        partial_result = context.get_partial_result(failed_step.value)
        if partial_result:
            logger.info(f"Using partial result for step {failed_step.value}")
            # Apply partial result to context
            await self._apply_partial_result(context, failed_step, partial_result)
        
        return context
    
    async def _apply_partial_result(
        self, 
        context: ProcessingContext, 
        step: ProcessingStep, 
        partial_result: Any
    ):
        """Apply a partial result to the processing context."""
        if step == ProcessingStep.TRANSCRIPTION:
            context.transcription_result = partial_result
        elif step == ProcessingStep.DIARIZATION:
            context.diarization_result = partial_result
        elif step == ProcessingStep.FRAME_ANALYSIS:
            context.visual_analysis = partial_result
        # Add more mappings as needed
    
    async def _save_partial_results(self, context: ProcessingContext, step: ProcessingStep):
        """Save partial results to Redis for error recovery."""
        try:
            result_data = None
            
            if step == ProcessingStep.VALIDATION and context.video_metadata:
                result_data = asdict(context.video_metadata)
            elif step == ProcessingStep.SCENE_DETECTION and context.scenes:
                result_data = [asdict(scene) for scene in context.scenes]
            elif step == ProcessingStep.TRANSCRIPTION and context.transcription_result:
                result_data = context.transcription_result
            elif step == ProcessingStep.DIARIZATION and context.diarization_result:
                result_data = context.diarization_result
            elif step == ProcessingStep.FRAME_ANALYSIS and context.visual_analysis:
                result_data = context.visual_analysis
            
            if result_data:
                key = f"partial_result:{context.task_id}:{step.value}"
                client = await cache_manager.redis_client.get_client()
                await client.setex(key, 3600, json.dumps(result_data, default=str))  # 1 hour TTL
                
        except Exception as e:
            logger.warning(f"Failed to save partial result for step {step.value}: {e}")
    
    async def _save_error_context(self, context: ProcessingContext, error: Exception):
        """Save error context for debugging."""
        try:
            error_data = {
                "task_id": context.task_id,
                "error": str(error),
                "traceback": traceback.format_exc(),
                "partial_results": context.partial_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            key = f"error_context:{context.task_id}"
            client = await cache_manager.redis_client.get_client()
            await client.setex(key, 86400, json.dumps(error_data, default=str))  # 24 hour TTL
            
        except Exception as e:
            logger.warning(f"Failed to save error context: {e}")
    
    # Processing step implementations
    
    async def _step_validate_video(self, context: ProcessingContext, progress_tracker: TaskProgressTracker) -> ProcessingContext:
        """Step 1: Validate video and extract metadata."""
        logger.info(f"Validating video: {context.video_path}")
        
        # Check if file exists
        if not Path(context.video_path).exists():
            raise ProcessingError(f"Video file not found: {context.video_path}")
        
        # Validate video
        validation_result = await self.video_validator.validate_video(context.video_path)
        
        if not validation_result.is_valid:
            raise ProcessingError(f"Video validation failed: {validation_result.error}")
        
        context.video_metadata = validation_result.metadata
        
        # Check video integrity
        await progress_tracker.update_progress(0.5, "Проверка целостности видео")
        is_valid, error_msg = await self.video_validator.check_video_integrity(context.video_path)
        
        if not is_valid:
            raise ProcessingError(f"Video integrity check failed: {error_msg}")
        
        await progress_tracker.update_progress(1.0, "Видео успешно проверено")
        return context
    
    async def _step_extract_audio(self, context: ProcessingContext, progress_tracker: TaskProgressTracker) -> ProcessingContext:
        """Step 2: Extract audio from video."""
        if context.use_srt:
            logger.info("Skipping audio extraction (using SRT mode)")
            return context
        
        logger.info(f"Extracting audio from: {context.video_path}")
        
        # Generate output path
        video_file = Path(context.video_path)
        audio_output = video_file.parent / f"{video_file.stem}_audio.wav"
        
        # Extract audio
        context.audio_path = await self.audio_extractor.extract_audio(
            context.video_path, 
            str(audio_output)
        )
        
        await progress_tracker.update_progress(1.0, "Аудио успешно извлечено")
        return context
    
    async def _step_detect_scenes(self, context: ProcessingContext, progress_tracker: TaskProgressTracker) -> ProcessingContext:
        """Step 3: Detect scenes in video."""
        logger.info(f"Detecting scenes in: {context.video_path}")
        
        # Detect scenes with fallback
        context.scenes = await self.scene_detector.detect_scenes_with_fallback(
            context.video_path,
            min_scene_length=2.0
        )
        
        if not context.scenes:
            raise ProcessingError("No scenes detected in video")
        
        logger.info(f"Detected {len(context.scenes)} scenes")
        await progress_tracker.update_progress(1.0, f"Обнаружено {len(context.scenes)} сцен")
        return context
    
    async def _step_transcribe_audio(self, context: ProcessingContext, progress_tracker: TaskProgressTracker) -> ProcessingContext:
        """Step 4: Transcribe audio to text."""
        if context.use_srt:
            logger.info("Skipping transcription (using SRT mode)")
            return context
        
        if not context.audio_path:
            raise ProcessingError("Audio file not available for transcription")
        
        logger.info(f"Transcribing audio: {context.audio_path}")
        
        # Transcribe audio
        context.transcription_result = await self.transcription_service.transcribe_audio(
            context.audio_path,
            language="ru"
        )
        
        await progress_tracker.update_progress(1.0, "Транскрипция завершена")
        return context
    
    async def _step_diarize_speakers(self, context: ProcessingContext, progress_tracker: TaskProgressTracker) -> ProcessingContext:
        """Step 5: Perform speaker diarization."""
        if context.use_srt or not context.audio_path:
            logger.info("Skipping diarization (using SRT mode or no audio)")
            return context
        
        logger.info(f"Performing speaker diarization: {context.audio_path}")
        
        try:
            # Attempt diarization (may fail if HF_TOKEN not available)
            context.diarization_result = await self.diarization_service.diarize_audio(context.audio_path)
        except Exception as e:
            logger.warning(f"Diarization failed, continuing without speaker info: {e}")
            # This is recoverable - we can continue without speaker diarization
            context.diarization_result = None
        
        await progress_tracker.update_progress(1.0, "Диаризация завершена")
        return context
    
    async def _step_process_text(self, context: ProcessingContext, progress_tracker: TaskProgressTracker) -> ProcessingContext:
        """Step 6: Process and clean up transcribed text."""
        if context.use_srt:
            # Load text from SRT file
            if not context.srt_path or not Path(context.srt_path).exists():
                raise ProcessingError("SRT file not found")
            
            logger.info(f"Loading text from SRT: {context.srt_path}")
            # Parse SRT file (implement SRT parsing)
            context.processed_text = await self._parse_srt_file(context.srt_path)
        else:
            if not context.transcription_result:
                raise ProcessingError("No transcription result available for text processing")
            
            logger.info("Processing transcribed text")
            
            # Extract text from transcription result
            raw_text = context.transcription_result.get('text', '')
            
            # Process text with GPT
            context.processed_text = await self.text_processor.process_text(raw_text)
        
        await progress_tracker.update_progress(1.0, "Обработка текста завершена")
        return context
    
    async def _step_analyze_frames(self, context: ProcessingContext, progress_tracker: TaskProgressTracker) -> ProcessingContext:
        """Step 7: Extract keyframes and perform visual analysis."""
        if not context.scenes:
            raise ProcessingError("No scenes available for frame analysis")
        
        logger.info(f"Analyzing frames for {len(context.scenes)} scenes")
        
        # Extract keyframes
        await progress_tracker.update_progress(0.3, "Извлечение ключевых кадров")
        context.keyframes = await self.keyframe_extractor.extract_keyframes_from_scenes(
            context.video_path, 
            context.scenes
        )
        
        # Perform visual analysis
        await progress_tracker.update_progress(0.7, "Анализ кадров с помощью AI")
        context.visual_analysis = await self.visual_analyzer.analyze_scenes(
            context.keyframes,
            context.processed_text or ""
        )
        
        await progress_tracker.update_progress(1.0, "Анализ кадров завершен")
        return context
    
    async def _step_generate_montage(self, context: ProcessingContext, progress_tracker: TaskProgressTracker) -> ProcessingContext:
        """Step 8: Generate montage table."""
        logger.info("Generating montage table")
        
        # Map dialogue to scenes
        await progress_tracker.update_progress(0.3, "Распределение диалогов по сценам")
        if context.transcription_result:
            context.dialogue_mapping = await self.dialogue_mapper.map_dialogue_to_scenes(
                context.scenes,
                context.transcription_result,
                context.diarization_result
            )
        
        # Detect music in scenes
        await progress_tracker.update_progress(0.6, "Определение музыки в сценах")
        if context.audio_path:
            context.music_analysis = await self.music_detector.detect_music_in_scenes(
                context.audio_path,
                context.scenes
            )
        
        # Generate montage rows
        await progress_tracker.update_progress(0.9, "Создание монтажной таблицы")
        montage_result = await self.montage_service.generate_montage_table(
            scenes=context.scenes,
            dialogue_result=context.dialogue_mapping,
            visual_analysis_results=context.visual_analysis,
            music_detection_result=context.music_analysis
        )
        context.montage_rows = montage_result.montage_rows
        
        await progress_tracker.update_progress(1.0, "Монтажная таблица создана")
        return context
    
    async def _step_generate_document(self, context: ProcessingContext, progress_tracker: TaskProgressTracker) -> ProcessingContext:
        """Step 9: Generate final DOCX document."""
        if not context.montage_rows:
            raise ProcessingError("No montage data available for document generation")
        
        logger.info("Generating DOCX document")
        
        # Generate document
        docx_bytes = await self.docx_generator.generate_montage_docx(
            montage_rows=context.montage_rows,
            film_metadata=None,  # Will need to be provided from context
            use_gff_format=True
        )
        
        # Save document to file
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        docx_path = output_dir / f"montage_{context.task_id}.docx"
        
        with open(docx_path, 'wb') as f:
            f.write(docx_bytes)
        
        context.docx_path = str(docx_path)
        
        await progress_tracker.update_progress(1.0, "Документ успешно создан")
        return context
    
    async def _parse_srt_file(self, srt_path: str) -> str:
        """Parse SRT file and extract text content."""
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Simple SRT parsing - extract text lines
            lines = content.split('\n')
            text_lines = []
            
            for line in lines:
                line = line.strip()
                # Skip sequence numbers and timestamps
                if line and not line.isdigit() and '-->' not in line:
                    text_lines.append(line)
            
            return ' '.join(text_lines)
            
        except Exception as e:
            raise ProcessingError(f"Failed to parse SRT file: {e}")


# Global orchestrator instance (lazy initialization)
_pipeline_orchestrator = None

def get_pipeline_orchestrator() -> PipelineOrchestrator:
    """Get the global pipeline orchestrator instance."""
    global _pipeline_orchestrator
    if _pipeline_orchestrator is None:
        _pipeline_orchestrator = PipelineOrchestrator()
    return _pipeline_orchestrator