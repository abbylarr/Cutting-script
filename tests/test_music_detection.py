"""
Unit tests for music detection services.
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path

from app.services.music_detection import (
    MusicDetectionService,
    SceneMusicDetectionService,
    FallbackMusicDetectionService,
    AudioFeatureExtractor,
    MusicClassifier,
    MusicSegment,
    SceneMusicAnalysis,
    MusicDetectionResult,
    MusicDetectionError
)
from app.services.video_processor import Scene


class TestAudioFeatureExtractor:
    """Test cases for AudioFeatureExtractor."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = AudioFeatureExtractor()
    
    @pytest.mark.asyncio
    async def test_extract_audio_features_librosa_not_available(self):
        """Test feature extraction when librosa is not available."""
        # This should raise an error since librosa is not installed
        with pytest.raises(MusicDetectionError, match="librosa not available"):
            await self.extractor.extract_audio_features("test_audio.wav")
    



class TestMusicClassifier:
    """Test cases for MusicClassifier."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = MusicClassifier()
    
    @pytest.mark.asyncio
    async def test_classify_music_positive(self):
        """Test classification of clear music features."""
        # Features that should indicate music
        music_features = {
            "spectral_centroid_mean": 2000.0,
            "spectral_rolloff_mean": 3000.0,
            "spectral_bandwidth_mean": 1200.0,
            "tempo": 120.0,
            "beat_count": 10,
            "onset_rate": 2.0,
            "harmonic_ratio": 0.7,
            "percussive_ratio": 0.3,
            "rms_energy_mean": 0.08,
            "chroma_deviation_mean": 0.3,
            "duration": 5.0
        }
        
        is_music, confidence, music_type = await self.classifier.classify_music(music_features)
        
        assert is_music is True
        assert confidence > 0.6
        assert music_type in ["background", "foreground", "mixed"]
    
    @pytest.mark.asyncio
    async def test_classify_music_negative(self):
        """Test classification of non-music features."""
        # Features that should indicate speech/noise
        non_music_features = {
            "spectral_centroid_mean": 500.0,  # Too low for music
            "spectral_rolloff_mean": 1000.0,  # Too low
            "spectral_bandwidth_mean": 200.0,
            "tempo": 0.0,  # No tempo
            "beat_count": 0,
            "onset_rate": 0.1,  # Very low
            "harmonic_ratio": 0.1,  # Very low
            "percussive_ratio": 0.9,
            "rms_energy_mean": 0.005,  # Very low energy
            "chroma_deviation_mean": 0.01,
            "duration": 5.0
        }
        
        is_music, confidence, music_type = await self.classifier.classify_music(non_music_features)
        
        assert is_music is False
        assert confidence <= 0.6
        assert music_type == "none"
    
    @pytest.mark.asyncio
    async def test_classify_music_background_type(self):
        """Test classification of background music."""
        # Features indicating background music (lower energy, more harmonic)
        background_features = {
            "spectral_centroid_mean": 1500.0,
            "spectral_rolloff_mean": 2500.0,
            "spectral_bandwidth_mean": 1000.0,
            "tempo": 80.0,
            "beat_count": 8,
            "onset_rate": 1.0,
            "harmonic_ratio": 0.8,  # High harmonic content
            "percussive_ratio": 0.2,
            "rms_energy_mean": 0.03,  # Low energy
            "chroma_deviation_mean": 0.2,
            "duration": 5.0
        }
        
        is_music, confidence, music_type = await self.classifier.classify_music(background_features)
        
        assert is_music is True
        assert music_type == "background"
    
    @pytest.mark.asyncio
    async def test_classify_music_foreground_type(self):
        """Test classification of foreground music."""
        # Features indicating foreground music (higher energy, strong rhythm)
        foreground_features = {
            "spectral_centroid_mean": 3000.0,
            "spectral_rolloff_mean": 5000.0,
            "spectral_bandwidth_mean": 2000.0,
            "tempo": 140.0,  # High tempo
            "beat_count": 15,
            "onset_rate": 3.0,
            "harmonic_ratio": 0.6,
            "percussive_ratio": 0.4,
            "rms_energy_mean": 0.15,  # High energy
            "chroma_deviation_mean": 0.4,
            "duration": 5.0
        }
        
        is_music, confidence, music_type = await self.classifier.classify_music(foreground_features)
        
        assert is_music is True
        assert music_type == "foreground"
    
    def test_calculate_spectral_score(self):
        """Test spectral score calculation."""
        good_features = {
            "spectral_centroid_mean": 2000.0,
            "spectral_rolloff_mean": 3000.0,
            "spectral_bandwidth_mean": 1500.0
        }
        
        score = self.classifier._calculate_spectral_score(good_features)
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should be high for good features
        
        bad_features = {
            "spectral_centroid_mean": 100.0,  # Too low
            "spectral_rolloff_mean": 500.0,   # Too low
            "spectral_bandwidth_mean": 100.0  # Too low
        }
        
        score = self.classifier._calculate_spectral_score(bad_features)
        assert score < 0.5  # Should be low for bad features
    
    def test_calculate_rhythmic_score(self):
        """Test rhythmic score calculation."""
        good_features = {
            "tempo": 120.0,
            "onset_rate": 2.0,
            "beat_count": 10,
            "duration": 5.0
        }
        
        score = self.classifier._calculate_rhythmic_score(good_features)
        assert 0.0 <= score <= 1.0
        assert score > 0.5
        
        bad_features = {
            "tempo": 0.0,
            "onset_rate": 0.1,
            "beat_count": 0,
            "duration": 5.0
        }
        
        score = self.classifier._calculate_rhythmic_score(bad_features)
        assert score < 0.5


class TestSceneMusicDetectionService:
    """Test cases for SceneMusicDetectionService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = SceneMusicDetectionService()
        
        # Create test scenes
        self.test_scenes = [
            Scene(start_time=0.0, end_time=10.0, duration=10.0, scene_number=1),
            Scene(start_time=10.0, end_time=20.0, duration=10.0, scene_number=2),
            Scene(start_time=20.0, end_time=30.0, duration=10.0, scene_number=3)
        ]
    
    @pytest.mark.asyncio
    @patch('pathlib.Path.exists')
    @patch.object(SceneMusicDetectionService, '_analyze_scene_music')
    async def test_detect_music_in_scenes_success(self, mock_analyze, mock_exists):
        """Test successful music detection in scenes."""
        mock_exists.return_value = True
        
        # Mock scene analysis results
        mock_analysis_results = [
            SceneMusicAnalysis(
                scene_number=1, start_time=0.0, end_time=10.0,
                has_music=True, music_segments=[
                    MusicSegment(0.0, 8.0, 0.8, "background", 0.05, {})
                ],
                music_coverage=0.8, dominant_music_type="background",
                average_music_confidence=0.8
            ),
            SceneMusicAnalysis(
                scene_number=2, start_time=10.0, end_time=20.0,
                has_music=False, music_segments=[],
                music_coverage=0.0, dominant_music_type=None,
                average_music_confidence=0.2
            ),
            SceneMusicAnalysis(
                scene_number=3, start_time=20.0, end_time=30.0,
                has_music=True, music_segments=[
                    MusicSegment(22.0, 28.0, 0.9, "foreground", 0.12, {})
                ],
                music_coverage=0.6, dominant_music_type="foreground",
                average_music_confidence=0.9
            )
        ]
        
        mock_analyze.side_effect = mock_analysis_results
        
        result = await self.service.detect_music_in_scenes("test_audio.wav", self.test_scenes)
        
        assert isinstance(result, MusicDetectionResult)
        assert result.total_scenes == 3
        assert result.scenes_with_music == 2
        assert len(result.scene_analyses) == 3
        assert result.total_music_duration > 0
    
    @pytest.mark.asyncio
    async def test_detect_music_in_scenes_file_not_found(self):
        """Test music detection with missing audio file."""
        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(MusicDetectionError, match="Audio file not found"):
                await self.service.detect_music_in_scenes("missing_audio.wav", self.test_scenes)
    
    def test_create_analysis_windows_short_scene(self):
        """Test window creation for short scenes."""
        windows = self.service._create_analysis_windows(0.0, 3.0)  # 3-second scene
        
        # Should create single window for short scene
        assert len(windows) == 1
        assert windows[0] == (0.0, 3.0)
    
    def test_create_analysis_windows_long_scene(self):
        """Test window creation for long scenes."""
        windows = self.service._create_analysis_windows(0.0, 20.0)  # 20-second scene
        
        # Should create multiple overlapping windows
        assert len(windows) > 1
        
        # Check that windows overlap
        for i in range(len(windows) - 1):
            assert windows[i][1] > windows[i + 1][0]  # Overlap
    
    @pytest.mark.asyncio
    async def test_merge_adjacent_music_segments(self):
        """Test merging of adjacent music segments."""
        segments = [
            MusicSegment(0.0, 3.0, 0.8, "background", 0.05, {}),
            MusicSegment(3.5, 6.0, 0.7, "background", 0.04, {}),  # Small gap
            MusicSegment(10.0, 13.0, 0.9, "foreground", 0.1, {})  # Large gap
        ]
        
        merged = await self.service._merge_adjacent_music_segments(segments)
        
        # First two should be merged, third should remain separate
        assert len(merged) == 2
        assert merged[0].start_time == 0.0
        assert merged[0].end_time == 6.0  # Merged
        assert merged[1].start_time == 10.0
    
    @pytest.mark.asyncio
    async def test_merge_short_segments_filtered(self):
        """Test that short segments are filtered out."""
        segments = [
            MusicSegment(0.0, 0.5, 0.8, "background", 0.05, {}),  # Too short
            MusicSegment(5.0, 8.0, 0.9, "foreground", 0.1, {})   # Long enough
        ]
        
        merged = await self.service._merge_adjacent_music_segments(segments)
        
        # Only the long segment should remain
        assert len(merged) == 1
        assert merged[0].start_time == 5.0
    
    def test_calculate_music_coverage(self):
        """Test music coverage calculation."""
        segments = [
            MusicSegment(2.0, 5.0, 0.8, "background", 0.05, {}),  # 3 seconds
            MusicSegment(7.0, 9.0, 0.9, "foreground", 0.1, {})   # 2 seconds
        ]
        
        coverage = self.service._calculate_music_coverage(segments, 10.0)  # 10-second scene
        
        assert coverage == 0.5  # 5 seconds of music in 10-second scene
    
    def test_get_dominant_music_type(self):
        """Test dominant music type detection."""
        segments = [
            MusicSegment(0.0, 3.0, 0.8, "background", 0.05, {}),   # 3 seconds
            MusicSegment(5.0, 6.0, 0.9, "foreground", 0.1, {}),   # 1 second
            MusicSegment(8.0, 12.0, 0.7, "background", 0.04, {})  # 4 seconds
        ]
        
        dominant_type = self.service._get_dominant_music_type(segments)
        
        assert dominant_type == "background"  # 7 seconds vs 1 second
    
    def test_get_dominant_music_type_empty(self):
        """Test dominant music type with no segments."""
        dominant_type = self.service._get_dominant_music_type([])
        assert dominant_type is None


