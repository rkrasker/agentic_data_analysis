"""
Base LLM wrapper providing a unified interface across providers.

Designed for LangChain 0.2.x+ compatibility with graceful degradation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

from pydantic import BaseModel

from .config import ModelConfig, Provider, get_model_config
from .structured import StructuredOutputHandler, parse_to_model, create_json_prompt_suffix

T = TypeVar("T", bound=BaseModel)


@dataclass
class LLMResponse:
    """Standardized response from LLM calls."""
    content: str
    input_tokens: int
    output_tokens: int
    model: str
    raw_response: Any = None
    finish_reason: Optional[str] = None

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
    """

    def __init__(
        self,
        model_name: str,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """
        Initialize provider.

        Args:
            model_name: Name of the model (must be in MODEL_REGISTRY)
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Max output tokens (uses model default if None)
            **kwargs: Provider-specific arguments
        """
        self.config = get_model_config(model_name)
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens or self.config.max_tokens

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

    def invoke(
        self,
        messages: Union[List[Message], List[Dict], List[Any]],
        **kwargs
    ) -> LLMResponse:
        """
        Invoke the model with messages.

        Args:
            messages: List of messages (Message objects, dicts, or LangChain messages)
            **kwargs: Additional model arguments

        Returns:
            LLMResponse with content and token usage
        """
        lc_messages = self._convert_messages(messages)
        response = self._model.invoke(lc_messages, **kwargs)

        input_tokens, output_tokens = self._extract_token_usage(response)

        return LLMResponse(
            content=response.content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self.model_name,
            raw_response=response,
            finish_reason=getattr(response, "response_metadata", {}).get("finish_reason"),
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
