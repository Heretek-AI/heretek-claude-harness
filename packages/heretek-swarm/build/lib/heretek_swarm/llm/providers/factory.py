"""
LLM Provider Factory

Factory for creating LLM provider instances based on configuration.
Supports dynamic provider instantiation and registry.
"""

from __future__ import annotations

from typing import Any

import structlog

from .base import LLMProviderBase, ProviderConfigurationError
from .lemonade_provider import LemonadeProvider
from .llamacpp_provider import LlamaCppProvider
from .minimax_provider import MiniMaxProvider
from .ollama_provider import OllamaProvider
from .openai_compatible import OpenAICompatibleProvider
from .openai_provider import OpenAIProvider
from .zai_provider import ZAIProvider

logger = structlog.get_logger("llm.providers.factory")

# Provider registry mapping provider types to implementation classes
PROVIDER_REGISTRY: dict[str, type[LLMProviderBase]] = {
    "openai": OpenAIProvider,
    "openai_compatible": OpenAICompatibleProvider,
    "ollama": OllamaProvider,
    "llamacpp": LlamaCppProvider,
    "zai": ZAIProvider,
    "minimax": MiniMaxProvider,
    "lemonade": LemonadeProvider,
}


def register_provider(provider_type: str, provider_class: type[LLMProviderBase]) -> None:
    """
    Register a new provider implementation.

    Args:
        provider_type: The provider type identifier
        provider_class: The provider implementation class
    """
    PROVIDER_REGISTRY[provider_type] = provider_class
    logger.info("Provider registered", provider_type=provider_type)


def unregister_provider(provider_type: str) -> None:
    """
    Unregister a provider implementation.

    Args:
        provider_type: The provider type identifier
    """
    if provider_type in PROVIDER_REGISTRY:
        del PROVIDER_REGISTRY[provider_type]
        logger.info("Provider unregistered", provider_type=provider_type)


def get_provider_class(provider_type: str) -> type[LLMProviderBase]:
    """
    Get the provider class for a given type.

    Args:
        provider_type: The provider type identifier

    Returns:
        The provider implementation class

    Raises:
        ProviderConfigurationError: If the provider type is not registered
    """
    if provider_type not in PROVIDER_REGISTRY:
        available = ", ".join(PROVIDER_REGISTRY.keys())
        raise ProviderConfigurationError(
            f"Unknown provider type: {provider_type}. Available: {available}"
        )
    return PROVIDER_REGISTRY[provider_type]


def list_available_providers() -> list[str]:
    """
    List all available provider types.

    Returns:
        List of provider type identifiers
    """
    return list(PROVIDER_REGISTRY.keys())


def create_llm_provider(
    provider_type: str,
    config: dict[str, Any],
) -> LLMProviderBase:
    """
    Create an LLM provider instance from configuration.

    This is the main factory function for creating providers. It takes a
    provider type and configuration dictionary and returns an initialized
    provider instance.

    Args:
        provider_type: The type of provider to create (e.g., "openai", "ollama")
        config: Configuration dictionary with provider-specific settings

    Returns:
        An initialized LLM provider instance

    Raises:
        ProviderConfigurationError: If configuration is invalid

    Example:
        # Create OpenAI provider
        provider = create_llm_provider(
            "openai",
            {
                "api_key": "sk-...",
                "default_model": "gpt-4o"
            }
        )

        # Create Ollama provider
        provider = create_llm_provider(
            "ollama",
            {
                "base_url": "http://localhost:11434",
                "default_model": "llama2"
            }
        )
    """
    provider_class = get_provider_class(provider_type)

    try:
        # Extract common parameters
        base_url = config.get("base_url")
        api_key = config.get("api_key")
        default_model = config.get("default_model")
        extra_config = config.get("extra_config", {})

        # Create provider based on type
        if provider_type == "openai":
            if not api_key:
                raise ProviderConfigurationError("OpenAI provider requires api_key")
            return OpenAIProvider(
                api_key=api_key,
                base_url=base_url or "https://api.openai.com/v1",
                default_model=default_model,
                organization=config.get("organization"),
                extra_config=extra_config,
            )

        if provider_type == "openai_compatible":
            if not base_url:
                raise ProviderConfigurationError("OpenAI-compatible provider requires base_url")
            return OpenAICompatibleProvider(
                base_url=base_url,
                api_key=api_key,
                default_model=default_model,
                extra_config=extra_config,
            )

        if provider_type == "ollama":
            return OllamaProvider(
                base_url=base_url or "http://localhost:11434",
                default_model=default_model,
                extra_config=extra_config,
            )

        if provider_type == "llamacpp":
            return LlamaCppProvider(
                base_url=base_url or "http://localhost:8080",
                default_model=default_model,
                extra_config=extra_config,
            )

        if provider_type == "zai":
            if not api_key:
                raise ProviderConfigurationError("Z.AI provider requires api_key")
            return ZAIProvider(
                api_key=api_key,
                base_url=base_url or "https://open.bigmodel.cn/api/paas/v4",
                default_model=default_model,
                extra_config=extra_config,
            )

        if provider_type == "minimax":
            if not api_key:
                raise ProviderConfigurationError("MiniMax provider requires api_key")
            # group_id can be at top level or inside extra_config
            group_id = config.get("group_id") or extra_config.get("group_id")
            if not group_id:
                raise ProviderConfigurationError("MiniMax provider requires group_id")
            return MiniMaxProvider(
                api_key=api_key,
                group_id=group_id,
                base_url=base_url or "https://api.minimax.chat/v1",
                default_model=default_model,
                extra_config=extra_config,
            )

        if provider_type == "lemonade":
            return LemonadeProvider(
                base_url=base_url or "http://localhost:5000",
                default_model=default_model,
                extra_config=extra_config,
            )

        # Fallback to generic instantiation for registered providers
        # This allows custom providers to be created dynamically
        return provider_class(
            base_url=base_url,
            api_key=api_key,
            default_model=default_model,
            extra_config=extra_config,
        )

    except TypeError as e:
        raise ProviderConfigurationError(f"Invalid configuration for {provider_type}: {e}") from e


