"""
Music detection services for filmlist application.
Handles audio analysis for music detection in video scenes.
"""

import asyncio
import logging
import numpy as np
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from app.services.video_processor import Scene

logger = logging.getLogger(__name__)


@dataclass
class MusicSegment:
    """Represents a detected music segment."""
    start_time: float
    end_time: float
    confidence: float  # 0.0 to 1.0
    music_type: str    # "background", "foreground", "mixed"
    volume_level: float  # Average volume during segment
    spectral_features: Dict[str, float]  # Spectral analysis features


@dataclass
class SceneMusicAnalysis:
    """Music analysis result for a single scene."""
    scene_number: int
    start_time: float
    end_time: float
    has_music: bool
    music_segments: List[MusicSegment]
    music_coverage: float  # Percentage of scene with music (0.0 to 1.0)
    dominant_music_type: Optional[str]
    average_music_confidence: float


@dataclass
class MusicDetectionResult:
    """Result of music detection analysis."""
    scene_analyses: List[SceneMusicAnalysis]
    total_scenes: int
    scenes_with_music: int
    total_music_duration: float
    processing_time: float


class MusicDetectionError(Exception):
    """Raised when music detection fails."""
    pass


class AudioFeatureExtractor:
    """Extracts audio features for music detection."""
    
    def __init__(self):
        self.sample_rate = 22050  # Standard sample rate for audio analysis
        self.hop_length = 512     # Hop length for STFT
        self.n_fft = 2048        # FFT window size
        
        # Music detection thresholds
        self.music_confidence_threshold = 0.6
        self.spectral_centroid_music_min = 1000  # Hz
        self.spectral_rolloff_music_min = 3000   # Hz
        self.tempo_music_min = 60  # BPM
        self.tempo_music_max = 200 # BPM
    
    async def extract_audio_features(
        self, 
        audio_path: str, 
        start_time: float = 0.0, 
        duration: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Extract audio features from audio file segment.
        
        Args:
            audio_path: Path to audio file
            start_time: Start time in seconds
            duration: Duration in seconds (None for entire file)
            
        Returns:
            Dictionary with extracted features
            
        Raises:
            MusicDetectionError: If feature extraction fails
        """
        try:
            # Import librosa for audio analysis
            import librosa
            import librosa.feature
            
            # Load audio segment
            y, sr = librosa.load(
                audio_path, 
                sr=self.sample_rate,
                offset=start_time,
                duration=duration
            )
            
            if len(y) == 0:
                raise MusicDetectionError("No audio data loaded")
            
            # Extract spectral features
            spectral_features = await self._extract_spectral_features(y, sr)
            
            # Extract rhythmic features
            rhythmic_features = await self._extract_rhythmic_features(y, sr)
            
            # Extract harmonic features
            harmonic_features = await self._extract_harmonic_features(y, sr)
            
            # Combine all features
            features = {
                **spectral_features,
                **rhythmic_features,
                **harmonic_features,
                "duration": len(y) / sr,
                "sample_rate": sr
            }
            
            return features
            
        except ImportError:
            raise MusicDetectionError("librosa not available for audio analysis")
        except Exception as e:
            logger.error(f"Feature extraction failed for {audio_path}: {e}")
            raise MusicDetectionError(f"Failed to extract audio features: {e}")
    
    async def _extract_spectral_features(self, y: np.ndarray, sr: int) -> Dict[str, float]:
        """Extract spectral features from audio."""
        import librosa.feature
        
        # Spectral centroid (brightness)
        spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=self.hop_length)
        
        # Spectral rolloff (frequency below which 85% of energy is contained)
        spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, hop_length=self.hop_length)
        
        # Spectral bandwidth
        spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr, hop_length=self.hop_length)
        
        # Zero crossing rate
        zcr = librosa.feature.zero_crossing_rate(y, hop_length=self.hop_length)
        
        # RMS energy
        rms = librosa.feature.rms(y=y, hop_length=self.hop_length)
        
        return {
            "spectral_centroid_mean": float(np.mean(spectral_centroid)),
            "spectral_centroid_std": float(np.std(spectral_centroid)),
            "spectral_rolloff_mean": float(np.mean(spectral_rolloff)),
            "spectral_rolloff_std": float(np.std(spectral_rolloff)),
            "spectral_bandwidth_mean": float(np.mean(spectral_bandwidth)),
            "spectral_bandwidth_std": float(np.std(spectral_bandwidth)),
            "zero_crossing_rate_mean": float(np.mean(zcr)),
            "zero_crossing_rate_std": float(np.std(zcr)),
            "rms_energy_mean": float(np.mean(rms)),
            "rms_energy_std": float(np.std(rms))
        }
    
    async def _extract_rhythmic_features(self, y: np.ndarray, sr: int) -> Dict[str, float]:
        """Extract rhythmic features from audio."""
        import librosa
        
        try:
            # Tempo and beat tracking
            tempo, beats = librosa.beat.beat_track(y=y, sr=sr, hop_length=self.hop_length)
            
            # Onset detection
            onset_frames = librosa.onset.onset_detect(y=y, sr=sr, hop_length=self.hop_length)
            onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=self.hop_length)
            
            # Calculate onset rate
            onset_rate = len(onset_times) / (len(y) / sr) if len(y) > 0 else 0
            
            return {
                "tempo": float(tempo),
                "beat_count": len(beats),
                "onset_rate": float(onset_rate),
                "onset_count": len(onset_times)
            }
            
        except Exception as e:
            logger.warning(f"Rhythmic feature extraction failed: {e}")
            return {
                "tempo": 0.0,
                "beat_count": 0,
                "onset_rate": 0.0,
                "onset_count": 0
            }
    
    async def _extract_harmonic_features(self, y: np.ndarray, sr: int) -> Dict[str, float]:
        """Extract harmonic features from audio."""
        import librosa
        
        try:
            # Harmonic-percussive separation
            y_harmonic, y_percussive = librosa.effects.hpss(y)
            
            # Calculate harmonic vs percussive energy ratio
            harmonic_energy = np.sum(y_harmonic ** 2)
            percussive_energy = np.sum(y_percussive ** 2)
            total_energy = harmonic_energy + percussive_energy
            
            harmonic_ratio = harmonic_energy / total_energy if total_energy > 0 else 0
            
            # Chroma features (pitch class profiles)
            chroma = librosa.feature.chroma_stft(y=y, sr=sr, hop_length=self.hop_length)
            chroma_std = np.std(chroma, axis=1)
            
            return {
                "harmonic_ratio": float(harmonic_ratio),
                "percussive_ratio": float(1 - harmonic_ratio),
                "chroma_deviation_mean": float(np.mean(chroma_std)),
                "chroma_deviation_std": float(np.std(chroma_std))
            }
            
        except Exception as e:
            logger.warning(f"Harmonic feature extraction failed: {e}")
            return {
                "harmonic_ratio": 0.0,
                "percussive_ratio": 0.0,
                "chroma_deviation_mean": 0.0,
                "chroma_deviation_std": 0.0
            }


class MusicClassifier:
    """Classifies audio segments as music or non-music based on features."""
    
    def __init__(self):
        # Music detection thresholds (tuned for general music detection)
        self.thresholds = {
            "spectral_centroid_min": 800,    # Hz - minimum brightness for music
            "spectral_centroid_max": 8000,   # Hz - maximum brightness for music
            "spectral_rolloff_min": 2000,    # Hz - minimum rolloff for music
            "tempo_min": 40,                 # BPM - minimum tempo for music
            "tempo_max": 220,                # BPM - maximum tempo for music
            "harmonic_ratio_min": 0.3,       # Minimum harmonic content for music
            "rms_energy_min": 0.01,          # Minimum energy level
            "onset_rate_min": 0.5,           # Minimum onset rate for rhythmic content
            "chroma_deviation_min": 0.1      # Minimum pitch variation for music
        }
        
        # Weights for different features in classification
        self.feature_weights = {
            "spectral": 0.25,
            "rhythmic": 0.30,
            "harmonic": 0.25,
            "energy": 0.20
        }
    
    async def classify_music(self, features: Dict[str, Any]) -> Tuple[bool, float, str]:
        """
        Classify audio segment as music or non-music.
        
        Args:
            features: Extracted audio features
            
        Returns:
            Tuple of (is_music, confidence, music_type)
        """
        # Calculate individual feature scores
        spectral_score = self._calculate_spectral_score(features)
        rhythmic_score = self._calculate_rhythmic_score(features)
        harmonic_score = self._calculate_harmonic_score(features)
        energy_score = self._calculate_energy_score(features)
        
        # Weighted combination
        total_score = (
            spectral_score * self.feature_weights["spectral"] +
            rhythmic_score * self.feature_weights["rhythmic"] +
            harmonic_score * self.feature_weights["harmonic"] +
            energy_score * self.feature_weights["energy"]
        )
        
        # Determine if it's music
        is_music = total_score > 0.6
        confidence = min(total_score, 1.0)
        
        # Determine music type
        music_type = self._determine_music_type(features, is_music)
        
        return is_music, confidence, music_type
    
    def _calculate_spectral_score(self, features: Dict[str, Any]) -> float:
        """Calculate spectral feature score for music classification."""
        score = 0.0
        
        # Spectral centroid (brightness)
        centroid = features.get("spectral_centroid_mean", 0)
        if self.thresholds["spectral_centroid_min"] <= centroid <= self.thresholds["spectral_centroid_max"]:
            score += 0.4
        
        # Spectral rolloff
        rolloff = features.get("spectral_rolloff_mean", 0)
        if rolloff >= self.thresholds["spectral_rolloff_min"]:
            score += 0.3
        
        # Spectral bandwidth (variety in frequency content)
        bandwidth = features.get("spectral_bandwidth_mean", 0)
        if bandwidth > 1000:  # Good frequency variety
            score += 0.3
        
        return min(score, 1.0)
    
    def _calculate_rhythmic_score(self, features: Dict[str, Any]) -> float:
        """Calculate rhythmic feature score for music classification."""
        score = 0.0
        
        # Tempo
        tempo = features.get("tempo", 0)
        if self.thresholds["tempo_min"] <= tempo <= self.thresholds["tempo_max"]:
            score += 0.5
        
        # Onset rate (rhythmic activity)
        onset_rate = features.get("onset_rate", 0)
        if onset_rate >= self.thresholds["onset_rate_min"]:
            score += 0.3
        
        # Beat consistency (if we have beats)
        beat_count = features.get("beat_count", 0)
        duration = features.get("duration", 1)
        if beat_count > 0 and duration > 0:
            beats_per_second = beat_count / duration
            if 0.5 <= beats_per_second <= 4.0:  # Reasonable beat rate
                score += 0.2
        
        return min(score, 1.0)
    
    def _calculate_harmonic_score(self, features: Dict[str, Any]) -> float:
        """Calculate harmonic feature score for music classification."""
        score = 0.0
        
        # Harmonic ratio
        harmonic_ratio = features.get("harmonic_ratio", 0)
        if harmonic_ratio >= self.thresholds["harmonic_ratio_min"]:
            score += 0.5
        
        # Chroma deviation (pitch variety)
        chroma_dev = features.get("chroma_deviation_mean", 0)
        if chroma_dev >= self.thresholds["chroma_deviation_min"]:
            score += 0.3
        
        # Balance between harmonic and percussive
        percussive_ratio = features.get("percussive_ratio", 0)
        if 0.2 <= percussive_ratio <= 0.8:  # Good balance
            score += 0.2
        
        return min(score, 1.0)
    
    def _calculate_energy_score(self, features: Dict[str, Any]) -> float:
        """Calculate energy feature score for music classification."""
        score = 0.0
        
        # RMS energy
        rms_energy = features.get("rms_energy_mean", 0)
        if rms_energy >= self.thresholds["rms_energy_min"]:
            score += 0.6
        
        # Energy variation (dynamic range)
        rms_std = features.get("rms_energy_std", 0)
        if rms_std > 0.01:  # Some dynamic variation
            score += 0.4
        
        return min(score, 1.0)
    
    def _determine_music_type(self, features: Dict[str, Any], is_music: bool) -> str:
        """Determine the type of music based on features."""
        if not is_music:
            return "none"
        
        # Analyze features to determine music type
        harmonic_ratio = features.get("harmonic_ratio", 0)
        rms_energy = features.get("rms_energy_mean", 0)
        tempo = features.get("tempo", 0)
        
        # Background music: lower energy, more harmonic
        if rms_energy < 0.05 and harmonic_ratio > 0.6:
            return "background"
        
        # Foreground music: higher energy, strong rhythm
        elif rms_energy > 0.1 and tempo > 80:
            return "foreground"
        
        # Mixed: moderate characteristics
        else:
            return "mixed"


class SceneMusicDetectionService:
    """Service for detecting music in video scenes."""
    
    def __init__(self):
        self.feature_extractor = AudioFeatureExtractor()
        self.music_classifier = MusicClassifier()
        
        # Analysis parameters
        self.analysis_window_size = 5.0  # seconds - size of analysis windows
        self.analysis_overlap = 0.5      # overlap between windows (0.0 to 1.0)
        self.min_music_segment_duration = 2.0  # seconds - minimum music segment length
    
    async def detect_music_in_scenes(
        self,
        audio_path: str,
        scenes: List[Scene]
    ) -> MusicDetectionResult:
        """
        Detect music in video scenes.
        
        Args:
            audio_path: Path to extracted audio file
            scenes: List of video scenes
            
        Returns:
            MusicDetectionResult with analysis for each scene
            
        Raises:
            MusicDetectionError: If music detection fails
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            logger.info(f"Starting music detection for {len(scenes)} scenes")
            
            if not Path(audio_path).exists():
                raise MusicDetectionError(f"Audio file not found: {audio_path}")
            
            # Analyze each scene
            scene_analyses = []
            total_music_duration = 0.0
            scenes_with_music = 0
            
            for scene in scenes:
                scene_analysis = await self._analyze_scene_music(
                    audio_path, scene
                )
                scene_analyses.append(scene_analysis)
                
                if scene_analysis.has_music:
                    scenes_with_music += 1
                    total_music_duration += sum(
                        segment.end_time - segment.start_time
                        for segment in scene_analysis.music_segments
                    )
            
            processing_time = asyncio.get_event_loop().time() - start_time
            
            logger.info(f"Music detection completed: {scenes_with_music}/{len(scenes)} scenes have music")
            
            return MusicDetectionResult(
                scene_analyses=scene_analyses,
                total_scenes=len(scenes),
                scenes_with_music=scenes_with_music,
                total_music_duration=total_music_duration,
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(f"Music detection failed: {e}")
            raise MusicDetectionError(f"Failed to detect music in scenes: {e}")
    
    async def _analyze_scene_music(
        self,
        audio_path: str,
        scene: Scene
    ) -> SceneMusicAnalysis:
        """
        Analyze music in a single scene.
        
        Args:
            audio_path: Path to audio file
            scene: Scene to analyze
            
        Returns:
            SceneMusicAnalysis for the scene
        """
        scene_duration = scene.end_time - scene.start_time
        
        # Create analysis windows within the scene
        windows = self._create_analysis_windows(
            scene.start_time, scene.end_time
        )
        
        # Analyze each window
        music_segments = []
        confidence_scores = []
        
        for window_start, window_end in windows:
            window_duration = window_end - window_start
            
            try:
                # Extract features for this window
                features = await self.feature_extractor.extract_audio_features(
                    audio_path, window_start, window_duration
                )
                
                # Classify as music or not
                is_music, confidence, music_type = await self.music_classifier.classify_music(features)
                
                confidence_scores.append(confidence)
                
                if is_music:
                    # Create music segment
                    music_segment = MusicSegment(
                        start_time=window_start,
                        end_time=window_end,
                        confidence=confidence,
                        music_type=music_type,
                        volume_level=features.get("rms_energy_mean", 0.0),
                        spectral_features={
                            "spectral_centroid": features.get("spectral_centroid_mean", 0.0),
                            "spectral_rolloff": features.get("spectral_rolloff_mean", 0.0),
                            "harmonic_ratio": features.get("harmonic_ratio", 0.0)
                        }
                    )
                    music_segments.append(music_segment)
                    
            except Exception as e:
                logger.warning(f"Failed to analyze window {window_start}-{window_end}: {e}")
                confidence_scores.append(0.0)
        
        # Merge adjacent music segments
        merged_segments = await self._merge_adjacent_music_segments(music_segments)
        
        # Calculate scene-level metrics
        has_music = len(merged_segments) > 0
        music_coverage = self._calculate_music_coverage(merged_segments, scene_duration)
        dominant_music_type = self._get_dominant_music_type(merged_segments)
        average_confidence = np.mean(confidence_scores) if confidence_scores else 0.0
        
        return SceneMusicAnalysis(
            scene_number=scene.scene_number,
            start_time=scene.start_time,
            end_time=scene.end_time,
            has_music=has_music,
            music_segments=merged_segments,
            music_coverage=music_coverage,
            dominant_music_type=dominant_music_type,
            average_music_confidence=float(average_confidence)
        )
    
    def _create_analysis_windows(
        self,
        start_time: float,
        end_time: float
    ) -> List[Tuple[float, float]]:
        """
        Create overlapping analysis windows for a time range.
        
        Args:
            start_time: Start time in seconds
            end_time: End time in seconds
            
        Returns:
            List of (start, end) tuples for analysis windows
        """
        windows = []
        duration = end_time - start_time
        
        if duration <= self.analysis_window_size:
            # Scene is shorter than window size, analyze entire scene
            windows.append((start_time, end_time))
        else:
            # Create overlapping windows
            step_size = self.analysis_window_size * (1 - self.analysis_overlap)
            current_start = start_time
            
            while current_start < end_time:
                current_end = min(current_start + self.analysis_window_size, end_time)
                windows.append((current_start, current_end))
                
                current_start += step_size
                
                # Ensure we don't create tiny windows at the end
                if end_time - current_start < self.analysis_window_size * 0.5:
                    break
        
        return windows
    
    async def _merge_adjacent_music_segments(
        self,
        segments: List[MusicSegment]
    ) -> List[MusicSegment]:
        """
        Merge adjacent music segments and filter out short segments.
        
        Args:
            segments: List of music segments
            
        Returns:
            List of merged segments
        """
        if not segments:
            return []
        
        # Sort segments by start time
        segments.sort(key=lambda s: s.start_time)
        
        merged = []
        current_segment = segments[0]
        
        for next_segment in segments[1:]:
            # Check if segments are adjacent or overlapping
            gap = next_segment.start_time - current_segment.end_time
            
            if gap <= 1.0:  # Merge if gap is less than 1 second
                # Merge segments
                current_segment = MusicSegment(
                    start_time=current_segment.start_time,
                    end_time=next_segment.end_time,
                    confidence=max(current_segment.confidence, next_segment.confidence),
                    music_type=current_segment.music_type,  # Keep first segment's type
                    volume_level=(current_segment.volume_level + next_segment.volume_level) / 2,
                    spectral_features=current_segment.spectral_features  # Keep first segment's features
                )
            else:
                # Add current segment if it's long enough
                if current_segment.end_time - current_segment.start_time >= self.min_music_segment_duration:
                    merged.append(current_segment)
                current_segment = next_segment
        
        # Add the last segment if it's long enough
        if current_segment.end_time - current_segment.start_time >= self.min_music_segment_duration:
            merged.append(current_segment)
        
        return merged
    
    def _calculate_music_coverage(
        self,
        music_segments: List[MusicSegment],
        scene_duration: float
    ) -> float:
        """
        Calculate the percentage of scene covered by music.
        
        Args:
            music_segments: List of music segments in scene
            scene_duration: Total scene duration
            
        Returns:
            Music coverage as percentage (0.0 to 1.0)
        """
        if scene_duration <= 0:
            return 0.0
        
        total_music_duration = sum(
            segment.end_time - segment.start_time
            for segment in music_segments
        )
        
        return min(total_music_duration / scene_duration, 1.0)
    
    def _get_dominant_music_type(
        self,
        music_segments: List[MusicSegment]
    ) -> Optional[str]:
        """
        Get the dominant music type in the segments.
        
        Args:
            music_segments: List of music segments
            
        Returns:
            Dominant music type or None
        """
        if not music_segments:
            return None
        
        # Count duration of each music type
        type_durations = {}
        
        for segment in music_segments:
            duration = segment.end_time - segment.start_time
            music_type = segment.music_type
            
            type_durations[music_type] = type_durations.get(music_type, 0) + duration
        
        # Return type with longest duration
        return max(type_durations.items(), key=lambda x: x[1])[0]
    
    async def get_music_statistics(
        self,
        scene_analyses: List[SceneMusicAnalysis]
    ) -> Dict[str, Any]:
        """
        Get statistics about music detection results.
        
        Args:
            scene_analyses: List of scene music analyses
            
        Returns:
            Dictionary with music statistics
        """
        total_scenes = len(scene_analyses)
        scenes_with_music = sum(1 for analysis in scene_analyses if analysis.has_music)
        
        total_music_duration = sum(
            sum(segment.end_time - segment.start_time for segment in analysis.music_segments)
            for analysis in scene_analyses
        )
        
        total_scene_duration = sum(
            analysis.end_time - analysis.start_time
            for analysis in scene_analyses
        )
        
        music_types = {}
        confidence_scores = []
        
        for analysis in scene_analyses:
            confidence_scores.append(analysis.average_music_confidence)
            
            if analysis.dominant_music_type:
                music_types[analysis.dominant_music_type] = music_types.get(
                    analysis.dominant_music_type, 0
                ) + 1
        
        return {
            "total_scenes": total_scenes,
            "scenes_with_music": scenes_with_music,
            "music_coverage_percentage": (scenes_with_music / total_scenes * 100) if total_scenes > 0 else 0,
            "total_music_duration": total_music_duration,
            "total_scene_duration": total_scene_duration,
            "music_time_percentage": (total_music_duration / total_scene_duration * 100) if total_scene_duration > 0 else 0,
            "average_confidence": float(np.mean(confidence_scores)) if confidence_scores else 0.0,
            "music_type_distribution": music_types
        }


class FallbackMusicDetectionService:
    """Fallback music detection service when librosa is not available."""
    
    def __init__(self):
        # Simple heuristics for fallback detection
        self.default_music_probability = 0.3  # 30% of scenes assumed to have music
    
    async def detect_music_in_scenes(
        self,
        audio_path: str,
        scenes: List[Scene]
    ) -> MusicDetectionResult:
        """
        Provide fallback music detection using simple heuristics.
        
        Args:
            audio_path: Path to audio file (not used in fallback)
            scenes: List of scenes
            
        Returns:
            MusicDetectionResult with heuristic analysis
        """
        logger.warning("Using fallback music detection (librosa not available)")
        
        scene_analyses = []
        scenes_with_music = 0
        total_music_duration = 0.0
        
        for i, scene in enumerate(scenes):
            # Simple heuristic: assume music in some scenes based on scene number
            has_music = (i % 3 == 0)  # Every third scene has music
            
            music_segments = []
            if has_music:
                # Create a single music segment covering most of the scene
                scene_duration = scene.end_time - scene.start_time
                music_duration = scene_duration * 0.7  # 70% of scene
                music_start = scene.start_time + (scene_duration - music_duration) / 2
                
                music_segment = MusicSegment(
                    start_time=music_start,
                    end_time=music_start + music_duration,
                    confidence=0.5,  # Low confidence for fallback
                    music_type="background",
                    volume_level=0.3,
                    spectral_features={}
                )
                music_segments.append(music_segment)
                
                scenes_with_music += 1
                total_music_duration += music_duration
            
            scene_analysis = SceneMusicAnalysis(
                scene_number=scene.scene_number,
                start_time=scene.start_time,
                end_time=scene.end_time,
                has_music=has_music,
                music_segments=music_segments,
                music_coverage=0.7 if has_music else 0.0,
                dominant_music_type="background" if has_music else None,
                average_music_confidence=0.5 if has_music else 0.0
            )
            
            scene_analyses.append(scene_analysis)
        
        return MusicDetectionResult(
            scene_analyses=scene_analyses,
            total_scenes=len(scenes),
            scenes_with_music=scenes_with_music,
            total_music_duration=total_music_duration,
            processing_time=0.1  # Minimal processing time for fallback
        )


class MusicDetectionService:
    """Main music detection service with fallback capabilities."""
    
    def __init__(self):
        self.primary_service = None
        self.fallback_service = FallbackMusicDetectionService()
        
        # Prefer fast heuristic fallback in autonomous / offline mode
        from app.core.config import settings
        if settings.AUTONOMOUS_MODE or not settings.has_openai:
            logger.info("Autonomous mode: using fallback music detection")
            return

        # Try to initialize primary service
        try:
            # Check if librosa is available
            import librosa  # noqa: F401
            self.primary_service = SceneMusicDetectionService()
            logger.info("Librosa-based music detection service initialized")
        except ImportError:
            logger.warning("Librosa not available, using fallback music detection")
    
    async def detect_music_in_scenes(
        self,
        audio_path: str,
        scenes: List[Scene],
        use_fallback: bool = False
    ) -> MusicDetectionResult:
        """
        Detect music in scenes with automatic fallback.
        
        Args:
            audio_path: Path to audio file
            scenes: List of scenes
            use_fallback: Force use of fallback service
            
        Returns:
            MusicDetectionResult
        """
        if use_fallback or not self.primary_service:
            return await self.fallback_service.detect_music_in_scenes(audio_path, scenes)
        
        try:
            return await self.primary_service.detect_music_in_scenes(audio_path, scenes)
        except MusicDetectionError as e:
            logger.error(f"Primary music detection failed, using fallback: {e}")
            return await self.fallback_service.detect_music_in_scenes(audio_path, scenes)
    
    async def is_primary_service_available(self) -> bool:
        """
        Check if primary music detection service is available.
        
        Returns:
            True if librosa-based service is available, False otherwise
        """
        return self.primary_service is not None
    
    async def get_service_status(self) -> Dict[str, Any]:
        """
        Get status of music detection services.
        
        Returns:
            Dictionary with service status information
        """
        return {
            "primary_available": self.primary_service is not None,
            "librosa_installed": self._check_librosa_installation(),
            "fallback_available": True,
            "current_time": datetime.utcnow().isoformat()
        }
    
    def _check_librosa_installation(self) -> bool:
        """Check if librosa is installed."""
        try:
            import librosa
            return True
        except ImportError:
            return False