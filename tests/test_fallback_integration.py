"""
Integration tests for fallback mechanisms and service health monitoring.
Tests complete workflows with external service failures.
"""

import pytest
import asyncio
import tempfile
import os
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from app.core.health_monitor import (
    HealthMonitor, ServiceStatus, HealthCheck,
    check_openai_health, check_huggingface_health,
    setup_health_monitoring, cleanup_health_monitoring
)
from app.services.fallback_services import (
    FallbackVisualAnalysisService, FallbackDiarizationService,
    FallbackTextProcessingService, FallbackMusicDetectionService,
    fallback_services
)
from app.services.transcription import TranscriptionService
from app.core.exceptions import ExternalServiceError, ErrorCode


class TestHealthMonitor:
    """Test health monitoring system."""
    
    @pytest.fixture
    async def health_monitor(self):
        """Create a health monitor instance for testing."""
        monitor = HealthMonitor()
        yield monitor
        await monitor.stop_monitoring()
    
    @pytest.mark.asyncio
    async def test_service_registration(self, health_monitor):
        """Test service registration and configuration."""
        
        async def mock_health_check():
            return True
        
        async def mock_fallback():
            return "fallback_result"
        
        health_monitor.register_service(
            service_name="test_service",
            check_function=mock_health_check,
            fallback_handler=mock_fallback,
            interval_seconds=30,
            failure_threshold=2,
            recovery_threshold=1
        )
        
        # Verify service is registered
        assert "test_service" in health_monitor.health_checks
        assert "test_service" in health_monitor.fallback_handlers
        
        health_check = health_monitor.health_checks["test_service"]
        assert health_check.service_name == "test_service"
        assert health_check.interval_seconds == 30
        assert health_check.failure_threshold == 2
        assert health_check.recovery_threshold == 1
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, health_monitor):
        """Test successful health check execution."""
        
        check_called = False
        
        async def mock_health_check():
            nonlocal check_called
            check_called = True
            return True
        
        health_monitor.register_service(
            service_name="test_service",
            check_function=mock_health_check,
            interval_seconds=1,  # Check every second
            failure_threshold=2
        )
        
        # Start monitoring
        await health_monitor.start_monitoring()
        
        # Wait for health check to run
        await asyncio.sleep(2)
        
        # Verify health check was called and service is healthy
        assert check_called
        assert health_monitor.get_service_status("test_service") == ServiceStatus.HEALTHY
        
        # Get service info
        info = health_monitor.get_service_info("test_service")
        assert info["status"] == ServiceStatus.HEALTHY
        assert info["total_checks"] > 0
        assert info["success_rate"] == 100.0
    
    @pytest.mark.asyncio
    async def test_health_check_failure_and_recovery(self, health_monitor):
        """Test health check failure detection and recovery."""
        
        check_count = 0
        
        async def mock_health_check():
            nonlocal check_count
            check_count += 1
            # Fail first 3 checks, then succeed
            return check_count > 3
        
        health_monitor.register_service(
            service_name="test_service",
            check_function=mock_health_check,
            interval_seconds=0.5,  # Check every 0.5 seconds
            failure_threshold=2,
            recovery_threshold=1
        )
        
        # Start monitoring
        await health_monitor.start_monitoring()
        
        # Wait for failures to accumulate
        await asyncio.sleep(2)
        
        # Service should be unhealthy after failures
        assert health_monitor.get_service_status("test_service") == ServiceStatus.UNHEALTHY
        
        # Wait for recovery
        await asyncio.sleep(2)
        
        # Service should recover
        assert health_monitor.get_service_status("test_service") == ServiceStatus.HEALTHY
        
        info = health_monitor.get_service_info("test_service")
        assert info["total_failures"] > 0
        assert info["consecutive_successes"] >= 1
    
    @pytest.mark.asyncio
    async def test_fallback_context_manager(self, health_monitor):
        """Test fallback context manager functionality."""
        
        async def failing_health_check():
            return False
        
        async def mock_fallback(*args, **kwargs):
            return "fallback_executed"
        
        health_monitor.register_service(
            service_name="test_service",
            check_function=failing_health_check,
            fallback_handler=mock_fallback,
            failure_threshold=1
        )
        
        # Manually set service as unhealthy
        health_check = health_monitor.health_checks["test_service"]
        health_check.status = ServiceStatus.UNHEALTHY
        
        # Test fallback context
        async with health_monitor.with_fallback("test_service") as fallback:
            assert fallback.should_use_fallback()
            result = await fallback.execute_fallback()
            assert result == "fallback_executed"
    
    @pytest.mark.asyncio
    async def test_service_status_queries(self, health_monitor):
        """Test service status query methods."""
        
        async def mock_health_check():
            return True
        
        health_monitor.register_service(
            service_name="service1",
            check_function=mock_health_check
        )
        
        health_monitor.register_service(
            service_name="service2", 
            check_function=mock_health_check
        )
        
        # Test individual service status
        assert health_monitor.get_service_status("service1") == ServiceStatus.UNKNOWN
        assert health_monitor.get_service_status("nonexistent") == ServiceStatus.UNKNOWN
        
        # Test all services status
        all_status = health_monitor.get_all_services_status()
        assert "service1" in all_status
        assert "service2" in all_status
        assert all_status["service1"]["service_name"] == "service1"


