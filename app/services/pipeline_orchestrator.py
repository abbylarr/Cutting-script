"""
Processing pipeline orchestration service.
Coordinates video processing with progress tracking and offline fallbacks.
"""
import asyncio
import logging
import traceback
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict, is_dataclass
import json

from app.core.config import settings
from app.services.task_queue import TaskProgressTracker
from app.services.video_processor import (
    VideoValidationService, AudioExtractionService, SceneDetectionService,
    VideoMetadata, Scene,
)
from app.services.transcription import TranscriptionService, TranscriptionResult
from app.services.diarization import SpeakerDiarizationService
from app.services.text_processing import TextProcessingService
from app.services.keyframe_extraction import KeyframeExtractionService
from app.services.gpt_visual_analysis import GPTVisualAnalysisService, SceneAnalysisResult
from app.services.dialogue_mapping import DialogueSceneMappingService
from app.services.music_detection import MusicDetectionService
from app.services.montage_table import MontageTableAssemblyService
from app.services.docx_generator import DOCXGeneratorService
from app.schemas.processing_task import ProcessingStep
from app.schemas.film_project import FilmMetadata, ProjectSettings, MontageRow
from app.core.redis import cache_manager


logger = logging.getLogger(__name__)


def _to_serializable(obj: Any) -> Any:
    if obj is None:
        return None
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if isinstance(obj, list):
        return [_to_serializable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    return obj


@dataclass
class ProcessingContext:
    """Context object that holds all processing data and intermediate results."""
    task_id: str
    user_id: str
    video_path: str
    srt_path: Optional[str] = None
    use_srt: bool = False

    video_metadata: Optional[VideoMetadata] = None
    audio_path: Optional[str] = None
    scenes: Optional[List[Scene]] = None
    transcription_result: Optional[TranscriptionResult] = None
    diarization_result: Optional[Any] = None
    processed_text: Optional[str] = None
    keyframes: Optional[List[Any]] = None
    visual_analysis: Optional[List[SceneAnalysisResult]] = None
    dialogue_mapping: Optional[Any] = None
    music_analysis: Optional[Any] = None
    montage_rows: Optional[List[Any]] = None
    docx_path: Optional[str] = None

    film_metadata: Optional[Dict[str, Any]] = None
    project_settings: Optional[Dict[str, Any]] = None
    timecode_start: str = "01:00:00:00"
    standard: str = "ГФФ"

    partial_results: Dict[str, Any] = None

    def __post_init__(self):
        if self.partial_results is None:
            self.partial_results = {}

    def save_partial_result(self, step: str, result: Any):
        self.partial_results[step] = result

    def get_partial_result(self, step: str) -> Optional[Any]:
        return self.partial_results.get(step)


class ProcessingError(Exception):
    def __init__(self, message: str, step: Optional[ProcessingStep] = None, recoverable: bool = False):
        super().__init__(message)
        self.step = step
        self.recoverable = recoverable


class PipelineOrchestrator:
    """Orchestrates the complete video processing pipeline."""

    def __init__(self):
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

        self.processing_steps = [
            (ProcessingStep.VALIDATION, self._step_validate_video),
            (ProcessingStep.AUDIO_EXTRACTION, self._step_extract_audio),
            (ProcessingStep.SCENE_DETECTION, self._step_detect_scenes),
            (ProcessingStep.TRANSCRIPTION, self._step_transcribe_audio),
            (ProcessingStep.DIARIZATION, self._step_diarize_speakers),
            (ProcessingStep.TEXT_PROCESSING, self._step_process_text),
            (ProcessingStep.FRAME_ANALYSIS, self._step_analyze_frames),
            (ProcessingStep.MONTAGE_GENERATION, self._step_generate_montage),
            (ProcessingStep.DOCUMENT_GENERATION, self._step_generate_document),
        ]

        self.step_descriptions = {
            ProcessingStep.VALIDATION: "Проверка видеофайла и извлечение метаданных",
            ProcessingStep.AUDIO_EXTRACTION: "Извлечение аудиодорожки из видео",
            ProcessingStep.SCENE_DETECTION: "Определение границ сцен в видео",
            ProcessingStep.TRANSCRIPTION: "Транскрипция речи",
            ProcessingStep.DIARIZATION: "Определение спикеров",
            ProcessingStep.TEXT_PROCESSING: "Обработка текста",
            ProcessingStep.FRAME_ANALYSIS: "Анализ ключевых кадров",
            ProcessingStep.MONTAGE_GENERATION: "Создание монтажной таблицы",
            ProcessingStep.DOCUMENT_GENERATION: "Генерация итогового документа",
        }

        self.step_eta_base = {
            ProcessingStep.VALIDATION: 5,
            ProcessingStep.AUDIO_EXTRACTION: 10,
            ProcessingStep.SCENE_DETECTION: 30,
            ProcessingStep.TRANSCRIPTION: 60,
            ProcessingStep.DIARIZATION: 45,
            ProcessingStep.TEXT_PROCESSING: 15,
            ProcessingStep.FRAME_ANALYSIS: 90,
            ProcessingStep.MONTAGE_GENERATION: 10,
            ProcessingStep.DOCUMENT_GENERATION: 5,
        }

    async def process_video(
        self, progress_tracker: TaskProgressTracker, context: ProcessingContext
    ) -> ProcessingContext:
        logger.info(f"Starting video processing pipeline for task {context.task_id}")
        if not settings.has_openai:
            logger.info("Running in offline/autonomous mode (no OpenAI key)")

        steps_to_execute = self._get_steps_for_context(context)
        await progress_tracker.set_total_steps(len(steps_to_execute))

        try:
            for step, step_func in steps_to_execute:
                progress_tracker.check_cancellation()
                await progress_tracker.start_step(
                    step,
                    self.step_descriptions.get(step, step.value),
                )

                try:
                    context = await self._execute_step_with_recovery(
                        step_func, context, progress_tracker
                    )
                    await self._save_partial_results(context, step)
                except ProcessingError as e:
                    if e.recoverable:
                        logger.warning(f"Recoverable error in step {step.value}: {e}")
                        context = await self._recover_from_error(context, step, e)
                    else:
                        raise

                await progress_tracker.complete_step()
                logger.info(f"Completed step {step.value} for task {context.task_id}")

            logger.info(f"Pipeline completed for task {context.task_id}")
            return context

        except Exception as e:
            logger.error(f"Pipeline failed for task {context.task_id}: {e}")
            logger.error(traceback.format_exc())
            await self._save_error_context(context, e)
            if isinstance(e, ProcessingError):
                raise
            raise ProcessingError(f"Pipeline execution failed: {str(e)}")

    def _get_steps_for_context(self, context: ProcessingContext) -> List[tuple]:
        if context.use_srt:
            skip = {
                ProcessingStep.TRANSCRIPTION,
                ProcessingStep.DIARIZATION,
            }
            return [(s, f) for s, f in self.processing_steps if s not in skip]
        return list(self.processing_steps)

    async def _execute_step_with_recovery(
        self,
        step_func: Callable,
        context: ProcessingContext,
        progress_tracker: TaskProgressTracker,
    ) -> ProcessingContext:
        max_retries = 2
        retry_delay = 0.5

        for attempt in range(max_retries):
            try:
                return await step_func(context, progress_tracker)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise ProcessingError(
                        f"Step failed after {max_retries} attempts: {str(e)}",
                        recoverable=False,
                    )
                logger.warning(f"Step attempt {attempt + 1} failed: {e}, retrying")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2

        return context

    async def _recover_from_error(
        self, context: ProcessingContext, failed_step: ProcessingStep, error: ProcessingError
    ) -> ProcessingContext:
        partial_result = context.get_partial_result(failed_step.value)
        if partial_result:
            await self._apply_partial_result(context, failed_step, partial_result)
        return context

    async def _apply_partial_result(
        self, context: ProcessingContext, step: ProcessingStep, partial_result: Any
    ):
        if step == ProcessingStep.TRANSCRIPTION:
            context.transcription_result = partial_result
        elif step == ProcessingStep.DIARIZATION:
            context.diarization_result = partial_result
        elif step == ProcessingStep.FRAME_ANALYSIS:
            context.visual_analysis = partial_result

    async def _save_partial_results(self, context: ProcessingContext, step: ProcessingStep):
        try:
            result_data = None
            if step == ProcessingStep.VALIDATION and context.video_metadata:
                result_data = asdict(context.video_metadata)
            elif step == ProcessingStep.SCENE_DETECTION and context.scenes:
                result_data = [asdict(scene) for scene in context.scenes]
            elif step == ProcessingStep.TRANSCRIPTION and context.transcription_result:
                result_data = _to_serializable(context.transcription_result)
            elif step == ProcessingStep.DIARIZATION and context.diarization_result:
                result_data = _to_serializable(context.diarization_result)
            elif step == ProcessingStep.FRAME_ANALYSIS and context.visual_analysis:
                result_data = [
                    {
                        "scene_index": a.scene_index,
                        "shot_type": getattr(
                            a.visual_analysis.shot_type, "value", str(a.visual_analysis.shot_type)
                        ),
                        "description": a.visual_analysis.description,
                    }
                    for a in context.visual_analysis
                ]

            if result_data:
                key = f"partial_result:{context.task_id}:{step.value}"
                client = await cache_manager.redis_client.get_client()
                await client.setex(key, 3600, json.dumps(result_data, default=str))
        except Exception as e:
            logger.warning(f"Failed to save partial result for step {step.value}: {e}")

    async def _save_error_context(self, context: ProcessingContext, error: Exception):
        try:
            error_data = {
                "task_id": context.task_id,
                "error": str(error),
                "traceback": traceback.format_exc(),
                "timestamp": datetime.utcnow().isoformat(),
            }
            key = f"error_context:{context.task_id}"
            client = await cache_manager.redis_client.get_client()
            await client.setex(key, 86400, json.dumps(error_data, default=str))
        except Exception as e:
            logger.warning(f"Failed to save error context: {e}")

    async def _step_validate_video(
        self, context: ProcessingContext, progress_tracker: TaskProgressTracker
    ) -> ProcessingContext:
        if not Path(context.video_path).exists():
            raise ProcessingError(f"Video file not found: {context.video_path}")

        validation_result = await self.video_validator.validate_video(context.video_path)
        if not validation_result.is_valid:
            raise ProcessingError(f"Video validation failed: {validation_result.error}")

        context.video_metadata = validation_result.metadata
        await progress_tracker.update_progress(1.0, "Видео успешно проверено")
        return context

    async def _step_extract_audio(
        self, context: ProcessingContext, progress_tracker: TaskProgressTracker
    ) -> ProcessingContext:
        if context.use_srt and not context.audio_path:
            # Still useful for music detection; soft-fail if extraction fails
            pass

        logger.info(f"Extracting audio from: {context.video_path}")
        video_file = Path(context.video_path)
        audio_output = video_file.parent / f"{video_file.stem}_audio.wav"

        try:
            context.audio_path = await self.audio_extractor.extract_audio(
                context.video_path, str(audio_output)
            )
        except Exception as e:
            if context.use_srt:
                logger.warning(f"Audio extraction failed in SRT mode (continuing): {e}")
            else:
                raise ProcessingError(f"Audio extraction failed: {e}")

        await progress_tracker.update_progress(1.0, "Аудио успешно извлечено")
        return context

    async def _step_detect_scenes(
        self, context: ProcessingContext, progress_tracker: TaskProgressTracker
    ) -> ProcessingContext:
        context.scenes = await self.scene_detector.detect_scenes_with_fallback(
            context.video_path,
            min_scene_length=settings.MIN_SCENE_LENGTH,
        )
        if not context.scenes:
            raise ProcessingError("No scenes detected in video")

        logger.info(f"Detected {len(context.scenes)} scenes")
        await progress_tracker.update_progress(1.0, f"Обнаружено {len(context.scenes)} сцен")
        return context

    async def _step_transcribe_audio(
        self, context: ProcessingContext, progress_tracker: TaskProgressTracker
    ) -> ProcessingContext:
        if context.use_srt:
            return context
        if not context.audio_path:
            raise ProcessingError("Audio file not available for transcription")

        context.transcription_result = await self.transcription_service.transcribe_audio(
            context.audio_path, language="ru"
        )
        await progress_tracker.update_progress(1.0, "Транскрипция завершена")
        return context

    async def _step_diarize_speakers(
        self, context: ProcessingContext, progress_tracker: TaskProgressTracker
    ) -> ProcessingContext:
        if context.use_srt or not context.audio_path:
            return context

        try:
            context.diarization_result = await self.diarization_service.diarize_audio(
                context.audio_path
            )
        except Exception as e:
            logger.warning(f"Diarization failed, continuing: {e}")
            context.diarization_result = None

        await progress_tracker.update_progress(1.0, "Диаризация завершена")
        return context

    async def _step_process_text(
        self, context: ProcessingContext, progress_tracker: TaskProgressTracker
    ) -> ProcessingContext:
        if context.use_srt:
            if not context.srt_path or not Path(context.srt_path).exists():
                raise ProcessingError("SRT file not found")
            context.processed_text = await self._parse_srt_file(context.srt_path)
        else:
            if not context.transcription_result:
                raise ProcessingError("No transcription result available")
            raw_text = context.transcription_result.text or ""
            text_result = await self.text_processor.process_text(raw_text)
            context.processed_text = getattr(text_result, "processed_text", None) or str(text_result)

        await progress_tracker.update_progress(1.0, "Обработка текста завершена")
        return context

    async def _step_analyze_frames(
        self, context: ProcessingContext, progress_tracker: TaskProgressTracker
    ) -> ProcessingContext:
        if not context.scenes:
            raise ProcessingError("No scenes available for frame analysis")

        await progress_tracker.update_progress(0.3, "Извлечение и анализ кадров")

        dialogue_map: Dict[int, str] = {}
        if context.dialogue_mapping and hasattr(context.dialogue_mapping, "scene_dialogues"):
            for sd in context.dialogue_mapping.scene_dialogues:
                dialogue_map[sd.scene_number - 1] = sd.full_text or ""
        elif context.processed_text:
            # Spread processed text across scenes as weak prior
            for i, _ in enumerate(context.scenes):
                dialogue_map[i] = context.processed_text[:200]

        try:
            context.visual_analysis = await self.visual_analyzer.analyze_scenes(
                video_path=context.video_path,
                scenes=context.scenes,
                task_id=context.task_id,
                dialogue_mapping=dialogue_map,
            )
        except Exception as e:
            logger.warning(f"Visual analysis failed, building minimal fallbacks: {e}")
            context.visual_analysis = [
                self.visual_analyzer._create_fallback_analysis(scene, i, [])
                for i, scene in enumerate(context.scenes)
            ]

        await progress_tracker.update_progress(1.0, "Анализ кадров завершен")
        return context

    async def _step_generate_montage(
        self, context: ProcessingContext, progress_tracker: TaskProgressTracker
    ) -> ProcessingContext:
        await progress_tracker.update_progress(0.3, "Распределение диалогов по сценам")

        if context.transcription_result and not context.use_srt:
            try:
                context.dialogue_mapping = await self.dialogue_mapper.map_dialogue_to_scenes(
                    context.scenes,
                    context.transcription_result,
                    context.diarization_result,
                )
            except Exception as e:
                logger.warning(f"Dialogue mapping failed: {e}")
                context.dialogue_mapping = None

        await progress_tracker.update_progress(0.6, "Определение музыки")
        if context.audio_path:
            try:
                context.music_analysis = await self.music_detector.detect_music_in_scenes(
                    context.audio_path, context.scenes
                )
            except Exception as e:
                logger.warning(f"Music detection failed: {e}")
                context.music_analysis = None

        project_settings = None
        if context.project_settings:
            try:
                project_settings = ProjectSettings(**context.project_settings)
            except Exception:
                project_settings = ProjectSettings(
                    timecode_start=context.timecode_start,
                    standard=context.standard,
                )
        else:
            project_settings = ProjectSettings(
                timecode_start=context.timecode_start,
                standard=context.standard,
            )

        self.montage_service = MontageTableAssemblyService(project_settings)

        await progress_tracker.update_progress(0.9, "Создание монтажной таблицы")
        montage_result = await self.montage_service.generate_montage_table(
            scenes=context.scenes,
            dialogue_result=context.dialogue_mapping,
            visual_analysis_results=context.visual_analysis,
            music_detection_result=context.music_analysis,
        )
        context.montage_rows = montage_result.montage_rows

        await progress_tracker.update_progress(1.0, "Монтажная таблица создана")
        return context

    async def _step_generate_document(
        self, context: ProcessingContext, progress_tracker: TaskProgressTracker
    ) -> ProcessingContext:
        if not context.montage_rows:
            raise ProcessingError("No montage data available for document generation")

        film_meta = self._build_film_metadata(context)

        docx_bytes = await self.docx_generator.generate_montage_docx(
            montage_rows=context.montage_rows,
            film_metadata=film_meta,
            use_gff_format=True,
        )

        output_dir = Path(settings.OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        docx_path = output_dir / f"montage_{context.task_id}.docx"

        with open(docx_path, "wb") as f:
            f.write(docx_bytes)

        context.docx_path = str(docx_path)
        await progress_tracker.update_progress(1.0, "Документ успешно создан")
        return context

    def _build_film_metadata(self, context: ProcessingContext) -> FilmMetadata:
        if context.film_metadata:
            try:
                return FilmMetadata(**context.film_metadata)
            except Exception as e:
                logger.warning(f"Invalid film_metadata, using defaults: {e}")

        duration_str = "00:01:00"
        if context.video_metadata:
            total = int(context.video_metadata.duration)
            h, rem = divmod(total, 3600)
            m, s = divmod(rem, 60)
            duration_str = f"{h:02d}:{m:02d}:{s:02d}"

        return FilmMetadata(
            title="Без названия",
            production_company="Не указано",
            year=datetime.utcnow().year,
            country="Россия",
            screenwriters=["Не указано"],
            copyright_holders=["Не указано"],
            duration=duration_str,
            episodes_count=1,
            format="Digital",
            color_type="Цветной",
            media_carrier="Файл",
            original_language="Русский",
            audio_language="Русский",
        )

    async def _parse_srt_file(self, srt_path: str) -> str:
        try:
            with open(srt_path, "r", encoding="utf-8") as f:
                content = f.read()
            lines = content.split("\n")
            text_lines = []
            for line in lines:
                line = line.strip()
                if line and not line.isdigit() and "-->" not in line:
                    text_lines.append(line)
            return " ".join(text_lines)
        except Exception as e:
            raise ProcessingError(f"Failed to parse SRT file: {e}")


_pipeline_orchestrator = None


def get_pipeline_orchestrator() -> PipelineOrchestrator:
    global _pipeline_orchestrator
    if _pipeline_orchestrator is None:
        _pipeline_orchestrator = PipelineOrchestrator()
    return _pipeline_orchestrator
