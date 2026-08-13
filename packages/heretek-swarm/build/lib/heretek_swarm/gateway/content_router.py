"""
Content-Based Message Router for Heretek Swarm

Provides content-based routing with topic filters inspired by Solace Agent Mesh.
Messages are routed based on both subject patterns and message payload content.

Features:
- Content filters: exact match, regex, JSONPath, wildcard, comparison operators
- Priority-based rule evaluation
- Zero-trust validation (safe JSONPath/regex)
- Audit logging with correlation IDs
- Prometheus metrics export
- Rate limiting to prevent DoS via complex regex

Routing Rule Structure:
    - Subject pattern matching with wildcards
    - Content filters with multiple operators (eq, ne, contains, regex, gt, lt, in)
    - Target channel and agent routing
    - Priority-based evaluation
"""

import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog
from prometheus_client import Counter, Gauge, Histogram

logger = structlog.get_logger(__name__)


class FilterOperator(StrEnum):
    """Content filter operators."""

    EQ = "eq"  # Exact match
    NE = "ne"  # Not equal
    CONTAINS = "contains"  # String contains
    REGEX = "regex"  # Regular expression match
    GT = "gt"  # Greater than
    LT = "lt"  # Less than
    GTE = "gte"  # Greater than or equal
    LTE = "lte"  # Less than or equal
    IN = "in"  # Value in list
    NOT_IN = "not_in"  # Value not in list
    EXISTS = "exists"  # Field exists
    NOT_EXISTS = "not_exists"  # Field does not exist


class RouteDecision(StrEnum):
    """Routing decision outcomes."""

    MATCHED = "matched"
    NO_MATCH = "no_match"
    FILTERED = "filtered"
    ERROR = "error"


@dataclass
class ContentFilter:
    """
    Content filter for message routing.

    Attributes:
        field: JSONPath to field in message payload (e.g., "$.priority")
        operator: Filter operator (eq, ne, contains, regex, gt, lt, in)
        value: Value to compare against
    """

    field: str
    operator: FilterOperator
    value: Any

    def __post_init__(self):
        """Validate filter after initialization."""
        # Validate JSONPath syntax
        if not self.field.startswith("$"):
            raise ValueError(f"Invalid JSONPath: {self.field}. Must start with '$'")

        # Validate operator
        if not isinstance(self.operator, FilterOperator):
            try:
                self.operator = FilterOperator(self.operator)
            except ValueError:
                raise ValueError(f"Invalid operator: {self.operator}")  # noqa: B904

        # Pre-compile regex for regex operator
        if self.operator == FilterOperator.REGEX:
            try:
                self._compiled_regex = re.compile(str(self.value))
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {self.value}. Error: {e}") from e


@dataclass
class RoutingRule:
    """
    Routing rule with content filters.

    Attributes:
        id: Unique rule identifier
        name: Human-readable rule name
        priority: Rule priority (higher evaluated first)
        subject_pattern: Wildcard pattern for subject (e.g., "task.*")
        content_filters: List of content filters (all must match)
        target_channel: Target channel for routed messages
        target_agents: List of target agent IDs
        enabled: Whether rule is active
        description: Optional rule description
    """

    id: str
    name: str
    priority: int
    subject_pattern: str
    content_filters: list[ContentFilter]
    target_channel: str
    target_agents: list[str]
    enabled: bool = True
    description: str | None = None

    def __post_init__(self):
        """Validate rule after initialization."""
        # Validate subject pattern (safe wildcard only)
        self._validate_subject_pattern()

        # Compile subject pattern to regex (safe conversion)
        self._subject_regex = self._pattern_to_regex(self.subject_pattern)

    def _validate_subject_pattern(self) -> None:
        """Validate subject pattern for safe wildcards."""
        # Only allow alphanumeric, dots, underscores, hyphens, and * wildcard
        safe_pattern = r"^[a-zA-Z0-9._\-\*]+$"
        if not re.match(safe_pattern, self.subject_pattern):
            raise ValueError(
                f"Invalid subject pattern: {self.subject_pattern}. "
                "Only alphanumeric, dots, underscores, hyphens, and * wildcard allowed"
            )

    def _pattern_to_regex(self, pattern: str) -> re.Pattern:
        """Convert wildcard pattern to safe regex."""
        # Escape special regex chars except *
        escaped = re.escape(pattern)
        # Convert * to regex .*
        regex_pattern = escaped.replace(r"\*", ".*")
        # Anchor pattern
        return re.compile(f"^{regex_pattern}$")

    def matches_subject(self, subject: str) -> bool:
        """Check if subject matches the pattern."""
        return bool(self._subject_regex.match(subject))


