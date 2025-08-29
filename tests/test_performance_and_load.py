"""
Performance and load testing for video processing pipeline.
"""
import pytest
import asyncio
import time
import psutil
import tempfile
import statistics
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any

from app.services.pipeline_orchestrator import PipelineOrchestrator, ProcessingContext
from app.services.task_queue import TaskQueue, TaskInfo, TaskPriority, TaskProgressTracker
from app.services.video_processor import VideoValidationService, AudioExtractionService, SceneDetectionService
from app.services.transcription import TranscriptionService
from app.services.diarization import SpeakerDiarizationService


class PerformanceMetrics:
    """Class to track performance metrics."""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.memory_usage = []
        self.cpu_usage = []
        self.processing_times = {}
    
    def start_monitoring(self):
        """Start performance monitoring."""
        self.start_time = time.time()
        self.memory_usage = []
        self.cpu_usage = []
    
    def record_step_time(self, step_name: str, duration: float):
        """Record processing time for a step."""
        self.processing_times[step_name] = duration
    
    def record_system_metrics(self):
        """Record current system metrics."""
        process = psutil.Process()
        self.memory_usage.append(process.memory_info().rss / 1024 / 1024)  # MB
        self.cpu_usage.append(process.cpu_percent())
    
    def stop_monitoring(self):
        """Stop monitoring and calculate final metrics."""
        self.end_time = time.time()
        return {
            'total_time': self.end_time - self.start_time,
            'avg_memory_mb': statistics.mean(self.memory_usage) if self.memory_usage else 0,
            'max_memory_mb': max(self.memory_usage) if self.memory_usage else 0,
            'avg_cpu_percent': statistics.mean(self.cpu_usage) if self.cpu_usage else 0,
            'max_cpu_percent': max(self.cpu_usage) if self.cpu_usage else 0,
            'step_times': self.processing_times
        }


