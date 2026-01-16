"""
Base LLM wrapper providing a unified interface across providers.

Designed for LangChain 0.2.x+ compatibility with graceful degradation.
Includes retry logic with exponential backoff for fault tolerance.
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

from pydantic import BaseModel

from .config import ModelConfig, Provider, get_model_config
from .structured import StructuredOutputHandler, parse_to_model, create_json_prompt_suffix

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    """Maximum number of retry attempts."""

    initial_delay: float = 1.0
    """Initial delay in seconds before first retry."""

    max_delay: float = 60.0
    """Maximum delay between retries."""

    exponential_base: float = 2.0
    """Base for exponential backoff calculation."""

    retry_on_timeout: bool = True
    """Whether to retry on timeout errors."""

    retry_on_rate_limit: bool = True
    """Whether to retry on rate limit errors."""


@dataclass
class LLMResponse:
    """Standardized response from LLM calls."""
    content: str
    input_tokens: int
    output_tokens: int
    model: str
    raw_response: Any = None
    finish_reason: Optional[str] = None
    retry_count: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class Message:
    """Simple message container for provider-agnostic use."""
    role: str  # "system", "human", "assistant"
    content: str

    def to_langchain(self):
        """Convert to LangChain message type."""
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

        if self.role == "system":
            return SystemMessage(content=self.content)
        elif self.role == "human" or self.role == "user":
            return HumanMessage(content=self.content)
        elif self.role == "assistant" or self.role == "ai":
            return AIMessage(content=self.content)
        else:
            raise ValueError(f"Unknown role: {self.role}")


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    Subclasses implement provider-specific initialization and token counting.
    The base class handles common operations like message conversion and
    structured output.

    Includes retry logic with exponential backoff for fault tolerance.
    """

    def __init__(
        self,
        model_name: str,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        retry_config: Optional[RetryConfig] = None,
        **kwargs
    ):
        """
        Initialize provider.

        Args:
            model_name: Name of the model (must be in MODEL_REGISTRY)
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Max output tokens (uses model default if None)
            retry_config: Configuration for retry behavior (uses defaults if None)
            **kwargs: Provider-specific arguments
        """
        self.config = get_model_config(model_name)
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens or self.config.max_tokens
        self.retry_config = retry_config or RetryConfig()

        # Initialize the underlying LangChain model
        self._model = self._create_model(**kwargs)

    @abstractmethod
    def _create_model(self, **kwargs) -> Any:
        """Create the underlying LangChain model. Provider-specific."""
        pass

    @abstractmethod
    def _extract_token_usage(self, response: Any) -> tuple:
        """
        Extract token counts from response.

        Returns:
            Tuple of (input_tokens, output_tokens)
        """
        pass

    def _convert_messages(
        self,
        messages: Union[List[Message], List[Dict], List[Any]]
    ) -> List[Any]:
        """Convert messages to LangChain format."""
        from langchain_core.messages import BaseMessage

        result = []
        for msg in messages:
            if isinstance(msg, Message):
                result.append(msg.to_langchain())
            elif isinstance(msg, dict):
                result.append(Message(
                    role=msg.get("role", "human"),
                    content=msg.get("content", "")
                ).to_langchain())
            elif isinstance(msg, BaseMessage):
                result.append(msg)
            else:
                raise TypeError(f"Unsupported message type: {type(msg)}")
        return result

    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if an error is retryable based on retry config."""
        error_str = str(error).lower()

        # Timeout errors
        if self.retry_config.retry_on_timeout:
            timeout_indicators = ["timeout", "timed out", "deadline exceeded"]
            if any(ind in error_str for ind in timeout_indicators):
                return True

        # Rate limit errors
        if self.retry_config.retry_on_rate_limit:
            rate_limit_indicators = ["rate limit", "quota exceeded", "429", "too many requests"]
            if any(ind in error_str for ind in rate_limit_indicators):
                return True

        # Connection errors (usually transient)
        connection_indicators = ["connection", "network", "refused", "reset"]
        if any(ind in error_str for ind in connection_indicators):
            return True

        return False

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt using exponential backoff."""
        delay = self.retry_config.initial_delay * (
            self.retry_config.exponential_base ** attempt
        )
        return min(delay, self.retry_config.max_delay)

    def _invoke_with_retry(
        self,
        lc_messages: List[Any],
        **kwargs
    ) -> tuple:
        """
        Invoke the model with retry logic.

        Returns:
            Tuple of (response, retry_count)
        """
        last_error = None

        for attempt in range(self.retry_config.max_retries + 1):
            try:
                response = self._model.invoke(lc_messages, **kwargs)
                return response, attempt

            except Exception as e:
                last_error = e

                if attempt >= self.retry_config.max_retries:
                    logger.error(f"LLM call failed after {attempt + 1} attempts: {e}")
                    raise

                if not self._is_retryable_error(e):
                    logger.error(f"Non-retryable error: {e}")
                    raise

                delay = self._calculate_delay(attempt)
                logger.warning(
                    f"LLM call failed (attempt {attempt + 1}/{self.retry_config.max_retries + 1}), "
                    f"retrying in {delay:.1f}s: {e}"
                )
                time.sleep(delay)

        # Should not reach here, but just in case
        raise last_error

    def invoke(
        self,
        messages: Union[List[Message], List[Dict], List[Any]],
        **kwargs
    ) -> LLMResponse:
        """
        Invoke the model with messages.

        Includes automatic retry with exponential backoff for transient errors.

        Args:
            messages: List of messages (Message objects, dicts, or LangChain messages)
            **kwargs: Additional model arguments

        Returns:
            LLMResponse with content and token usage
        """
        lc_messages = self._convert_messages(messages)
        response, retry_count = self._invoke_with_retry(lc_messages, **kwargs)

        input_tokens, output_tokens = self._extract_token_usage(response)

        return LLMResponse(
            content=response.content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self.model_name,
            raw_response=response,
            finish_reason=getattr(response, "response_metadata", {}).get("finish_reason"),
            retry_count=retry_count,
        )

    def invoke_structured(
        self,
        messages: Union[List[Message], List[Dict], List[Any]],
        output_class: Type[T],
        **kwargs
    ) -> tuple:
        """
        Invoke model and parse response into Pydantic model.

        Args:
            messages: List of messages
            output_class: Pydantic model class for output
            **kwargs: Additional model arguments

        Returns:
            Tuple of (parsed_model, LLMResponse)
        """
        lc_messages = self._convert_messages(messages)

        # Try LangChain's structured output first
        handler = StructuredOutputHandler(self._model, output_class)

        try:
            parsed = handler.invoke(lc_messages, **kwargs)
            # Get token usage from a regular call for tracking
            # (structured output may not expose tokens directly)
            response = self._model.invoke(lc_messages, **kwargs)
            input_tokens, output_tokens = self._extract_token_usage(response)

            return parsed, LLMResponse(
                content=response.content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=self.model_name,
                raw_response=response,
            )
        except Exception as e:
            # Fallback: add JSON prompt and parse manually
            suffix = create_json_prompt_suffix(output_class)
            modified_messages = list(lc_messages)
            if modified_messages:
                from langchain_core.messages import HumanMessage
                last = modified_messages[-1]
                modified_messages[-1] = HumanMessage(
                    content=last.content + suffix
                )

            response = self._model.invoke(modified_messages, **kwargs)
            input_tokens, output_tokens = self._extract_token_usage(response)

            parsed = parse_to_model(response.content, output_class)

            return parsed, LLMResponse(
                content=response.content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=self.model_name,
                raw_response=response,
            )

    def batch(
        self,
        message_batches: List[List[Union[Message, Dict, Any]]],
        **kwargs
    ) -> List[LLMResponse]:
        """
        Batch invoke the model with multiple message lists.

        Args:
            message_batches: List of message lists
            **kwargs: Additional model arguments

        Returns:
            List of LLMResponses
        """
        lc_batches = [self._convert_messages(msgs) for msgs in message_batches]
        responses = self._model.batch(lc_batches, **kwargs)

        results = []
        for response in responses:
            input_tokens, output_tokens = self._extract_token_usage(response)
            results.append(LLMResponse(
                content=response.content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=self.model_name,
                raw_response=response,
            ))
        return results

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for given token counts."""
        return self.config.estimate_cost(input_tokens, output_tokens)


def create_provider(
    model_name: str,
    temperature: float = 0.0,
    **kwargs
) -> BaseLLMProvider:
    """
    Factory function to create the appropriate provider for a model.

    Args:
        model_name: Name of the model (from MODEL_REGISTRY)
        temperature: Sampling temperature
        **kwargs: Provider-specific arguments

    Returns:
        Configured LLM provider instance
    """
    config = get_model_config(model_name)

    if config.provider == Provider.GEMINI:
        from .providers.gemini import GeminiProvider
        return GeminiProvider(model_name, temperature=temperature, **kwargs)

    elif config.provider == Provider.ANTHROPIC:
        from .providers.anthropic import AnthropicProvider
        return AnthropicProvider(model_name, temperature=temperature, **kwargs)

    elif config.provider == Provider.OPENAI:
        from .providers.openai import OpenAIProvider
        return OpenAIProvider(model_name, temperature=temperature, **kwargs)

    else:
        raise ValueError(f"No provider implementation for: {config.provider}")
