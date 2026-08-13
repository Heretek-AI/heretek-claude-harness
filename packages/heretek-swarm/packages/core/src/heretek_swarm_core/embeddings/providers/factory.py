"""
Embedding Provider Factory

Factory for creating embedding provider instances based on configuration.
Supports dynamic provider instantiation and registry.
"""

from __future__ import annotations

from typing import Any

import structlog

from .base import EmbeddingConfigurationError, EmbeddingProviderBase
from .ollama_provider import OllamaEmbeddingProvider
from .openai_provider import OpenAIEmbeddingProvider

logger = structlog.get_logger("embeddings.providers.factory")

# Provider registry mapping provider types to implementation classes
PROVIDER_REGISTRY: dict[str, type[EmbeddingProviderBase]] = {
    "openai": OpenAIEmbeddingProvider,
    "openai_compatible": OpenAIEmbeddingProvider,  # Use OpenAI provider for compatible APIs
    "ollama": OllamaEmbeddingProvider,
}


def register_provider(
    provider_type: str,
    provider_class: type[EmbeddingProviderBase],
) -> None:
    """
    Register a new provider implementation.

    Args:
        provider_type: The provider type identifier
        provider_class: The provider implementation class
    """
    PROVIDER_REGISTRY[provider_type] = provider_class
    logger.info("Embedding provider registered", provider_type=provider_type)


def unregister_provider(provider_type: str) -> None:
    """
    Unregister a provider implementation.

    Args:
        provider_type: The provider type identifier
    """
    if provider_type in PROVIDER_REGISTRY:
        del PROVIDER_REGISTRY[provider_type]
        logger.info("Embedding provider unregistered", provider_type=provider_type)


def get_provider_class(provider_type: str) -> type[EmbeddingProviderBase]:
    """
    Get the provider class for a given type.

    Args:
        provider_type: The provider type identifier

    Returns:
        The provider implementation class

    Raises:
        EmbeddingConfigurationError: If the provider type is not registered
    """
    if provider_type not in PROVIDER_REGISTRY:
        available = ", ".join(PROVIDER_REGISTRY.keys())
        raise EmbeddingConfigurationError(
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


def create_embedding_provider(
    provider_type: str,
    config: dict[str, Any],
) -> EmbeddingProviderBase:
    """
    Create an embedding provider instance from configuration.

    This is the main factory function for creating providers. It takes a
    provider type and configuration dictionary and returns an initialized
    provider instance.

    Args:
        provider_type: The type of provider to create (e.g., "openai", "ollama")
        config: Configuration dictionary with provider-specific settings

    Returns:
        An initialized embedding provider instance

    Raises:
        EmbeddingConfigurationError: If configuration is invalid

    Example:
        # Create OpenAI embedding provider
        provider = create_embedding_provider(
            "openai",
            {
                "api_key": "sk-...",
                "default_model": "text-embedding-3-small"
            }
        )

        # Create Ollama embedding provider
        provider = create_embedding_provider(
            "ollama",
            {
                "base_url": "http://localhost:11434",
                "default_model": "nomic-embed-text"
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
                raise EmbeddingConfigurationError("OpenAI embedding provider requires api_key")
            return OpenAIEmbeddingProvider(
                api_key=api_key,
                base_url=base_url or "https://api.openai.com/v1",
                default_model=default_model,
                organization=config.get("organization"),
                extra_config=extra_config,
            )

        if provider_type == "openai_compatible":
            # Use OpenAI provider for compatible APIs
            if not base_url:
                raise EmbeddingConfigurationError(
                    "OpenAI-compatible embedding provider requires base_url"
                )
            return OpenAIEmbeddingProvider(
                api_key=api_key,
                base_url=base_url,
                default_model=default_model,
                extra_config=extra_config,
            )

        if provider_type == "ollama":
            return OllamaEmbeddingProvider(
                base_url=base_url or "http://localhost:11434",
                default_model=default_model,
                extra_config=extra_config,
            )

        # Fallback to generic instantiation for registered providers
        return provider_class(
            base_url=base_url,
            api_key=api_key,
            default_model=default_model,
            extra_config=extra_config,
        )

    except TypeError as e:
        raise EmbeddingConfigurationError(f"Invalid configuration for {provider_type}: {e}") from e


def create_embedding_provider_from_db_config(
    db_config: Any,
    api_key_decrypt_func: callable | None = None,
) -> EmbeddingProviderBase:
    """
    Create an embedding provider instance from a database configuration model.

    Args:
        db_config: Database configuration model (EmbeddingProvider from models.py)
        api_key_decrypt_func: Optional function to decrypt the API key

    Returns:
        An initialized embedding provider instance

    Example:
        provider = create_embedding_provider_from_db_config(
            db_embedding_provider,
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

    return create_embedding_provider(db_config.provider_type, config)


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
    try:
        if provider_type == "openai":
            temp_provider = provider_class(api_key="temp")
        elif provider_type == "ollama":
            temp_provider = provider_class()
        else:
            temp_provider = provider_class()

        capabilities = temp_provider.capabilities

        return {
            "provider_type": provider_type,
            "class_name": provider_class.__name__,
            "max_batch_size": capabilities.max_batch_size,
            "max_tokens_per_batch": capabilities.max_tokens_per_batch,
            "supported_formats": capabilities.supported_formats,
            "supports_dimensions_override": capabilities.supports_dimensions_override,
            "default_dimensions": capabilities.default_dimensions,
        }
    except Exception as e:
        logger.warning(
            "Failed to get embedding provider info",
            provider_type=provider_type,
            error=str(e),
        )
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
