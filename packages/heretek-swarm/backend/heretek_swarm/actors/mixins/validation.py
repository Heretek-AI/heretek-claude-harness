"""ValidationMixin for Zero-Trust internal function validation (ZERO-02).

This mixin provides pre-execution validation for all agent functions that
handle external input or cross-agent messages. It enforces the Zero-Trust
principle: never trust, always verify.

Features:
- Pre-execution input validation hooks
- Behavioral baseline tracking
- Anomaly detection with configurable thresholds
- Validation timeout protection
- Circular validation prevention
"""

import time
from typing import Any

import structlog

logger = structlog.get_logger("ValidationMixin")


class ValidationMixin:
    """Mixin for Zero-Trust internal validation (ZERO-02)."""

    # =========================================================================
    # Behavioral Baseline Constants
    # =========================================================================
    # Critical immutable behaviors that are always enforced regardless of
    # learned baseline. These rules represent hard security boundaries.
    # These were originally defined in actors/validation.py and are consolidated
    # here as the single source of truth.

    IMMUTABLE_RULES: list[dict[str, str]] = [
        {
            "pattern": r"eval\s*\(",
            "severity": "CRITICAL",
            "description": "Code execution via eval()",
            "action": "BLOCK",
        },
        {
            "pattern": r"exec\s*\(",
            "severity": "CRITICAL",
            "description": "Code execution via exec()",
            "action": "BLOCK",
        },
        {
            "pattern": r"__import__\s*\(",
            "severity": "HIGH",
            "description": "Dynamic import via __import__",
            "action": "BLOCK",
        },
        {
            "pattern": r"subprocess\s*\(",
            "severity": "HIGH",
            "description": "Shell execution via subprocess",
            "action": "BLOCK",
        },
        {
            "pattern": r"os\.system\s*\(",
            "severity": "HIGH",
            "description": "System command via os.system",
            "action": "BLOCK",
        },
        {
            "pattern": r"pickle\.loads?",
            "severity": "HIGH",
            "description": "Unpickle arbitrary data",
            "action": "BLOCK",
        },
        {
            "pattern": r"ctorch\.load|torch\.load",
            "severity": "HIGH",
            "description": "Loading untrusted PyTorch models",
            "action": "BLOCK",
        },
        {
            "pattern": r"yaml\.load\s*\(\s*Loader\s*=\s*None",
            "severity": "HIGH",
            "description": "Unsafe YAML deserialization",
            "action": "BLOCK",
        },
    ]

    BASELINE_CONFIG: dict[str, object] = {
        "initialization_mode": "static_rules_bootstrap",
        "learning_period": 100,
        "anomaly_threshold": 3.0,
        "min_baseline_samples": 50,
        "baseline_decay_factor": 0.95,
        "max_baseline_age_hours": 24,
        "enable_immutable_rules": True,
        "enable_behavioral_learning": True,
        "flag_anomalies_until_baseline": True,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ZERO-02: Validation configuration
        self._validation_timeout_ms: float = self._get_config_value("validation_timeout_ms", 10.0)
        self._anomaly_threshold_std_dev: float = self._get_config_value(
            "anomaly_threshold_std_dev", 3.0
        )

        # Behavioral baseline tracking
        self._behavioral_baseline: dict[str, Any] = {}
        self._behavioral_history: list[dict[str, Any]] = []
        self._max_history_size: int = 1000

        # Circular validation prevention
        self._validated_outputs: set[str] = set()
        self._max_validated_outputs: int = 10000

        # Validation statistics
        self._validation_stats = {
            "total_validations": 0,
            "successful_validations": 0,
            "failed_validations": 0,
            "timeout_validations": 0,
            "anomalies_detected": 0,
        }

        logger.info(
            "zero02_validation_mixin_initialized",
            agent_id=getattr(self, "agent_id", "unknown"),
            validation_timeout_ms=self._validation_timeout_ms,
            anomaly_threshold=self._anomaly_threshold_std_dev,
        )

    def _get_config_value(self, key: str, default: Any) -> Any:
        """Get configuration value from agent config or default."""
        if hasattr(self, "_config") and self._config:
            return self._config.get(key, default)
        return default

    async def validate_input(
        self,
        input_data: Any,
        operation: str,
        source_id: str | None = None,
    ) -> tuple[bool, Any]:
        """
        ZERO-02: Validate input before executing function.

        All agent functions that handle external input or cross-agent messages
        should call this method first.

        Validation steps:
        1. Check for circular validation (already validated internal outputs)
        2. Apply validation timeout (fail-safe after 10ms)
        3. Check against behavioral baseline
        4. Detect anomalies at >= 3.0 std dev

        Args:
            input_data: Data to validate
            operation: Name of the operation being performed
            source_id: Optional identifier of the data source

        Returns:
            Tuple of (is_valid, sanitized_data)
            If is_valid is False, the operation should be rejected
        """
        start_time = time.perf_counter()
        self._validation_stats["total_validations"] += 1

        try:
            # Step 1: Check for circular validation
            if self._is_already_validated(input_data):
                logger.debug(
                    "zero02_skip_validation_already_validated",
                    operation=operation,
                    source_id=source_id,
                )
                self._validation_stats["successful_validations"] += 1
                return True, input_data

            # Step 2: Apply timeout protection
            async def _validate_with_timeout() -> tuple[bool, Any]:
                return await self._perform_validation(input_data, operation, source_id)

            # Run validation with timeout
            validation_result = await self._run_with_timeout(
                _validate_with_timeout(),
                timeout_ms=self._validation_timeout_ms,
            )

            if validation_result is None:
                # Timeout occurred
                self._validation_stats["timeout_validations"] += 1
                logger.warning(
                    "zero02_validation_timeout",
                    operation=operation,
                    timeout_ms=self._validation_timeout_ms,
                )
                return False, None

            is_valid, sanitized_data = validation_result

            if is_valid:
                self._validation_stats["successful_validations"] += 1
                # Mark as validated to prevent circular validation
                self._mark_as_validated(input_data)
            else:
                self._validation_stats["failed_validations"] += 1

            return is_valid, sanitized_data

        except Exception as e:
            self._validation_stats["failed_validations"] += 1
            logger.error(
                "zero02_validation_error",
                operation=operation,
                error=str(e),
            )
            return False, None

        finally:
            # Track validation latency
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            if elapsed_ms > self._validation_timeout_ms:
                logger.warning(
                    "zero02_validation_exceeded_timeout",
                    operation=operation,
                    elapsed_ms=elapsed_ms,
                    timeout_ms=self._validation_timeout_ms,
                )

    async def _perform_validation(
        self,
        input_data: Any,
        operation: str,
        source_id: str | None = None,
    ) -> tuple[bool, Any]:
        """
        Perform actual validation logic.

        Override this method in subclasses for custom validation logic.

        Default implementation:
        1. Basic type validation
        2. Behavioral baseline check
        3. Anomaly detection
        """
        # Basic validation - not None
        if input_data is None:
            logger.warning(
                "zero02_rejected_null_input",
                operation=operation,
                source_id=source_id,
            )
            return False, None

        # Behavioral baseline check
        _baseline_valid, anomaly_score = self._check_behavioral_baseline(input_data, operation)

        if anomaly_score >= self._anomaly_threshold_std_dev:
            self._validation_stats["anomalies_detected"] += 1
            logger.warning(
                "zero02_behavioral_anomaly_detected",
                operation=operation,
                anomaly_score=anomaly_score,
                threshold=self._anomaly_threshold_std_dev,
                source_id=source_id,
            )
            return False, None

        # Update behavioral history
        self._update_behavioral_history(input_data, operation)

        return True, input_data

    async def _run_with_timeout(self, coro, timeout_ms: float) -> Any | None:
        """Run coroutine with timeout, returning None on timeout."""
        import asyncio

        try:
            timeout_sec = timeout_ms / 1000.0
            return await asyncio.wait_for(coro, timeout=timeout_sec)
        except TimeoutError:
            return None
        except Exception:
            return None

    def _is_already_validated(self, data: Any) -> bool:
        """Check if data has already been validated (prevent circular validation)."""
        if not isinstance(data, (dict, list)):
            return False

        # Create a hash of the data for quick lookup
        data_hash = self._hash_data(data)
        return data_hash in self._validated_outputs

    def _mark_as_validated(self, data: Any) -> None:
        """Mark data as validated to prevent circular validation."""
        if not isinstance(data, (dict, list)):
            return

        data_hash = self._hash_data(data)
        self._validated_outputs.add(data_hash)

        # Prune old entries if needed
        if len(self._validated_outputs) > self._max_validated_outputs:
            # Remove oldest 10%
            to_remove = self._max_validated_outputs // 10
            for _ in range(to_remove):
                if self._validated_outputs:
                    self._validated_outputs.pop()

    def _hash_data(self, data: Any) -> str:
        """Create a hash of data for comparison."""
        import hashlib
        import json

        try:
            data_str = json.dumps(data, sort_keys=True, default=str)
            return hashlib.sha256(data_str.encode()).hexdigest()
        except Exception:
            return str(hash(str(data)))

    def _check_behavioral_baseline(
        self,
        input_data: Any,
        operation: str,
    ) -> tuple[bool, float]:
        """
        Check input against behavioral baseline.

        Returns:
            Tuple of (is_within_baseline, anomaly_score_in_std_dev)
        """
        if operation not in self._behavioral_baseline:
            # No baseline yet - allow but track
            return True, 0.0

        baseline = self._behavioral_baseline[operation]
        current_metrics = self._extract_metrics(input_data)

        # Calculate anomaly score (number of standard deviations from mean)
        anomaly_score = 0.0
        for metric_name, current_value in current_metrics.items():
            if metric_name in baseline:
                mean = baseline[metric_name]["mean"]
                std_dev = baseline[metric_name]["std_dev"]

                if std_dev > 0:
                    z_score = abs(current_value - mean) / std_dev
                    anomaly_score = max(anomaly_score, z_score)

        return anomaly_score < self._anomaly_threshold_std_dev, anomaly_score

    def _extract_metrics(self, data: Any) -> dict[str, float]:
        """Extract numerical metrics from data for baseline comparison."""
        if isinstance(data, dict):
            return self._extract_dict_metrics(data)
        if isinstance(data, (list, tuple)):
            return self._extract_list_metrics(data)
        if isinstance(data, (int, float)):
            return {"value": float(data)}
        return {}

    @staticmethod
    def _extract_dict_metrics(data: dict[str, Any]) -> dict[str, float]:
        metrics: dict[str, float] = {}
        for key, value in data.items():
            if isinstance(value, (int, float)):
                metrics[str(key)] = float(value)
            elif isinstance(value, (list, tuple)):
                metrics[f"{key}_len"] = float(len(value))
                if value and all(isinstance(x, (int, float)) for x in value):
                    metrics[f"{key}_sum"] = float(sum(value))
                    metrics[f"{key}_avg"] = float(sum(value) / len(value))
        return metrics

    @staticmethod
    def _extract_list_metrics(data: list | tuple) -> dict[str, float]:
        metrics: dict[str, float] = {"length": float(len(data))}
        if data and all(isinstance(x, (int, float)) for x in data):
            metrics["sum"] = float(sum(data))
            metrics["avg"] = float(sum(data) / len(data))
        return metrics

    def _update_behavioral_history(
        self,
        input_data: Any,
        operation: str,
    ) -> None:
        """Update behavioral history with new data point."""
        metrics = self._extract_metrics(input_data)

        self._behavioral_history.append(
            {
                "operation": operation,
                "metrics": metrics,
                "timestamp": time.time(),
            }
        )

        # Prune history if needed
        if len(self._behavioral_history) > self._max_history_size:
            self._behavioral_history = self._behavioral_history[-self._max_history_size :]

        # Update baseline periodically (every 100 data points)
        if len(self._behavioral_history) % 100 == 0:
            self._recalculate_baseline()

    def _recalculate_baseline(self) -> None:
        """Recalculate behavioral baseline from history."""
        from statistics import mean, stdev

        # Group by operation
        operations: dict[str, list[dict[str, float]]] = {}
        for entry in self._behavioral_history:
            op = entry["operation"]
            if op not in operations:
                operations[op] = []
            operations[op].append(entry["metrics"])

        # Calculate mean and std_dev for each metric
        for op, metrics_list in operations.items():
            baseline = {}
            all_metric_names = set()
            for m in metrics_list:
                all_metric_names.update(m.keys())

            for metric_name in all_metric_names:
                values = [m.get(metric_name, 0) for m in metrics_list]
                if len(values) >= 2:
                    baseline[metric_name] = {
                        "mean": mean(values),
                        "std_dev": stdev(values),
                    }

            self._behavioral_baseline[op] = baseline

    def get_validation_stats(self) -> dict[str, Any]:
        """Get validation statistics."""
        return {
            **self._validation_stats,
            "anomaly_threshold": self._anomaly_threshold_std_dev,
            "validation_timeout_ms": self._validation_timeout_ms,
            "baseline_operations": len(self._behavioral_baseline),
            "history_size": len(self._behavioral_history),
        }

    def reset_validation_stats(self) -> None:
        """Reset validation statistics."""
        self._validation_stats = {
            "total_validations": 0,
            "successful_validations": 0,
            "failed_validations": 0,
            "timeout_validations": 0,
            "anomalies_detected": 0,
        }

    def clear_validated_outputs(self) -> None:
        """Clear the set of validated outputs."""
        self._validated_outputs.clear()

    async def validate_output(
        self,
        output_data: Any,
        operation: str,
    ) -> tuple[bool, Any]:
        """
        Validate output before sending to other agents.

        This provides an additional layer of Zero-Trust by ensuring
        that even internal agents don't propagate invalid data.

        Args:
            output_data: Data to validate before sending
            operation: Name of the operation that produced the output

        Returns:
            Tuple of (is_valid, sanitized_data)
        """
        # For outputs, we primarily check:
        # 1. Not None or empty
        # 2. Within expected structure
        # 3. No anomalies detected

        if output_data is None:
            logger.warning(
                "zero02_rejected_null_output",
                operation=operation,
            )
            return False, None

        # Update behavioral tracking
        self._update_behavioral_history(output_data, operation)

        # Check baseline
        is_valid, anomaly_score = self._check_behavioral_baseline(output_data, operation)

        if not is_valid:
            self._validation_stats["anomalies_detected"] += 1
            logger.warning(
                "zero02_output_anomaly_detected",
                operation=operation,
                anomaly_score=anomaly_score,
            )

        return is_valid, output_data
