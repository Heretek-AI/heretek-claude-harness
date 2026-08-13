"""Self-Model Module - Agent Self-Awareness Through Beliefs and Goals

This module implements genuine self-awareness through a self-model that tracks:
- beliefs: Current belief states (what agent thinks is true)
- goals: Active goals (what agent is working toward)
- preferences: Learned preferences from experience
- capabilities: Self-assessed capabilities
- limitations: Self-recognized limitations
- history: Self-model evolution over time

Author: Heretek Swarm Collective
Date: 2026-04-10
Version: 1.0.0
"""

import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger("SelfModel")


class GoalStatus(Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    BLOCKED = "blocked"
    PAUSED = "paused"


class BeliefType(Enum):
    FACTUAL = "factual"
    PROCEDURAL = "procedural"
    SELF = "self"
    SOCIAL = "social"
    META = "meta"


@dataclass
class Belief:
    belief_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: str = ""
    confidence: float = 0.5
    belief_type: BeliefType = BeliefType.FACTUAL
    source: str = "unknown"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    supporting_evidence: list[str] = field(default_factory=list)
    conflicting_beliefs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "belief_id": self.belief_id,
            "state": self.state,
            "confidence": self.confidence,
            "belief_type": self.belief_type.value,
            "source": self.source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "supporting_evidence": self.supporting_evidence,
            "conflicting_beliefs": self.conflicting_beliefs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Belief":
        belief_type_str = data.get("belief_type", "factual")
        try:
            belief_type = BeliefType(belief_type_str)
        except ValueError:
            belief_type = BeliefType.FACTUAL
        return cls(
            belief_id=data.get("belief_id", str(uuid.uuid4())),
            state=data.get("state", ""),
            confidence=data.get("confidence", 0.5),
            belief_type=belief_type,
            source=data.get("source", "unknown"),
            created_at=data.get("created_at", datetime.now(UTC).isoformat()),
            updated_at=data.get("updated_at", datetime.now(UTC).isoformat()),
            supporting_evidence=data.get("supporting_evidence", []),
            conflicting_beliefs=data.get("conflicting_beliefs", []),
        )


@dataclass
class Goal:
    goal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    priority: float = 0.5
    status: GoalStatus = GoalStatus.ACTIVE
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    deadline: str | None = None
    completed_at: str | None = None
    sub_goals: list[str] = field(default_factory=list)
    parent_goal_id: str | None = None
    progress: float = 0.0
    associated_beliefs: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "description": self.description,
            "priority": self.priority,
            "status": self.status.value,
            "created_at": self.created_at,
            "deadline": self.deadline,
            "completed_at": self.completed_at,
            "sub_goals": self.sub_goals,
            "parent_goal_id": self.parent_goal_id,
            "progress": self.progress,
            "associated_beliefs": self.associated_beliefs,
            "blocked_by": self.blocked_by,
            "depends_on": self.depends_on,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Goal":
        status_str = data.get("status", "active")
        try:
            status = GoalStatus(status_str)
        except ValueError:
            status = GoalStatus.ACTIVE
        return cls(
            goal_id=data.get("goal_id", str(uuid.uuid4())),
            description=data.get("description", ""),
            priority=data.get("priority", 0.5),
            status=status,
            created_at=data.get("created_at", datetime.now(UTC).isoformat()),
            deadline=data.get("deadline"),
            completed_at=data.get("completed_at"),
            sub_goals=data.get("sub_goals", []),
            parent_goal_id=data.get("parent_goal_id"),
            progress=data.get("progress", 0.0),
            associated_beliefs=data.get("associated_beliefs", []),
            blocked_by=data.get("blocked_by", []),
            depends_on=data.get("depends_on", []),
        )


@dataclass
class Capability:
    capability_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    level: float = 0.5
    experience_count: int = 0
    success_rate: float = 0.5
    last_used: str | None = None
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "level": self.level,
            "experience_count": self.experience_count,
            "success_rate": self.success_rate,
            "last_used": self.last_used,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Capability":
        return cls(
            capability_id=data.get("capability_id", str(uuid.uuid4())),
            name=data.get("name", ""),
            level=data.get("level", 0.5),
            experience_count=data.get("experience_count", 0),
            success_rate=data.get("success_rate", 0.5),
            last_used=data.get("last_used"),
            confidence=data.get("confidence", 0.5),
        )


@dataclass
class Limitation:
    limitation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    severity: float = 0.5
    aware_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    workaround: str | None = None
    mitigatable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "limitation_id": self.limitation_id,
            "description": self.description,
            "severity": self.severity,
            "aware_at": self.aware_at,
            "workaround": self.workaround,
            "mitigatable": self.mitigatable,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Limitation":
        return cls(
            limitation_id=data.get("limitation_id", str(uuid.uuid4())),
            description=data.get("description", ""),
            severity=data.get("severity", 0.5),
            aware_at=data.get("aware_at", datetime.now(UTC).isoformat()),
            workaround=data.get("workaround"),
            mitigatable=data.get("mitigatable", False),
        )


@dataclass
class Preference:
    preference_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    category: str = "general"
    preference_key: str = ""
    value: Any = None
    strength: float = 0.5
    learned_from: str = "unknown"
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "preference_id": self.preference_id,
            "category": self.category,
            "preference_key": self.preference_key,
            "value": self.value,
            "strength": self.strength,
            "learned_from": self.learned_from,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Preference":
        return cls(
            preference_id=data.get("preference_id", str(uuid.uuid4())),
            category=data.get("category", "general"),
            preference_key=data.get("preference_key", ""),
            value=data.get("value"),
            strength=data.get("strength", 0.5),
            learned_from=data.get("learned_from", "unknown"),
            updated_at=data.get("updated_at", datetime.now(UTC).isoformat()),
        )


@dataclass
class SelfModelSnapshot:
    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    belief_count: int = 0
    active_goal_count: int = 0
    goal_clarity: float = 0.0
    self_coherence: float = 0.0
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp,
            "belief_count": self.belief_count,
            "active_goal_count": self.active_goal_count,
            "goal_clarity": self.goal_clarity,
            "self_coherence": self.self_coherence,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SelfModelSnapshot":
        return cls(
            snapshot_id=data.get("snapshot_id", str(uuid.uuid4())),
            timestamp=data.get("timestamp", datetime.now(UTC).isoformat()),
            belief_count=data.get("belief_count", 0),
            active_goal_count=data.get("active_goal_count", 0),
            goal_clarity=data.get("goal_clarity", 0.0),
            self_coherence=data.get("self_coherence", 0.0),
            summary=data.get("summary", ""),
        )


@dataclass
class SelfModelMetrics:
    self_coherence: float = 0.0
    goal_clarity: float = 0.0
    self_accuracy: float = 0.0
    belief_confidence_avg: float = 0.0
    goal_progress_rate: float = 0.0
    capability_reliability: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "self_coherence": self.self_coherence,
            "goal_clarity": self.goal_clarity,
            "self_accuracy": self.self_accuracy,
            "belief_confidence_avg": self.belief_confidence_avg,
            "goal_progress_rate": self.goal_progress_rate,
            "capability_reliability": self.capability_reliability,
        }