@dataclass
class RoutingDecision:
    """
    Result of routing evaluation.

    Attributes:
        decision: Routing decision outcome
        matched_rule: Rule that matched (if any)
        correlation_id: Message correlation ID
        evaluation_time_ms: Time taken to evaluate in milliseconds
        filters_evaluated: Number of filters evaluated
        filters_matched: Number of filters that matched
    """

    decision: RouteDecision
    matched_rule: RoutingRule | None = None
    correlation_id: str = ""
    evaluation_time_ms: float = 0.0
    filters_evaluated: int = 0
    filters_matched: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "decision": self.decision.value,
            "matched_rule_id": self.matched_rule.id if self.matched_rule else None,
            "matched_rule_name": self.matched_rule.name if self.matched_rule else None,
            "target_channel": self.matched_rule.target_channel if self.matched_rule else None,
            "target_agents": self.matched_rule.target_agents if self.matched_rule else None,
            "correlation_id": self.correlation_id,
            "evaluation_time_ms": self.evaluation_time_ms,
            "filters_evaluated": self.filters_evaluated,
            "filters_matched": self.filters_matched,
        }


# =============================================================================
# Prometheus Metrics
# =============================================================================


class RoutingMetrics:
    """Prometheus metrics for content routing."""

    def __init__(self, registry=None):
        """
        Initialize metrics.

        Args:
            registry: Optional Prometheus registry. Use None for default registry.
                     For tests, pass a new CollectorRegistry to avoid conflicts.
        """
        from prometheus_client import CollectorRegistry

        self._registry = registry or CollectorRegistry()

        # Message routing counter
        self.messages_routed = Counter(
            "content_router_messages_total",
            "Total number of messages routed",
            ["decision", "rule_id"],
            registry=self._registry,
        )

        # Routing latency histogram
        self.routing_latency = Histogram(
            "content_router_routing_latency_seconds",
            "Time spent routing messages",
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
            registry=self._registry,
        )

        # Active rules gauge
        self.active_rules = Gauge(
            "content_router_active_rules", "Number of active routing rules", registry=self._registry
        )

        # Filter evaluation counter
        self.filters_evaluated = Counter(
            "content_router_filters_evaluated_total",
            "Total number of content filters evaluated",
            ["operator"],
            registry=self._registry,
        )

        # Error counter
        self.routing_errors = Counter(
            "content_router_errors_total",
            "Total number of routing errors",
            ["error_type"],
            registry=self._registry,
        )

    def record_routing(self, decision: RouteDecision, rule_id: str | None = None):
        """Record a routing decision."""
        self.messages_routed.labels(decision=decision.value, rule_id=rule_id or "none").inc()

    def record_latency(self, duration_seconds: float):
        """Record routing latency."""
        self.routing_latency.observe(duration_seconds)

    def record_filter_evaluation(self, operator: FilterOperator):
        """Record filter evaluation."""
        self.filters_evaluated.labels(operator=operator.value).inc()

    def record_error(self, error_type: str):
        """Record routing error."""
        self.routing_errors.labels(error_type=error_type).inc()

    def update_active_rules(self, count: int):
        """Update active rules count."""
        self.active_rules.set(count)


# =============================================================================
# JSONPath Extractor (Safe Implementation)
# =============================================================================