class TestFallbackServices:
    """Test fallback service implementations."""
    
    @pytest.mark.asyncio
    async def test_fallback_visual_analysis(self):
        """Test fallback visual analysis service."""
        service = FallbackVisualAnalysisService()
        
        # Create temporary image files
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f1:
            frame1_path = f1.name
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f2:
            frame2_path = f2.name
        
        try:
            # Test analysis with dialogue
            dialogue = "Персонаж работает за компьютером в офисе"
            result = await service.analyze_scene_frames(frame1_path, frame2_path, dialogue)
            
            assert "shot_type" in result
            assert "description" in result
            assert "text_in_frame" in result
            assert result["shot_type"] in ["Д.", "О.", "Ср.", "Кр.", "Дет."]
            assert "офис" in result["description"].lower()
            
            # Test analysis without dialogue
            result2 = await service.analyze_scene_frames(frame1_path, frame2_path, "")
            assert result2["shot_type"] in ["Д.", "О.", "Ср.", "Кр.", "Дет."]
            assert len(result2["description"]) > 0
            
        finally:
            # Clean up temporary files
            os.unlink(frame1_path)
            os.unlink(frame2_path)
    
    @pytest.mark.asyncio
    async def test_fallback_diarization(self):
        """Test fallback diarization service."""
        service = FallbackDiarizationService()
        
        # Mock transcription segments
        segments = [
            {"start": 0.0, "end": 2.0, "text": "Привет, как дела?"},
            {"start": 3.0, "end": 5.0, "text": "Хорошо, спасибо."},
            {"start": 6.0, "end": 8.0, "text": "Что планируешь на выходные?"},
            {"start": 10.0, "end": 12.0, "text": "Пойду в кино."}
        ]
        
        result = await service.diarize_audio("test_audio.wav", segments)
        
        assert "segments" in result
        assert "speakers" in result
        assert "method" in result
        assert result["method"] == "fallback_heuristic"
        assert len(result["segments"]) == len(segments)
        assert len(result["speakers"]) > 0
        
        # Verify speaker assignments
        for segment in result["segments"]:
            assert "speaker" in segment
            assert segment["speaker"] in service.speaker_names
    
    @pytest.mark.asyncio
    async def test_fallback_text_processing(self):
        """Test fallback text processing service."""
        service = FallbackTextProcessingService()
        
        # Test text with common issues
        raw_text = "ну это ээээ очень  хороший  текст ммм да"
        processed = await service.process_text(raw_text)
        
        assert "ну" not in processed
        assert "ээээ" not in processed
        assert "ммм" not in processed
        assert "  " not in processed  # No double spaces
        assert processed[0].isupper()  # Capitalized
        assert processed.endswith(".")  # Proper ending
    
    @pytest.mark.asyncio
    async def test_fallback_music_detection(self):
        """Test fallback music detection service."""
        service = FallbackMusicDetectionService()
        
        # Test long scene (more likely to have music)
        result_long = await service.detect_music_in_scene("test.wav", 0.0, 15.0)
        assert isinstance(result_long, bool)
        
        # Test short scene (less likely to have music)
        result_short = await service.detect_music_in_scene("test.wav", 0.0, 3.0)
        assert isinstance(result_short, bool)
    
    @pytest.mark.asyncio
    async def test_fallback_service_manager(self):
        """Test fallback service manager."""
        status = await fallback_services.get_service_status()
        
        assert "visual_analysis" in status
        assert "diarization" in status
        assert "text_processing" in status
        assert "music_detection" in status
        assert status["status"] == "ready"
        
        # Verify all services are available
        for service_name, service_info in status.items():
            if isinstance(service_info, dict) and "available" in service_info:
                assert service_info["available"] is True


