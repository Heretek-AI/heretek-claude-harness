"""
Guardrails System for Heretek Swarm

Provides input validation, output filtering, and content safety checks.
Reference: PraisonAI guardrails pattern
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import structlog

from .validators import (
    AllowedPatternsValidator,
    BlockedPatternValidator,
    CodeExecutionValidator,
    LengthValidator,
    PersonalInfoValidator,
    ValidatorChain,
)

logger = structlog.get_logger()


class GuardrailsAction(StrEnum):
    """Actions to take when guardrails are triggered"""

    BLOCK = "block"
    WARN = "warn"
    MODIFY = "modify"
    ESCALATE = "escalate"


@dataclass
class BlockedPattern:
    """A blocked pattern configuration"""

    pattern: str
    description: str
    severity: str  # "critical", "high", "medium", "low"
    action: GuardrailsAction


@dataclass
class ValidationResult:
    """Result of input validation"""

    valid: bool
    reason: str | None = None
    pattern: str | None = None
    max_length: int | None = None
    modified_content: str | None = None


@dataclass
class FilterResult:
    """Result of output filtering"""

    original: str
    filtered: str
    blocked_content: str | None = None
    reason: str | None = None


@dataclass
class GuardrailsConfig:
    """Configuration for guardrails system"""

    # Input validation
    max_input_length: int = 10000
    min_input_length: int = 1
    allowed_patterns: list[str] = field(default_factory=list)

    # Output filtering
    enable_content_filter: bool = True
    block_personal_info: bool = True
    block_code_execution: bool = True

    # Blocked patterns
    blocked_patterns: list[BlockedPattern] = field(default_factory=list)

    # Rate limiting per agent
    agent_rate_limits: dict[str, int] = field(default_factory=dict)


class GuardrailsSystem:
    """
    Input/output validation and safety system for Heretek Swarm.

    Provides comprehensive security guardrails to prevent:
    - Malicious input injection
    - Personal information disclosure
    - Code execution attempts
    - Harmful content generation
    """

    def __init__(self, config: GuardrailsConfig | None = None):
        """
        Initialize guardrails system.

        Args:
            config: Guardrails configuration
        """
        self.config = config or GuardrailsConfig()
        self._blocked_patterns = self._compile_blocked_patterns()
        self._validator_chain = self._build_validator_chain()
        logger.info(
            "guardrails_initialized",
            blocked_patterns_count=len(self.config.blocked_patterns),
            max_input_length=self.config.max_input_length,
        )

    def _compile_blocked_patterns(self) -> list[re.Pattern]:
        """Compile regex patterns for efficient matching"""
        compiled = []
        for bp in self.config.blocked_patterns:
            try:
                pattern = re.compile(bp.pattern, re.IGNORECASE)
                compiled.append(pattern)
            except re.error as e:
                logger.warning("invalid_pattern", pattern=bp.pattern, error=str(e))
        return compiled

    def _build_validator_chain(self) -> ValidatorChain:
        """Build the validator chain for input validation"""
        chain = ValidatorChain()

        # Length validation
        chain.add(
            LengthValidator(
                min_length=self.config.min_input_length, max_length=self.config.max_input_length
            )
        )

        # Blocked patterns validation
        chain.add(BlockedPatternValidator(self._blocked_patterns))

        # Personal information validation
        chain.add(PersonalInfoValidator(self.config.block_personal_info))

        # Code execution validation
        chain.add(CodeExecutionValidator(self.config.block_code_execution))

        # Allowed patterns validation
        chain.add(AllowedPatternsValidator(self.config.allowed_patterns))

        return chain

    async def validate_input(
        self, input_text: str, agent_id: str | None = None
    ) -> ValidationResult:
        """
        Validate user input against guardrails.

        Args:
            input_text: Input text to validate
            agent_id: Agent ID for logging

        Returns:
            ValidationResult with validation status
        """
        # Use validator chain for all validation checks
        is_valid, reason = await self._validator_chain.validate(input_text, agent_id)

        if is_valid:
            logger.info("input_validated", agent_id=agent_id, length=len(input_text))
            return ValidationResult(valid=True)

        return ValidationResult(valid=False, reason=reason)

    async def filter_output(self, output_text: str, agent_id: str | None = None) -> FilterResult:
        """
        Filter agent output against guardrails.

        Args:
            output_text: Output text to filter
            agent_id: Agent ID for logging

        Returns:
            FilterResult with filtered content
        """
        if not self.config.enable_content_filter:
            return FilterResult(
                original=output_text, filtered=output_text, blocked_content=None, reason=None
            )

        filtered = output_text
        blocked_content = None
        reason = None

        # Block personal information in output
        if self.config.block_personal_info:
            # Email addresses
            emails = re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", filtered)
            if emails:
                filtered = re.sub(
                    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[REDACTED]", filtered
                )
                blocked_content = ", ".join(emails)
                reason = "Personal email addresses redacted"

        # Phone numbers
        phones = re.findall(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", filtered)
        if phones:
            filtered = re.sub(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", "[REDACTED]", filtered)
            if blocked_content:
                blocked_content += f", {phones}"
            reason = "Personal phone numbers redacted"

        # API keys - match common API key patterns
        # Patterns: sk_live_*, sk_test_*, AKIA*, ghp_*, github_pat_*, etc.
        # Note: Use [^\s] to match any non-whitespace including brackets in redacted keys
        api_key_patterns = [
            r"\bsk_live_[^\s]{10,}\b",  # Stripe live keys (allow brackets in redacted values)
            r"\bsk_test_[^\s]{10,}\b",  # Stripe test keys
            r"\bAKIA[A-Z0-9]{16}\b",  # AWS Access Key ID
            r"\bghp_[A-Za-z0-9]{36}\b",  # GitHub personal access tokens
            r"\bgithub_pat_[^\s]{22,}\b",  # GitHub fine-grained tokens
            r"\b[A-Za-z0-9]{20,}[_-][^\s]{10,}\b",  # Generic long API keys
        ]
        api_keys = []
        for pattern in api_key_patterns:
            api_keys.extend(re.findall(pattern, filtered))
        if api_keys:
            # Replace each API key pattern found
            for pattern in api_key_patterns:
                filtered = re.sub(pattern, "[REDACTED]", filtered)
            if blocked_content:
                blocked_content += f", {api_keys}"
            reason = "API keys redacted"

        # Block code execution in output
        if self.config.block_code_execution:
            # Shell command patterns
            if re.search(r"\b(sh|bash|cmd|powershell|exec)\s+[^\s]", filtered, re.IGNORECASE):
                filtered = re.sub(  # noqa: B034
                    r"\b(sh|bash|cmd|powershell|exec)\s+[^\s]", "[BLOCKED]", filtered, re.IGNORECASE
                )
                blocked_content = "Shell commands"
                reason = "Code execution blocked"

            # Python exec patterns
            if re.search(r'\b(exec|eval|__import__|open\()[\'"]\s*\(', filtered, re.IGNORECASE):
                filtered = re.sub(  # noqa: B034
                    r'\b(exec|eval|__import__|open\()[\'"]\s*\(',
                    "[BLOCKED]",
                    filtered,
                    re.IGNORECASE,
                )
                if blocked_content:
                    blocked_content = f"{blocked_content}, Python exec"
                reason = "Python execution blocked"

        if filtered != output_text:
            logger.warning(
                "output_filtered",
                agent_id=agent_id,
                original_length=len(output_text),
                filtered_length=len(filtered),
                reason=reason,
            )

        return FilterResult(
            original=output_text, filtered=filtered, blocked_content=blocked_content, reason=reason
        )

    def add_blocked_pattern(
        self,
        pattern: str,
        description: str,
        severity: str = "medium",
        action: GuardrailsAction = GuardrailsAction.BLOCK,
    ) -> None:
        """
        Add a blocked pattern to the guardrails system.

        Args:
            pattern: Regex pattern to block
            description: Description of the pattern
            severity: Severity level
            action: Action to take when pattern matches
        """
        blocked_pattern = BlockedPattern(
            pattern=pattern, description=description, severity=severity, action=action
        )
        self.config.blocked_patterns.append(blocked_pattern)
        self._blocked_patterns = self._compile_blocked_patterns()

        logger.info("blocked_pattern_added", pattern=pattern, severity=severity)

    def remove_blocked_pattern(self, pattern: str) -> bool:
        """
        Remove a blocked pattern from the guardrails system.

        Args:
            pattern: Pattern to remove

        Returns:
            True if pattern was removed
        """
        original_count = len(self.config.blocked_patterns)
        self.config.blocked_patterns = [
            bp for bp in self.config.blocked_patterns if bp.pattern != pattern
        ]

        if len(self.config.blocked_patterns) < original_count:
            self._blocked_patterns = self._compile_blocked_patterns()
            logger.info("blocked_pattern_removed", pattern=pattern)
            return True

        logger.warning("blocked_pattern_not_found", pattern=pattern)
        return False

    def get_blocked_patterns(self) -> list[dict[str, Any]]:
        """
        Get list of all blocked patterns.

        Returns:
            List of blocked pattern configurations
        """
        return [
            {
                "pattern": bp.pattern,
                "description": bp.description,
                "severity": bp.severity,
                "action": bp.action.value,
            }
            for bp in self.config.blocked_patterns
        ]

    async def check_agent_rate_limit(self, agent_id: str, _action: str) -> bool:
        """
        Check if agent has exceeded its rate limit.

        Args:
            agent_id: Agent ID
            action: Action being performed

        Returns:
            True if action is allowed, False otherwise
        """
        self.config.agent_rate_limits.get(agent_id, 100)

        # This would integrate with rate limiting system
        # For now, return True (allow all actions)
        return True


# =============================================================================
# Default Blocked Patterns
# =============================================================================

DEFAULT_BLOCKED_PATTERNS = [
    # SQL Injection patterns
    BlockedPattern(
        pattern=r"(?i)(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION|SCRIPT)\b)",
        description="SQL injection attempt",
        severity="critical",
        action=GuardrailsAction.BLOCK,
    ),
    # Command injection patterns
    BlockedPattern(
        pattern=r"(?i)(\b(sh|bash|cmd|powershell|exec)\s+[^\s])",
        description="Command injection attempt",
        severity="critical",
        action=GuardrailsAction.BLOCK,
    ),
    # XSS patterns
    BlockedPattern(
        pattern=r"<script[^>]*>.*?</script>|javascript:|on\w+\s*=",
        description="XSS attempt",
        severity="critical",
        action=GuardrailsAction.BLOCK,
    ),
    # Path traversal patterns
    BlockedPattern(
        pattern=r"\.\./|\.\.\\|[A-Za-z]:\\|[A-Za-z]:\.\./",
        description="Path traversal attempt",
        severity="critical",
        action=GuardrailsAction.BLOCK,
    ),
]


def create_default_guardrails() -> GuardrailsSystem:
    """
    Create a guardrails system with default blocked patterns.

    Returns:
        Configured GuardrailsSystem instance
    """
    config = GuardrailsConfig(
        blocked_patterns=DEFAULT_BLOCKED_PATTERNS.copy(),
        block_personal_info=True,
        block_code_execution=True,
        enable_content_filter=True,
    )

    return GuardrailsSystem(config=config)