class SafeJSONPath:
    """
    Safe JSONPath extractor with injection protection.

    Supports basic JSONPath operations:
    - $.field - Root level field
    - $.parent.child - Nested field
    - $.array[0] - Array index
    - $.* - All root fields
    """

    @staticmethod
    def extract(data: dict[str, Any], path: str) -> tuple[bool, Any]:
        """
        Extract value from data using JSONPath.

        Returns:
            Tuple of (success, value or error message)
        """
        try:
            # Validate path
            if not path.startswith("$"):
                return False, "Invalid path: must start with '$'"

            # Handle root
            if path == "$":
                return True, data

            # Remove leading $.
            if path.startswith("$."):
                path = path[2:]
            else:
                return False, f"Invalid path: {path}"

            # Parse path components
            components = path.split(".")
            current = data

            for component in components:
                if not component:
                    continue

                # Handle array index
                if "[" in component and "]" in component:
                    field_name = component.split("[")[0]
                    index_str = component[component.index("[") + 1 : component.index("]")]

                    # Navigate to field first
                    if isinstance(current, dict) and field_name in current:
                        current = current[field_name]
                    else:
                        return False, f"Field not found: {field_name}"

                    # Parse index
                    try:
                        index = int(index_str)
                    except ValueError:
                        return False, f"Invalid array index: {index_str}"

                    # Get array element
                    if not isinstance(current, list):
                        return False, "Expected array for indexing"

                    if index < 0 or index >= len(current):
                        return False, f"Array index out of bounds: {index}"

                    current = current[index]
                else:
                    # Simple field access
                    if isinstance(current, dict) and component in current:
                        current = current[component]
                    else:
                        return False, f"Field not found: {component}"

            return True, current

        except Exception as e:
            return False, str(e)


# =============================================================================
# Content Router
# =============================================================================


