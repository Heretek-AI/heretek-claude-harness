"""Persistent ledger for the issue-loop driver.

JSON file at .omc/state/issue-loop/ledger.json. One entry per issue.
Status transitions are monotonic: pending -> {merged | skipped | failed}.
`failed` is non-terminal; the loop retries on the next tick.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

TERMINAL = frozenset({"merged", "skipped"})


@dataclass(frozen=True)
class IssueRef:
    number: int
    title: str
    files: list[str]  # file paths named in the scanner report (for diff-sanity)


class Ledger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            # TODO(follow-up): I5 — no error handling for corrupt/truncated JSON.
            self._entries: dict[str, dict] = json.loads(self.path.read_text())
        else:
            self._entries = {}
            self._save()

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._entries, indent=2, sort_keys=True))

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _ensure(self, number: int, title: str = "") -> dict:
        key = str(number)
        if key not in self._entries:
            self._entries[key] = {
                "title": title,
                "branch": None,
                "pr_url": None,
                "attempts": 0,
                "last_gate_state": "pending",
                "status": "pending",
                "last_error": None,
                "started_at": None,
                "finished_at": None,
            }
        return self._entries[key]

    def select_next(self, candidates: list[IssueRef]) -> IssueRef | None:
        eligible = []
        for c in sorted(candidates, key=lambda x: x.number):
            entry = self._entries.get(str(c.number))
            if entry is None:
                eligible.append(c)
                continue
            if entry["status"] in TERMINAL:
                continue
            if entry["attempts"] >= 3:
                continue
            eligible.append(c)
        return eligible[0] if eligible else None

    def mark_attempt(self, issue_number: int) -> None:
        e = self._ensure(issue_number)
        e["attempts"] += 1
        e["started_at"] = e["started_at"] or self._now()
        self._save()

    def mark_merged(self, issue_number: int, pr_url: str) -> None:
        e = self._ensure(issue_number)
        e["status"] = "merged"
        e["pr_url"] = pr_url
        e["finished_at"] = self._now()
        self._save()

    def mark_skipped(self, issue_number: int, reason: str) -> None:
        e = self._ensure(issue_number)
        e["status"] = "skipped"
        e["last_error"] = reason
        e["finished_at"] = self._now()
        self.reset_verifier_rejects()
        self._save()

    def mark_failed(self, issue_number: int, error: str) -> None:
        e = self._ensure(issue_number)
        e["status"] = "failed"
        e["last_error"] = error
        # do NOT set finished_at -- failed is non-terminal
        self._save()

    def record_verifier_reject(self) -> int:
        self._entries.setdefault("__root__", {})
        self._entries["__root__"].setdefault("verifier_rejects_in_a_row", 0)
        self._entries["__root__"]["verifier_rejects_in_a_row"] += 1
        self._save()
        return self._entries["__root__"]["verifier_rejects_in_a_row"]

    def reset_verifier_rejects(self) -> None:
        if "__root__" in self._entries:
            self._entries["__root__"]["verifier_rejects_in_a_row"] = 0
            self._save()

    def verifier_rejects_in_a_row(self) -> int:
        return self._entries.get("__root__", {}).get("verifier_rejects_in_a_row", 0)