class TestPerformanceBaseline:
    """Test performance baselines for individual components."""
    
    @pytest.fixture
    def performance_metrics(self):
        """Create performance metrics tracker."""
        return PerformanceMetrics()
    
    @pytest.fixture
    def large_video_file(self):
        """Create a large mock video file for performance testing."""
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
            # Write a larger mock video file (simulate 10MB)
            header = b'\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom'
            f.write(header)
            f.write(b'\x00' * (10 * 1024 * 1024 - len(header)))  # 10MB total
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        Path(temp_path).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_video_validation_performance(self, large_video_file: str, performance_metrics: PerformanceMetrics):
        """Test video validation performance with large files."""
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            # Mock FFmpeg probe response
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (
                b'{"format":{"duration":"600.0","bit_rate":"5000000"},"streams":[{"codec_type":"video","codec_name":"h264","width":1920,"height":1080,"r_frame_rate":"25/1"}]}',
                b''
            )
            mock_subprocess.return_value = mock_process
            
            validator = VideoValidationService()
            
            performance_metrics.start_monitoring()
            
            # Test multiple validations
            validation_times = []
            for i in range(10):
                start_time = time.time()
                
                result = await validator.validate_video(large_video_file)
                
                end_time = time.time()
                validation_times.append(end_time - start_time)
                performance_metrics.record_system_metrics()
            
            metrics = performance_metrics.stop_monitoring()
            
            # Performance assertions
            avg_validation_time = statistics.mean(validation_times)
            assert avg_validation_time < 2.0, f"Video validation too slow: {avg_validation_time:.2f}s"
            assert metrics['max_memory_mb'] < 500, f"Memory usage too high: {metrics['max_memory_mb']:.2f}MB"
            
            print(f"Video validation performance:")
            print(f"  Average time: {avg_validation_time:.3f}s")
            print(f"  Max memory: {metrics['max_memory_mb']:.2f}MB")
            print(f"  Max CPU: {metrics['max_cpu_percent']:.1f}%")
    
    @pytest.mark.asyncio
    async def test_audio_extraction_performance(self, large_video_file: str, performance_metrics: PerformanceMetrics):
        """Test audio extraction performance."""
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (b'', b'')
            mock_subprocess.return_value = mock_process
            
            with patch('pathlib.Path.exists', return_value=True), \
                 patch('pathlib.Path.mkdir'):
                
                extractor = AudioExtractionService()
                
                performance_metrics.start_monitoring()
                
                start_time = time.time()
                audio_path = await extractor.extract_audio(large_video_file)
                end_time = time.time()
                
                performance_metrics.record_step_time('audio_extraction', end_time - start_time)
                performance_metrics.record_system_metrics()
                
                metrics = performance_metrics.stop_monitoring()
                
                # Performance assertions
                extraction_time = metrics['step_times']['audio_extraction']
                assert extraction_time < 5.0, f"Audio extraction too slow: {extraction_time:.2f}s"
                assert metrics['max_memory_mb'] < 1000, f"Memory usage too high: {metrics['max_memory_mb']:.2f}MB"
                
                print(f"Audio extraction performance:")
                print(f"  Extraction time: {extraction_time:.3f}s")
                print(f"  Max memory: {metrics['max_memory_mb']:.2f}MB")
    
    @pytest.mark.asyncio
    async def test_scene_detection_performance(self, large_video_file: str, performance_metrics: PerformanceMetrics):
        """Test scene detection performance."""
        
        # Mock scenedetect
        mock_scene_list = [
            (MagicMock(get_seconds=MagicMock(return_value=i*30)), 
             MagicMock(get_seconds=MagicMock(return_value=(i+1)*30)))
            for i in range(20)  # 20 scenes for performance testing
        ]
        
        with patch('scenedetect.VideoManager') as mock_vm, \
             patch('scenedetect.SceneManager') as mock_sm, \
             patch('scenedetect.detectors.ContentDetector'):
            
            mock_vm_instance = MagicMock()
            mock_sm_instance = MagicMock()
            mock_sm_instance.get_scene_list.return_value = mock_scene_list
            
            mock_vm.return_value = mock_vm_instance
            mock_sm.return_value = mock_sm_instance
            
            detector = SceneDetectionService()
            
            performance_metrics.start_monitoring()
            
            start_time = time.time()
            scenes = await detector.detect_scenes(large_video_file)
            end_time = time.time()
            
            performance_metrics.record_step_time('scene_detection', end_time - start_time)
            performance_metrics.record_system_metrics()
            
            metrics = performance_metrics.stop_monitoring()
            
            # Performance assertions
            detection_time = metrics['step_times']['scene_detection']
            assert detection_time < 10.0, f"Scene detection too slow: {detection_time:.2f}s"
            assert len(scenes) == 20, f"Expected 20 scenes, got {len(scenes)}"
            
            print(f"Scene detection performance:")
            print(f"  Detection time: {detection_time:.3f}s")
            print(f"  Scenes detected: {len(scenes)}")
            print(f"  Max memory: {metrics['max_memory_mb']:.2f}MB")
    
    @pytest.mark.asyncio
    async def test_transcription_performance(self, performance_metrics: PerformanceMetrics):
        """Test transcription service performance with mock responses."""
        
        # Mock OpenAI response
        mock_response = {
            "text": "Это тестовая транскрипция для проверки производительности системы. " * 50,  # Long text
            "segments": [
                {"start": i, "end": i+5, "text": f"Сегмент {i}"} 
                for i in range(0, 250, 5)  # 50 segments
            ]
        }
        
        with patch('openai.Audio.transcribe', return_value=mock_response):
            transcription_service = TranscriptionService()
            
            performance_metrics.start_monitoring()
            
            # Test multiple transcriptions
            transcription_times = []
            for i in range(5):
                start_time = time.time()
                
                result = await transcription_service.transcribe_audio("/fake/audio.wav")
                
                end_time = time.time()
                transcription_times.append(end_time - start_time)
                performance_metrics.record_system_metrics()
            
            metrics = performance_metrics.stop_monitoring()
            
            # Performance assertions
            avg_transcription_time = statistics.mean(transcription_times)
            assert avg_transcription_time < 3.0, f"Transcription too slow: {avg_transcription_time:.2f}s"
            
            print(f"Transcription performance:")
            print(f"  Average time: {avg_transcription_time:.3f}s")
            print(f"  Max memory: {metrics['max_memory_mb']:.2f}MB")


