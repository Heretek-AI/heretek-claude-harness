"""
LLM provider catalog for the configuration wizard.

Extracted from ``api/wizard.py`` as part of Phase 2.4 of PLAN.md
(§1.4 "Configuration service masquerading as a router"). The
``AVAILABLE_PROVIDERS`` dict is 110+ lines of metadata for
the seven LLM backends the wizard can configure. Moving it to
:mod:`heretek_swarm.config` keeps the wizard router thin and
lets other surfaces (the configuration CLI, the providers
config router, the LLM provider self-test, etc.) reuse the
same catalog.

Backwards compatibility: ``from heretek_swarm.api.wizard
import AVAILABLE_PROVIDERS`` keeps working — the wizard module
re-exports the constant from this file.
"""

from __future__ import annotations


AVAILABLE_PROVIDERS: dict[str, dict[str, object]] = {
    "anthropic": {
        "id": "anthropic",
        "name": "Anthropic Claude",
        "type": "anthropic",
        "icon": "brain",
        "description": "Claude models via Anthropic's API",
        "default_model": "claude-sonnet-4-20250514",
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": True,
        "requires_api_key": True,
        "api_key_label": "Anthropic API Key",
        "api_key_env_var": "ANTHROPIC_API_KEY",
        "base_url": "https://api.anthropic.com",
        "color": "#ff6b35",
    },
    "openai": {
        "id": "openai",
        "name": "OpenAI",
        "type": "openai",
        "icon": "sparkles",
        "description": "GPT models via OpenAI's API",
        "default_model": "gpt-4o",
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": True,
        "requires_api_key": True,
        "api_key_label": "OpenAI API Key",
        "api_key_env_var": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "color": "#10a37f",
    },
    "ollama": {
        "id": "ollama",
        "name": "Ollama",
        "type": "ollama",
        "icon": "cpu",
        "description": "Local LLM inference with Ollama",
        "default_model": "llama3.2",
        "supports_streaming": True,
        "supports_function_calling": False,
        "supports_vision": False,
        "requires_api_key": False,
        "api_key_label": "Ollama API Key (optional)",
        "api_key_env_var": "OLLAMA_API_KEY",
        "base_url": "http://localhost:11434",
        "color": "#ff6b9d",
    },
    "groq": {
        "id": "groq",
        "name": "Groq",
        "type": "openai_compatible",
        "icon": "zap",
        "description": "Fast inference via Groq's API",
        "default_model": "llama-3.3-70b-versatile",
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": False,
        "requires_api_key": True,
        "api_key_label": "Groq API Key",
        "api_key_env_var": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "color": "#fb5a47",
    },
    "mistral": {
        "id": "mistral",
        "name": "Mistral AI",
        "type": "openai_compatible",
        "icon": "cloud",
        "description": "Mistral models via Mistral's API",
        "default_model": "mistral-large-latest",
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": False,
        "requires_api_key": True,
        "api_key_label": "Mistral API Key",
        "api_key_env_var": "MISTRAL_API_KEY",
        "base_url": "https://api.mistral.ai/v1",
        "color": "#d636f8",
    },
    "deepseek": {
        "id": "deepseek",
        "name": "DeepSeek",
        "type": "openai_compatible",
        "icon": "fish",
        "description": "DeepSeek V3 and Coder models",
        "default_model": "deepseek-chat",
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": False,
        "requires_api_key": True,
        "api_key_label": "DeepSeek API Key",
        "api_key_env_var": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com",
        "color": "#4ade80",
    },
    "local": {
        "id": "local",
        "name": "Local / LiteLLM",
        "type": "openai_compatible",
        "icon": "server",
        "description": "Local OpenAI-compatible server (LiteLLM, vLLM, etc.)",
        "default_model": "gpt-3.5-turbo",
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": False,
        "requires_api_key": False,
        "api_key_label": "LiteLLM API Key (optional)",
        "api_key_env_var": "LITELLM_API_KEY",
        "base_url": "http://localhost:4000",
        "color": "#60a5fa",
    },
}


__all__ = ["AVAILABLE_PROVIDERS"]
