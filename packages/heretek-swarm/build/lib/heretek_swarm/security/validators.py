"""
Input Validators for Guardrails System

Provides specialized validator classes for different validation checks.
"""

import re
from abc import ABC, abstractmethod

import structlog

logger = structlog.get_logger(__name__)


class InputValidator(ABC):
    """Abstract base class for input validators"""

    @abstractmethod
    async def validate(
        self, input_text: str, agent_id: str | None = None
    ) -> tuple[bool, str | None]:
        """
        Validate input and return (is_valid, reason)

        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """


class LengthValidator(InputValidator):
    """Validates input length constraints"""

    def __init__(self, min_length: int, max_length: int):
        self.min_length = min_length
        self.max_length = max_length

    async def validate(
        self, input_text: str, agent_id: str | None = None
    ) -> tuple[bool, str | None]:
        text_length = len(input_text)

        if text_length < self.min_length:
            logger.warning("input_too_short", agent_id=agent_id, length=text_length)
            return False, f"Input too short (min: {self.min_length})"

        if text_length > self.max_length:
            logger.warning(
                "input_too_long", agent_id=agent_id, length=text_length, max_length=self.max_length
            )
            return False, f"Input too long (max: {self.max_length})"

        return True, None


class BlockedPatternValidator(InputValidator):
    """Validates input against blocked regex patterns"""

    def __init__(self, compiled_patterns: list[re.Pattern]):
        self.patterns = compiled_patterns

    async def validate(
        self, input_text: str, agent_id: str | None = None
    ) -> tuple[bool, str | None]:
        for pattern in self.patterns:
            match = pattern.search(input_text)
            if match:
                logger.warning(
                    "input_blocked",
                    agent_id=agent_id,
                    pattern=pattern.pattern,
                    match=match.group(0),
                )
                return False, f"Blocked pattern detected: {pattern.pattern}"

        return True, None


class PersonalInfoValidator(InputValidator):
    """Validates input for personal information disclosure"""

    # Pre-compiled patterns for performance
    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    PHONE_PATTERN = re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b")
    SSN_PATTERN = re.compile(r"\b\d{3}[-]\d{2}[-]\d{4}\b")
    API_KEY_PATTERN = re.compile(r"\b[A-Za-z0-9]{20,}[_-][A-Za-z0-9]{10,}\b")

    def __init__(self, block_personal_info: bool = True):
        self.block_personal_info = block_personal_info

    async def validate(
        self, input_text: str, agent_id: str | None = None
    ) -> tuple[bool, str | None]:
        if not self.block_personal_info:
            return True, None

        # Check email
        if self.EMAIL_PATTERN.search(input_text):
            logger.warning("input_blocked_personal_email", agent_id=agent_id)
            return False, "Personal email address detected"

        # Check phone
        if self.PHONE_PATTERN.search(input_text):
            logger.warning("input_blocked_personal_phone", agent_id=agent_id)
            return False, "Personal phone number detected"

        # Check SSN
        if self.SSN_PATTERN.search(input_text):
            logger.warning("input_blocked_personal_ssn", agent_id=agent_id)
            return False, "Personal SSN pattern detected"

        # Check API keys
        if self.API_KEY_PATTERN.search(input_text):
            logger.warning("input_blocked_personal_api_key", agent_id=agent_id)
            return False, "API key pattern detected"

        return True, None


class CodeExecutionValidator(InputValidator):
    """Validates input for code execution attempts"""

    # Pre-compiled patterns for performance
    SHELL_PATTERN = re.compile(r"\b(sh|bash|cmd|powershell|exec)\s+[^\s]", re.IGNORECASE)
    PYTHON_EXEC_PATTERN = re.compile(r'\b(exec|eval|__import__|open\()[\'"]\s*\(', re.IGNORECASE)

    def __init__(self, block_code_execution: bool = True):
        self.block_code_execution = block_code_execution

    async def validate(
        self, input_text: str, agent_id: str | None = None
    ) -> tuple[bool, str | None]:
        if not self.block_code_execution:
            return True, None

        # Check shell commands
        if self.SHELL_PATTERN.search(input_text):
            logger.warning("input_blocked_code_execution", agent_id=agent_id)
            return False, "Shell command execution attempt detected"

        # Check Python exec
        if self.PYTHON_EXEC_PATTERN.search(input_text):
            logger.warning("input_blocked_python_execution", agent_id=agent_id)
            return False, "Python execution attempt detected"

        return True, None


class AllowedPatternsValidator(InputValidator):
    """Validates input against allowed patterns"""

    def __init__(self, allowed_patterns: list[str]):
        self.allowed_patterns = allowed_patterns
        self._compiled = [re.compile(p, re.IGNORECASE) for p in allowed_patterns]

    async def validate(
        self, input_text: str, agent_id: str | None = None
    ) -> tuple[bool, str | None]:
        if not self.allowed_patterns:
            return True, None

        for pattern in self._compiled:
            if pattern.search(input_text):
                return True, None

        logger.warning("input_not_allowed", agent_id=agent_id, input=input_text[:100])
        return False, "Input does not match allowed patterns"


class ValidatorChain:
    """Chains multiple validators together"""

    def __init__(self):
        self._validators: list[InputValidator] = []

    def add(self, validator: InputValidator) -> "ValidatorChain":
        """Add a validator to the chain"""
        self._validators.append(validator)
        return self

    async def validate(
        self, input_text: str, agent_id: str | None = None
    ) -> tuple[bool, str | None]:
        """Run all validators in sequence"""
        for validator in self._validators:
            is_valid, reason = await validator.validate(input_text, agent_id)
            if not is_valid:
                return False, reason
        return True, None
