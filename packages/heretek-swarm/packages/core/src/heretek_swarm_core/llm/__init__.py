"""heretek_swarm_core.llm — LLM provider garage and compatibility shims.

Re-exports the canonical public surface so
``from heretek_swarm_core.llm import *`` resolves the same names that
previously lived under ``heretek_swarm.llm``.
"""

from heretek_swarm_core.llm.headroom_compat import (  # noqa: F401
    HEADROOM_AVAILABLE,
    wrap as headroom_wrap,
    unwrap as headroom_unwrap,
)
from heretek_swarm_core.llm.hindsight_compat import (  # noqa: F401
    HindsightClient,
    HINDSIGHT_ENABLED as HINDSIGHT_AVAILABLE,
    HINDSIGHT_URL,
    get_hindsight_client,
)
from heretek_swarm_core.llm.model_garage import (  # noqa: F401
    ChatMessage,
    LLMRequest,
    LLMResponse,
    LLMProvider,
    ModelInfo,
    ModelGarage,
    ProviderConfig,
    ProviderType,
    get_model_garage,
    initialize_model_garage,
    register_provider_class,
)
from heretek_swarm_core.llm.pydantic_ai_agent_factory import (  # noqa: F401
    build_pydantic_ai_agent_for,
)

__all__ = [
    "HEADROOM_AVAILABLE",
    "headroom_wrap",
    "headroom_unwrap",
    "HindsightClient",
    "HINDSIGHT_AVAILABLE",
    "HINDSIGHT_URL",
    "get_hindsight_client",
    "ChatMessage",
    "LLMRequest",
    "LLMResponse",
    "LLMProvider",
    "ModelInfo",
    "ModelGarage",
    "ProviderConfig",
    "ProviderType",
    "get_model_garage",
    "initialize_model_garage",
    "register_provider_class",
    "build_pydantic_ai_agent_for",
]