def create_llm_provider_from_db_config(
    db_config: Any,
    api_key_decrypt_func: callable | None = None,
) -> LLMProviderBase:
    """
    Create an LLM provider instance from a database configuration model.

    Args:
        db_config: Database configuration model (LLMProvider from models.py)
        api_key_decrypt_func: Optional function to decrypt the API key

    Returns:
        An initialized LLM provider instance

    Example:
        provider = create_llm_provider_from_db_config(
            db_llm_provider,
            api_key_decrypt_func=decrypt_api_key
        )
    """
    config = {
        "base_url": db_config.base_url,
        "api_key": None,
        "default_model": db_config.default_model,
        "extra_config": db_config.extra_config or {},
    }

    # Decrypt API key if function provided and key exists
    if db_config.api_key_encrypted and api_key_decrypt_func:
        config["api_key"] = api_key_decrypt_func(db_config.api_key_encrypted)

    return create_llm_provider(db_config.provider_type, config)


def get_provider_info(provider_type: str) -> dict[str, Any]:
    """
    Get information about a provider type.

    Args:
        provider_type: The provider type identifier

    Returns:
        Dictionary with provider information
    """
    provider_class = get_provider_class(provider_type)

    # Create a temporary instance to get capabilities
    # (with minimal config to avoid errors)
    try:
        if provider_type == "openai":
            temp_provider = provider_class(api_key="temp", base_url="https://api.openai.com/v1")
        elif provider_type in ["ollama", "llamacpp", "lemonade", "openai_compatible"]:
            temp_provider = provider_class(base_url="http://localhost")
        elif provider_type == "zai":
            temp_provider = provider_class(api_key="temp")
        elif provider_type == "minimax":
            temp_provider = provider_class(api_key="temp", group_id="temp")
        else:
            temp_provider = provider_class()

        capabilities = temp_provider.capabilities

        return {
            "provider_type": provider_type,
            "class_name": provider_class.__name__,
            "supports_streaming": capabilities.supports_streaming,
            "supports_function_calling": capabilities.supports_function_calling,
            "supports_vision": capabilities.supports_vision,
            "supports_json_mode": capabilities.supports_json_mode,
            "max_context_length": capabilities.max_context_length,
            "max_output_tokens": capabilities.max_output_tokens,
        }
    except Exception as e:
        logger.warning("Failed to get provider info", provider_type=provider_type, error=str(e))
        return {
            "provider_type": provider_type,
            "class_name": provider_class.__name__,
            "error": str(e),
        }


def get_all_provider_info() -> list[dict[str, Any]]:
    """
    Get information about all available providers.

    Returns:
        List of provider information dictionaries
    """
    return [get_provider_info(pt) for pt in PROVIDER_REGISTRY]
