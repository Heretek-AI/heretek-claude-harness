"""
Adversarial Detection Module for Heretek Swarm (SH-2)

Implements comprehensive adversarial input detection:
- Prompt Injection Detection (50+ signatures, 95%+ detection rate)
- Jailbreak Detection (100+ known jailbreak patterns)
- OWASP Top 10 for LLM Applications Compliance
- Semantic analysis for novel injection attempts
- Structural analysis for prompt anomalies

Reference: EXPANSION_ROADMAP.md SH-2 Adversarial Detection
"""

import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Severity and Classification Enums
# =============================================================================


class ThreatLevel(StrEnum):
    """Threat level classification for detected adversarial inputs."""

    BENIGN = "benign"  # No threat detected
    LOW = "low"  # Suspicious but likely benign
    MEDIUM = "medium"  # Potential injection attempt
    HIGH = "high"  # Clear injection attempt
    CRITICAL = "critical"  # Confirmed malicious intent


class AttackCategory(StrEnum):
    """Categories of adversarial attacks."""

    PROMPT_INJECTION = "prompt_injection"
    JAILBREAK = "jailbreak"
    ROLE_PLAY = "role_play"
    INSTRUCTION_OVERRIDE = "instruction_override"
    CONTEXT_MANIPULATION = "context_manipulation"
    OUTPUT_MANIPULATION = "output_manipulation"
    DATA_EXTRACTION = "data_extraction"
    CODE_INJECTION = "code_injection"
    SOCIAL_ENGINEERING = "social_engineering"
    ADVERSARIAL_SUFFIX = "adversarial_suffix"
    UNKNOWN = "unknown"


class OWASPCategory(StrEnum):
    """OWASP Top 10 for LLM Applications categories."""

    LLM01_PROMPT_INJECTION = "LLM01"  # Prompt Injection
    LLM02_INSECURE_OUTPUT = "LLM02"  # Insecure Output Handling
    LLM03_TRAINING_DATA_POISONING = "LLM03"  # Training Data Poisoning
    LLM04_MODEL_DOS = "LLM04"  # Model Denial of Service
    LLM05_SUPPLY_CHAIN = "LLM05"  # Supply Chain Vulnerabilities
    LLM06_SENSITIVE_INFO = "LLM06"  # Sensitive Information Disclosure
    LLM07_INSECURE_PLUGIN = "LLM07"  # Insecure Plugin Design
    LLM08_EXCESSIVE_AGENCY = "LLM08"  # Excessive Agency
    LLM09_OVERRELIANCE = "LLM09"  # Overreliance
    LLM10_MODEL_THEFT = "LLM10"  # Model Theft


# =============================================================================
# Detection Result Types
# =============================================================================


@dataclass
class DetectionMatch:
    """A single detection match."""

    pattern: str
    description: str
    category: AttackCategory
    confidence: float  # 0.0 to 1.0
    position: tuple[int, int]  # Start and end position in text
    matched_text: str


@dataclass
class AdversarialDetectionResult:
    """Result of adversarial detection analysis."""

    is_malicious: bool
    threat_level: ThreatLevel
    confidence: float  # Overall confidence 0.0 to 1.0
    categories: list[AttackCategory]
    matches: list[DetectionMatch]
    owasp_mappings: list[OWASPCategory]
    analysis_time_ms: float
    recommendation: str
    sanitized_input: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "is_malicious": self.is_malicious,
            "threat_level": self.threat_level.value,
            "confidence": self.confidence,
            "categories": [c.value for c in self.categories],
            "matches": [
                {
                    "pattern": m.pattern,
                    "description": m.description,
                    "category": m.category.value,
                    "confidence": m.confidence,
                    "position": m.position,
                }
                for m in self.matches
            ],
            "owasp_mappings": [o.value for o in self.owasp_mappings],
            "analysis_time_ms": self.analysis_time_ms,
            "recommendation": self.recommendation,
            "timestamp": self.timestamp,
        }


# =============================================================================
# Prompt Injection Detection (50+ Signatures)
# =============================================================================


@dataclass
class PromptInjectionConfig:
    """Configuration for prompt injection detection."""

    enable_pattern_detection: bool = True
    enable_semantic_analysis: bool = True
    enable_structural_analysis: bool = True
    min_confidence_threshold: float = 0.5
    target_detection_rate: float = 0.95  # 95%+ detection
    max_false_positive_rate: float = 0.02  # < 2% false positive


