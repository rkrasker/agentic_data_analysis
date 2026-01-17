"""
Google Gemini provider implementation.

Requires: langchain-google-genai>=1.0.0
Compatible with: langchain-core>=0.2.0
"""

import os
from typing import Any, Optional

from ..base import BaseLLMProvider


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini provider using LangChain.

    Environment variables:
        GEMINI_API_KEY: Google AI API key (required)
        GOOGLE_API_KEY: Alternative name for API key
    """

    def _create_model(self, **kwargs) -> Any:
        """Create the Gemini chat model."""
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise ImportError(
                "langchain-google-genai is required for Gemini support. "
                "Install with: pip install langchain-google-genai>=1.0.0"
            )

        # Get API key from environment
        api_key = kwargs.pop("api_key", None)
        if not api_key:
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable not set. "
                "Set it in your .env file or pass api_key parameter."
            )

        # Build model kwargs
        model_kwargs = {
            "model": self.config.model_id,
            "temperature": self.temperature,
            "max_output_tokens": self.max_tokens,
            "google_api_key": api_key,
            "timeout": kwargs.pop("timeout", 120),  # 120 second timeout to prevent indefinite hangs
        }

        # LangChain 0.2.x vs 1.0+ compatibility
        # Both versions support these core parameters
        model_kwargs.update(kwargs)

        return ChatGoogleGenerativeAI(**model_kwargs)

    def _extract_token_usage(self, response: Any) -> tuple:
        """
        Extract token counts from Gemini response.

        Token usage location varies by LangChain version:
        - 0.2.x: response.response_metadata.get("usage_metadata")
        - 1.0+: response.usage_metadata or response.response_metadata
        """
        input_tokens = 0
        output_tokens = 0

        # Try multiple locations for token counts
        usage = None

        # Method 1: Direct usage_metadata attribute (newer versions)
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage = response.usage_metadata

        # Method 2: response_metadata dict (common in 0.2.x+)
        if not usage and hasattr(response, "response_metadata"):
            metadata = response.response_metadata
            if isinstance(metadata, dict):
                usage = metadata.get("usage_metadata") or metadata.get("usage")

        # Extract from usage object/dict
        if usage:
            if isinstance(usage, dict):
                input_tokens = usage.get("prompt_token_count", 0) or usage.get("input_tokens", 0)
                output_tokens = usage.get("candidates_token_count", 0) or usage.get("output_tokens", 0)
            elif hasattr(usage, "prompt_token_count"):
                input_tokens = getattr(usage, "prompt_token_count", 0) or 0
                output_tokens = getattr(usage, "candidates_token_count", 0) or 0
            elif hasattr(usage, "input_tokens"):
                input_tokens = getattr(usage, "input_tokens", 0) or 0
                output_tokens = getattr(usage, "output_tokens", 0) or 0

        # Fallback: estimate from content length
        if input_tokens == 0 and output_tokens == 0:
            # Rough estimate: ~4 chars per token
            if hasattr(response, "content") and response.content:
                output_tokens = len(response.content) // 4

        return input_tokens, output_tokens


def get_gemini_model(
    model_name: str = "gemini-2.5-pro",
    temperature: float = 0.0,
    **kwargs
) -> GeminiProvider:
    """
    Convenience function to get a configured Gemini provider.

    Args:
        model_name: Gemini model name (default: gemini-2.5-pro)
        temperature: Sampling temperature
        **kwargs: Additional model arguments

    Returns:
        Configured GeminiProvider instance
    """
    return GeminiProvider(model_name, temperature=temperature, **kwargs)