class TestFallbackMusicDetectionService:
    """Test cases for FallbackMusicDetectionService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = FallbackMusicDetectionService()
        
        self.test_scenes = [
            Scene(start_time=0.0, end_time=10.0, duration=10.0, scene_number=1),
            Scene(start_time=10.0, end_time=20.0, duration=10.0, scene_number=2),
            Scene(start_time=20.0, end_time=30.0, duration=10.0, scene_number=3)
        ]
    
    @pytest.mark.asyncio
    async def test_detect_music_in_scenes_fallback(self):
        """Test fallback music detection."""
        result = await self.service.detect_music_in_scenes("dummy_audio.wav", self.test_scenes)
        
        assert isinstance(result, MusicDetectionResult)
        assert result.total_scenes == 3
        assert len(result.scene_analyses) == 3
        
        # Check that some scenes have music (based on heuristic)
        scenes_with_music = sum(1 for analysis in result.scene_analyses if analysis.has_music)
        assert scenes_with_music > 0
        
        # Check that music segments have low confidence (fallback indicator)
        for analysis in result.scene_analyses:
            if analysis.has_music:
                for segment in analysis.music_segments:
                    assert segment.confidence <= 0.5


class TestMusicDetectionService:
    """Test cases for main MusicDetectionService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.test_scenes = [
            Scene(start_time=0.0, end_time=10.0, duration=10.0, scene_number=1),
            Scene(start_time=10.0, end_time=20.0, duration=10.0, scene_number=2)
        ]
    
    @pytest.mark.asyncio
    async def test_detect_music_with_service(self):
        """Test music detection with available service."""
        service = MusicDetectionService()
        
        result = await service.detect_music_in_scenes("test_audio.wav", self.test_scenes)
        
        assert isinstance(result, MusicDetectionResult)
        assert result.total_scenes == 2
    
    @pytest.mark.asyncio
    async def test_detect_music_with_fallback_forced(self):
        """Test music detection with forced fallback."""
        service = MusicDetectionService()
        
        result = await service.detect_music_in_scenes(
            "test_audio.wav", 
            self.test_scenes, 
            use_fallback=True
        )
        
        assert isinstance(result, MusicDetectionResult)
        # Should use fallback
    
    @pytest.mark.asyncio
    async def test_is_primary_service_available(self):
        """Test checking primary service availability."""
        service = MusicDetectionService()
        available = await service.is_primary_service_available()
        assert isinstance(available, bool)  # Should return a boolean
    
    @pytest.mark.asyncio
    async def test_get_service_status(self):
        """Test getting service status."""
        service = MusicDetectionService()
        status = await service.get_service_status()
        
        assert "primary_available" in status
        assert "librosa_installed" in status
        assert "fallback_available" in status
        assert "current_time" in status
        assert status["fallback_available"] is True
        assert isinstance(status["librosa_installed"], bool)
    
    def test_check_librosa_installation(self):
        """Test librosa installation check."""
        service = MusicDetectionService()
        
        # Should return a boolean
        result = service._check_librosa_installation()
        assert isinstance(result, bool)