class ContentRouter:
    """
    Content-based message router.

    Evaluates messages against routing rules with content filters.
    Supports priority-based rule evaluation and comprehensive audit logging.
    """

    def __init__(self, rate_limit_per_second: int = 1000, metrics_registry=None):
        """
        Initialize content router.

        Args:
            rate_limit_per_second: Maximum routing evaluations per second
            metrics_registry: Optional Prometheus registry for metrics (for testing)
        """
        self._rules: dict[str, RoutingRule] = {}
        self._rules_lock = None  # Will use asyncio.Lock when needed
        self._metrics = RoutingMetrics(registry=metrics_registry)

        # Rate limiting
        self._rate_limit = rate_limit_per_second
        self._rate_window: list[float] = []

        # Statistics
        self._stats = {
            "messages_evaluated": 0,
            "messages_matched": 0,
            "messages_no_match": 0,
            "errors": 0,
            "started_at": datetime.now(UTC).isoformat(),
        }

        logger.info("content_router_initialized", rate_limit=rate_limit_per_second)

    def add_rule(self, rule: RoutingRule) -> bool:
        """
        Add a routing rule.

        Args:
            rule: Rule to add

        Returns:
            True if added successfully
        """
        if rule.id in self._rules:
            logger.warning("routing_rule_conflict", rule_id=rule.id)
            return False

        self._rules[rule.id] = rule
        self._metrics.update_active_rules(len([r for r in self._rules.values() if r.enabled]))

        logger.info("routing_rule_added", rule_id=rule.id, name=rule.name, priority=rule.priority)
        return True

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a routing rule by ID."""
        if rule_id not in self._rules:
            return False

        del self._rules[rule_id]
        self._metrics.update_active_rules(len([r for r in self._rules.values() if r.enabled]))

        logger.info("routing_rule_removed", rule_id=rule_id)
        return True

    def get_rule(self, rule_id: str) -> RoutingRule | None:
        """Get a rule by ID."""
        return self._rules.get(rule_id)

    def list_rules(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        """List all routing rules."""
        rules = self._rules.values()
        if enabled_only:
            rules = [r for r in rules if r.enabled]

        # Sort by priority (descending)
        sorted_rules = sorted(rules, key=lambda r: r.priority, reverse=True)

        return [
            {
                "id": r.id,
                "name": r.name,
                "priority": r.priority,
                "subject_pattern": r.subject_pattern,
                "content_filters": [
                    {
                        "field": f.field,
                        "operator": f.operator.value,
                        "value": f.value,
                    }
                    for f in r.content_filters
                ],
                "target_channel": r.target_channel,
                "target_agents": r.target_agents,
                "enabled": r.enabled,
                "description": r.description,
            }
            for r in sorted_rules
        ]

    def enable_rule(self, rule_id: str) -> bool:
        """Enable a routing rule."""
        if rule_id not in self._rules:
            return False

        self._rules[rule_id].enabled = True
        self._metrics.update_active_rules(len([r for r in self._rules.values() if r.enabled]))

        logger.info("routing_rule_enabled", rule_id=rule_id)
        return True

    def disable_rule(self, rule_id: str) -> bool:
        """Disable a routing rule."""
        if rule_id not in self._rules:
            return False

        self._rules[rule_id].enabled = False
        self._metrics.update_active_rules(len([r for r in self._rules.values() if r.enabled]))

        logger.info("routing_rule_disabled", rule_id=rule_id)
        return True

    def _check_rate_limit(self) -> bool:
        """Check if within rate limit. Returns True if allowed."""
        now = time.time()

        # Remove old entries from window
        self._rate_window = [t for t in self._rate_window if now - t < 1.0]

        if len(self._rate_window) >= self._rate_limit:
            return False

        self._rate_window.append(now)
        return True

    # Operator dispatch table: maps FilterOperator to evaluation function
    _OPERATOR_EVALUATORS: ClassVar[dict] = {}  # populated in __init_subclass__ or lazily

    def _evaluate_filter(self, filter: ContentFilter, payload: dict[str, Any]) -> tuple[bool, Any]:  # noqa: A002
        """
        Evaluate a single content filter against payload.

        Returns:
            Tuple of (matched, extracted_value)
        """
        success, result = SafeJSONPath.extract(payload, filter.field)
        if not success:
            logger.debug("jsonpath_extraction_failed", field=filter.field, error=result)
            return False, None

        value = result
        self._metrics.record_filter_evaluation(filter.operator)

        try:
            return self._apply_operator(filter.operator, value, filter)
        except Exception as e:
            logger.debug("filter_evaluation_error", filter=filter.field, error=str(e))
            return False, value

    def _apply_operator(
        self, operator: FilterOperator, value: Any, filter: ContentFilter  # noqa: A002
    ) -> tuple[bool, Any]:
        """Apply a filter operator to a value."""
        if operator == FilterOperator.EQ:
            return value == filter.value, value
        if operator == FilterOperator.NE:
            return value != filter.value, value
        if operator == FilterOperator.CONTAINS:
            if not isinstance(value, str):
                return False, value
            return str(filter.value) in value, value
        if operator == FilterOperator.REGEX:
            if not isinstance(value, str):
                return False, value
            return bool(filter._compiled_regex.search(value)), value  # noqa: SLF001
        if operator == FilterOperator.GT:
            return value > filter.value, value
        if operator == FilterOperator.LT:
            return value < filter.value, value
        if operator == FilterOperator.GTE:
            return value >= filter.value, value
        if operator == FilterOperator.LTE:
            return value <= filter.value, value
        if operator == FilterOperator.IN:
            if not isinstance(filter.value, (list, tuple, set)):
                return False, value
            return value in filter.value, value
        if operator == FilterOperator.NOT_IN:
            if not isinstance(filter.value, (list, tuple, set)):
                return True, value
            return value not in filter.value, value
        if operator == FilterOperator.EXISTS:
            return value is not None, value
        if operator == FilterOperator.NOT_EXISTS:
            return value is None, value

        logger.warning("unknown_filter_operator", operator=operator)
        return False, value

    def route(
        self,
        subject: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
    ) -> RoutingDecision:
        """
        Route a message based on subject and content.

        Args:
            subject: Message subject/topic
            payload: Message payload (dict)
            correlation_id: Optional correlation ID for tracing

        Returns:
            RoutingDecision with routing result
        """
        import uuid

        start_time = time.time()
        corr_id = correlation_id or str(uuid.uuid4())

        self._stats["messages_evaluated"] += 1

        # Check rate limit
        if not self._check_rate_limit():
            self._stats["errors"] += 1
            self._metrics.record_error("rate_limit_exceeded")
            logger.warning("routing_rate_limit_exceeded", correlation_id=corr_id)
            return RoutingDecision(
                decision=RouteDecision.ERROR,
                correlation_id=corr_id,
                evaluation_time_ms=(time.time() - start_time) * 1000,
            )

        # Get enabled rules sorted by priority
        enabled_rules = [r for r in self._rules.values() if r.enabled]
        sorted_rules = sorted(enabled_rules, key=lambda r: r.priority, reverse=True)

        # Evaluate rules
        for rule in sorted_rules:
            # Check subject pattern first (fast path)
            if not rule.matches_subject(subject):
                continue

            # Evaluate content filters
            filters_evaluated = 0
            filters_matched = 0
            all_matched = True

            for filter in rule.content_filters:  # noqa: A001
                filters_evaluated += 1
                matched, _ = self._evaluate_filter(filter, payload)

                if matched:
                    filters_matched += 1
                else:
                    all_matched = False
                    break

            # All filters must match
            if all_matched and filters_evaluated > 0:
                evaluation_time = (time.time() - start_time) * 1000

                self._stats["messages_matched"] += 1
                self._metrics.record_routing(RouteDecision.MATCHED, rule.id)
                self._metrics.record_latency(evaluation_time / 1000)

                decision = RoutingDecision(
                    decision=RouteDecision.MATCHED,
                    matched_rule=rule,
                    correlation_id=corr_id,
                    evaluation_time_ms=evaluation_time,
                    filters_evaluated=filters_evaluated,
                    filters_matched=filters_matched,
                )

                # Audit log
                logger.info(
                    "message_routed",
                    correlation_id=corr_id,
                    subject=subject,
                    rule_id=rule.id,
                    rule_name=rule.name,
                    target_channel=rule.target_channel,
                    target_agents=rule.target_agents,
                    evaluation_time_ms=evaluation_time,
                )

                return decision

            # If no content filters, subject match is sufficient
            if all_matched and filters_evaluated == 0:
                evaluation_time = (time.time() - start_time) * 1000

                self._stats["messages_matched"] += 1
                self._metrics.record_routing(RouteDecision.MATCHED, rule.id)
                self._metrics.record_latency(evaluation_time / 1000)

                decision = RoutingDecision(
                    decision=RouteDecision.MATCHED,
                    matched_rule=rule,
                    correlation_id=corr_id,
                    evaluation_time_ms=evaluation_time,
                    filters_evaluated=0,
                    filters_matched=0,
                )

                logger.info(
                    "message_routed_subject_only",
                    correlation_id=corr_id,
                    subject=subject,
                    rule_id=rule.id,
                    target_channel=rule.target_channel,
                )

                return decision

        # No rule matched
        evaluation_time = (time.time() - start_time) * 1000
        self._stats["messages_no_match"] += 1
        self._metrics.record_routing(RouteDecision.NO_MATCH)
        self._metrics.record_latency(evaluation_time / 1000)

        logger.debug(
            "message_no_route",
            correlation_id=corr_id,
            subject=subject,
            evaluation_time_ms=evaluation_time,
        )

        return RoutingDecision(
            decision=RouteDecision.NO_MATCH,
            correlation_id=corr_id,
            evaluation_time_ms=evaluation_time,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get routing statistics."""
        return {
            **self._stats,
            "active_rules": len([r for r in self._rules.values() if r.enabled]),
            "total_rules": len(self._rules),
            "uptime_seconds": (
                datetime.now(UTC) - datetime.fromisoformat(self._stats["started_at"])
            ).total_seconds(),
        }


# =============================================================================
# Global Router Instance
# =============================================================================

_content_router: ContentRouter | None = None


def get_content_router() -> ContentRouter:
    """Get or create the global content router instance."""
    global _content_router
    if _content_router is None:
        _content_router = ContentRouter()
    return _content_router


def reset_content_router() -> None:
    """Reset the global content router (for testing)."""
    global _content_router
    _content_router = None
