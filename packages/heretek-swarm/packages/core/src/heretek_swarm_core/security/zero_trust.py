"""Zero-Trust Security Module — backward-compatible re-export shim.

All implementation has been moved to the `zero_trust/` sub-package.
This module re-exports everything for backward compatibility.
"""

from heretek_swarm_core.security.zero_trust.audit_logger import AuditLogConfig, AuditLogger
from heretek_swarm_core.security.zero_trust.context_validator import (
    BehavioralBaseline,
    ContextValidationConfig,
    ContextValidator,
)
from heretek_swarm_core.security.zero_trust.exceptions import (
    EXCEPTION_CATEGORIES,
    EXCEPTION_RULES,
    get_exception_rule,
    is_exception_topic,
    should_sanitize,
)
from heretek_swarm_core.security.zero_trust.external_validator import (
    ExternalInputValidator,
    ExternalThreatConfig,
)
from heretek_swarm_core.security.zero_trust.input_validator import (
    InputValidationConfig,
    InputValidator,
    ValidatedInput,
)
from heretek_swarm_core.security.zero_trust.orchestrator import (
    ZeroTrustValidator,
    create_default_validator,
    create_external_validator,
    create_strict_validator,
)
from heretek_swarm_core.security.zero_trust.output_validator import (
    OutputValidationConfig,
    OutputValidator,
)
from heretek_swarm_core.security.zero_trust.result_types import (
    LayerResult,
    Severity,
    ZeroTrustResult,
)

__all__ = [
    'AuditLogConfig',
    'AuditLogger',
    'BehavioralBaseline',
    'ContextValidationConfig',
    'ContextValidator',
    'EXCEPTION_CATEGORIES',
    'EXCEPTION_RULES',
    'ExternalInputValidator',
    'ExternalThreatConfig',
    'InputValidationConfig',
    'InputValidator',
    'LayerResult',
    'OutputValidationConfig',
    'OutputValidator',
    'Severity',
    'ValidatedInput',
    'ZeroTrustResult',
    'ZeroTrustValidator',
    'create_default_validator',
    'create_external_validator',
    'create_strict_validator',
    'get_exception_rule',
    'is_exception_topic',
    'should_sanitize',
]