class TestMusicDetectionIntegration:
    """Integration tests for music detection."""
    
    @pytest.mark.asyncio
    async def test_full_music_detection_workflow(self):
        """Test complete music detection workflow with fallback."""
        # Use fallback service for reliable testing
        service = FallbackMusicDetectionService()
        
        scenes = [
            Scene(start_time=0.0, end_time=15.0, duration=15.0, scene_number=1),
            Scene(start_time=15.0, end_time=30.0, duration=15.0, scene_number=2),
            Scene(start_time=30.0, end_time=45.0, duration=15.0, scene_number=3),
            Scene(start_time=45.0, end_time=60.0, duration=15.0, scene_number=4)
        ]
        
        result = await service.detect_music_in_scenes("test_audio.wav", scenes)
        
        # Verify basic structure
        assert result.total_scenes == 4
        assert len(result.scene_analyses) == 4
        
        # Verify each scene analysis
        for i, analysis in enumerate(result.scene_analyses):
            assert analysis.scene_number == i + 1
            assert analysis.start_time == i * 15.0
            assert analysis.end_time == (i + 1) * 15.0
            
            if analysis.has_music:
                assert len(analysis.music_segments) > 0
                assert analysis.music_coverage > 0
                assert analysis.dominant_music_type is not None
                assert analysis.average_music_confidence > 0
            else:
                assert len(analysis.music_segments) == 0
                assert analysis.music_coverage == 0
                assert analysis.dominant_music_type is None
        
        # Get statistics
        main_service = MusicDetectionService()
        stats = await main_service.primary_service.get_music_statistics(result.scene_analyses) if main_service.primary_service else {}
        
        # Basic statistics validation would go here if we had the method implemented
        # For now, just verify the result structure is correct
        assert isinstance(result.processing_time, float)
        assert result.processing_time >= 0
    
    @pytest.mark.asyncio
    async def test_error_handling_music_detection(self):
        """Test error handling in music detection."""
        service = MusicDetectionService()
        
        # Test with empty scenes
        result = await service.detect_music_in_scenes("test_audio.wav", [])
        assert result.total_scenes == 0
        assert len(result.scene_analyses) == 0
    
    @pytest.mark.asyncio
    async def test_music_detection_with_various_scene_lengths(self):
        """Test music detection with scenes of various lengths."""
        service = FallbackMusicDetectionService()
        
        # Create scenes of different lengths
        scenes = [
            Scene(start_time=0.0, end_time=2.0, duration=2.0, scene_number=1),    # Very short
            Scene(start_time=2.0, end_time=10.0, duration=8.0, scene_number=2),   # Short
            Scene(start_time=10.0, end_time=30.0, duration=20.0, scene_number=3), # Medium
            Scene(start_time=30.0, end_time=90.0, duration=60.0, scene_number=4)  # Long
        ]
        
        result = await service.detect_music_in_scenes("test_audio.wav", scenes)
        
        assert result.total_scenes == 4
        assert len(result.scene_analyses) == 4
        
        # Verify that all scenes are processed regardless of length
        for analysis in result.scene_analyses:
            assert analysis.start_time >= 0
            assert analysis.end_time > analysis.start_time
            assert isinstance(analysis.has_music, bool)
            assert isinstance(analysis.music_coverage, float)
            assert 0.0 <= analysis.music_coverage <= 1.0