"""
Integration tests for GPT visual analysis service.
"""

import pytest
import asyncio
import tempfile
import json
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from app.services.gpt_visual_analysis import (
    GPTVisualAnalysisService,
    SceneAnalysisResult
)
from app.services.keyframe_extraction import (
    KeyframeExtractionService,
    Keyframe,
    Scene
)
from app.services.visual_analysis import (
    MontageAssistantPromptSystem,
    VisualAnalysisResult,
    ShotType,
    SpecialTag
)


@pytest.fixture
def mock_openai_api_key():
    """Mock OpenAI API key."""
    return "test-api-key-12345"


@pytest.fixture
def sample_scenes():
    """Create sample scenes for testing."""
    return [
        Scene(start_time=0.0, end_time=10.0, duration=10.0),
        Scene(start_time=10.0, end_time=25.0, duration=15.0),
        Scene(start_time=25.0, end_time=30.0, duration=5.0)
    ]


@pytest.fixture
def sample_keyframes():
    """Create sample keyframes for testing."""
    return [
        Keyframe(0, 35.0, 3.5, "/path/to/scene_000_35pct.jpg", 0.8),
        Keyframe(0, 70.0, 7.0, "/path/to/scene_000_70pct.jpg", 0.9),
        Keyframe(1, 35.0, 15.25, "/path/to/scene_001_35pct.jpg", 0.7),
        Keyframe(1, 70.0, 20.5, "/path/to/scene_001_70pct.jpg", 0.8),
        Keyframe(2, 35.0, 26.75, "/path/to/scene_002_35pct.jpg", 0.9),
        Keyframe(2, 70.0, 28.5, "/path/to/scene_002_70pct.jpg", 0.8)
    ]


@pytest.fixture
def gpt_service(mock_openai_api_key):
    """Create GPT visual analysis service with mocked dependencies."""
    mock_keyframe_service = Mock(spec=KeyframeExtractionService)
    mock_prompt_system = Mock(spec=MontageAssistantPromptSystem)
    
    return GPTVisualAnalysisService(
        openai_api_key=mock_openai_api_key,
        keyframe_service=mock_keyframe_service,
        prompt_system=mock_prompt_system
    )