class TestLoadTesting:
    """Test system behavior under load."""
    
    @pytest.fixture
    def mock_services_for_load_test(self):
        """Mock all services for load testing."""
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
            
            # Setup fast mock responses
            from app.services.video_processor import VideoMetadata, ValidationResult, Scene
            
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
            
            # Add small delays to simulate real processing
            async def mock_with_delay(delay=0.1):
                await asyncio.sleep(delay)
                return "/tmp/result"
            
            mocks['AudioExtractionService'].return_value.extract_audio = AsyncMock(
                side_effect=lambda *args: mock_with_delay(0.2)
            )
            
            mocks['SceneDetectionService'].return_value.detect_scenes_with_fallback = AsyncMock(
                return_value=[Scene(start_time=0.0, end_time=60.0, duration=60.0, scene_number=1)]
            )
            
            mocks['TranscriptionService'].return_value.transcribe_audio = AsyncMock(
                side_effect=lambda *args: asyncio.sleep(0.5) or {"text": "Mock transcription"}
            )
            
            # Setup other services with minimal delays
            for service_name in ['SpeakerDiarizationService', 'TextProcessingService', 
                               'KeyframeExtractionService', 'GPTVisualAnalysisService',
                               'DialogueSceneMappingService', 'MusicDetectionService']:
                mocks[service_name].return_value = MagicMock()
                for method in ['diarize_audio', 'process_text', 'extract_keyframes_for_scenes',
                              'analyze_scenes', 'map_dialogue_to_scenes', 'detect_music_in_scenes']:
                    if hasattr(mocks[service_name].return_value, method):
                        setattr(mocks[service_name].return_value, method, 
                               AsyncMock(side_effect=lambda *args: asyncio.sleep(0.1) or {}))
            
            mocks['MontageTableAssemblyService'].return_value.generate_montage_table = AsyncMock(
                return_value=[{"number": 1, "start_timecode": "01:00:00:00"}]
            )
            
            mocks['DOCXGeneratorService'].return_value.generate_docx_for_task = AsyncMock(
                return_value="/tmp/document.docx"
            )
            
            yield mocks
    
    @pytest.mark.asyncio
    async def test_concurrent_task_processing(self, mock_services_for_load_test):
        """Test processing multiple tasks concurrently."""
        
        with patch('app.services.pipeline_orchestrator.cache_manager') as mock_cache:
            mock_cache.redis_client.get_client = AsyncMock()
            mock_client = AsyncMock()
            mock_cache.redis_client.get_client.return_value = mock_client
            mock_client.setex = AsyncMock()
            
            orchestrator = PipelineOrchestrator()
            
            # Create multiple processing contexts
            contexts = []
            for i in range(10):  # 10 concurrent tasks
                context = ProcessingContext(
                    task_id=f"load-test-{i}",
                    user_id=f"user-{i}",
                    video_path=f"/tmp/video-{i}.mp4"
                )
                contexts.append(context)
            
            # Create progress trackers
            trackers = []
            for i, context in enumerate(contexts):
                task_info = TaskInfo(
                    task_id=context.task_id,
                    user_id=context.user_id,
                    priority=TaskPriority.NORMAL,
                    created_at=time.time()
                )
                
                tracker = TaskProgressTracker(context.task_id, task_info)
                tracker.set_total_steps = AsyncMock()
                tracker.start_step = AsyncMock()
                tracker.complete_step = AsyncMock()
                tracker.update_progress = AsyncMock()
                tracker.check_cancellation = MagicMock(return_value=False)
                trackers.append(tracker)
            
            # Mock file existence
            with patch('pathlib.Path.exists', return_value=True):
                
                # Measure concurrent processing performance
                start_time = time.time()
                
                # Process all tasks concurrently
                results = await asyncio.gather(*[
                    orchestrator.process_video(tracker, context)
                    for tracker, context in zip(trackers, contexts)
                ])
                
                end_time = time.time()
                total_time = end_time - start_time
                
                # Performance assertions
                assert len(results) == 10, f"Expected 10 results, got {len(results)}"
                assert total_time < 30.0, f"Concurrent processing too slow: {total_time:.2f}s"
                
                # Verify all tasks completed successfully
                for i, result in enumerate(results):
                    assert result.montage_rows is not None, f"Task {i} failed to generate montage"
                
                print(f"Concurrent processing performance:")
                print(f"  Total time for 10 tasks: {total_time:.2f}s")
                print(f"  Average time per task: {total_time/10:.2f}s")
                print(f"  Tasks per second: {10/total_time:.2f}")
    
    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, mock_services_for_load_test):
        """Test memory usage during high load."""
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        with patch('app.services.pipeline_orchestrator.cache_manager') as mock_cache:
            mock_cache.redis_client.get_client = AsyncMock()
            mock_client = AsyncMock()
            mock_cache.redis_client.get_client.return_value = mock_client
            mock_client.setex = AsyncMock()
            
            orchestrator = PipelineOrchestrator()
            
            memory_measurements = []
            
            # Process tasks in batches to monitor memory growth
            for batch in range(5):  # 5 batches
                contexts = []
                trackers = []
                
                for i in range(5):  # 5 tasks per batch
                    task_id = f"memory-test-{batch}-{i}"
                    context = ProcessingContext(
                        task_id=task_id,
                        user_id=f"user-{batch}-{i}",
                        video_path=f"/tmp/video-{batch}-{i}.mp4"
                    )
                    contexts.append(context)
                    
                    task_info = TaskInfo(
                        task_id=task_id,
                        user_id=context.user_id,
                        priority=TaskPriority.NORMAL,
                        created_at=time.time()
                    )
                    
                    tracker = TaskProgressTracker(task_id, task_info)
                    tracker.set_total_steps = AsyncMock()
                    tracker.start_step = AsyncMock()
                    tracker.complete_step = AsyncMock()
                    tracker.update_progress = AsyncMock()
                    tracker.check_cancellation = MagicMock(return_value=False)
                    trackers.append(tracker)
                
                # Process batch
                with patch('pathlib.Path.exists', return_value=True):
                    await asyncio.gather(*[
                        orchestrator.process_video(tracker, context)
                        for tracker, context in zip(trackers, contexts)
                    ])
                
                # Measure memory after batch
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_measurements.append(current_memory)
                
                print(f"Batch {batch + 1} completed. Memory usage: {current_memory:.2f}MB")
            
            final_memory = memory_measurements[-1]
            memory_growth = final_memory - initial_memory
            
            # Memory assertions
            assert memory_growth < 500, f"Memory growth too high: {memory_growth:.2f}MB"
            
            # Check for memory leaks (memory should not grow linearly with batches)
            if len(memory_measurements) >= 3:
                # Calculate memory growth rate
                growth_rates = []
                for i in range(1, len(memory_measurements)):
                    growth_rate = memory_measurements[i] - memory_measurements[i-1]
                    growth_rates.append(growth_rate)
                
                avg_growth_rate = statistics.mean(growth_rates)
                assert avg_growth_rate < 50, f"Potential memory leak detected: {avg_growth_rate:.2f}MB per batch"
            
            print(f"Memory usage analysis:")
            print(f"  Initial memory: {initial_memory:.2f}MB")
            print(f"  Final memory: {final_memory:.2f}MB")
            print(f"  Total growth: {memory_growth:.2f}MB")
            print(f"  Memory measurements: {[f'{m:.1f}' for m in memory_measurements]}")
    
    @pytest.mark.asyncio
    async def test_task_queue_performance(self):
        """Test task queue performance under load."""
        
        task_queue = TaskQueue(max_concurrent_tasks=5)
        
        # Create many tasks
        task_infos = []
        for i in range(50):
            task_info = TaskInfo(
                task_id=f"queue-test-{i}",
                user_id=f"user-{i % 10}",  # 10 different users
                priority=TaskPriority.NORMAL if i % 2 == 0 else TaskPriority.HIGH,
                created_at=time.time() + i * 0.1  # Stagger creation times
            )
            task_infos.append(task_info)
        
        # Mock task processor
        processed_tasks = []
        
        async def mock_processor(task_info: TaskInfo) -> Dict[str, Any]:
            await asyncio.sleep(0.1)  # Simulate processing time
            processed_tasks.append(task_info.task_id)
            return {"status": "completed", "task_id": task_info.task_id}
        
        # Add all tasks to queue
        start_time = time.time()
        
        for task_info in task_infos:
            await task_queue.add_task(task_info, mock_processor)
        
        # Wait for all tasks to complete
        while task_queue.get_queue_size() > 0 or task_queue.get_active_count() > 0:
            await asyncio.sleep(0.1)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Performance assertions
        assert len(processed_tasks) == 50, f"Expected 50 processed tasks, got {len(processed_tasks)}"
        assert total_time < 15.0, f"Queue processing too slow: {total_time:.2f}s"
        
        # Verify high priority tasks were processed first
        high_priority_tasks = [f"queue-test-{i}" for i in range(1, 50, 2)]
        normal_priority_tasks = [f"queue-test-{i}" for i in range(0, 50, 2)]
        
        # Find positions of first high and normal priority tasks
        first_high_pos = min([processed_tasks.index(task) for task in high_priority_tasks[:5]])
        first_normal_pos = min([processed_tasks.index(task) for task in normal_priority_tasks[:5]])
        
        # High priority should generally be processed before normal priority
        # (allowing some overlap due to concurrent processing)
        assert first_high_pos <= first_normal_pos + 2, "Priority queue not working correctly"
        
        print(f"Task queue performance:")
        print(f"  Total time for 50 tasks: {total_time:.2f}s")
        print(f"  Average time per task: {total_time/50:.3f}s")
        print(f"  Tasks per second: {50/total_time:.2f}")
        print(f"  First high priority position: {first_high_pos}")
        print(f"  First normal priority position: {first_normal_pos}")
    
    @pytest.mark.asyncio
    async def test_error_handling_under_load(self, mock_services_for_load_test):
        """Test error handling and recovery under load conditions."""
        
        # Modify mocks to introduce random failures
        original_transcribe = mock_services_for_load_test['TranscriptionService'].return_value.transcribe_audio
        
        failure_count = 0
        async def failing_transcribe(*args, **kwargs):
            nonlocal failure_count
            failure_count += 1
            if failure_count % 3 == 0:  # Fail every 3rd call
                raise Exception("Simulated API failure")
            await asyncio.sleep(0.1)
            return {"text": "Mock transcription"}
        
        mock_services_for_load_test['TranscriptionService'].return_value.transcribe_audio = AsyncMock(
            side_effect=failing_transcribe
        )
        
        with patch('app.services.pipeline_orchestrator.cache_manager') as mock_cache:
            mock_cache.redis_client.get_client = AsyncMock()
            mock_client = AsyncMock()
            mock_cache.redis_client.get_client.return_value = mock_client
            mock_client.setex = AsyncMock()
            
            orchestrator = PipelineOrchestrator()
            
            # Process multiple tasks with failures
            contexts = []
            trackers = []
            
            for i in range(15):  # 15 tasks, expect 5 failures
                context = ProcessingContext(
                    task_id=f"error-test-{i}",
                    user_id=f"user-{i}",
                    video_path=f"/tmp/video-{i}.mp4"
                )
                contexts.append(context)
                
                task_info = TaskInfo(
                    task_id=context.task_id,
                    user_id=context.user_id,
                    priority=TaskPriority.NORMAL,
                    created_at=time.time()
                )
                
                tracker = TaskProgressTracker(context.task_id, task_info)
                tracker.set_total_steps = AsyncMock()
                tracker.start_step = AsyncMock()
                tracker.complete_step = AsyncMock()
                tracker.update_progress = AsyncMock()
                tracker.check_cancellation = MagicMock(return_value=False)
                trackers.append(tracker)
            
            # Process with error handling
            with patch('pathlib.Path.exists', return_value=True):
                
                results = []
                errors = []
                
                for tracker, context in zip(trackers, contexts):
                    try:
                        result = await orchestrator.process_video(tracker, context)
                        results.append(result)
                    except Exception as e:
                        errors.append(str(e))
                
                # Verify error handling
                success_count = len(results)
                error_count = len(errors)
                
                print(f"Error handling under load:")
                print(f"  Successful tasks: {success_count}")
                print(f"  Failed tasks: {error_count}")
                print(f"  Success rate: {success_count/(success_count + error_count)*100:.1f}%")
                
                # Should have some successes and some failures
                assert success_count > 0, "No tasks succeeded"
                assert error_count > 0, "No failures occurred (test setup issue)"
                assert success_count >= error_count, "Too many failures"


