"""
GPT-5-mini visual analysis integration service.

This service integrates keyframe extraction with GPT-5-mini visual analysis
using the professional montage assistant prompt system.
"""

import asyncio
import base64
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
import aiohttp
import json
from dataclasses import dataclass

from app.services.keyframe_extraction import KeyframeExtractionService, Keyframe, Scene
from app.services.visual_analysis import (
    MontageAssistantPromptSystem, 
    VisualAnalysisResult,
    ShotType,
    SpecialTag
)

logger = logging.getLogger(__name__)


@dataclass
class SceneAnalysisResult:
    """Complete analysis result for a scene including keyframes and visual analysis."""
    scene_index: int
    scene: Scene
    keyframes: List[Keyframe]
    visual_analysis: VisualAnalysisResult
    raw_gpt_response: Optional[str] = None
    processing_time: float = 0.0


class GPTVisualAnalysisService:
    """Service for integrating GPT visual analysis with keyframe extraction.
    
    Works without OPENAI_API_KEY — uses rule-based fallback analysis.
    """
    
    def __init__(
        self, 
        openai_api_key: Optional[str] = None,
        keyframe_service: Optional[KeyframeExtractionService] = None,
        prompt_system: Optional[MontageAssistantPromptSystem] = None
    ):
        """
        Initialize the GPT visual analysis service.
        
        Args:
            openai_api_key: OpenAI API key (optional — enables GPT path)
            keyframe_service: Optional keyframe extraction service instance
            prompt_system: Optional prompt system instance
        """
        from app.core.config import settings
        self.api_key = openai_api_key if openai_api_key is not None else (settings.OPENAI_API_KEY or "")
        self.use_gpt = bool(self.api_key and self.api_key not in ("", "your_openai_token_here", "changeme"))
        self.keyframe_service = keyframe_service or KeyframeExtractionService()
        self.prompt_system = prompt_system or MontageAssistantPromptSystem()
        self.base_url = "https://api.openai.com/v1/chat/completions"
        if not self.use_gpt:
            logger.warning("OPENAI_API_KEY not set — visual analysis will use offline fallback")
    
    async def analyze_scenes(
        self,
        video_path: str,
        scenes: List[Scene],
        task_id: str,
        dialogue_mapping: Optional[Dict[int, str]] = None,
    ) -> List[SceneAnalysisResult]:
        """Adapter used by PipelineOrchestrator."""
        return await self.analyze_scenes_with_visual_analysis(
            video_path=video_path,
            scenes=scenes,
            task_id=task_id,
            dialogue_mapping=dialogue_mapping,
        )
        
    async def analyze_scenes_with_visual_analysis(
        self,
        video_path: str,
        scenes: List[Scene],
        task_id: str,
        dialogue_mapping: Optional[Dict[int, str]] = None
    ) -> List[SceneAnalysisResult]:
        """
        Analyze all scenes with keyframe extraction and GPT-5-mini visual analysis.
        
        Args:
            video_path: Path to the video file
            scenes: List of scenes to analyze
            task_id: Unique task identifier
            dialogue_mapping: Optional mapping of scene index to dialogue text
            
        Returns:
            List of complete scene analysis results
        """
        # Extract keyframes for all scenes
        logger.info(f"Extracting keyframes for {len(scenes)} scenes")
        keyframes = await self.keyframe_service.extract_keyframes_from_scenes(
            video_path, scenes, task_id
        )
        
        # Group keyframes by scene
        keyframes_by_scene = self._group_keyframes_by_scene(keyframes)
        
        # Analyze each scene
        analysis_results = []
        for i, scene in enumerate(scenes):
            try:
                scene_keyframes = keyframes_by_scene.get(i, [])
                dialogue = dialogue_mapping.get(i) if dialogue_mapping else None
                
                result = await self._analyze_single_scene(
                    scene, scene_keyframes, i, dialogue
                )
                analysis_results.append(result)
                
                logger.info(f"Completed analysis for scene {i}")
                
            except Exception as e:
                logger.error(f"Failed to analyze scene {i}: {e}")
                # Create fallback result
                fallback_result = self._create_fallback_analysis(scene, i, scene_keyframes)
                analysis_results.append(fallback_result)
                
        return analysis_results
    
    def _group_keyframes_by_scene(self, keyframes: List[Keyframe]) -> Dict[int, List[Keyframe]]:
        """
        Group keyframes by scene index.
        
        Args:
            keyframes: List of all keyframes
            
        Returns:
            Dictionary mapping scene index to list of keyframes
        """
        grouped = {}
        for keyframe in keyframes:
            scene_idx = keyframe.scene_index
            if scene_idx not in grouped:
                grouped[scene_idx] = []
            grouped[scene_idx].append(keyframe)
        
        # Sort keyframes within each scene by position percentage
        for scene_keyframes in grouped.values():
            scene_keyframes.sort(key=lambda k: k.position_percent)
            
        return grouped
    
    async def _analyze_single_scene(
        self,
        scene: Scene,
        keyframes: List[Keyframe],
        scene_index: int,
        dialogue: Optional[str] = None
    ) -> SceneAnalysisResult:
        """
        Analyze a single scene with GPT-5-mini visual analysis.
        
        Args:
            scene: Scene object with timing information
            keyframes: List of keyframes for this scene
            scene_index: Index of the scene
            dialogue: Optional dialogue text for the scene
            
        Returns:
            Complete scene analysis result
        """
        import time
        start_time = time.time()
        
        if not self.use_gpt:
            return self._create_fallback_analysis(scene, scene_index, keyframes)
        
        if len(keyframes) < 2:
            logger.warning(f"Scene {scene_index} has insufficient keyframes ({len(keyframes)})")
            return self._create_fallback_analysis(scene, scene_index, keyframes)
        
        # Get the 35% and 70% keyframes
        keyframe_35 = next((k for k in keyframes if k.position_percent == 35.0), None)
        keyframe_70 = next((k for k in keyframes if k.position_percent == 70.0), None)
        
        if not keyframe_35 or not keyframe_70:
            logger.warning(f"Scene {scene_index} missing required keyframes")
            return self._create_fallback_analysis(scene, scene_index, keyframes)
        
        try:
            # Perform GPT-5-mini analysis
            gpt_response = await self._call_gpt_vision_api(keyframe_35, keyframe_70)
            
            # Parse and validate response
            json_data = self.prompt_system.validate_json_response(gpt_response)
            if not json_data:
                logger.error(f"Invalid GPT response for scene {scene_index}")
                return self._create_fallback_analysis(scene, scene_index, keyframes)
            
            # Create visual analysis result
            visual_analysis = self.prompt_system.create_analysis_result(json_data, dialogue)
            
            processing_time = time.time() - start_time
            
            return SceneAnalysisResult(
                scene_index=scene_index,
                scene=scene,
                keyframes=keyframes,
                visual_analysis=visual_analysis,
                raw_gpt_response=gpt_response,
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(f"GPT analysis failed for scene {scene_index}: {e}")
            return self._create_fallback_analysis(scene, scene_index, keyframes)
    
    async def _call_gpt_vision_api(
        self, 
        keyframe_35: Keyframe, 
        keyframe_70: Keyframe
    ) -> str:
        """
        Call GPT-5-mini vision API with dual keyframes and health monitoring.
        
        Args:
            keyframe_35: Keyframe at 35% position
            keyframe_70: Keyframe at 70% position
            
        Returns:
            Raw GPT response text
        """
        # Import health monitor
        from app.core.health_monitor import health_monitor
        
        # Use health monitor to check service availability
        async with health_monitor.with_fallback("openai") as fallback:
            if fallback.should_use_fallback():
                logger.warning("OpenAI service unhealthy, cannot perform GPT vision analysis")
                raise Exception("OpenAI service unavailable")
            
            # Encode images to base64
            image_35_b64 = await self._encode_image_to_base64(keyframe_35.file_path)
            image_70_b64 = await self._encode_image_to_base64(keyframe_70.file_path)
            
            # Prepare API request
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "gpt-4o-mini",  # Using GPT-4o-mini as GPT-5-mini equivalent
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": self.prompt_system.get_scene_analysis_prompt()
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_35_b64}",
                                    "detail": "high"
                                }
                            },
                            {
                                "type": "image_url", 
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_70_b64}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 500,
                "temperature": 0.1  # Low temperature for consistent analysis
            }
            
            # Make API call with retry logic
            return await self._make_api_call_with_retry(headers, payload)
    
    async def _encode_image_to_base64(self, image_path: str) -> str:
        """
        Encode image file to base64 string.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Base64 encoded image string
        """
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to encode image {image_path}: {e}")
            raise
    
    async def _make_api_call_with_retry(
        self, 
        headers: Dict[str, str], 
        payload: Dict[str, Any],
        max_retries: int = 3
    ) -> str:
        """
        Make API call with exponential backoff retry logic.
        
        Args:
            headers: HTTP headers for the request
            payload: Request payload
            max_retries: Maximum number of retry attempts
            
        Returns:
            GPT response text
        """
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.base_url, 
                        headers=headers, 
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=60)
                    ) as response:
                        
                        if response.status == 200:
                            data = await response.json()
                            return data["choices"][0]["message"]["content"]
                        
                        elif response.status == 429:  # Rate limit
                            error_data = await response.json()
                            retry_after = self._parse_retry_after(error_data)
                            
                            if attempt < max_retries - 1:
                                logger.warning(f"Rate limited, retrying after {retry_after}s")
                                await asyncio.sleep(retry_after)
                                continue
                            else:
                                raise Exception(f"Rate limit exceeded after {max_retries} attempts")
                        
                        else:
                            error_text = await response.text()
                            raise Exception(f"API call failed with status {response.status}: {error_text}")
                            
            except asyncio.TimeoutError:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"API call timeout, retrying in {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise Exception("API call timed out after all retry attempts")
            
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"API call failed: {e}, retrying in {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise
        
        raise Exception("All retry attempts failed")
    
    def _parse_retry_after(self, error_data: Dict[str, Any]) -> float:
        """
        Parse retry delay from OpenAI error response.
        
        Args:
            error_data: Error response from OpenAI API
            
        Returns:
            Delay in seconds
        """
        try:
            error_message = error_data.get("error", {}).get("message", "")
            
            # Look for "try again in X seconds" pattern
            import re
            match = re.search(r'try again in (\d+(?:\.\d+)?) seconds?', error_message)
            if match:
                return float(match.group(1))
            
            # Default retry delay
            return 5.0
            
        except Exception:
            return 5.0  # Default fallback
    
    def _create_fallback_analysis(
        self, 
        scene: Scene, 
        scene_index: int, 
        keyframes: List[Keyframe]
    ) -> SceneAnalysisResult:
        """
        Create a fallback analysis result when GPT analysis fails.
        
        Args:
            scene: Scene object
            scene_index: Index of the scene
            keyframes: Available keyframes
            
        Returns:
            Fallback scene analysis result
        """
        fallback_visual = VisualAnalysisResult(
            shot_type=ShotType.MEDIUM,  # Default to medium shot
            description="Сцена требует ручного анализа",
            confidence_score=0.0
        )
        
        return SceneAnalysisResult(
            scene_index=scene_index,
            scene=scene,
            keyframes=keyframes,
            visual_analysis=fallback_visual,
            raw_gpt_response=None,
            processing_time=0.0
        )
    
    def format_results_for_montage_table(
        self, 
        analysis_results: List[SceneAnalysisResult]
    ) -> List[Dict[str, Any]]:
        """
        Format analysis results for montage table integration.
        
        Args:
            analysis_results: List of scene analysis results
            
        Returns:
            List of formatted montage table rows
        """
        montage_rows = []
        
        for result in analysis_results:
            # Format visual analysis for montage
            formatted_analysis = self.prompt_system.format_analysis_for_montage(
                result.visual_analysis
            )
            
            # Create montage row
            row = {
                "scene_index": result.scene_index,
                "start_time": result.scene.start_time,
                "end_time": result.scene.end_time,
                "duration": result.scene.duration,
                "shot_type": formatted_analysis["shot_type"],
                "description": formatted_analysis["description"],
                "text_in_frame": formatted_analysis["text_in_frame"],
                "special_tags": formatted_analysis["special_tags"],
                "confidence_score": formatted_analysis["confidence_score"],
                "keyframes": [kf.file_path for kf in result.keyframes],
                "processing_time": result.processing_time
            }
            
            montage_rows.append(row)
        
        return montage_rows
    
    async def cleanup_analysis_files(self, task_id: str) -> None:
        """
        Clean up analysis files for a specific task.
        
        Args:
            task_id: Task identifier for cleanup
        """
        try:
            self.keyframe_service.cleanup_keyframes(task_id)
            logger.info(f"Cleaned up analysis files for task {task_id}")
        except Exception as e:
            logger.error(f"Failed to cleanup analysis files for task {task_id}: {e}")
    
    def get_analysis_statistics(
        self, 
        analysis_results: List[SceneAnalysisResult]
    ) -> Dict[str, Any]:
        """
        Get statistics about the analysis results.
        
        Args:
            analysis_results: List of scene analysis results
            
        Returns:
            Dictionary with analysis statistics
        """
        if not analysis_results:
            return {}
        
        # Count shot types
        shot_type_counts = {}
        special_tag_counts = {}
        total_processing_time = 0.0
        successful_analyses = 0
        
        for result in analysis_results:
            # Count shot types
            shot_type = result.visual_analysis.shot_type.value
            shot_type_counts[shot_type] = shot_type_counts.get(shot_type, 0) + 1
            
            # Count special tags
            for tag in result.visual_analysis.special_tags:
                tag_value = tag.value
                special_tag_counts[tag_value] = special_tag_counts.get(tag_value, 0) + 1
            
            # Accumulate processing time
            total_processing_time += result.processing_time
            
            # Count successful analyses (confidence > 0)
            if result.visual_analysis.confidence_score > 0:
                successful_analyses += 1
        
        return {
            "total_scenes": len(analysis_results),
            "successful_analyses": successful_analyses,
            "success_rate": successful_analyses / len(analysis_results),
            "total_processing_time": total_processing_time,
            "average_processing_time": total_processing_time / len(analysis_results),
            "shot_type_distribution": shot_type_counts,
            "special_tag_distribution": special_tag_counts
        }