class TestGPTVisualAnalysisService:
    """Test GPTVisualAnalysisService functionality."""
    
    def test_initialization(self, mock_openai_api_key):
        """Test service initialization."""
        service = GPTVisualAnalysisService(openai_api_key=mock_openai_api_key)
        
        assert service.api_key == mock_openai_api_key
        assert service.base_url == "https://api.openai.com/v1/chat/completions"
        assert isinstance(service.keyframe_service, KeyframeExtractionService)
        assert isinstance(service.prompt_system, MontageAssistantPromptSystem)
    
    def test_group_keyframes_by_scene(self, gpt_service, sample_keyframes):
        """Test grouping keyframes by scene index."""
        grouped = gpt_service._group_keyframes_by_scene(sample_keyframes)
        
        assert len(grouped) == 3  # 3 scenes
        assert len(grouped[0]) == 2  # 2 keyframes per scene
        assert len(grouped[1]) == 2
        assert len(grouped[2]) == 2
        
        # Check sorting by position percentage
        assert grouped[0][0].position_percent == 35.0
        assert grouped[0][1].position_percent == 70.0
    
    def test_group_keyframes_empty_list(self, gpt_service):
        """Test grouping empty keyframes list."""
        grouped = gpt_service._group_keyframes_by_scene([])
        assert grouped == {}
    
    @pytest.mark.asyncio
    async def test_analyze_scenes_with_visual_analysis_success(
        self, 
        gpt_service, 
        sample_scenes, 
        sample_keyframes
    ):
        """Test successful scene analysis with visual analysis."""
        video_path = "test_video.mp4"
        task_id = "test_task_123"
        dialogue_mapping = {
            0: "Привет, как дела?",
            1: "Все хорошо, спасибо",
            2: None
        }
        
        # Mock keyframe extraction
        gpt_service.keyframe_service.extract_keyframes_from_scenes = AsyncMock(
            return_value=sample_keyframes
        )
        
        # Mock single scene analysis
        mock_results = []
        for i, scene in enumerate(sample_scenes):
            mock_result = SceneAnalysisResult(
                scene_index=i,
                scene=scene,
                keyframes=[kf for kf in sample_keyframes if kf.scene_index == i],
                visual_analysis=VisualAnalysisResult(
                    shot_type=ShotType.MEDIUM,
                    description=f"Тестовое описание сцены {i}",
                    confidence_score=0.8
                ),
                processing_time=1.5
            )
            mock_results.append(mock_result)
        
        with patch.object(gpt_service, '_analyze_single_scene') as mock_analyze:
            mock_analyze.side_effect = mock_results
            
            results = await gpt_service.analyze_scenes_with_visual_analysis(
                video_path, sample_scenes, task_id, dialogue_mapping
            )
        
        assert len(results) == 3
        assert all(isinstance(r, SceneAnalysisResult) for r in results)
        assert mock_analyze.call_count == 3
        
        # Verify keyframe extraction was called
        gpt_service.keyframe_service.extract_keyframes_from_scenes.assert_called_once_with(
            video_path, sample_scenes, task_id
        )
    
    @pytest.mark.asyncio
    async def test_analyze_scenes_with_failures(
        self, 
        gpt_service, 
        sample_scenes, 
        sample_keyframes
    ):
        """Test scene analysis with some failures."""
        video_path = "test_video.mp4"
        task_id = "test_task_456"
        
        # Mock keyframe extraction
        gpt_service.keyframe_service.extract_keyframes_from_scenes = AsyncMock(
            return_value=sample_keyframes
        )
        
        # Mock mixed success/failure
        def mock_analyze_side_effect(scene, keyframes, scene_index, dialogue):
            if scene_index == 1:  # Simulate failure for scene 1
                raise Exception("GPT API error")
            
            return SceneAnalysisResult(
                scene_index=scene_index,
                scene=scene,
                keyframes=keyframes,
                visual_analysis=VisualAnalysisResult(
                    shot_type=ShotType.MEDIUM,
                    description=f"Описание сцены {scene_index}",
                    confidence_score=0.8 if scene_index != 1 else 0.0
                ),
                processing_time=1.0
            )
        
        with patch.object(gpt_service, '_analyze_single_scene') as mock_analyze:
            with patch.object(gpt_service, '_create_fallback_analysis') as mock_fallback:
                mock_analyze.side_effect = mock_analyze_side_effect
                mock_fallback.return_value = SceneAnalysisResult(
                    scene_index=1,
                    scene=sample_scenes[1],
                    keyframes=[],
                    visual_analysis=VisualAnalysisResult(
                        shot_type=ShotType.MEDIUM,
                        description="Сцена требует ручного анализа",
                        confidence_score=0.0
                    ),
                    processing_time=0.0
                )
                
                results = await gpt_service.analyze_scenes_with_visual_analysis(
                    video_path, sample_scenes, task_id
                )
        
        assert len(results) == 3
        assert mock_fallback.call_count == 1  # Called once for failed scene
    
    @pytest.mark.asyncio
    async def test_analyze_single_scene_success(self, gpt_service):
        """Test successful single scene analysis."""
        scene = Scene(start_time=0.0, end_time=10.0, duration=10.0)
        keyframes = [
            Keyframe(0, 35.0, 3.5, "/path/to/scene_000_35pct.jpg", 0.8),
            Keyframe(0, 70.0, 7.0, "/path/to/scene_000_70pct.jpg", 0.9)
        ]
        scene_index = 0
        dialogue = "Тестовый диалог"
        
        # Mock GPT API call
        mock_gpt_response = '''
        {
            "shot_type": "Ср.",
            "description": "Человек работает за компьютером",
            "text_in_frame": null
        }
        '''
        
        # Mock prompt system methods
        gpt_service.prompt_system.validate_json_response.return_value = {
            "shot_type": "Ср.",
            "description": "Человек работает за компьютером",
            "text_in_frame": None
        }
        
        gpt_service.prompt_system.create_analysis_result.return_value = VisualAnalysisResult(
            shot_type=ShotType.MEDIUM,
            description="Человек работает за компьютером",
            confidence_score=0.9
        )
        
        with patch.object(gpt_service, '_call_gpt_vision_api', return_value=mock_gpt_response):
            result = await gpt_service._analyze_single_scene(
                scene, keyframes, scene_index, dialogue
            )
        
        assert isinstance(result, SceneAnalysisResult)
        assert result.scene_index == 0
        assert result.scene == scene
        assert result.keyframes == keyframes
        assert result.visual_analysis.shot_type == ShotType.MEDIUM
        assert result.processing_time > 0
    
    @pytest.mark.asyncio
    async def test_analyze_single_scene_insufficient_keyframes(self, gpt_service):
        """Test single scene analysis with insufficient keyframes."""
        scene = Scene(start_time=0.0, end_time=10.0, duration=10.0)
        keyframes = [Keyframe(0, 35.0, 3.5, "/path/to/scene_000_35pct.jpg", 0.8)]  # Only one keyframe
        scene_index = 0
        
        with patch.object(gpt_service, '_create_fallback_analysis') as mock_fallback:
            mock_fallback.return_value = SceneAnalysisResult(
                scene_index=0,
                scene=scene,
                keyframes=keyframes,
                visual_analysis=VisualAnalysisResult(
                    shot_type=ShotType.MEDIUM,
                    description="Сцена требует ручного анализа",
                    confidence_score=0.0
                ),
                processing_time=0.0
            )
            
            result = await gpt_service._analyze_single_scene(
                scene, keyframes, scene_index
            )
        
        assert result.visual_analysis.confidence_score == 0.0
        mock_fallback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_call_gpt_vision_api_success(self, gpt_service):
        """Test successful GPT vision API call."""
        keyframe_35 = Keyframe(0, 35.0, 3.5, "/path/to/test_35.jpg", 0.8)
        keyframe_70 = Keyframe(0, 70.0, 7.0, "/path/to/test_70.jpg", 0.9)
        
        mock_response = '''
        {
            "shot_type": "Кр.",
            "description": "Лицо человека крупным планом",
            "text_in_frame": null
        }
        '''
        
        # Mock image encoding
        with patch.object(gpt_service, '_encode_image_to_base64') as mock_encode:
            mock_encode.return_value = "base64_encoded_image_data"
            
            # Mock API call
            with patch.object(gpt_service, '_make_api_call_with_retry') as mock_api:
                mock_api.return_value = mock_response
                
                # Mock prompt system
                gpt_service.prompt_system.get_scene_analysis_prompt.return_value = "Test prompt"
                
                result = await gpt_service._call_gpt_vision_api(keyframe_35, keyframe_70)
        
        assert result == mock_response
        assert mock_encode.call_count == 2  # Called for both keyframes
        mock_api.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_encode_image_to_base64_success(self, gpt_service):
        """Test successful image encoding to base64."""
        # Create a temporary image file
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
            temp_file.write(b"fake_image_data")
            temp_path = temp_file.name
        
        try:
            result = await gpt_service._encode_image_to_base64(temp_path)
            
            # Verify base64 encoding
            import base64
            decoded = base64.b64decode(result)
            assert decoded == b"fake_image_data"
            
        finally:
            Path(temp_path).unlink()  # Clean up
    
    @pytest.mark.asyncio
    async def test_encode_image_to_base64_file_not_found(self, gpt_service):
        """Test image encoding with non-existent file."""
        with pytest.raises(Exception):
            await gpt_service._encode_image_to_base64("/nonexistent/path.jpg")
    
    @pytest.mark.asyncio
    async def test_make_api_call_with_retry_success(self, gpt_service):
        """Test successful API call with retry logic."""
        headers = {"Authorization": "Bearer test-key"}
        payload = {"model": "gpt-4o-mini", "messages": []}
        
        mock_response_data = {
            "choices": [
                {
                    "message": {
                        "content": "Test response"
                    }
                }
            ]
        }
        
        # Mock aiohttp session and response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_response_data)
        
        mock_post_context = AsyncMock()
        mock_post_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post_context)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await gpt_service._make_api_call_with_retry(headers, payload)
        
        assert result == "Test response"
    
    @pytest.mark.asyncio
    async def test_make_api_call_with_retry_rate_limit(self, gpt_service):
        """Test API call with rate limit handling."""
        headers = {"Authorization": "Bearer test-key"}
        payload = {"model": "gpt-4o-mini", "messages": []}
        
        # Mock rate limit response
        rate_limit_response = AsyncMock()
        rate_limit_response.status = 429
        rate_limit_response.json = AsyncMock(return_value={
            "error": {
                "message": "Rate limit exceeded. Please try again in 5 seconds."
            }
        })
        
        # Mock successful response after retry
        success_response = AsyncMock()
        success_response.status = 200
        success_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "Success after retry"}}]
        })
        
        # Create context managers for both responses
        rate_limit_context = AsyncMock()
        rate_limit_context.__aenter__ = AsyncMock(return_value=rate_limit_response)
        rate_limit_context.__aexit__ = AsyncMock(return_value=None)
        
        success_context = AsyncMock()
        success_context.__aenter__ = AsyncMock(return_value=success_response)
        success_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = AsyncMock()
        mock_session.post = Mock(side_effect=[rate_limit_context, success_context])
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            with patch('asyncio.sleep') as mock_sleep:  # Speed up test
                result = await gpt_service._make_api_call_with_retry(headers, payload)
        
        assert result == "Success after retry"
        mock_sleep.assert_called_once_with(5.0)  # Should parse retry delay
    
    def test_parse_retry_after_with_message(self, gpt_service):
        """Test parsing retry delay from error message."""
        error_data = {
            "error": {
                "message": "Rate limit exceeded. Please try again in 10.5 seconds."
            }
        }
        
        delay = gpt_service._parse_retry_after(error_data)
        assert delay == 10.5
    
    def test_parse_retry_after_no_message(self, gpt_service):
        """Test parsing retry delay with no specific message."""
        error_data = {"error": {"message": "Generic error"}}
        
        delay = gpt_service._parse_retry_after(error_data)
        assert delay == 5.0  # Default delay
    
    def test_create_fallback_analysis(self, gpt_service):
        """Test creating fallback analysis result."""
        scene = Scene(start_time=0.0, end_time=10.0, duration=10.0)
        scene_index = 1
        keyframes = []
        
        result = gpt_service._create_fallback_analysis(scene, scene_index, keyframes)
        
        assert isinstance(result, SceneAnalysisResult)
        assert result.scene_index == 1
        assert result.scene == scene
        assert result.keyframes == keyframes
        assert result.visual_analysis.shot_type == ShotType.MEDIUM
        assert result.visual_analysis.description == "Сцена требует ручного анализа"
        assert result.visual_analysis.confidence_score == 0.0
        assert result.processing_time == 0.0
    
    def test_format_results_for_montage_table(self, gpt_service, sample_scenes):
        """Test formatting analysis results for montage table."""
        # Create sample analysis results
        analysis_results = []
        for i, scene in enumerate(sample_scenes):
            result = SceneAnalysisResult(
                scene_index=i,
                scene=scene,
                keyframes=[],
                visual_analysis=VisualAnalysisResult(
                    shot_type=ShotType.MEDIUM,
                    description=f"Описание сцены {i}",
                    special_tags=[SpecialTag.TEXT_OVERLAY] if i == 0 else [],
                    confidence_score=0.8
                ),
                processing_time=1.5
            )
            analysis_results.append(result)
        
        # Mock prompt system formatting
        def mock_format_for_montage(analysis):
            return {
                "shot_type": "Ср." + (" (НДП)" if analysis.special_tags else ""),
                "description": analysis.description,
                "text_in_frame": None,
                "special_tags": [tag.value for tag in analysis.special_tags],
                "confidence_score": analysis.confidence_score
            }
        
        gpt_service.prompt_system.format_analysis_for_montage.side_effect = mock_format_for_montage
        
        formatted = gpt_service.format_results_for_montage_table(analysis_results)
        
        assert len(formatted) == 3
        assert all("scene_index" in row for row in formatted)
        assert all("start_time" in row for row in formatted)
        assert all("shot_type" in row for row in formatted)
        assert formatted[0]["shot_type"] == "Ср. (НДП)"  # Has special tag
        assert formatted[1]["shot_type"] == "Ср."        # No special tags
    
    @pytest.mark.asyncio
    async def test_cleanup_analysis_files(self, gpt_service):
        """Test cleanup of analysis files."""
        task_id = "test_task_cleanup"
        
        # Mock keyframe service cleanup
        gpt_service.keyframe_service.cleanup_keyframes = Mock()
        
        await gpt_service.cleanup_analysis_files(task_id)
        
        gpt_service.keyframe_service.cleanup_keyframes.assert_called_once_with(task_id)
    
    def test_get_analysis_statistics(self, gpt_service):
        """Test getting analysis statistics."""
        # Create sample analysis results with various shot types and tags
        analysis_results = [
            SceneAnalysisResult(
                scene_index=0,
                scene=Scene(0, 10, 10),
                keyframes=[],
                visual_analysis=VisualAnalysisResult(
                    shot_type=ShotType.MEDIUM,
                    description="Test",
                    special_tags=[SpecialTag.TEXT_OVERLAY],
                    confidence_score=0.8
                ),
                processing_time=1.5
            ),
            SceneAnalysisResult(
                scene_index=1,
                scene=Scene(10, 20, 10),
                keyframes=[],
                visual_analysis=VisualAnalysisResult(
                    shot_type=ShotType.CLOSE,
                    description="Test",
                    special_tags=[SpecialTag.DARKENING, SpecialTag.TEXT_OVERLAY],
                    confidence_score=0.9
                ),
                processing_time=2.0
            ),
            SceneAnalysisResult(
                scene_index=2,
                scene=Scene(20, 30, 10),
                keyframes=[],
                visual_analysis=VisualAnalysisResult(
                    shot_type=ShotType.MEDIUM,
                    description="Test",
                    special_tags=[],
                    confidence_score=0.0  # Failed analysis
                ),
                processing_time=0.5
            )
        ]
        
        stats = gpt_service.get_analysis_statistics(analysis_results)
        
        assert stats["total_scenes"] == 3
        assert stats["successful_analyses"] == 2  # Two with confidence > 0
        assert stats["success_rate"] == 2/3
        assert stats["total_processing_time"] == 4.0
        assert stats["average_processing_time"] == 4.0/3
        assert stats["shot_type_distribution"]["Средний"] == 2
        assert stats["shot_type_distribution"]["Крупный"] == 1
        assert stats["special_tag_distribution"]["НДП"] == 2
        assert stats["special_tag_distribution"]["ЗТМ"] == 1
    
    def test_get_analysis_statistics_empty(self, gpt_service):
        """Test getting statistics for empty results."""
        stats = gpt_service.get_analysis_statistics([])
        assert stats == {}


@pytest.mark.integration
class TestGPTVisualAnalysisIntegration:
    """Integration tests for complete GPT visual analysis workflow."""
    
    @pytest.mark.asyncio
    async def test_complete_analysis_workflow_mock(self, mock_openai_api_key):
        """Test complete analysis workflow with mocked external dependencies."""
        # This test would require real integration with OpenAI API
        # For now, we test the workflow structure with mocks
        
        service = GPTVisualAnalysisService(openai_api_key=mock_openai_api_key)
        
        # Verify service is properly initialized for integration
        assert service.api_key == mock_openai_api_key
        assert hasattr(service, 'keyframe_service')
        assert hasattr(service, 'prompt_system')
        assert hasattr(service, 'base_url')