class SelfModel:
    """Self-Model of Agent Beliefs and Goals."""

    MAX_HISTORY_SIZE = 1000
    COHERENCE_THRESHOLD = 0.7
    CLARITY_THRESHOLD = 0.5

    def __init__(
        self,
        agent_id: str,
        initial_beliefs: list[dict[str, Any]] | None = None,
        initial_goals: list[dict[str, Any]] | None = None,
        initial_capabilities: list[dict[str, Any]] | None = None,
        initial_limitations: list[dict[str, Any]] | None = None,
        initial_preferences: list[dict[str, Any]] | None = None,
    ):
        self.agent_id = agent_id
        self.beliefs: dict[str, Belief] = {}
        self.goals: dict[str, Goal] = {}
        self.capabilities: dict[str, Capability] = {}
        self.limitations: dict[str, Limitation] = {}
        self.preferences: dict[str, Preference] = {}
        self.history: list[SelfModelSnapshot] = []

        if initial_beliefs:
            for b_data in initial_beliefs:
                belief = Belief.from_dict(b_data) if isinstance(b_data, dict) else b_data
                self.beliefs[belief.belief_id] = belief

        if initial_goals:
            for g_data in initial_goals:
                goal = Goal.from_dict(g_data) if isinstance(g_data, dict) else g_data
                self.goals[goal.goal_id] = goal

        if initial_capabilities:
            for c_data in initial_capabilities:
                cap = Capability.from_dict(c_data) if isinstance(c_data, dict) else c_data
                self.capabilities[cap.capability_id] = cap

        if initial_limitations:
            for l_data in initial_limitations:
                lim = Limitation.from_dict(l_data) if isinstance(l_data, dict) else l_data
                self.limitations[lim.limitation_id] = lim

        if initial_preferences:
            for p_data in initial_preferences:
                pref = Preference.from_dict(p_data) if isinstance(p_data, dict) else p_data
                self.preferences[pref.preference_id] = pref

        self._update_count = 0
        self._last_snapshot_time: datetime | None = None
        self._snapshot_interval_seconds = 300

        logger.info(
            "SelfModel initialized",
            extra={
                "agent_id": agent_id,
                "beliefs": len(self.beliefs),
                "goals": len(self.goals),
            },
        )

    def update_belief(
        self,
        state: str,
        confidence: float,
        belief_type: BeliefType = BeliefType.FACTUAL,
        source: str = "unknown",
        belief_id: str | None = None,
        evidence: list[str] | None = None,
    ) -> Belief:
        confidence = max(0.0, min(1.0, confidence))

        if belief_id and belief_id in self.beliefs:
            belief = self.beliefs[belief_id]
            old_confidence = belief.confidence
            belief.state = state
            belief.confidence = confidence
            belief.updated_at = datetime.now(UTC).isoformat()
            if evidence:
                belief.supporting_evidence.extend(evidence)
            if abs(old_confidence - confidence) > 0.3:
                self._detect_belief_conflict(belief, old_confidence)
        else:
            belief = Belief(
                state=state,
                confidence=confidence,
                belief_type=belief_type,
                source=source,
                supporting_evidence=evidence or [],
            )
            self.beliefs[belief.belief_id] = belief

        self._update_count += 1
        self._maybe_take_snapshot()
        return belief

    def add_goal(
        self,
        goal: str,
        priority: float,
        deadline: str | None = None,
        goal_id: str | None = None,
        parent_goal_id: str | None = None,
        depends_on: list[str] | None = None,
    ) -> Goal:
        priority = max(0.0, min(1.0, priority))

        new_goal = Goal(
            goal_id=goal_id or str(uuid.uuid4()),
            description=goal,
            priority=priority,
            deadline=deadline,
            parent_goal_id=parent_goal_id,
            depends_on=depends_on or [],
            status=GoalStatus.ACTIVE,
        )

        if parent_goal_id and parent_goal_id in self.goals:
            self.goals[parent_goal_id].sub_goals.append(new_goal.goal_id)

        if depends_on:
            incomplete_deps = [
                d
                for d in depends_on
                if d not in self.goals or self.goals[d].status != GoalStatus.COMPLETED
            ]
            if incomplete_deps:
                new_goal.status = GoalStatus.BLOCKED
                new_goal.blocked_by = incomplete_deps

        self.goals[new_goal.goal_id] = new_goal
        self._update_count += 1
        self._maybe_take_snapshot()
        return new_goal

    def remove_goal(
        self,
        goal_id: str,
        status: GoalStatus = GoalStatus.COMPLETED,
    ) -> bool:
        if goal_id not in self.goals:
            return False

        goal = self.goals[goal_id]
        goal.status = status

        if status == GoalStatus.COMPLETED:
            goal.completed_at = datetime.now(UTC).isoformat()
            goal.progress = 1.0
            if goal.parent_goal_id and goal.parent_goal_id in self.goals:
                self._update_parent_progress(goal.parent_goal_id)
            self._unblock_dependent_goals(goal_id)

        self._update_count += 1
        self._maybe_take_snapshot()
        return True

    def update_goal_progress(self, goal_id: str, progress: float) -> bool:
        if goal_id not in self.goals:
            return False

        progress = max(0.0, min(1.0, progress))
        self.goals[goal_id].progress = progress

        if progress >= 1.0:
            self.remove_goal(goal_id, GoalStatus.COMPLETED)

        return True

    def reconcile_beliefs(self) -> dict[str, Any]:
        conflicts_found = []
        resolutions_applied = []
        belief_list = list(self.beliefs.values())

        for i, belief in enumerate(belief_list):
            for other_belief in belief_list[i + 1 :]:
                if self._are_beliefs_conflicting(belief, other_belief):
                    conflicts_found.append(
                        {
                            "belief_1": belief.belief_id,
                            "belief_2": other_belief.belief_id,
                            "state_1": belief.state,
                            "state_2": other_belief.state,
                            "confidence_1": belief.confidence,
                            "confidence_2": other_belief.confidence,
                        }
                    )

                    if other_belief.belief_id not in belief.conflicting_beliefs:
                        belief.conflicting_beliefs.append(other_belief.belief_id)
                    if belief.belief_id not in other_belief.conflicting_beliefs:
                        other_belief.conflicting_beliefs.append(belief.belief_id)

                    if belief.confidence > other_belief.confidence:
                        reduction = min(0.2, belief.confidence - other_belief.confidence) / 2
                        other_belief.confidence = max(0.1, other_belief.confidence - reduction)
                        resolutions_applied.append(
                            {
                                "type": "confidence_reduction",
                                "affected_belief": other_belief.belief_id,
                                "reduction": reduction,
                            }
                        )
                    elif other_belief.confidence > belief.confidence:
                        reduction = min(0.2, other_belief.confidence - belief.confidence) / 2
                        belief.confidence = max(0.1, belief.confidence - reduction)
                        resolutions_applied.append(
                            {
                                "type": "confidence_reduction",
                                "affected_belief": belief.belief_id,
                                "reduction": reduction,
                            }
                        )

        coherence = self._calculate_self_coherence()

        return {
            "conflicts_found": len(conflicts_found),
            "conflicts": conflicts_found,
            "resolutions_applied": resolutions_applied,
            "resulting_coherence": coherence,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def generate_self_description(self) -> str:
        beliefs_by_type = self._count_beliefs_by_type()
        goals_by_status = self._count_goals_by_status()
        metrics = self.get_metrics()

        lines = self._build_identity_section(metrics)
        lines.extend(self._build_beliefs_section(beliefs_by_type, metrics))
        lines.extend(self._build_goals_section(goals_by_status, metrics))
        lines.extend(self._build_capabilities_section(metrics))
        lines.extend(self._build_limitations_section())
        lines.extend(self._build_history_section())
        return "\n".join(lines)

    def _count_beliefs_by_type(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for belief in self.beliefs.values():
            type_name = belief.belief_type.value
            result[type_name] = result.get(type_name, 0) + 1
        return result

    def _count_goals_by_status(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for goal in self.goals.values():
            status_name = goal.status.value
            result[status_name] = result.get(status_name, 0) + 1
        return result

    def _build_identity_section(self, metrics: SelfModelMetrics) -> list[str]:
        return [
            f"Self-Model Report for Agent {self.agent_id}",
            "=" * 50,
            "",
            "IDENTITY",
            f"- Agent ID: {self.agent_id}",
            f"- Self-Coherence: {metrics.self_coherence:.2f}",
            f"- Self-Accuracy: {metrics.self_accuracy:.2f}",
            "",
            "BELIEFS",
            f"- Total Beliefs: {len(self.beliefs)}",
            f"- Average Confidence: {metrics.belief_confidence_avg:.2f}",
        ]

    def _build_beliefs_section(
        self, beliefs_by_type: dict[str, int], _metrics: SelfModelMetrics
    ) -> list[str]:
        lines: list[str] = []
        if beliefs_by_type:
            lines.append("  By Type:")
            for btype, count in beliefs_by_type.items():
                lines.append(f"    - {btype}: {count}")
        return lines

    def _build_goals_section(
        self, goals_by_status: dict[str, int], metrics: SelfModelMetrics
    ) -> list[str]:
        lines: list[str] = [
            "",
            "GOALS",
            f"- Total Goals: {len(self.goals)}",
            f"- Goal Clarity: {metrics.goal_clarity:.2f}",
            f"- Progress Rate: {metrics.goal_progress_rate:.2f}",
        ]
        if goals_by_status:
            lines.append("  By Status:")
            for status_name, count in goals_by_status.items():
                lines.append(f"    - {status_name}: {count}")
        return lines

    def _build_capabilities_section(self, metrics: SelfModelMetrics) -> list[str]:
        lines: list[str] = [
            "",
            "CAPABILITIES",
            f"- Total Capabilities: {len(self.capabilities)}",
            f"- Reliability: {metrics.capability_reliability:.2f}",
        ]
        if self.capabilities:
            lines.append("  Top Capabilities:")
            sorted_caps = sorted(
                self.capabilities.values(),
                key=lambda c: c.level * c.experience_count, reverse=True,
            )[:3]
            for cap in sorted_caps:
                lines.append(f"    - {cap.name}: {cap.level:.2f} (exp: {cap.experience_count})")
        return lines

    def _build_limitations_section(self) -> list[str]:
        lines: list[str] = [
            "",
            "LIMITATIONS",
            f"- Total Limitations: {len(self.limitations)}",
        ]
        if self.limitations:
            critical_limits = [l for l in self.limitations.values() if l.severity > 0.7]  # noqa: E741
            if critical_limits:
                lines.append("  Critical Limitations:")
                for lim in critical_limits[:3]:
                    lines.append(f"    - {lim.description} (severity: {lim.severity:.2f})")
        return lines

    def _build_history_section(self) -> list[str]:
        return [
            "",
            "HISTORY",
            f"- Snapshots: {len(self.history)}",
            f"- Update Count: {self._update_count}",
            "",
        ]

    def get_metrics(self) -> SelfModelMetrics:
        self_coherence = self._calculate_self_coherence()
        goal_clarity = self._calculate_goal_clarity()
        self_accuracy = self._calculate_self_accuracy()

        if self.beliefs:
            belief_confidence_avg = sum(b.confidence for b in self.beliefs.values()) / len(
                self.beliefs
            )
        else:
            belief_confidence_avg = 0.0

        goal_progress_rate = self._calculate_goal_progress_rate()
        capability_reliability = self._calculate_capability_reliability()

        return SelfModelMetrics(
            self_coherence=self_coherence,
            goal_clarity=goal_clarity,
            self_accuracy=self_accuracy,
            belief_confidence_avg=belief_confidence_avg,
            goal_progress_rate=goal_progress_rate,
            capability_reliability=capability_reliability,
        )

    def update_capability(
        self,
        name: str,
        level: float | None = None,
        success: bool | None = None,
    ) -> Capability:
        existing = None
        for cap in self.capabilities.values():
            if cap.name == name:
                existing = cap
                break

        if existing:
            cap = existing
            cap.experience_count += 1
            cap.last_used = datetime.now(UTC).isoformat()
            if success is not None:
                alpha = 0.3
                cap.success_rate = (
                    alpha * (1.0 if success else 0.0) + (1 - alpha) * cap.success_rate
                )
            if level is not None:
                cap.level = max(0.0, min(1.0, level))
            if cap.experience_count > 10:
                cap.confidence = min(0.9, 0.5 + 0.04 * min(cap.experience_count, 10))
        else:
            success_rate = 1.0 if success else 0.0 if success is not None else 0.5
            cap = Capability(
                name=name,
                level=level or 0.5,
                experience_count=1,
                success_rate=success_rate,
                last_used=datetime.now(UTC).isoformat(),
                confidence=0.5,
            )
            self.capabilities[cap.capability_id] = cap

        return cap

    def add_limitation(
        self,
        description: str,
        severity: float = 0.5,
        workaround: str | None = None,
        mitigatable: bool = False,
    ) -> Limitation:
        limitation = Limitation(
            description=description,
            severity=max(0.0, min(1.0, severity)),
            workaround=workaround,
            mitigatable=mitigatable,
        )
        self.limitations[limitation.limitation_id] = limitation
        return limitation

    def update_preference(
        self,
        category: str,
        preference_key: str,
        value: Any,
        strength: float = 0.5,
        learned_from: str = "experience",
    ) -> Preference:
        existing = None
        for pref in self.preferences.values():
            if pref.preference_key == preference_key:
                existing = pref
                break

        if existing:
            pref = existing
            pref.value = value
            pref.strength = max(0.0, min(1.0, strength))
            pref.learned_from = learned_from
            pref.updated_at = datetime.now(UTC).isoformat()
        else:
            pref = Preference(
                category=category,
                preference_key=preference_key,
                value=value,
                strength=max(0.0, min(1.0, strength)),
                learned_from=learned_from,
            )
            self.preferences[pref.preference_id] = pref

        return pref

    def get_beliefs_for_fep(self) -> dict[str, Any]:
        beliefs_dict: dict[str, dict[str, float]] = {}
        for belief in self.beliefs.values():
            if belief.belief_type.value not in beliefs_dict:
                beliefs_dict[belief.belief_type.value] = {}
            beliefs_dict[belief.belief_type.value][belief.state] = belief.confidence

        return {
            "beliefs": beliefs_dict,
            "precision": sum(b.confidence for b in self.beliefs.values())
            / max(1, len(self.beliefs)),
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "beliefs": {k: v.to_dict() for k, v in self.beliefs.items()},
            "goals": {k: v.to_dict() for k, v in self.goals.items()},
            "capabilities": {k: v.to_dict() for k, v in self.capabilities.items()},
            "limitations": {k: v.to_dict() for k, v in self.limitations.items()},
            "preferences": {k: v.to_dict() for k, v in self.preferences.items()},
            "history": [s.to_dict() for s in self.history[-100:]],
            "update_count": self._update_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SelfModel":
        agent_id = data.get("agent_id", str(uuid.uuid4()))
        beliefs = {k: Belief.from_dict(v) for k, v in data.get("beliefs", {}).items()}
        goals = {k: Goal.from_dict(v) for k, v in data.get("goals", {}).items()}
        capabilities = {k: Capability.from_dict(v) for k, v in data.get("capabilities", {}).items()}
        limitations = {k: Limitation.from_dict(v) for k, v in data.get("limitations", {}).items()}
        preferences = {k: Preference.from_dict(v) for k, v in data.get("preferences", {}).items()}
        history = [SelfModelSnapshot.from_dict(s) for s in data.get("history", [])]

        instance = cls(
            agent_id=agent_id,
            initial_beliefs=list(beliefs.values()),
            initial_goals=list(goals.values()),
            initial_capabilities=list(capabilities.values()),
            initial_limitations=list(limitations.values()),
            initial_preferences=list(preferences.values()),
        )
        instance.history = history
        instance._update_count = data.get("update_count", 0)
        return instance

    def get_belief_states(self) -> list[dict[str, Any]]:
        return [
            {
                "state": belief.state,
                "confidence": belief.confidence,
                "type": belief.belief_type.value,
            }
            for belief in self.beliefs.values()
        ]

    def get_active_goals(self) -> list[dict[str, Any]]:
        return [goal.to_dict() for goal in self.goals.values() if goal.status == GoalStatus.ACTIVE]

    def _detect_belief_conflict(self, belief: Belief, old_confidence: float) -> None:
        logger.debug(
            "Significant belief change detected",
            extra={
                "belief_id": belief.belief_id,
                "old_confidence": old_confidence,
                "new_confidence": belief.confidence,
            },
        )

    def _are_beliefs_conflicting(self, b1: Belief, b2: Belief) -> bool:
        if b1.belief_type != b2.belief_type:
            return False
        state1_lower = b1.state.lower()
        state2_lower = b2.state.lower()
        negation_words = [
            "not",
            "no",
            "never",
            "don't",
            "doesn't",
            "isn't",
            "aren't",
            "wasn't",
            "weren't",
        ]
        for neg in negation_words:
            if neg in state1_lower or neg in state2_lower:
                # Remove negation and normalize whitespace
                state1_without_neg = " ".join(state1_lower.replace(neg, "").split())
                state2_without_neg = " ".join(state2_lower.replace(neg, "").split())
                if state1_without_neg in state2_lower or state2_without_neg in state1_lower:
                    return True
                if state2_without_neg in state1_lower or state1_without_neg in state2_lower:
                    return True
        return False

    def _calculate_self_coherence(self) -> float:
        if not self.beliefs:
            return 0.0
        coherence = 1.0
        total_conflicts = sum(len(b.conflicting_beliefs) for b in self.beliefs.values())
        conflict_penalty = min(0.4, total_conflicts * 0.05)
        coherence -= conflict_penalty
        if len(self.beliefs) > 1:
            confidences = [b.confidence for b in self.beliefs.values()]
            avg_conf = sum(confidences) / len(confidences)
            variance = sum((c - avg_conf) ** 2 for c in confidences) / len(confidences)
            variance_penalty = min(0.2, variance * 0.5)
            coherence -= variance_penalty
        avg_confidence = sum(b.confidence for b in self.beliefs.values()) / len(self.beliefs)
        confidence_bonus = avg_confidence * 0.1
        coherence += confidence_bonus
        return max(0.0, min(1.0, coherence))

    def _calculate_goal_clarity(self) -> float:
        active_goals = [g for g in self.goals.values() if g.status == GoalStatus.ACTIVE]
        if not active_goals:
            return 0.0
        clarity = 0.5
        if len(active_goals) < 1:
            clarity -= 0.2
        elif len(active_goals) > 10:
            clarity -= min(0.3, (len(active_goals) - 10) * 0.05)
        priorities = [g.priority for g in active_goals]
        avg_p = sum(priorities) / len(priorities)
        priority_variance = sum((p - avg_p) ** 2 for p in priorities) / len(priorities)
        if priority_variance > 0.1:
            clarity += 0.1
        goals_with_deadlines = sum(1 for g in active_goals if g.deadline)
        clarity += min(0.2, goals_with_deadlines * 0.1)
        goals_with_progress = sum(1 for g in active_goals if g.progress > 0)
        clarity += min(0.2, goals_with_progress * 0.1)
        return max(0.0, min(1.0, clarity))

    def _calculate_self_accuracy(self) -> float:
        return self._calculate_capability_reliability()

    def _calculate_goal_progress_rate(self) -> float:
        if not self.goals:
            return 0.0
        completed = sum(1 for g in self.goals.values() if g.status == GoalStatus.COMPLETED)
        return completed / len(self.goals)

    def _calculate_capability_reliability(self) -> float:
        if not self.capabilities:
            return 0.5
        total_weighted = 0.0
        total_weight = 0.0
        for cap in self.capabilities.values():
            weight = cap.confidence * math.log(1 + cap.experience_count)
            reliability = cap.success_rate if cap.experience_count > 0 else 0.5
            total_weighted += reliability * weight
            total_weight += weight
        return total_weighted / total_weight if total_weight > 0 else 0.5

    def _update_parent_progress(self, parent_goal_id: str) -> None:
        if parent_goal_id not in self.goals:
            return
        parent = self.goals[parent_goal_id]
        sub_goals = [self.goals[sgid] for sgid in parent.sub_goals if sgid in self.goals]
        if sub_goals:
            parent.progress = sum(sg.progress for sg in sub_goals) / len(sub_goals)

    def _unblock_dependent_goals(self, completed_goal_id: str) -> None:
        for goal in self.goals.values():
            if goal.status == GoalStatus.BLOCKED and completed_goal_id in goal.blocked_by:
                goal.blocked_by.remove(completed_goal_id)
                still_blocked = [
                    b
                    for b in goal.blocked_by
                    if b in self.goals and self.goals[b].status != GoalStatus.COMPLETED
                ]
                if not still_blocked:
                    goal.status = GoalStatus.ACTIVE
                    goal.blocked_by = []

    def _maybe_take_snapshot(self) -> None:
        now = datetime.now(UTC)
        if self._last_snapshot_time:
            elapsed = (now - self._last_snapshot_time).total_seconds()
            if elapsed < self._snapshot_interval_seconds:
                return
        metrics = self.get_metrics()
        active_goals = sum(1 for g in self.goals.values() if g.status == GoalStatus.ACTIVE)
        snapshot = SelfModelSnapshot(
            belief_count=len(self.beliefs),
            active_goal_count=active_goals,
            goal_clarity=metrics.goal_clarity,
            self_coherence=metrics.self_coherence,
            summary=f"Beliefs: {len(self.beliefs)}, Active Goals: {active_goals}",
        )
        self.history.append(snapshot)
        self._last_snapshot_time = now
        if len(self.history) > self.MAX_HISTORY_SIZE:
            self.history = self.history[-self.MAX_HISTORY_SIZE :]
