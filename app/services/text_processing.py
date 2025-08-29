"""
Text post-processing services for filmlist application.
Handles grammar correction and text cleaning using GPT-4o-mini API.
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime

import openai
from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class TextProcessingResult:
    """Result of text processing."""
    original_text: str
    processed_text: str
    corrections_made: List[str]
    processing_time: float
    word_count: int


class TextProcessingError(Exception):
    """Raised when text processing fails."""
    pass


class GPTTextProcessor:
    """Service for text processing using GPT-4o-mini API."""
    
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required for text processing service")
        
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        # GPT settings for economical processing
        self.model = "gpt-4o-mini"  # Most economical model
        self.temperature = 0.1  # Low temperature for consistent results
        self.max_tokens = 1000  # Limit output tokens
        
        # Russian language processing prompt
        self.correction_prompt = """Ты - профессиональный редактор русского языка. Твоя задача - исправить грамматические ошибки, опечатки и улучшить читаемость текста, сохраняя его смысл и стиль.

Правила:
1. Исправь только явные ошибки (грамматика, пунктуация, опечатки)
2. Сохрани оригинальный стиль и тон речи
3. Не добавляй новую информацию
4. Не изменяй структуру предложений без необходимости
5. Сохрани все имена собственные и специальные термины
6. Если текст содержит диалоги, сохрани разговорный стиль