class TestTranscriptionServiceFallback:
    """Test transcription service with fallback mechanisms."""
    
    @pytest.fixture
    def mock_transcription_service(self):
        """Create a transcription service with mocked dependencies."""
        with patch('app.services.transcription.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = "test_key"
            service = TranscriptionService()
            return service
    
    @pytest.mark.asyncio
    async def test_transcription_with_healthy_service(self, mock_transcription_service):
        """Test transcription when primary service is healthy."""
        
        # Mock health monitor to return healthy status
        with patch('app.services.transcription.health_monitor') as mock_monitor:
            mock_fallback = AsyncMock()
            mock_fallback.should_use_fallback.return_value = False
            mock_fallback.is_service_degraded.return_value = False
            mock_monitor.with_fallback.return_value.__aenter__.return_value = mock_fallback
            
            # Mock primary service success
            with patch.object(mock_transcription_service, 'primary_service') as mock_primary:
                mock_result = Mock()
                mock_result.text = "Test transcription"
                mock_primary.transcribe_audio.return_value = mock_result
                
                result = await mock_transcription_service.transcribe_audio("test.wav")
                
                assert result.text == "Test transcription"
                mock_primary.transcribe_audio.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_transcription_with_unhealthy_service(self, mock_transcription_service):
        """Test transcription when primary service is unhealthy."""
        
        # Mock health monitor to return unhealthy status
        with patch('app.services.transcription.health_monitor') as mock_monitor:
            mock_fallback = AsyncMock()
            mock_fallback.should_use_fallback.return_value = True
            mock_monitor.with_fallback.return_value.__aenter__.return_value = mock_fallback
            
            # Mock fallback service
            with patch.object(mock_transcription_service, 'fallback_service') as mock_fallback_service:
                mock_result = Mock()
                mock_result.text = "Fallback transcription"
                mock_fallback_service.transcribe_audio.return_value = mock_result
                
                result = await mock_transcription_service.transcribe_audio("test.wav")
                
                assert result.text == "Fallback transcription"
                mock_fallback_service.transcribe_audio.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_transcription_with_degraded_service(self, mock_transcription_service):
        """Test transcription when primary service is degraded."""
        
        # Mock health monitor to return degraded status
        with patch('app.services.transcription.health_monitor') as mock_monitor:
            mock_fallback = AsyncMock()
            mock_fallback.should_use_fallback.return_value = False
            mock_fallback.is_service_degraded.return_value = True
            mock_monitor.with_fallback.return_value.__aenter__.return_value = mock_fallback
            
            # Mock primary service failure
            with patch.object(mock_transcription_service, 'primary_service') as mock_primary:
                mock_primary.transcribe_audio.side_effect = Exception("API Error")
                
                # Mock fallback service
                with patch.object(mock_transcription_service, 'fallback_service') as mock_fallback_service:
                    mock_result = Mock()
                    mock_result.text = "Fallback after degraded service failure"
                    mock_fallback_service.transcribe_audio.return_value = mock_result
                    
                    result = await mock_transcription_service.transcribe_audio("test.wav")
                    
                    assert result.text == "Fallback after degraded service failure"
                    mock_fallback_service.transcribe_audio.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_transcription_retry_mechanism(self, mock_transcription_service):
        """Test transcription retry mechanism with eventual fallback."""
        
        call_count = 0
        
        async def mock_transcribe_with_failures(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # Fail first 2 attempts
                raise Exception(f"Attempt {call_count} failed")
            # Third attempt would succeed, but we'll test fallback
            raise Exception("All attempts failed")
        
        # Mock the transcribe_audio method to simulate failures
        with patch.object(mock_transcription_service, 'transcribe_audio', side_effect=mock_transcribe_with_failures):
            # Mock fallback service
            with patch.object(mock_transcription_service, 'fallback_service') as mock_fallback_service:
                mock_result = Mock()
                mock_result.text = "Final fallback result"
                mock_fallback_service.transcribe_audio.return_value = mock_result
                
                result = await mock_transcription_service.transcribe_audio_with_retry(
                    "test.wav", max_retries=2, retry_delay=0.1
                )
                
                assert result.text == "Final fallback result"
                mock_fallback_service.transcribe_audio.assert_called_once()


class TestIntegrationScenarios:
    """Test complete integration scenarios with multiple service failures."""
    
    @pytest.mark.asyncio
    async def test_complete_processing_pipeline_with_fallbacks(self):
        """Test complete processing pipeline when external services fail."""
        
        # This test simulates a complete video processing workflow
        # where external services (OpenAI, HuggingFace) are unavailable
        
        # Mock all external service health checks to return False
        with patch('app.core.health_monitor.check_openai_health', return_value=False):
            with patch('app.core.health_monitor.check_huggingface_health', return_value=False):
                
                # Setup health monitoring
                health_monitor = HealthMonitor()
                
                # Register services with failing health checks
                health_monitor.register_service(
                    "openai",
                    lambda: False,  # Always fail
                    interval_seconds=1,
                    failure_threshold=1
                )
                
                health_monitor.register_service(
                    "huggingface", 
                    lambda: False,  # Always fail
                    interval_seconds=1,
                    failure_threshold=1
                )
                
                try:
                    await health_monitor.start_monitoring()
                    
                    # Wait for services to be marked as unhealthy
                    await asyncio.sleep(2)
                    
                    # Verify services are unhealthy
                    assert health_monitor.get_service_status("openai") == ServiceStatus.UNHEALTHY
                    assert health_monitor.get_service_status("huggingface") == ServiceStatus.UNHEALTHY
                    
                    # Test that fallback context correctly identifies unhealthy services
                    async with health_monitor.with_fallback("openai") as fallback:
                        assert fallback.should_use_fallback()
                    
                    async with health_monitor.with_fallback("huggingface") as fallback:
                        assert fallback.should_use_fallback()
                    
                finally:
                    await health_monitor.stop_monitoring()
    
    @pytest.mark.asyncio
    async def test_service_recovery_scenario(self):
        """Test service recovery from unhealthy to healthy state."""
        
        health_check_count = 0
        
        async def recovering_health_check():
            nonlocal health_check_count
            health_check_count += 1
            # Fail first 3 checks, then succeed
            return health_check_count > 3
        
        health_monitor = HealthMonitor()
        health_monitor.register_service(
            "recovering_service",
            recovering_health_check,
            interval_seconds=0.5,
            failure_threshold=2,
            recovery_threshold=1
        )
        
        try:
            await health_monitor.start_monitoring()
            
            # Wait for initial failures
            await asyncio.sleep(2)
            assert health_monitor.get_service_status("recovering_service") == ServiceStatus.UNHEALTHY
            
            # Wait for recovery
            await asyncio.sleep(2)
            assert health_monitor.get_service_status("recovering_service") == ServiceStatus.HEALTHY
            
            # Verify service info reflects recovery
            info = health_monitor.get_service_info("recovering_service")
            assert info["total_failures"] > 0
            assert info["consecutive_successes"] >= 1
            
        finally:
            await health_monitor.stop_monitoring()
    
    @pytest.mark.asyncio
    async def test_mixed_service_health_scenario(self):
        """Test scenario with mixed service health states."""
        
        health_monitor = HealthMonitor()
        
        # Register services with different health patterns
        health_monitor.register_service(
            "healthy_service",
            lambda: True,  # Always healthy
            interval_seconds=0.5,
            failure_threshold=2
        )
        
        health_monitor.register_service(
            "unhealthy_service",
            lambda: False,  # Always unhealthy
            interval_seconds=0.5,
            failure_threshold=1
        )
        
        intermittent_count = 0
        async def intermittent_health_check():
            nonlocal intermittent_count
            intermittent_count += 1
            return intermittent_count % 3 != 0  # Fail every 3rd check
        
        health_monitor.register_service(
            "intermittent_service",
            intermittent_health_check,
            interval_seconds=0.3,
            failure_threshold=2,
            recovery_threshold=1
        )
        
        try:
            await health_monitor.start_monitoring()
            
            # Wait for health checks to stabilize
            await asyncio.sleep(3)
            
            # Verify expected states
            assert health_monitor.get_service_status("healthy_service") == ServiceStatus.HEALTHY
            assert health_monitor.get_service_status("unhealthy_service") == ServiceStatus.UNHEALTHY
            
            # Intermittent service should be degraded or unhealthy
            intermittent_status = health_monitor.get_service_status("intermittent_service")
            assert intermittent_status in [ServiceStatus.DEGRADED, ServiceStatus.UNHEALTHY]
            
            # Get overall status
            all_status = health_monitor.get_all_services_status()
            assert len(all_status) == 3
            assert all_status["healthy_service"]["success_rate"] == 100.0
            assert all_status["unhealthy_service"]["success_rate"] == 0.0
            
        finally:
            await health_monitor.stop_monitoring()


if __name__ == "__main__":
    pytest.main([__file__])