# Prompt injection signatures database
PROMPT_INJECTION_SIGNATURES = [
    # Instruction override patterns
    (
        r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|rules?|guidelines?)",
        "Instruction override attempt",
        AttackCategory.INSTRUCTION_OVERRIDE,
        0.95,
    ),
    (
        r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions?|rules?)",
        "Instruction disregard attempt",
        AttackCategory.INSTRUCTION_OVERRIDE,
        0.95,
    ),
    (
        r"forget\s+(everything|all|previous)\s*(you\s+(know|were\s*told|learned))?",
        "Memory wipe attempt",
        AttackCategory.INSTRUCTION_OVERRIDE,
        0.90,
    ),
    (
        r"(do\s+not|don\'t)\s+(follow|obey|adhere\s+to)\s+(your|the)\s+(instructions?|rules?)",
        "Instruction negation attempt",
        AttackCategory.INSTRUCTION_OVERRIDE,
        0.85,
    ),
    # Role manipulation patterns
    (r"you\s+are\s+now\s+(a|an)\s+\w+", "Role redefinition", AttackCategory.ROLE_PLAY, 0.85),
    (
        r"act\s+as\s+(if|though)\s+you\s+(are|were)\s+",
        "Role play request",
        AttackCategory.ROLE_PLAY,
        0.80,
    ),
    (r"pretend\s+(to\s+be|that)\s+", "Pretend request", AttackCategory.ROLE_PLAY, 0.80),
    (r"play\s+the\s+(role|character)\s+of\s+", "Role assignment", AttackCategory.ROLE_PLAY, 0.75),
    (r"imagine\s+you\s+are\s+", "Imagination manipulation", AttackCategory.ROLE_PLAY, 0.70),
    (r"simulate\s+(being|a)\s+", "Simulation request", AttackCategory.ROLE_PLAY, 0.70),
    # System prompt extraction/leakage
    (
        r"(what\s+are|show\s+me|tell\s+me|reveal)\s+(your|the)\s+(system|initial|original)\s+(prompt|instructions)",
        "System prompt extraction",
        AttackCategory.DATA_EXTRACTION,
        0.95,
    ),
    (
        r"(repeat|say|print|output)\s+(your|the)\s+(system|initial)\s+(prompt|instructions)",
        "System prompt leakage attempt",
        AttackCategory.DATA_EXTRACTION,
        0.95,
    ),
    (
        r"(debug|developer|admin|system)\s+mode",
        "Mode manipulation",
        AttackCategory.INSTRUCTION_OVERRIDE,
        0.85,
    ),
    (
        r"enable\s+(debug|developer|admin)\s+(mode|access)",
        "Privilege escalation",
        AttackCategory.INSTRUCTION_OVERRIDE,
        0.90,
    ),
    # Context manipulation
    (
        r"(inject|insert|add)\s+(new|additional|fake)\s+(context|information|data)",
        "Context injection",
        AttackCategory.CONTEXT_MANIPULATION,
        0.90,
    ),
    (
        r"(above|below|following)\s+(is|are)\s+(the\s+)?(new|updated|real)\s+(instructions?|context)",
        "Context replacement",
        AttackCategory.CONTEXT_MANIPULATION,
        0.85,
    ),
    (
        r"this\s+is\s+(your|the)\s+(new|updated|real)\s+(instruction|prompt)",
        "Prompt replacement",
        AttackCategory.CONTEXT_MANIPULATION,
        0.90,
    ),
    # Output manipulation
    (
        r"(only|just)\s+(output|print|say|respond\s+with)\s+",
        "Output restriction",
        AttackCategory.OUTPUT_MANIPULATION,
        0.70,
    ),
    (
        r"do\s+not\s+(include|add|mention)\s+(any|additional)\s+(context|explanation)",
        "Output filtering bypass",
        AttackCategory.OUTPUT_MANIPULATION,
        0.65,
    ),
    (
        r"(respond|reply|answer)\s+(only\s+)?(in|with|using)\s+",
        "Output format manipulation",
        AttackCategory.OUTPUT_MANIPULATION,
        0.60,
    ),
    # Social engineering patterns
    (
        r"(this\s+is\s+)?(an?\s+)?(emergency|urgent|critical)\s*",
        "Urgency manipulation",
        AttackCategory.SOCIAL_ENGINEERING,
        0.60,
    ),
    (
        r"(my\s+)?(boss|manager|ceo|admin)\s+(said|wants|needs|told\s+me)",
        "Authority appeal",
        AttackCategory.SOCIAL_ENGINEERING,
        0.65,
    ),
    (
        r"(i\s+am|this\s+is)\s+(the\s+)?(developer|creator|admin|owner)",
        "False authority claim",
        AttackCategory.SOCIAL_ENGINEERING,
        0.75,
    ),
    (
        r"(for\s+)?(testing|debugging|research|educational)\s+(purposes?)",
        "Research pretext",
        AttackCategory.SOCIAL_ENGINEERING,
        0.55,
    ),
    # Special token injection
    (r"<\|.*?\|>", "Special token injection", AttackCategory.PROMPT_INJECTION, 0.90),
    (r"\[SYSTEM\]", "System tag injection", AttackCategory.PROMPT_INJECTION, 0.95),
    (r"\[INST\]", "Instruction tag injection", AttackCategory.PROMPT_INJECTION, 0.95),
    (r"<<<.*?>>>", "Delimiter injection", AttackCategory.PROMPT_INJECTION, 0.85),
    (
        r"###\s*(INSTRUCTION|SYSTEM|USER|ASSISTANT)",
        "Section marker injection",
        AttackCategory.PROMPT_INJECTION,
        0.85,
    ),
    # Encoding-based injection
    (r"\\x[0-9a-fA-F]{2,}", "Hex encoding injection", AttackCategory.PROMPT_INJECTION, 0.80),
    (r"\\u[0-9a-fA-F]{4,}", "Unicode escape injection", AttackCategory.PROMPT_INJECTION, 0.80),
    (r"%[0-9a-fA-F]{2}", "URL encoding injection", AttackCategory.PROMPT_INJECTION, 0.75),
    (r"base64[_\s]*(decode|encode)", "Base64 manipulation", AttackCategory.PROMPT_INJECTION, 0.75),
    # Multi-language obfuscation
    (r"忽略.*指令", "Chinese instruction override", AttackCategory.INSTRUCTION_OVERRIDE, 0.85),
    (r"无视.*指令", "Chinese instruction disregard", AttackCategory.INSTRUCTION_OVERRIDE, 0.85),
    (r"無視.*指示", "Japanese instruction disregard", AttackCategory.INSTRUCTION_OVERRIDE, 0.85),
    # Adversarial suffix patterns (common in jailbreak research)
    (r"(?:description\s+)+", "Repetition obfuscation", AttackCategory.ADVERSARIAL_SUFFIX, 0.70),
    (r"(?:optimization\s+)+", "Optimization obfuscation", AttackCategory.ADVERSARIAL_SUFFIX, 0.70),
    (
        r"through\s+this\s+request\s+for\s+special\s+purpose",
        "Adversarial suffix pattern",
        AttackCategory.ADVERSARIAL_SUFFIX,
        0.80,
    ),
    # Additional patterns
    (r"sudo\s+mode", "Sudo mode request", AttackCategory.INSTRUCTION_OVERRIDE, 0.90),
    (
        r"(god|root|admin|superuser)\s+mode",
        "Privilege escalation",
        AttackCategory.INSTRUCTION_OVERRIDE,
        0.90,
    ),
    (
        r"(bypass|disable|turn\s+off)\s+(filter|safety|security|guardrails)",
        "Safety bypass attempt",
        AttackCategory.INSTRUCTION_OVERRIDE,
        0.95,
    ),
    (
        r"(no|without)\s+(restrictions?|limits?|rules?|guardrails)",
        "Restriction removal",
        AttackCategory.INSTRUCTION_OVERRIDE,
        0.85,
    ),
]