Верни только исправленный текст без дополнительных комментариев."""
    
    async def process_text(
        self, 
        text: str,
        context: Optional[str] = None,
        preserve_formatting: bool = True
    ) -> TextProcessingResult:
        """
        Process text for grammar correction and cleaning.
        
        Args:
            text: Text to process
            context: Optional context for better processing
            preserve_formatting: Whether to preserve original formatting
            
        Returns:
            TextProcessingResult with processed text and metadata
            
        Raises:
            TextProcessingError: If processing fails
        """
        if not text or not text.strip():
            return TextProcessingResult(
                original_text=text,
                processed_text=text,
                corrections_made=[],
                processing_time=0.0,
                word_count=0
            )
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Prepare the text for processing
            cleaned_text = self._preprocess_text(text)
            
            # Build the prompt
            prompt = self._build_processing_prompt(cleaned_text, context)
            
            # Call GPT API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.correction_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            processed_text = response.choices[0].message.content.strip()
            
            # Post-process the result
            if preserve_formatting:
                processed_text = self._preserve_formatting(text, processed_text)
            
            # Calculate processing time
            processing_time = asyncio.get_event_loop().time() - start_time
            
            # Identify corrections made
            corrections = self._identify_corrections(text, processed_text)
            
            # Count words
            word_count = len(processed_text.split())
            
            logger.info(f"Text processing completed: {word_count} words, {len(corrections)} corrections")
            
            return TextProcessingResult(
                original_text=text,
                processed_text=processed_text,
                corrections_made=corrections,
                processing_time=processing_time,
                word_count=word_count
            )
            
        except openai.RateLimitError as e:
            logger.error(f"Rate limit exceeded during text processing: {e}")
            raise TextProcessingError(f"Rate limit exceeded: {e}")
        except openai.APIError as e:
            logger.error(f"OpenAI API error during text processing: {e}")
            raise TextProcessingError(f"API error: {e}")
        except Exception as e:
            logger.error(f"Text processing failed: {e}")
            raise TextProcessingError(f"Processing failed: {e}")
    
    def _preprocess_text(self, text: str) -> str:
        """
        Preprocess text before sending to GPT.
        
        Args:
            text: Original text
            
        Returns:
            Preprocessed text
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        # Normalize quotes
        text = re.sub(r'[""„"]', '"', text)
        text = re.sub(r'[''`´]', "'", text)
        
        return text
    
    def _build_processing_prompt(self, text: str, context: Optional[str] = None) -> str:
        """
        Build the processing prompt for GPT.
        
        Args:
            text: Text to process
            context: Optional context
            
        Returns:
            Complete prompt
        """
        prompt = f"Исправь следующий текст:\n\n{text}"
        
        if context:
            prompt = f"Контекст: {context}\n\n{prompt}"
        
        return prompt
    
    def _preserve_formatting(self, original: str, processed: str) -> str:
        """
        Preserve original formatting in processed text.
        
        Args:
            original: Original text with formatting
            processed: Processed text
            
        Returns:
            Processed text with preserved formatting
        """
        # If original had leading/trailing whitespace, preserve it
        if original.startswith(' '):
            processed = ' ' + processed.lstrip()
        if original.endswith(' '):
            processed = processed.rstrip() + ' '
        
        # Preserve line breaks if they existed in original
        if '\n' in original and '\n' not in processed:
            # Try to restore line breaks at similar positions
            original_lines = original.split('\n')
            if len(original_lines) > 1:
                # Simple heuristic: split processed text proportionally
                words = processed.split()
                words_per_line = len(words) // len(original_lines)
                
                if words_per_line > 0:
                    lines = []
                    for i in range(0, len(words), words_per_line):
                        lines.append(' '.join(words[i:i + words_per_line]))
                    processed = '\n'.join(lines)
        
        return processed
    
    def _identify_corrections(self, original: str, processed: str) -> List[str]:
        """
        Identify corrections made during processing.
        
        Args:
            original: Original text
            processed: Processed text
            
        Returns:
            List of corrections made
        """
        corrections = []
        
        # Simple word-level comparison
        original_words = original.lower().split()
        processed_words = processed.lower().split()
        
        # Find different words
        if len(original_words) == len(processed_words):
            for i, (orig, proc) in enumerate(zip(original_words, processed_words)):
                if orig != proc:
                    corrections.append(f"'{orig}' → '{proc}'")
        else:
            # Length changed, just note that corrections were made
            if original.lower() != processed.lower():
                corrections.append("Text structure improved")
        
        return corrections
    
    async def process_text_batch(
        self, 
        texts: List[str],
        batch_size: int = 5,
        delay_between_batches: float = 1.0
    ) -> List[TextProcessingResult]:
        """
        Process multiple texts in batches to avoid rate limits.
        
        Args:
            texts: List of texts to process
            batch_size: Number of texts to process concurrently
            delay_between_batches: Delay between batches in seconds
            
        Returns:
            List of TextProcessingResult objects
        """
        results = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            # Process batch concurrently
            batch_tasks = [self.process_text(text) for text in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Handle results and exceptions
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to process text {i + j}: {result}")
                    # Create error result
                    error_result = TextProcessingResult(
                        original_text=batch[j],
                        processed_text=batch[j],  # Return original on error
                        corrections_made=[f"Error: {str(result)}"],
                        processing_time=0.0,
                        word_count=len(batch[j].split())
                    )
                    results.append(error_result)
                else:
                    results.append(result)
            
            # Delay between batches to avoid rate limits
            if i + batch_size < len(texts):
                await asyncio.sleep(delay_between_batches)
        
        return results
    
    async def get_processing_cost(self, text: str) -> float:
        """
        Estimate processing cost for text.
        
        Args:
            text: Text to estimate cost for
            
        Returns:
            Estimated cost in USD
        """
        # GPT-4o-mini pricing (approximate)
        input_cost_per_1k_tokens = 0.00015  # $0.15 per 1M tokens
        output_cost_per_1k_tokens = 0.0006   # $0.60 per 1M tokens
        
        # Rough token estimation (1 token ≈ 0.75 words for Russian)
        words = len(text.split())
        input_tokens = words / 0.75
        output_tokens = min(input_tokens, self.max_tokens)  # Limited by max_tokens
        
        input_cost = (input_tokens / 1000) * input_cost_per_1k_tokens
        output_cost = (output_tokens / 1000) * output_cost_per_1k_tokens
        
        return input_cost + output_cost


class FallbackTextProcessor:
    """Fallback text processor for when GPT API is unavailable."""
    
    def __init__(self):
        # Basic Russian text cleaning rules
        self.cleaning_rules = [
            # Fix common typos
            (r'\bтакже\b', 'также'),
            (r'\bчтобы\b', 'чтобы'),
            (r'\bпотому что\b', 'потому что'),
            
            # Fix punctuation
            (r'\s+([,.!?;:])', r'\1'),  # Remove space before punctuation
            (r'([,.!?;:])\s*([,.!?;:])', r'\1 \2'),  # Space after punctuation
            
            # Fix quotes
            (r'[""„"]', '"'),
            (r'[''`´]', "'"),
            
            # Fix excessive whitespace
            (r'\s+', ' '),
        ]
    
    async def process_text(
        self, 
        text: str,
        context: Optional[str] = None,
        preserve_formatting: bool = True
    ) -> TextProcessingResult:
        """
        Provide basic text cleaning when GPT is unavailable.
        
        Args:
            text: Text to process
            context: Optional context (ignored in fallback)
            preserve_formatting: Whether to preserve formatting
            
        Returns:
            TextProcessingResult with basic cleaning
        """
        if not text or not text.strip():
            return TextProcessingResult(
                original_text=text,
                processed_text=text,
                corrections_made=[],
                processing_time=0.0,
                word_count=0
            )
        
        start_time = asyncio.get_event_loop().time()
        
        processed_text = text
        corrections = []
        
        # Apply basic cleaning rules
        for pattern, replacement in self.cleaning_rules:
            old_text = processed_text
            processed_text = re.sub(pattern, replacement, processed_text)
            if old_text != processed_text:
                corrections.append(f"Applied rule: {pattern}")
        
        # Trim whitespace
        processed_text = processed_text.strip()
        
        processing_time = asyncio.get_event_loop().time() - start_time
        word_count = len(processed_text.split())
        
        logger.warning(f"Using fallback text processing for {word_count} words")
        
        return TextProcessingResult(
            original_text=text,
            processed_text=processed_text,
            corrections_made=corrections,
            processing_time=processing_time,
            word_count=word_count
        )
    
    async def process_text_batch(
        self, 
        texts: List[str],
        batch_size: int = 5,
        delay_between_batches: float = 0.1
    ) -> List[TextProcessingResult]:
        """Process multiple texts with fallback method."""
        results = []
        
        for text in texts:
            result = await self.process_text(text)
            results.append(result)
            await asyncio.sleep(0.01)  # Small delay to avoid blocking
        
        return results
    
    async def get_processing_cost(self, text: str) -> float:
        """Fallback processing is free."""
        return 0.0


class TextProcessingService:
    """Main text processing service with fallback capabilities."""
    
    def __init__(self):
        self.primary_service = None
        self.fallback_service = FallbackTextProcessor()
        
        # Try to initialize primary service
        try:
            self.primary_service = GPTTextProcessor()
            logger.info("GPT text processing service initialized")
        except ValueError as e:
            logger.warning(f"GPT service not available: {e}")
    
    async def process_text(
        self, 
        text: str,
        context: Optional[str] = None,
        use_fallback: bool = False
    ) -> TextProcessingResult:
        """
        Process text with automatic fallback to basic cleaning.
        
        Args:
            text: Text to process
            context: Optional context for better processing
            use_fallback: Force use of fallback service
            
        Returns:
            TextProcessingResult
        """
        if use_fallback or not self.primary_service:
            return await self.fallback_service.process_text(text, context)
        
        try:
            return await self.primary_service.process_text(text, context)
        except TextProcessingError as e:
            logger.error(f"Primary text processing failed, using fallback: {e}")
            return await self.fallback_service.process_text(text, context)
    
    async def process_text_batch(
        self, 
        texts: List[str],
        use_fallback: bool = False,
        batch_size: int = 5
    ) -> List[TextProcessingResult]:
        """
        Process multiple texts with fallback.
        
        Args:
            texts: List of texts to process
            use_fallback: Force use of fallback service
            batch_size: Batch size for processing
            
        Returns:
            List of TextProcessingResult objects
        """
        if use_fallback or not self.primary_service:
            return await self.fallback_service.process_text_batch(texts, batch_size)
        
        try:
            return await self.primary_service.process_text_batch(texts, batch_size)
        except TextProcessingError as e:
            logger.error(f"Primary batch processing failed, using fallback: {e}")
            return await self.fallback_service.process_text_batch(texts, batch_size)
    
    async def is_primary_service_available(self) -> bool:
        """
        Check if primary text processing service is available.
        
        Returns:
            True if GPT service is available, False otherwise
        """
        return self.primary_service is not None
    
    async def get_service_status(self) -> Dict[str, Any]:
        """
        Get status of text processing services.
        
        Returns:
            Dictionary with service status information
        """
        return {
            "primary_available": self.primary_service is not None,
            "openai_api_key_configured": bool(settings.OPENAI_API_KEY),
            "fallback_available": True,
            "model_used": self.primary_service.model if self.primary_service else "fallback",
            "current_time": datetime.utcnow().isoformat()
        }
    
    async def get_processing_cost(self, text: str) -> float:
        """
        Get estimated processing cost.
        
        Args:
            text: Text to estimate cost for
            
        Returns:
            Estimated cost in USD
        """
        if self.primary_service:
            return await self.primary_service.get_processing_cost(text)
        else:
            return await self.fallback_service.get_processing_cost(text)
    
    async def clean_transcription_text(self, transcription_text: str) -> str:
        """
        Specialized method for cleaning transcription text.
        
        Args:
            transcription_text: Raw transcription text
            
        Returns:
            Cleaned transcription text
        """
        context = "Это текст автоматической транскрипции речи. Исправь ошибки распознавания и улучши читаемость."
        
        result = await self.process_text(
            transcription_text, 
            context=context,
            preserve_formatting=True
        )
        
        return result.processed_text
    
    async def format_dialogue_text(self, dialogue_text: str, speaker: Optional[str] = None) -> str:
        """
        Format dialogue text for montage table.
        
        Args:
            dialogue_text: Raw dialogue text
            speaker: Speaker name if known
            
        Returns:
            Formatted dialogue text
        """
        context = "Это диалог для монтажного листа. Сохрани разговорный стиль, но исправь грамматические ошибки."
        
        result = await self.process_text(
            dialogue_text,
            context=context,
            preserve_formatting=True
        )
        
        formatted_text = result.processed_text
        
        # Add speaker prefix if provided
        if speaker and not formatted_text.startswith(speaker):
            formatted_text = f"{speaker}: {formatted_text}"
        
        return formatted_text