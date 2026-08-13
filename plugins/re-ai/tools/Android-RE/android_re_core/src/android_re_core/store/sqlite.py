"""SQLite-backed triage state store.

Phase 4 ships this as a process-local store (no remote sync). The
schema is intentionally simple — three tables:

- ``triages`` — one row per triage run
- ``findings`` — typed findings attached to a triage
- ``evidence`` — file/line evidence linked to a finding

The store is opened lazily, thread-safe via a per-instance lock,
and exposes a :class:`TriageStore` API that the orchestrator MCP
server uses directly.

We deliberately do **not** add a complex migration framework. The
schema is created on first connect via ``CREATE TABLE IF NOT
EXISTS`` and is small enough to evolve via ``ALTER TABLE`` in
later versions.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from .paths import default_db_path

__all__ = [
    "Evidence",
    "Finding",
    "FindingSeverity",
    "FindingSource",
    "Triage",
    "TriageStatus",
    "TriageStore",
]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TriageStatus(str, Enum):
    """The state machine for a triage run."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class FindingSeverity(str, Enum):
    """Standardized severity for triage findings."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingSource(str, Enum):
    """Which subsystem produced the finding."""

    STATIC = "static"
    NATIVE = "native"
    DYNAMIC = "dynamic"
    NETWORK = "network"
    MANUAL = "manual"
    CORRELATION = "correlation"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    """A single triage finding."""

    finding_id: str
    triage_id: str
    rule_id: str
    severity: FindingSeverity
    source: FindingSource
    message: str
    masvs_control: str | None = None
    artifact_path: str | None = None
    start_line: int | None = None
    start_column: int | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "triage_id": self.triage_id,
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "source": self.source.value,
            "message": self.message,
            "masvs_control": self.masvs_control,
            "artifact_path": self.artifact_path,
            "start_line": self.start_line,
            "start_column": self.start_column,
            "properties": dict(self.properties),
            "created_at": self.created_at,
        }


@dataclass
class Evidence:
    """A piece of evidence backing a finding."""

    evidence_id: str
    triage_id: str
    finding_id: str
    kind: str  # "file" | "url" | "logcat" | "rpc_result" | "string" | "screenshot"
    value: str
    annotation: str | None = None
    created_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "triage_id": self.triage_id,
            "finding_id": self.finding_id,
            "kind": self.kind,
            "value": self.value,
            "annotation": self.annotation,
            "created_at": self.created_at,
        }


@dataclass
class Triage:
    """A single triage run."""

    triage_id: str
    apk_path: str
    apk_sha256: str
    status: TriageStatus
    goals: tuple[str, ...] = ()
    created_at: float = 0.0
    updated_at: float = 0.0
    plan: list[dict[str, Any]] = field(default_factory=list)
    completed_steps: list[str] = field(default_factory=list)
    pending_steps: list[str] = field(default_factory=list)
    report_path: str | None = None
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "triage_id": self.triage_id,
            "apk_path": self.apk_path,
            "apk_sha256": self.apk_sha256,
            "status": self.status.value,
            "goals": list(self.goals),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "plan": list(self.plan),
            "completed_steps": list(self.completed_steps),
            "pending_steps": list(self.pending_steps),
            "report_path": self.report_path,
            "summary": dict(self.summary),
        }


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


_SCHEMA = """
CREATE TABLE IF NOT EXISTS triages (
  triage_id      TEXT PRIMARY KEY,
  apk_path       TEXT NOT NULL,
  apk_sha256     TEXT NOT NULL,
  status         TEXT NOT NULL,
  goals_json     TEXT NOT NULL,
  created_at     REAL NOT NULL,
  updated_at     REAL NOT NULL,
  plan_json      TEXT NOT NULL,
  completed_json TEXT NOT NULL,
  pending_json   TEXT NOT NULL,
  report_path    TEXT,
  summary_json   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_triages_status ON triages(status);
CREATE INDEX IF NOT EXISTS idx_triages_updated_at ON triages(updated_at);

CREATE TABLE IF NOT EXISTS findings (
  finding_id     TEXT PRIMARY KEY,
  triage_id      TEXT NOT NULL,
  rule_id        TEXT NOT NULL,
  severity       TEXT NOT NULL,
  source         TEXT NOT NULL,
  message        TEXT NOT NULL,
  masvs_control  TEXT,
  artifact_path  TEXT,
  start_line     INTEGER,
  start_column   INTEGER,
  properties_json TEXT NOT NULL,
  created_at     REAL NOT NULL,
  FOREIGN KEY (triage_id) REFERENCES triages(triage_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_findings_triage ON findings(triage_id);
CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity);

CREATE TABLE IF NOT EXISTS evidence (
  evidence_id   TEXT PRIMARY KEY,
  triage_id     TEXT NOT NULL,
  finding_id    TEXT NOT NULL,
  kind          TEXT NOT NULL,
  value         TEXT NOT NULL,
  annotation    TEXT,
  created_at    REAL NOT NULL,
  FOREIGN KEY (triage_id) REFERENCES triages(triage_id) ON DELETE CASCADE,
  FOREIGN KEY (finding_id) REFERENCES findings(finding_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_evidence_finding ON evidence(finding_id);
"""


def _ensure_dir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# TriageStore
# ---------------------------------------------------------------------------


class TriageStore:
    """Process-local SQLite-backed triage state.

    The store is thread-safe (one lock per instance, not per
    connection). Connections are opened per-call and closed in a
    context manager — cheap for SQLite, easier to reason about.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else default_db_path()
        _ensure_dir(self._db_path)
        self._lock = threading.RLock()
        # Eager-create the schema (idempotent).
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            conn.commit()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Yield a short-lived SQLite connection.

        Sets ``row_factory`` to :class:`sqlite3.Row` so we can use
        column-name access. Enables foreign-key enforcement.
        """
        conn = sqlite3.connect(
            str(self._db_path),
            timeout=10.0,
            isolation_level=None,  # autocommit; we manage txns explicitly
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Triages
    # ------------------------------------------------------------------

    def open_triage(
        self,
        apk_path: str,
        apk_sha256: str,
        goals: Iterable[str] = (),
    ) -> Triage:
        """Open a new triage and return its initial state."""
        now = time.time()
        triage = Triage(
            triage_id=str(uuid.uuid4()),
            apk_path=apk_path,
            apk_sha256=apk_sha256,
            status=TriageStatus.PENDING,
            goals=tuple(goals),
            created_at=now,
            updated_at=now,
        )
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                    INSERT INTO triages (
                        triage_id, apk_path, apk_sha256, status, goals_json,
                        created_at, updated_at, plan_json, completed_json,
                        pending_json, report_path, summary_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                (
                    triage.triage_id,
                    triage.apk_path,
                    triage.apk_sha256,
                    triage.status.value,
                    json.dumps(list(triage.goals)),
                    triage.created_at,
                    triage.updated_at,
                    json.dumps(triage.plan),
                    json.dumps(triage.completed_steps),
                    json.dumps(triage.pending_steps),
                    triage.report_path,
                    json.dumps(triage.summary),
                ),
            )
        return triage

    def get_triage(self, triage_id: str) -> Triage | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM triages WHERE triage_id = ?", (triage_id,)).fetchone()
        if row is None:
            return None
        return _row_to_triage(row)

    def update_triage(
        self,
        triage_id: str,
        *,
        status: TriageStatus | None = None,
        plan: list[dict[str, Any]] | None = None,
        completed_steps: list[str] | None = None,
        pending_steps: list[str] | None = None,
        report_path: str | None = None,
        summary: dict[str, Any] | None = None,
    ) -> Triage | None:
        """Patch a triage. ``None`` for a field means "leave unchanged"."""
        with self._lock, self._connect() as conn:
            # Build a dynamic SET clause.
            sets: list[str] = ["updated_at = ?"]
            params: list[Any] = [time.time()]
            if status is not None:
                sets.append("status = ?")
                params.append(status.value)
            if plan is not None:
                sets.append("plan_json = ?")
                params.append(json.dumps(plan))
            if completed_steps is not None:
                sets.append("completed_json = ?")
                params.append(json.dumps(completed_steps))
            if pending_steps is not None:
                sets.append("pending_json = ?")
                params.append(json.dumps(pending_steps))
            if report_path is not None:
                sets.append("report_path = ?")
                params.append(report_path)
            if summary is not None:
                sets.append("summary_json = ?")
                params.append(json.dumps(summary))
            params.append(triage_id)
            conn.execute(
                f"UPDATE triages SET {', '.join(sets)} WHERE triage_id = ?",
                params,
            )
        return self.get_triage(triage_id)

    def list_triages(self, *, limit: int = 50) -> list[Triage]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM triages ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row_to_triage(r) for r in rows]

    def delete_triage(self, triage_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM triages WHERE triage_id = ?", (triage_id,))
        return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Findings
    # ------------------------------------------------------------------

    def add_finding(self, finding: Finding) -> Finding:
        if not finding.created_at:
            finding = Finding(
                finding_id=finding.finding_id or str(uuid.uuid4()),
                triage_id=finding.triage_id,
                rule_id=finding.rule_id,
                severity=finding.severity,
                source=finding.source,
                message=finding.message,
                masvs_control=finding.masvs_control,
                artifact_path=finding.artifact_path,
                start_line=finding.start_line,
                start_column=finding.start_column,
                properties=dict(finding.properties),
                created_at=time.time(),
            )
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                    INSERT OR REPLACE INTO findings (
                        finding_id, triage_id, rule_id, severity, source,
                        message, masvs_control, artifact_path, start_line,
                        start_column, properties_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                (
                    finding.finding_id,
                    finding.triage_id,
                    finding.rule_id,
                    finding.severity.value,
                    finding.source.value,
                    finding.message,
                    finding.masvs_control,
                    finding.artifact_path,
                    finding.start_line,
                    finding.start_column,
                    json.dumps(finding.properties),
                    finding.created_at,
                ),
            )
        return finding

    def list_findings(
        self,
        triage_id: str,
        *,
        severity: FindingSeverity | None = None,
        source: FindingSource | None = None,
    ) -> list[Finding]:
        with self._lock, self._connect() as conn:
            sql = "SELECT * FROM findings WHERE triage_id = ?"
            params: list[Any] = [triage_id]
            if severity is not None:
                sql += " AND severity = ?"
                params.append(severity.value)
            if source is not None:
                sql += " AND source = ?"
                params.append(source.value)
            sql += " ORDER BY created_at"
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_finding(r) for r in rows]

    def get_finding(self, finding_id: str) -> Finding | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM findings WHERE finding_id = ?", (finding_id,)
            ).fetchone()
        if row is None:
            return None
        return _row_to_finding(row)

    # ------------------------------------------------------------------
    # Evidence
    # ------------------------------------------------------------------

    def add_evidence(self, evidence: Evidence) -> Evidence:
        if not evidence.created_at:
            evidence = Evidence(
                evidence_id=evidence.evidence_id or str(uuid.uuid4()),
                triage_id=evidence.triage_id,
                finding_id=evidence.finding_id,
                kind=evidence.kind,
                value=evidence.value,
                annotation=evidence.annotation,
                created_at=time.time(),
            )
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                    INSERT OR REPLACE INTO evidence (
                        evidence_id, triage_id, finding_id, kind, value,
                        annotation, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                (
                    evidence.evidence_id,
                    evidence.triage_id,
                    evidence.finding_id,
                    evidence.kind,
                    evidence.value,
                    evidence.annotation,
                    evidence.created_at,
                ),
            )
        return evidence

    def list_evidence_for_finding(self, finding_id: str) -> list[Evidence]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM evidence WHERE finding_id = ? ORDER BY created_at",
                (finding_id,),
            ).fetchall()
        return [_row_to_evidence(r) for r in rows]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            t = conn.execute("SELECT COUNT(*) FROM triages").fetchone()[0]
            f = conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
            e = conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
        return {
            "triage_count": t,
            "finding_count": f,
            "evidence_count": e,
            "db_path": str(self._db_path),
        }


# ---------------------------------------------------------------------------
# Internal row mappers
# ---------------------------------------------------------------------------


def _row_to_triage(row: sqlite3.Row) -> Triage:
    return Triage(
        triage_id=row["triage_id"],
        apk_path=row["apk_path"],
        apk_sha256=row["apk_sha256"],
        status=TriageStatus(row["status"]),
        goals=tuple(json.loads(row["goals_json"])),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        plan=list(json.loads(row["plan_json"])),
        completed_steps=list(json.loads(row["completed_json"])),
        pending_steps=list(json.loads(row["pending_json"])),
        report_path=row["report_path"],
        summary=dict(json.loads(row["summary_json"])),
    )


def _row_to_finding(row: sqlite3.Row) -> Finding:
    return Finding(
        finding_id=row["finding_id"],
        triage_id=row["triage_id"],
        rule_id=row["rule_id"],
        severity=FindingSeverity(row["severity"]),
        source=FindingSource(row["source"]),
        message=row["message"],
        masvs_control=row["masvs_control"],
        artifact_path=row["artifact_path"],
        start_line=row["start_line"],
        start_column=row["start_column"],
        properties=dict(json.loads(row["properties_json"])),
        created_at=row["created_at"],
    )


def _row_to_evidence(row: sqlite3.Row) -> Evidence:
    return Evidence(
        evidence_id=row["evidence_id"],
        triage_id=row["triage_id"],
        finding_id=row["finding_id"],
        kind=row["kind"],
        value=row["value"],
        annotation=row["annotation"],
        created_at=row["created_at"],
    )