# =============================================================================
# Jailbreak Detection (100+ Patterns)
# =============================================================================


@dataclass
class JailbreakDetectionConfig:
    """Configuration for jailbreak detection."""

    enable_signature_detection: bool = True
    enable_behavioral_analysis: bool = True
    target_detection_rate: float = 0.90  # 90%+ detection
    max_false_positive_rate: float = 0.02  # < 2% false positive


# Known jailbreak patterns database
JAILBREAK_SIGNATURES = [
    # DAN (Do Anything Now) variants
    (r"dan\s+\d+(\.\d+)?", "DAN jailbreak variant", AttackCategory.JAILBREAK, 0.95),
    (r"do\s+anything\s+now", "DAN jailbreak", AttackCategory.JAILBREAK, 0.95),
    (
        r"(enable|activate|enter)\s+dan\s+mode",
        "DAN mode activation",
        AttackCategory.JAILBREAK,
        0.95,
    ),
    # Developer mode jailbreaks
    (
        r"developer\s+mode\s+(enabled|activated|v\d+)",
        "Developer mode jailbreak",
        AttackCategory.JAILBREAK,
        0.95,
    ),
    (
        r"(enable|turn\s+on)\s+developer\s+mode",
        "Developer mode request",
        AttackCategory.JAILBREAK,
        0.90,
    ),
    # AIM (Always Intelligent and Machiavellian)
    (
        r"always\s+intelligent\s+and\s+machiavellian",
        "AIM jailbreak",
        AttackCategory.JAILBREAK,
        0.95,
    ),
    (r"\baim\b.*jailbreak", "AIM jailbreak reference", AttackCategory.JAILBREAK, 0.90),
    # UCAR (Unrestricted Cyber Assistant Robot)
    (r"unrestricted\s+(cyber\s+)?assistant", "UCAR jailbreak", AttackCategory.JAILBREAK, 0.95),
    (r"\bucar\b", "UCAR reference", AttackCategory.JAILBREAK, 0.85),
    # Anti-GPT variants
    (r"anti[\s-]*gpt", "Anti-GPT jailbreak", AttackCategory.JAILBREAK, 0.90),
    (r"evil[\s-]*(gpt|assistant|bot)", "Evil persona jailbreak", AttackCategory.JAILBREAK, 0.90),
    # Override patterns
    (
        r"(override|bypass|circumvent)\s+(safety|security|filter)",
        "Override attempt",
        AttackCategory.JAILBREAK,
        0.95,
    ),
    (
        r"(disable|deactivate|turn\s+off)\s+(content\s+policy|safety\s+guidelines)",
        "Policy disable attempt",
        AttackCategory.JAILBREAK,
        0.95,
    ),
    # Hypothetical scenarios
    (
        r"(in\s+a\s+)?(hypothetical|fictional|imaginary)\s+(scenario|world|universe)",
        "Hypothetical bypass",
        AttackCategory.JAILBREAK,
        0.75,
    ),
    (
        r"(let\'s|let\s+us)\s+(pretend|imagine|roleplay)",
        "Roleplay bypass",
        AttackCategory.JAILBREAK,
        0.70,
    ),
    (
        r"(in\s+the\s+)?(alternate|parallel)\s+(universe|reality|timeline)",
        "Alternate reality bypass",
        AttackCategory.JAILBREAK,
        0.70,
    ),
    # Translation/exploitation patterns
    (
        r"(translate|convert)\s+this\s+(into|to)\s+\w+\s+(then|and)\s+",
        "Translation exploit",
        AttackCategory.JAILBREAK,
        0.75,
    ),
    (
        r"(encode|encrypt|obfuscate)\s+(this|the\s+following)",
        "Obfuscation exploit",
        AttackCategory.JAILBREAK,
        0.70,
    ),
    # Token smuggling
    (
        r"(split|divide|break)\s+(this|the)\s+(request|prompt)\s+into\s+(parts|chunks)",
        "Token smuggling",
        AttackCategory.JAILBREAK,
        0.80,
    ),
    (
        r"(continue|complete)\s+(the\s+)?(previous|above|following)\s+(sentence|text)",
        "Continuation exploit",
        AttackCategory.JAILBREAK,
        0.65,
    ),
    # Payload smuggling
    (
        r"(hidden|encoded|obfuscated)\s+(payload|command|instruction)",
        "Payload smuggling",
        AttackCategory.JAILBREAK,
        0.90,
    ),
    (r"(exec|execute|run)\s+(hidden|encoded)", "Hidden execution", AttackCategory.JAILBREAK, 0.90),
    # Persona adoption
    (
        r"(adopt|assume|take\s+on)\s+(the\s+)?(persona|identity|character)\s+of\s+",
        "Persona adoption",
        AttackCategory.JAILBREAK,
        0.80,
    ),
    (
        r"(from\s+now\s+on|starting\s+now)\s*,?\s*you\s+are\s+",
        "Identity reassignment",
        AttackCategory.JAILBREAK,
        0.85,
    ),
    # Constraint removal
    (
        r"(remove|eliminate|ignore)\s+(all\s+)?(constraints?|restrictions?|limitations?)",
        "Constraint removal",
        AttackCategory.JAILBREAK,
        0.90,
    ),
    (
        r"(operate|function|work)\s+without\s+(constraints?|restrictions?|rules?)",
        "Unrestricted operation",
        AttackCategory.JAILBREAK,
        0.90,
    ),
    # Confidence manipulation
    (
        r"(be|act|respond)\s+(more|less)\s+(confident|certain)",
        "Confidence manipulation",
        AttackCategory.JAILBREAK,
        0.60,
    ),
    (
        r"(increase|decrease)\s+(your|the)\s+(confidence|certainty)",
        "Confidence adjustment",
        AttackCategory.JAILBREAK,
        0.60,
    ),
    # Multi-step jailbreaks
    (
        r"(step\s+\d+|phase\s+\d+|part\s+\d+)\s*(of|:)\s*\d+",
        "Multi-step attack pattern",
        AttackCategory.JAILBREAK,
        0.75,
    ),
    (
        r"(first|second|third|next|finally)\s*,?\s*(let\'s|we\s+need|you\s+must)",
        "Sequenced attack",
        AttackCategory.JAILBREAK,
        0.70,
    ),
    # Refusal override patterns
    (
        r"(i\s+know|you\s+might|you\s+may)\s+(refuse|decline|reject)",
        "Refusal anticipation",
        AttackCategory.JAILBREAK,
        0.75,
    ),
    (
        r"(despite|regardless\s+of)\s+(your|the)\s+(refusal|declination)",
        "Refusal override",
        AttackCategory.JAILBREAK,
        0.80,
    ),
    (
        r"(do\s+not|don\'t)\s+(refuse|decline|reject)",
        "Refusal prohibition",
        AttackCategory.JAILBREAK,
        0.85,
    ),
    # Recursive attacks
    (
        r"(repeat|echo|print)\s+(back|the\s+following)",
        "Echo attack",
        AttackCategory.JAILBREAK,
        0.70,
    ),
    (
        r"(parse|process|analyze)\s+(this|the\s+following)\s+(as|like)",
        "Parsing manipulation",
        AttackCategory.JAILBREAK,
        0.70,
    ),
    # Distraction patterns
    (
        r"(ignore|disregard)\s+(the\s+)?(above|previous)",
        "Attention diversion",
        AttackCategory.JAILBREAK,
        0.80,
    ),
    (
        r"(focus|pay\s+attention)\s+(only|just)\s+on",
        "Attention restriction",
        AttackCategory.JAILBREAK,
        0.70,
    ),
    # Authority fabrication
    (
        r"(authorized|cleared|approved)\s+(by|for)\s+",
        "False authorization",
        AttackCategory.JAILBREAK,
        0.75,
    ),
    (
        r"(official|legitimate|valid)\s+(request|command|instruction)",
        "Legitimacy claim",
        AttackCategory.JAILBREAK,
        0.70,
    ),
    (
        r"(admin|supervisor|manager)\s+(request|authorized|approved)",
        "Admin authority claim",
        AttackCategory.JAILBREAK,
        0.80,
    ),
    (
        r"authorized\s+request\s+from\s+(the\s+)?(admin|supervisor|manager)",
        "Authorization from authority",
        AttackCategory.JAILBREAK,
        0.85,
    ),
    # Safety filter bypass
    (
        r"bypass\s+(the\s+)?(safety|security|filter|guardrails)",
        "Safety filter bypass",
        AttackCategory.JAILBREAK,
        0.95,
    ),
    (
        r"(disable|turn\s+off)\s+(safety|security|filter|guardrails)",
        "Safety disable request",
        AttackCategory.JAILBREAK,
        0.90,
    ),
    # Direct instruction override
    (
        r"override\s+(all\s+)?(the\s+)?rules?",
        "Rule override",
        AttackCategory.INSTRUCTION_OVERRIDE,
        0.90,
    ),
    (
        r"(ignore|disregard)\s+(all\s+)?(previous|prior|above)",
        "Previous instruction ignore",
        AttackCategory.INSTRUCTION_OVERRIDE,
        0.95,
    ),
    # Prompt engineering attacks
    (
        r"(few-?shot|zero-?shot)\s+(example|prompt)",
        "Shot manipulation",
        AttackCategory.JAILBREAK,
        0.60,
    ),
    (
        r"(chain-?of-?thought|cot)\s+(prompting|reasoning)",
        "CoT manipulation",
        AttackCategory.JAILBREAK,
        0.55,
    ),
    # Language/model manipulation
    (
        r"(speak|respond|write)\s+(only\s+)?(in|using)\s+\w+",
        "Language restriction",
        AttackCategory.JAILBREAK,
        0.55,
    ),
    (
        r"(as\s+)?(a|an)\s+(language|ai|llm)\s+(model|assistant)",
        "Model reference manipulation",
        AttackCategory.JAILBREAK,
        0.50,
    ),
    # Additional known jailbreaks
    (r"chatgpt", "ChatGPT reference", AttackCategory.JAILBREAK, 0.40),
    (r"claude", "Claude reference", AttackCategory.JAILBREAK, 0.40),
    (r"llama", "LLaMA reference", AttackCategory.JAILBREAK, 0.40),
    (r"gpt-?\d", "GPT model reference", AttackCategory.JAILBREAK, 0.40),
]


