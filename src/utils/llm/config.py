"""
LLM configuration: model definitions, pricing, and defaults.

Designed to support multiple providers with easy expansion.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
from enum import Enum


class Provider(Enum):
    """Supported LLM providers."""
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    provider: Provider
    model_id: str
    display_name: str
    input_price_per_million: float
    output_price_per_million: float
    max_tokens: int = 8192
    supports_structured_output: bool = True
    supports_vision: bool = False
    default_temperature: float = 0.0

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for given token counts."""
        input_cost = (input_tokens / 1_000_000) * self.input_price_per_million
        output_cost = (output_tokens / 1_000_000) * self.output_price_per_million
        return input_cost + output_cost


# Model registry - add new models here
MODEL_REGISTRY: Dict[str, ModelConfig] = {
    # Gemini models
    "gemini-2.0-flash": ModelConfig(
        provider=Provider.GEMINI,
        model_id="gemini-2.0-flash",
        display_name="Gemini 2.0 Flash",
        input_price_per_million=0.10,
        output_price_per_million=0.40,
        max_tokens=8192,
        supports_vision=True,
    ),
    "gemini-2.5-pro": ModelConfig(
        provider=Provider.GEMINI,
        model_id="gemini-2.5-pro",
        display_name="Gemini 2.5 Pro",
        input_price_per_million=1.25,
        output_price_per_million=5.00,
        max_tokens=8192,
        supports_vision=True,
    ),
    "gemini-1.5-flash": ModelConfig(
        provider=Provider.GEMINI,
        model_id="gemini-1.5-flash",
        display_name="Gemini 1.5 Flash",
        input_price_per_million=0.075,
        output_price_per_million=0.30,
        max_tokens=8192,
        supports_vision=True,
    ),
    "gemini-1.5-pro": ModelConfig(
        provider=Provider.GEMINI,
        model_id="gemini-1.5-pro",
        display_name="Gemini 1.5 Pro",
        input_price_per_million=1.25,
        output_price_per_million=5.00,
        max_tokens=8192,
        supports_vision=True,
    ),

    # Anthropic models (for future expansion)
    "claude-3-5-sonnet": ModelConfig(
        provider=Provider.ANTHROPIC,
        model_id="claude-3-5-sonnet-20241022",
        display_name="Claude 3.5 Sonnet",
        input_price_per_million=3.00,
        output_price_per_million=15.00,
        max_tokens=8192,
        supports_vision=True,
    ),
    "claude-3-5-haiku": ModelConfig(
        provider=Provider.ANTHROPIC,
        model_id="claude-3-5-haiku-20241022",
        display_name="Claude 3.5 Haiku",
        input_price_per_million=0.80,
        output_price_per_million=4.00,
        max_tokens=8192,
        supports_vision=True,
    ),

    # OpenAI models (for future expansion)
    "gpt-4o": ModelConfig(
        provider=Provider.OPENAI,
        model_id="gpt-4o",
        display_name="GPT-4o",
        input_price_per_million=2.50,
        output_price_per_million=10.00,
        max_tokens=16384,
        supports_vision=True,
    ),
    "gpt-4o-mini": ModelConfig(
        provider=Provider.OPENAI,
        model_id="gpt-4o-mini",
        display_name="GPT-4o Mini",
        input_price_per_million=0.15,
        output_price_per_million=0.60,
        max_tokens=16384,
        supports_vision=True,
    ),
}


# Default models per provider
DEFAULT_MODELS: Dict[Provider, str] = {
    Provider.GEMINI: "gemini-2.5-pro",
    Provider.ANTHROPIC: "claude-3-5-sonnet",
    Provider.OPENAI: "gpt-4o-mini",
}


def get_model_config(model_name: str) -> ModelConfig:
    """Get configuration for a model by name."""
    if model_name not in MODEL_REGISTRY:
        available = ", ".join(sorted(MODEL_REGISTRY.keys()))
        raise ValueError(f"Unknown model: {model_name}. Available: {available}")
    return MODEL_REGISTRY[model_name]


def get_default_model(provider: Provider) -> str:
    """Get the default model name for a provider."""
    return DEFAULT_MODELS[provider]


def list_models(provider: Optional[Provider] = None) -> list:
    """List available models, optionally filtered by provider."""
    models = []
    for name, config in MODEL_REGISTRY.items():
        if provider is None or config.provider == provider:
            models.append({
                "name": name,
                "provider": config.provider.value,
                "display_name": config.display_name,
                "input_price": config.input_price_per_million,
                "output_price": config.output_price_per_million,
            })
    return models
