"""
Multi-provider LLM client for LangChain.

Provides a unified interface for working with different LLM providers
(Gemini, Claude, OpenAI) through LangChain abstractions.

Designed for compatibility with LangChain 0.2.x and later.

Usage:
    from src.utils.llm import create_provider, Message

    # Create a provider
    llm = create_provider("gemini-2.5-pro", temperature=0.0)

    # Simple invocation
    response = llm.invoke([
        Message(role="system", content="You are a helpful assistant."),
        Message(role="human", content="What is 2+2?"),
    ])
    print(response.content)
    print(f"Tokens: {response.input_tokens} in, {response.output_tokens} out")

    # Structured output with Pydantic
    from pydantic import BaseModel

    class Answer(BaseModel):
        value: int
        explanation: str

    parsed, response = llm.invoke_structured(
        [Message(role="human", content="What is 2+2?")],
        output_class=Answer
    )
    print(parsed.value)  # 4

Available models:
    Gemini: gemini-2.0-flash, gemini-2.5-pro, gemini-1.5-flash, gemini-1.5-pro
    Claude: claude-3-5-sonnet, claude-3-5-haiku (requires langchain-anthropic)
    OpenAI: gpt-4o, gpt-4o-mini (requires langchain-openai)
"""

from .base import (
    BaseLLMProvider,
    LLMResponse,
    Message,
    create_provider,
)
from .config import (
    Provider,
    ModelConfig,
    get_model_config,
    get_default_model,
    list_models,
    MODEL_REGISTRY,
)
from .structured import (
    extract_json_from_text,
    parse_to_model,
    create_json_prompt_suffix,
    StructuredOutputHandler,
)

__all__ = [
    # Core classes
    "BaseLLMProvider",
    "LLMResponse",
    "Message",
    # Factory
    "create_provider",
    # Config
    "Provider",
    "ModelConfig",
    "get_model_config",
    "get_default_model",
    "list_models",
    "MODEL_REGISTRY",
    # Structured output
    "extract_json_from_text",
    "parse_to_model",
    "create_json_prompt_suffix",
    "StructuredOutputHandler",
]
