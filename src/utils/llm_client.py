"""
Minimal LLM client interface to keep strategy code provider-agnostic.
"""

from typing import Any, List, Sequence


class LLMClient:
    """Base class for LLM clients used by strategies."""

    def generate(self, messages: Sequence[Any], **kwargs: Any) -> Any:
        """
        Generate a response for a list of messages.

        Implementations should accept provider-specific kwargs and return the
        raw response object (or text) required by calling code.
        """
        raise NotImplementedError("LLMClient.generate must be implemented")
