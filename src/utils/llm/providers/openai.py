"""
OpenAI GPT provider implementation.

Requires: langchain-openai>=0.1.0
Compatible with: langchain-core>=0.2.0

STATUS: Stub implementation - expand when needed.
"""

import os
from typing import Any, Optional

from ..base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI GPT provider using LangChain.

    Environment variables:
        OPENAI_API_KEY: OpenAI API key (required)
    """

    def _create_model(self, **kwargs) -> Any:
        """Create the OpenAI chat model."""
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError(
                "langchain-openai is required for OpenAI support. "
                "Install with: pip install langchain-openai>=0.1.0"
            )

        # Get API key from environment
        api_key = kwargs.pop("api_key", None)
        if not api_key:
            api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable not set. "
                "Set it in your .env file or pass api_key parameter."
            )

        model_kwargs = {
            "model": self.config.model_id,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "api_key": api_key,
        }
        model_kwargs.update(kwargs)

        return ChatOpenAI(**model_kwargs)

    def _extract_token_usage(self, response: Any) -> tuple:
        """Extract token counts from OpenAI response."""
        input_tokens = 0
        output_tokens = 0

        # OpenAI responses have usage in response_metadata
        if hasattr(response, "response_metadata"):
            metadata = response.response_metadata
            if isinstance(metadata, dict):
                usage = metadata.get("token_usage", {})
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)

        # Fallback estimate
        if input_tokens == 0 and output_tokens == 0:
            if hasattr(response, "content") and response.content:
                output_tokens = len(response.content) // 4

        return input_tokens, output_tokens


def get_openai_model(
    model_name: str = "gpt-4o-mini",
    temperature: float = 0.0,
    **kwargs
) -> OpenAIProvider:
    """
    Convenience function to get a configured OpenAI provider.

    Args:
        model_name: OpenAI model name
        temperature: Sampling temperature
        **kwargs: Additional model arguments

    Returns:
        Configured OpenAIProvider instance
    """
    return OpenAIProvider(model_name, temperature=temperature, **kwargs)
