"""LLM error types — distinguishable for retry / abstain logic."""


class LLMError(Exception):
    """Base class for all LLM errors."""


class LLMUnavailable(LLMError):
    """All providers failed; circuit breaker tripped or every chain exhausted."""


class LLMTimeout(LLMError):
    """Provider exceeded the configured timeout."""


class LLMContentFiltered(LLMError):
    """Provider rejected the request as filtered content."""


class LLMMalformed(LLMError):
    """Provider returned output that did not match expected schema."""
