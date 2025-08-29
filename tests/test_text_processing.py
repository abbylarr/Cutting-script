"""
Unit tests for text processing services.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.text_processing import (
    GPTTextProcessor,
    FallbackTextProcessor,
    TextProcessingService,
    TextProcessingResult,
    TextProcessingError
)


class TestTextProcessingResult:
    """Test TextProcessingResult dataclass."""
    
    def test_text_processing_result_creation(self):
        """Test creating a text processing result."""
        result = TextProcessingResult(
            original_text="Привет мир",
            processed_text="Привет, мир!",
            corrections_made=["Added punctuation"],
            processing_time=0.5,
            word_count=2
        )
        
        assert result.original_text == "Привет мир"
        assert result.processed_text == "Привет, мир!"
        assert result.corrections_made == ["Added punctuation"]
        assert result.processing_time == 0.5
        assert result.word_count == 2


class TestGPTTextProcessor:
    """Test GPT text processor."""
    
    @pytest.fixture
    def mock_settings_with_key(self):
        """Mock settings with API key."""
        with patch('app.services.text_processing.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = "test-api-key"
            yield mock_settings
    
    @pytest.fixture
    def mock_settings_no_key(self):
        """Mock settings without API key."""
        with patch('app.services.text_processing.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = ""
            yield mock_settings
    
    @pytest.fixture
    def text_processor(self, mock_settings_with_key):
        """Create text processor with mocked dependencies."""
        with patch('app.services.text_processing.AsyncOpenAI'):
            return GPTTextProcessor()
    
    def test_init_with_api_key(self, mock_settings_with_key):
        """Test initialization with API key."""
        with patch('app.services.text_processing.AsyncOpenAI'):
            processor = GPTTextProcessor()
            assert processor.model == "gpt-4o-mini"
            assert processor.temperature == 0.1
    
    def test_init_without_api_key(self, mock_settings_no_key):
        """Test initialization without API key."""
        with pytest.raises(ValueError, match="OPENAI_API_KEY is required"):
            GPTTextProcessor()
    
    @pytest.mark.asyncio
    async def test_process_text_success(self, text_processor):
        """Test successful text processing."""
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Исправленный текст с правильной пунктуацией."
        
        text_processor.client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        result = await text_processor.process_text("Исправленый текст с правильной пунктуацией")
        
        assert isinstance(result, TextProcessingResult)
        assert result.processed_text == "Исправленный текст с правильной пунктуацией."
        assert result.word_count == 5
        assert result.processing_time > 0
    
    @pytest.mark.asyncio
    async def test_process_empty_text(self, text_processor):
        """Test processing empty text."""
        result = await text_processor.process_text("")
        
        assert result.original_text == ""
        assert result.processed_text == ""
        assert result.corrections_made == []
        assert result.word_count == 0
    
    @pytest.mark.asyncio
    async def test_process_text_with_context(self, text_processor):
        """Test text processing with context."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Обработанный текст"
        
        text_processor.client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        result = await text_processor.process_text(
            "Тестовый текст", 
            context="Это диалог"
        )
        
        assert result.processed_text == "Обработанный текст"
        
        # Check that context was included in the call
        call_args = text_processor.client.chat.completions.create.call_args
        messages = call_args[1]['messages']
        user_message = messages[1]['content']
        assert "Контекст: Это диалог" in user_message
    
    @pytest.mark.asyncio
    async def test_process_text_rate_limit_error(self, text_processor):
        """Test handling of rate limit errors."""
        # Create a custom exception that mimics RateLimitError
        class MockRateLimitError(Exception):
            pass
        
        # Patch the openai module to use our mock
        with patch('openai.RateLimitError', MockRateLimitError):
            text_processor.client.chat.completions.create = AsyncMock(
                side_effect=MockRateLimitError("Rate limit exceeded")
            )
            
            with pytest.raises(TextProcessingError, match="Rate limit exceeded"):
                await text_processor.process_text("Тестовый текст")
    
    @pytest.mark.asyncio
    async def test_process_text_api_error(self, text_processor):
        """Test handling of API errors."""
        # Create a custom exception that mimics APIError
        class MockAPIError(Exception):
            pass
        
        # Patch the openai module to use our mock
        with patch('openai.APIError', MockAPIError):
            text_processor.client.chat.completions.create = AsyncMock(
                side_effect=MockAPIError("API error")
            )
            
            with pytest.raises(TextProcessingError, match="API error"):
                await text_processor.process_text("Тестовый текст")
    
    def test_preprocess_text(self, text_processor):
        """Test text preprocessing."""
        # Test whitespace normalization
        result = text_processor._preprocess_text("  Много   пробелов  ")
        assert result == "Много пробелов"
        
        # Test quote normalization
        test_text = '"Кавычки" и \'апострофы\''
        result = text_processor._preprocess_text(test_text)
        assert '"Кавычки"' in result and "'" in result
    
    def test_build_processing_prompt(self, text_processor):
        """Test prompt building."""
        # Without context
        prompt = text_processor._build_processing_prompt("Тестовый текст")
        assert "Исправь следующий текст:" in prompt
        assert "Тестовый текст" in prompt
        
        # With context
        prompt = text_processor._build_processing_prompt("Тестовый текст", "Контекст")
        assert "Контекст: Контекст" in prompt
        assert "Тестовый текст" in prompt
    
    def test_preserve_formatting(self, text_processor):
        """Test formatting preservation."""
        # Test leading/trailing spaces
        result = text_processor._preserve_formatting(" original ", "processed")
        assert result == " processed "
        
        # Test line breaks
        original = "Первая строка\nВторая строка"
        processed = "Первая строка Вторая строка"
        result = text_processor._preserve_formatting(original, processed)
        assert "\n" in result or len(result.split()) == 4
    
    def test_identify_corrections(self, text_processor):
        """Test correction identification."""
        original = "Привет мир"
        processed = "Привет, мир!"
        
        corrections = text_processor._identify_corrections(original, processed)
        assert len(corrections) > 0
    
    @pytest.mark.asyncio
    async def test_process_text_batch(self, text_processor):
        """Test batch text processing."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Обработанный текст"
        
        text_processor.client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        texts = ["Текст 1", "Текст 2", "Текст 3"]
        results = await text_processor.process_text_batch(texts, batch_size=2)
        
        assert len(results) == 3
        for result in results:
            assert isinstance(result, TextProcessingResult)
            assert result.processed_text == "Обработанный текст"
    
    @pytest.mark.asyncio
    async def test_process_text_batch_with_errors(self, text_processor):
        """Test batch processing with some errors."""
        call_count = 0
        
        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Second call fails
                raise Exception("API error")
            
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Обработанный текст"
            return mock_response
        
        text_processor.client.chat.completions.create = mock_create
        
        texts = ["Текст 1", "Текст 2", "Текст 3"]
        results = await text_processor.process_text_batch(texts)
        
        assert len(results) == 3
        # First and third should succeed, second should have error
        assert results[0].processed_text == "Обработанный текст"
        assert results[1].processed_text == "Текст 2"  # Original text on error
        assert "Error:" in results[1].corrections_made[0]
        assert results[2].processed_text == "Обработанный текст"
    
    @pytest.mark.asyncio
    async def test_get_processing_cost(self, text_processor):
        """Test cost estimation."""
        text = "Это тестовый текст для оценки стоимости обработки"
        cost = await text_processor.get_processing_cost(text)
        
        assert isinstance(cost, float)
        assert cost > 0


class TestFallbackTextProcessor:
    """Test fallback text processor."""
    
    @pytest.fixture
    def fallback_processor(self):
        """Create fallback text processor."""
        return FallbackTextProcessor()
    
    @pytest.mark.asyncio
    async def test_process_text_basic_cleaning(self, fallback_processor):
        """Test basic text cleaning."""
        text = "Текст  с   лишними    пробелами ."
        result = await fallback_processor.process_text(text)
        
        assert isinstance(result, TextProcessingResult)
        assert result.processed_text == "Текст с лишними пробелами."
        assert len(result.corrections_made) > 0
    
    @pytest.mark.asyncio
    async def test_process_empty_text(self, fallback_processor):
        """Test processing empty text."""
        result = await fallback_processor.process_text("")
        
        assert result.original_text == ""
        assert result.processed_text == ""
        assert result.corrections_made == []
        assert result.word_count == 0
    
    @pytest.mark.asyncio
    async def test_process_text_batch(self, fallback_processor):
        """Test batch processing."""
        texts = ["Текст 1", "Текст  2", "Текст   3"]
        results = await fallback_processor.process_text_batch(texts)
        
        assert len(results) == 3
        for result in results:
            assert isinstance(result, TextProcessingResult)
    
    @pytest.mark.asyncio
    async def test_get_processing_cost(self, fallback_processor):
        """Test cost estimation (should be free)."""
        cost = await fallback_processor.get_processing_cost("Любой текст")
        assert cost == 0.0


class TestTextProcessingService:
    """Test main text processing service."""
    
    @pytest.fixture
    def mock_settings_with_key(self):
        """Mock settings with API key."""
        with patch('app.services.text_processing.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = "test-api-key"
            yield mock_settings
    
    @pytest.fixture
    def mock_settings_no_key(self):
        """Mock settings without API key."""
        with patch('app.services.text_processing.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = ""
            yield mock_settings
    
    @pytest.mark.asyncio
    async def test_service_with_primary(self, mock_settings_with_key):
        """Test service with primary processor available."""
        with patch('app.services.text_processing.AsyncOpenAI'):
            service = TextProcessingService()
            
            assert service.primary_service is not None
            assert await service.is_primary_service_available() is True
    
    @pytest.mark.asyncio
    async def test_service_without_primary(self, mock_settings_no_key):
        """Test service without primary processor."""
        service = TextProcessingService()
        
        assert service.primary_service is None
        assert await service.is_primary_service_available() is False
    
    @pytest.mark.asyncio
    async def test_process_text_with_fallback_forced(self, mock_settings_with_key):
        """Test text processing with forced fallback."""
        with patch('app.services.text_processing.AsyncOpenAI'):
            service = TextProcessingService()
            
            with patch.object(service.fallback_service, 'process_text') as mock_fallback:
                mock_result = TextProcessingResult(
                    original_text="test",
                    processed_text="fallback result",
                    corrections_made=[],
                    processing_time=0.1,
                    word_count=2
                )
                mock_fallback.return_value = mock_result
                
                result = await service.process_text("test", use_fallback=True)
                
                assert result.processed_text == "fallback result"
                mock_fallback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_text_primary_fails_fallback_used(self, mock_settings_with_key):
        """Test automatic fallback when primary service fails."""
        with patch('app.services.text_processing.AsyncOpenAI'):
            service = TextProcessingService()
            
            # Mock primary service to fail
            with patch.object(service.primary_service, 'process_text', side_effect=TextProcessingError("Primary failed")), \
                 patch.object(service.fallback_service, 'process_text') as mock_fallback:
                
                mock_result = TextProcessingResult(
                    original_text="test",
                    processed_text="fallback after failure",
                    corrections_made=[],
                    processing_time=0.1,
                    word_count=3
                )
                mock_fallback.return_value = mock_result
                
                result = await service.process_text("test")
                
                assert result.processed_text == "fallback after failure"
                mock_fallback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_text_batch(self, mock_settings_with_key):
        """Test batch text processing."""
        with patch('app.services.text_processing.AsyncOpenAI'):
            service = TextProcessingService()
            
            with patch.object(service.primary_service, 'process_text_batch') as mock_batch:
                mock_results = [
                    TextProcessingResult("text1", "processed1", [], 0.1, 1),
                    TextProcessingResult("text2", "processed2", [], 0.1, 1)
                ]
                mock_batch.return_value = mock_results
                
                results = await service.process_text_batch(["text1", "text2"])
                
                assert len(results) == 2
                assert results[0].processed_text == "processed1"
                assert results[1].processed_text == "processed2"
    
    @pytest.mark.asyncio
    async def test_get_service_status(self, mock_settings_with_key):
        """Test service status reporting."""
        with patch('app.services.text_processing.AsyncOpenAI'):
            service = TextProcessingService()
            
            status = await service.get_service_status()
            
            assert isinstance(status, dict)
            assert "primary_available" in status
            assert "openai_api_key_configured" in status
            assert "fallback_available" in status
            assert "model_used" in status
            assert "current_time" in status
            assert status["fallback_available"] is True
    
    @pytest.mark.asyncio
    async def test_get_processing_cost(self, mock_settings_with_key):
        """Test cost estimation."""
        with patch('app.services.text_processing.AsyncOpenAI'):
            service = TextProcessingService()
            
            with patch.object(service.primary_service, 'get_processing_cost', return_value=0.001):
                cost = await service.get_processing_cost("test text")
                assert cost == 0.001
    
    @pytest.mark.asyncio
    async def test_clean_transcription_text(self, mock_settings_with_key):
        """Test specialized transcription cleaning."""
        with patch('app.services.text_processing.AsyncOpenAI'):
            service = TextProcessingService()
            
            with patch.object(service, 'process_text') as mock_process:
                mock_result = TextProcessingResult(
                    original_text="raw transcription",
                    processed_text="cleaned transcription",
                    corrections_made=[],
                    processing_time=0.1,
                    word_count=2
                )
                mock_process.return_value = mock_result
                
                result = await service.clean_transcription_text("raw transcription")
                
                assert result == "cleaned transcription"
                # Check that context was provided
                call_args = mock_process.call_args
                assert "транскрипции" in call_args[1]['context']
    
    @pytest.mark.asyncio
    async def test_format_dialogue_text(self, mock_settings_with_key):
        """Test dialogue formatting."""
        with patch('app.services.text_processing.AsyncOpenAI'):
            service = TextProcessingService()
            
            with patch.object(service, 'process_text') as mock_process:
                mock_result = TextProcessingResult(
                    original_text="Привет как дела",
                    processed_text="Привет, как дела?",
                    corrections_made=[],
                    processing_time=0.1,
                    word_count=3
                )
                mock_process.return_value = mock_result
                
                result = await service.format_dialogue_text("Привет как дела", speaker="Иван")
                
                assert result == "Иван: Привет, как дела?"
    
    @pytest.mark.asyncio
    async def test_format_dialogue_text_speaker_already_present(self, mock_settings_with_key):
        """Test dialogue formatting when speaker is already in text."""
        with patch('app.services.text_processing.AsyncOpenAI'):
            service = TextProcessingService()
            
            with patch.object(service, 'process_text') as mock_process:
                mock_result = TextProcessingResult(
                    original_text="Иван: Привет как дела",
                    processed_text="Иван: Привет, как дела?",
                    corrections_made=[],
                    processing_time=0.1,
                    word_count=4
                )
                mock_process.return_value = mock_result
                
                result = await service.format_dialogue_text("Иван: Привет как дела", speaker="Иван")
                
                assert result == "Иван: Привет, как дела?"  # No duplicate speaker name


@pytest.mark.asyncio
async def test_text_processing_integration():
    """Integration test for text processing service."""
    # This test would require actual API keys
    # For now, we'll test the service initialization and basic functionality
    
    with patch('app.services.text_processing.settings') as mock_settings:
        mock_settings.OPENAI_API_KEY = ""
        
        service = TextProcessingService()
        
        # Should fall back to fallback service
        assert service.primary_service is None
        
        # Test status
        status = await service.get_service_status()
        assert status["primary_available"] is False
        assert status["fallback_available"] is True
        
        # Test basic processing
        result = await service.process_text("Тестовый  текст")
        assert isinstance(result, TextProcessingResult)
        assert result.processed_text.strip() == "Тестовый текст"