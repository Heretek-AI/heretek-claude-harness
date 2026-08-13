"""Zero-Trust Orchestrator — coordinates all 4 validation layers + external threat detection."""

import time
import uuid
from typing import Any

from .audit_logger import AuditLogConfig, AuditLogger
from .context_validator import ContextValidationConfig, ContextValidator
from .external_validator import ExternalInputValidator, ExternalThreatConfig
from .input_validator import InputValidationConfig, InputValidator, ValidatedInput
from .output_validator import OutputValidationConfig, OutputValidator
from .result_types import LayerResult, Severity, ZeroTrustResult


class ZeroTrustValidator:
    """Enhanced Zero-Trust Security Orchestrator with External Threat Detection.

    Coordinates all 4 validation layers:
    - Layer 1: Input Validation
    - Layer 2: Context Validation
    - Layer 3: Output Validation
    - Layer 4: Audit Logging
    - External input validation (SAFE-02)
    - Prompt injection detection
    - Source reputation checking

    Target Performance:
    - Validation latency < 50ms p95
    - False negative rate < 0.1%
    - Throughput > 1000 validations/second
    """

    def __init__(
        self,
        input_config: InputValidationConfig | None = None,
        context_config: ContextValidationConfig | None = None,
        output_config: OutputValidationConfig | None = None,
        audit_config: AuditLogConfig | None = None,
        external_config: ExternalThreatConfig | None = None,
    ):
        self.input_validator = InputValidator(input_config)
        self.context_validator = ContextValidator(context_config)
        self.output_validator = OutputValidator(output_config)
        self.audit_logger = AuditLogger(audit_config)
        self.external_validator = ExternalInputValidator(external_config, self.context_validator)

        self._validation_count = 0
        self._total_latency_ms = 0.0
        self._failed_validations = 0

    async def validate_request(
        self,
        data: dict[str, Any],
        context: dict[str, Any] | None = None,
        agent_id: str | None = None,
        request_id: str | None = None,
        model_class: type[ValidatedInput] | None = None,
    ) -> ZeroTrustResult:
        """Validate a request through all 4 layers."""
        start_time = time.time()
        request_id = request_id or str(uuid.uuid4())

        layer1 = self.input_validator.validate(data, model_class, agent_id)

        if layer1.severity == Severity.CRITICAL:
            layer2 = LayerResult(
                layer="context", passed=True,
                reason="Skipped due to Layer 1 critical failure", severity=Severity.INFO,
            )
        else:
            layer2 = self.context_validator.validate(data, context, agent_id)

        layer3 = LayerResult(
            layer="output", passed=True,
            reason="Input validation - output layer applied on response", severity=Severity.INFO,
        )

        passed = layer1.passed and layer2.passed
        latency_ms = (time.time() - start_time) * 1000

        result = ZeroTrustResult(
            passed=passed, layer1=layer1, layer2=layer2, layer3=layer3,
            layer4=LayerResult(layer="audit", passed=True, severity=Severity.INFO),
            request_id=request_id, agent_id=agent_id, total_latency_ms=latency_ms,
        )

        result.layer4 = self.audit_logger.log(
            event_type="request_validation", result=result,
            additional_context={"layer1_passed": layer1.passed, "layer2_passed": layer2.passed},
        )

        self._validation_count += 1
        self._total_latency_ms += latency_ms
        if not passed:
            self._failed_validations += 1

        return result

    async def validate_response(
        self, output: Any, agent_id: str | None = None, request_id: str | None = None,
    ) -> ZeroTrustResult:
        """Validate a response through output validation layer."""
        start_time = time.time()
        request_id = request_id or str(uuid.uuid4())

        layer1 = LayerResult(layer="input", passed=True, reason="Response validation - input layer skipped", severity=Severity.INFO)
        layer2 = LayerResult(layer="context", passed=True, reason="Response validation - context layer skipped", severity=Severity.INFO)
        layer3 = self.output_validator.validate(output, agent_id)

        latency_ms = (time.time() - start_time) * 1000
        sanitized = layer3.details.get("sanitized_output")

        result = ZeroTrustResult(
            passed=layer3.passed, layer1=layer1, layer2=layer2, layer3=layer3,
            layer4=LayerResult(layer="audit", passed=True, severity=Severity.INFO),
            request_id=request_id, agent_id=agent_id, total_latency_ms=latency_ms,
            sanitized_output=sanitized,
        )

        result.layer4 = self.audit_logger.log(
            event_type="response_validation", result=result,
            additional_context={"layer3_passed": layer3.passed, "pii_detected": layer3.details.get("pii_detected", [])},
        )

        return result

    async def validate_external_input(
        self, data: dict[str, Any], source: str, source_type: str = "unknown",
        context: dict[str, Any] | None = None, agent_id: str | None = None,
        request_id: str | None = None,
    ) -> ZeroTrustResult:
        """Validate external input through all layers plus external threat detection."""
        start_time = time.time()
        request_id = request_id or str(uuid.uuid4())

        layer1 = self.input_validator.validate(data, None, agent_id)

        if layer1.severity == Severity.CRITICAL:
            layer2 = LayerResult(layer="context", passed=True, reason="Skipped due to Layer 1 critical failure", severity=Severity.INFO)
        else:
            layer2 = self.context_validator.validate(data, context, agent_id)

        external_passed, external_reason, external_details = self.external_validator.validate_external_input(data, source, source_type)

        layer3 = LayerResult(layer="output", passed=True, reason="Input validation - output layer applied on response", severity=Severity.INFO)

        passed = layer1.passed and layer2.passed and external_passed
        latency_ms = (time.time() - start_time) * 1000

        result = ZeroTrustResult(
            passed=passed, layer1=layer1, layer2=layer2, layer3=layer3,
            layer4=LayerResult(layer="audit", passed=True, severity=Severity.INFO),
            request_id=request_id, agent_id=agent_id, total_latency_ms=latency_ms,
        )

        result.layer4 = self.audit_logger.log(
            event_type="external_input_validation", result=result,
            additional_context={
                "layer1_passed": layer1.passed, "layer2_passed": layer2.passed,
                "external_passed": external_passed,
                "external_threats": external_details.get("threat_indicators", []),
            },
        )

        self._validation_count += 1
        self._total_latency_ms += latency_ms
        if not passed:
            self._failed_validations += 1
            self.external_validator.update_reputation(source, True)
        else:
            self.external_validator.update_reputation(source, False)

        return result

    def get_metrics(self) -> dict[str, Any]:
        avg_latency = self._total_latency_ms / self._validation_count if self._validation_count > 0 else 0
        return {
            "total_validations": self._validation_count,
            "failed_validations": self._failed_validations,
            "success_rate": (
                (self._validation_count - self._failed_validations) / self._validation_count
                if self._validation_count > 0 else 1.0
            ),
            "avg_latency_ms": avg_latency,
            "event_counts": self.audit_logger.get_event_counts(),
        }

    def get_high_severity_events(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.audit_logger.get_high_severity_events(limit)


def create_default_validator() -> ZeroTrustValidator:
    return ZeroTrustValidator(
        input_config=InputValidationConfig(),
        context_config=ContextValidationConfig(),
        output_config=OutputValidationConfig(),
        audit_config=AuditLogConfig(),
    )


def create_strict_validator() -> ZeroTrustValidator:
    return ZeroTrustValidator(
        input_config=InputValidationConfig(max_content_size=5120, require_uuid_v4=True, max_nesting_depth=5),
        context_config=ContextValidationConfig(
            enable_injection_detection=True, enable_behavioral_analysis=True,
            enable_anomaly_detection=True, anomaly_threshold=2.0,
        ),
        output_config=OutputValidationConfig(
            enable_pii_detection=True, enable_sensitive_data_filtering=True,
            redact_pii=True, max_output_size=50000,
        ),
        audit_config=AuditLogConfig(enable_logging=True, log_all_events=True, retention_days=90),
    )


def create_external_validator() -> ExternalInputValidator:
    return ExternalInputValidator(external_config=ExternalThreatConfig(), context_validator=ContextValidator())