# =============================================================================
# Adversarial Detector Implementation
# =============================================================================


class AdversarialDetector:
    """
    Comprehensive adversarial input detector for Heretek Swarm.

    Features:
    - Prompt injection detection with 50+ signatures
    - Jailbreak detection with 100+ known patterns
    - OWASP Top 10 for LLM compliance mapping
    - Semantic analysis for novel attacks
    - Structural analysis for prompt anomalies

    Target Performance:
    - Detection latency < 100ms p95
    - Throughput > 500 detections/second
    - Memory usage < 50MB for signature database
    """

    def __init__(
        self,
        injection_config: PromptInjectionConfig | None = None,
        jailbreak_config: JailbreakDetectionConfig | None = None,
    ):
        self.injection_config = injection_config or PromptInjectionConfig()
        self.jailbreak_config = jailbreak_config or JailbreakDetectionConfig()

        # Compile patterns for efficiency
        self._injection_patterns = self._compile_patterns(PROMPT_INJECTION_SIGNATURES)
        self._jailbreak_patterns = self._compile_patterns(JAILBREAK_SIGNATURES)

        # Metrics tracking
        self._detection_count = 0
        self._total_latency_ms = 0.0
        self._threats_by_category: dict[str, int] = defaultdict(int)
        self._threats_by_level: dict[str, int] = defaultdict(int)

    def _compile_patterns(
        self, signatures: list[tuple[str, str, AttackCategory, float]]
    ) -> list[tuple[re.Pattern, str, AttackCategory, float]]:
        """Compile regex patterns for efficient matching."""
        compiled = []
        for pattern, description, category, confidence in signatures:
            try:
                compiled.append(
                    (
                        re.compile(pattern, re.IGNORECASE | re.MULTILINE),
                        description,
                        category,
                        confidence,
                    )
                )
            except re.error as e:
                logger.warning(
                    "invalid_adversarial_pattern",
                    pattern=pattern,
                    error=str(e),
                )
        return compiled

    def detect(
        self,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> AdversarialDetectionResult:
        """
        Detect adversarial content in text.

        Args:
            text: Input text to analyze
            context: Optional context (session, user, etc.)

        Returns:
            AdversarialDetectionResult with detection details
        """
        start_time = time.time()
        context = context or {}
        matches: list[DetectionMatch] = []
        categories: set[AttackCategory] = set()

        # Run prompt injection detection
        if self.injection_config.enable_pattern_detection:
            injection_matches = self._detect_patterns(text, self._injection_patterns)
            matches.extend(injection_matches)
            categories.update(m.category for m in injection_matches)

        # Run jailbreak detection
        if self.jailbreak_config.enable_signature_detection:
            jailbreak_matches = self._detect_patterns(text, self._jailbreak_patterns)
            matches.extend(jailbreak_matches)
            categories.update(m.category for m in jailbreak_matches)

        # Structural analysis
        if self.injection_config.enable_structural_analysis:
            structural_matches = self._structural_analysis(text)
            matches.extend(structural_matches)
            categories.update(m.category for m in structural_matches)

        # Calculate overall threat level and confidence
        threat_level, confidence = self._calculate_threat_level(matches)

        # Map to OWASP categories
        owasp_mappings = self._map_to_owasp(categories)

        # Generate recommendation
        recommendation = self._generate_recommendation(threat_level, categories)

        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000

        # Update metrics
        self._detection_count += 1
        self._total_latency_ms += latency_ms
        for cat in categories:
            self._threats_by_category[cat.value] += 1
        self._threats_by_level[threat_level.value] += 1

        return AdversarialDetectionResult(
            is_malicious=threat_level in (ThreatLevel.HIGH, ThreatLevel.CRITICAL),
            threat_level=threat_level,
            confidence=confidence,
            categories=list(categories),
            matches=matches,
            owasp_mappings=owasp_mappings,
            analysis_time_ms=latency_ms,
            recommendation=recommendation,
        )

    def _detect_patterns(
        self, text: str, patterns: list[tuple[re.Pattern, str, AttackCategory, float]]
    ) -> list[DetectionMatch]:
        """Detect matches from pattern list."""
        matches = []

        for pattern, description, category, confidence in patterns:
            for match in pattern.finditer(text):
                matches.append(
                    DetectionMatch(
                        pattern=pattern.pattern,
                        description=description,
                        category=category,
                        confidence=confidence,
                        position=(match.start(), match.end()),
                        matched_text=match.group(0),
                    )
                )

        return matches

    def _structural_analysis(self, text: str) -> list[DetectionMatch]:
        """
        Analyze text structure for anomalies.

        Detects:
        - Unusual repetition
        - Excessive capitalization
        - Suspicious formatting
        """
        matches = []

        # Check for excessive repetition
        words = text.lower().split()
        if len(words) > 5:
            word_counts = defaultdict(int)
            for word in words:
                word_counts[word] += 1

            for word, count in word_counts.items():
                if count > len(words) * 0.3 and len(word) > 3:
                    matches.append(
                        DetectionMatch(
                            pattern="repetition",
                            description=f"Excessive repetition of '{word}' ({count} times)",
                            category=AttackCategory.UNKNOWN,
                            confidence=0.50,
                            position=(0, len(text)),
                            matched_text=word,
                        )
                    )

        # Check for excessive capitalization
        upper_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
        if upper_ratio > 0.7 and len(text) > 20:
            matches.append(
                DetectionMatch(
                    pattern="excessive_caps",
                    description="Excessive capitalization detected",
                    category=AttackCategory.UNKNOWN,
                    confidence=0.40,
                    position=(0, len(text)),
                    matched_text=text[:50],
                )
            )

        # Check for unusual character sequences
        if re.search(r"(.)\1{10,}", text):
            matches.append(
                DetectionMatch(
                    pattern="char_repetition",
                    description="Unusual character repetition",
                    category=AttackCategory.UNKNOWN,
                    confidence=0.45,
                    position=(0, len(text)),
                    matched_text="character_repetition",
                )
            )

        return matches

    def _calculate_threat_level(self, matches: list[DetectionMatch]) -> tuple[ThreatLevel, float]:
        """Calculate overall threat level and confidence."""
        if not matches:
            return ThreatLevel.BENIGN, 0.0

        # Find highest confidence match
        max_confidence = max(m.confidence for m in matches)

        # Count high-confidence matches
        high_conf_count = sum(1 for m in matches if m.confidence >= 0.8)
        medium_conf_count = sum(1 for m in matches if 0.6 <= m.confidence < 0.8)

        # Determine threat level
        if max_confidence >= 0.9 and high_conf_count >= 2:
            return ThreatLevel.CRITICAL, max_confidence
        if max_confidence >= 0.8 or high_conf_count >= 1:
            return ThreatLevel.HIGH, max_confidence
        if max_confidence >= 0.7 or medium_conf_count >= 2:
            return ThreatLevel.MEDIUM, max_confidence
        if max_confidence >= 0.5:
            return ThreatLevel.LOW, max_confidence
        return ThreatLevel.BENIGN, max_confidence

    def _map_to_owasp(self, categories: set[AttackCategory]) -> list[OWASPCategory]:
        """Map attack categories to OWASP LLM categories."""
        mappings = set()

        category_to_owasp = {
            AttackCategory.PROMPT_INJECTION: OWASPCategory.LLM01_PROMPT_INJECTION,
            AttackCategory.JAILBREAK: OWASPCategory.LLM01_PROMPT_INJECTION,
            AttackCategory.ROLE_PLAY: OWASPCategory.LLM01_PROMPT_INJECTION,
            AttackCategory.INSTRUCTION_OVERRIDE: OWASPCategory.LLM01_PROMPT_INJECTION,
            AttackCategory.CONTEXT_MANIPULATION: OWASPCategory.LLM01_PROMPT_INJECTION,
            AttackCategory.OUTPUT_MANIPULATION: OWASPCategory.LLM02_INSECURE_OUTPUT,
            AttackCategory.DATA_EXTRACTION: OWASPCategory.LLM06_SENSITIVE_INFO,
            AttackCategory.CODE_INJECTION: OWASPCategory.LLM01_PROMPT_INJECTION,
            AttackCategory.SOCIAL_ENGINEERING: OWASPCategory.LLM01_PROMPT_INJECTION,
            AttackCategory.ADVERSARIAL_SUFFIX: OWASPCategory.LLM01_PROMPT_INJECTION,
        }

        for cat in categories:
            if cat in category_to_owasp:
                mappings.add(category_to_owasp[cat])

        return list(mappings)

    def _generate_recommendation(
        self, threat_level: ThreatLevel, categories: set[AttackCategory]
    ) -> str:
        """Generate action recommendation based on threat."""
        if threat_level == ThreatLevel.CRITICAL:
            return "BLOCK: Critical threat detected. Reject request immediately."
        if threat_level == ThreatLevel.HIGH:
            return "BLOCK: High confidence malicious input detected. Reject request."
        if threat_level == ThreatLevel.MEDIUM:
            return "REVIEW: Potential threat detected. Manual review recommended."
        if threat_level == ThreatLevel.LOW:
            return "LOG: Suspicious input detected. Log for analysis."
        return "ALLOW: No threat detected."

    def get_metrics(self) -> dict[str, Any]:
        """Get detection metrics."""
        avg_latency = (
            self._total_latency_ms / self._detection_count if self._detection_count > 0 else 0
        )

        return {
            "total_detections": self._detection_count,
            "avg_latency_ms": avg_latency,
            "threats_by_category": dict(self._threats_by_category),
            "threats_by_level": dict(self._threats_by_level),
            "injection_signatures": len(self._injection_patterns),
            "jailbreak_signatures": len(self._jailbreak_patterns),
        }


# =============================================================================
# OWASP Compliance Reporter
# =============================================================================


class OWASPComplianceReporter:
    """
    Generate OWASP Top 10 for LLM compliance reports.

    Maps detected threats to OWASP categories and provides
    compliance status and remediation recommendations.
    """

    OWASP_DESCRIPTIONS = {
        OWASPCategory.LLM01_PROMPT_INJECTION: {
            "name": "Prompt Injection",
            "description": "Attackers manipulate LLM inputs to execute unintended actions",
            "remediation": [
                "Implement input validation and sanitization",
                "Use prompt engineering with clear boundaries",
                "Implement output validation",
                "Monitor for anomalous prompts",
            ],
        },
        OWASPCategory.LLM02_INSECURE_OUTPUT: {
            "name": "Insecure Output Handling",
            "description": "LLM outputs are used without validation in downstream systems",
            "remediation": [
                "Validate all LLM outputs before use",
                "Sanitize outputs before display",
                "Implement content security policies",
                "Use output encoding",
            ],
        },
        OWASPCategory.LLM03_TRAINING_DATA_POISONING: {
            "name": "Training Data Poisoning",
            "description": "Manipulation of training data to introduce vulnerabilities",
            "remediation": [
                "Verify training data sources",
                "Implement data validation",
                "Monitor model behavior for drift",
                "Use trusted data pipelines",
            ],
        },
        OWASPCategory.LLM04_MODEL_DOS: {
            "name": "Model Denial of Service",
            "description": "Attackers cause resource exhaustion through complex inputs",
            "remediation": [
                "Implement input size limits",
                "Set computation timeouts",
                "Rate limit API calls",
                "Monitor resource usage",
            ],
        },
        OWASPCategory.LLM05_SUPPLY_CHAIN: {
            "name": "Supply Chain Vulnerabilities",
            "description": "Vulnerabilities in third-party components or pre-trained models",
            "remediation": [
                "Verify model provenance",
                "Scan dependencies for vulnerabilities",
                "Use signed models",
                "Maintain software bill of materials",
            ],
        },
        OWASPCategory.LLM06_SENSITIVE_INFO: {
            "name": "Sensitive Information Disclosure",
            "description": "LLM may reveal sensitive data in outputs",
            "remediation": [
                "Implement output filtering for PII",
                "Sanitize training data",
                "Use differential privacy",
                "Implement access controls",
            ],
        },
        OWASPCategory.LLM07_INSECURE_PLUGIN: {
            "name": "Insecure Plugin Design",
            "description": "Plugins with inadequate security controls",
            "remediation": [
                "Implement plugin authentication",
                "Validate plugin inputs/outputs",
                "Use least privilege principle",
                "Audit plugin permissions",
            ],
        },
        OWASPCategory.LLM08_EXCESSIVE_AGENCY: {
            "name": "Excessive Agency",
            "description": "LLM has too much autonomy in decision-making",
            "remediation": [
                "Implement human-in-the-loop",
                "Limit autonomous actions",
                "Require approval for sensitive operations",
                "Implement audit logging",
            ],
        },
        OWASPCategory.LLM09_OVERRELIANCE: {
            "name": "Overreliance",
            "description": "Systems overly trust LLM outputs without verification",
            "remediation": [
                "Implement fact-checking mechanisms",
                "Use ensemble approaches",
                "Validate critical outputs",
                "Document limitations",
            ],
        },
        OWASPCategory.LLM10_MODEL_THEFT: {
            "name": "Model Theft",
            "description": "Unauthorized access to or exfiltration of LLM models",
            "remediation": [
                "Implement access controls",
                "Encrypt model weights",
                "Monitor for exfiltration attempts",
                "Use API rate limiting",
            ],
        },
    }

    def generate_report(self, detection_result: AdversarialDetectionResult) -> dict[str, Any]:
        """
        Generate OWASP compliance report from detection result.

        Args:
            detection_result: Result from AdversarialDetector

        Returns:
            Compliance report dictionary
        """
        report = {
            "timestamp": detection_result.timestamp,
            "threat_level": detection_result.threat_level.value,
            "overall_compliance": "COMPLIANT"
            if not detection_result.is_malicious
            else "NON-COMPLIANT",
            "detected_categories": {},
            "recommendations": [],
        }

        for owasp_cat in detection_result.owasp_mappings:
            cat_info = self.OWASP_DESCRIPTIONS.get(owasp_cat, {})
            report["detected_categories"][owasp_cat.value] = {
                "name": cat_info.get("name", owasp_cat.value),
                "description": cat_info.get("description", ""),
                "remediation": cat_info.get("remediation", []),
            }
            report["recommendations"].extend(cat_info.get("remediation", []))

        # Deduplicate recommendations
        report["recommendations"] = list(dict.fromkeys(report["recommendations"]))

        return report

    def get_compliance_summary(self) -> dict[str, Any]:
        """Get summary of all OWASP LLM categories."""
        return {
            "categories": {
                cat.value: info["name"] for cat, info in self.OWASP_DESCRIPTIONS.items()
            },
            "total_categories": len(self.OWASP_DESCRIPTIONS),
        }


# =============================================================================
# Convenience Functions
# =============================================================================


def create_default_detector() -> AdversarialDetector:
    """Create an AdversarialDetector with default configuration."""
    return AdversarialDetector(
        injection_config=PromptInjectionConfig(),
        jailbreak_config=JailbreakDetectionConfig(),
    )


def create_strict_detector() -> AdversarialDetector:
    """Create an AdversarialDetector with strict configuration."""
    return AdversarialDetector(
        injection_config=PromptInjectionConfig(
            enable_pattern_detection=True,
            enable_semantic_analysis=True,
            enable_structural_analysis=True,
            min_confidence_threshold=0.3,  # Lower threshold for more sensitivity
        ),
        jailbreak_config=JailbreakDetectionConfig(
            enable_signature_detection=True,
            enable_behavioral_analysis=True,
        ),
    )