class TestMemoryOptimization:
    """Test memory optimization and resource management."""
    
    @pytest.mark.asyncio
    async def test_large_file_memory_usage(self):
        """Test memory usage with large files."""
        
        # Create a very large mock video file
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
            # Write 100MB mock file
            header = b'\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom'
            f.write(header)
            chunk_size = 1024 * 1024  # 1MB chunks
            for _ in range(100):  # 100MB total
                f.write(b'\x00' * chunk_size)
            large_file_path = f.name
        
        try:
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                mock_process = AsyncMock()
                mock_process.returncode = 0
                mock_process.communicate.return_value = (
                    b'{"format":{"duration":"3600.0"},"streams":[{"codec_type":"video","codec_name":"h264","width":1920,"height":1080}]}',
                    b''
                )
                mock_subprocess.return_value = mock_process
                
                validator = VideoValidationService()
                
                # Validate large file
                result = await validator.validate_video(large_file_path)
                
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_increase = current_memory - initial_memory
                
                # Memory increase should be reasonable (not loading entire file into memory)
                assert memory_increase < 50, f"Memory increase too high: {memory_increase:.2f}MB"
                assert result.is_valid is True
                
                print(f"Large file memory usage:")
                print(f"  File size: 100MB")
                print(f"  Memory increase: {memory_increase:.2f}MB")
                print(f"  Memory efficiency: {(100/memory_increase):.1f}x")
        
        finally:
            Path(large_file_path).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_resource_cleanup(self):
        """Test proper resource cleanup after processing."""
        
        import gc
        
        # Get initial object counts
        gc.collect()
        initial_objects = len(gc.get_objects())
        
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
            
            # Setup minimal mocks
            from app.services.video_processor import VideoMetadata, ValidationResult, Scene
            
            # Process multiple tasks and let them go out of scope
            for i in range(10):
                orchestrator = PipelineOrchestrator()
                context = ProcessingContext(
                    task_id=f"cleanup-test-{i}",
                    user_id=f"user-{i}",
                    video_path=f"/tmp/video-{i}.mp4"
                )
                
                # Simulate some processing data
                context.video_metadata = VideoMetadata(
                    duration=60.0, fps=25.0, width=1920, height=1080,
                    codec="h264", format="mp4"
                )
                context.scenes = [Scene(start_time=0.0, end_time=60.0, duration=60.0, scene_number=1)]
                context.transcription_result = {"text": "Test" * 1000}  # Large text
                
                # Let objects go out of scope
                del orchestrator
                del context
        
        # Force garbage collection
        gc.collect()
        
        # Check object count after cleanup
        final_objects = len(gc.get_objects())
        object_increase = final_objects - initial_objects
        
        # Should not have significant object leaks
        assert object_increase < 1000, f"Potential object leak: {object_increase} new objects"
        
        print(f"Resource cleanup test:")
        print(f"  Initial objects: {initial_objects}")
        print(f"  Final objects: {final_objects}")
        print(f"  Object increase: {object_increase}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])