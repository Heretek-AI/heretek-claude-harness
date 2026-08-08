"""False-positive suppression per spec §8.7.

Maintainers can suppress a scanner finding by adding a tag in the item's ADR:
    <!-- suppress: skillspector:prompt-injection -->

After the scanner runs, any finding whose (scanner, rule_id) is in the
suppression set is *downgraded* to severity=info but kept in the report.
This preserves an audit trail while unblocking the maintainer override.

The CODEOWNERS gate in .github/CODEOWNERS requires the `security` plugin owner
to approve any change to a catalog/reviews/*.md file, so suppressions are
human-reviewed.
"""
from __future__ import annotations

import re
from pathlib import Path

# A suppression comment looks like:
#   <!-- suppress: <scanner>:<rule_id> -->
# Group 1 = scanner, Group 2 = rule_id.
SUPPRESSION_RE = re.compile(
    r"<!--\s*suppress:\s*([a-zA-Z0-9_-]+):([a-zA-Z0-9_.-]+)\s*-->"
)


def load_suppressions(reviews_dir: Path) -> set[tuple[str, str]]:
    """Walk catalog/reviews/*.md and collect every (scanner, rule_id) suppression.

    Returns an empty set if the directory doesn't exist or has no suppressions.
    Errors reading individual files are swallowed (logged at debug level) so
    a malformed ADR never aborts the scan.
    """
    suppressions: set[tuple[str, str]] = set()
    if not reviews_dir.exists():
        return suppressions
    for path in sorted(reviews_dir.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in SUPPRESSION_RE.finditer(text):
            suppressions.add((match.group(1), match.group(2)))
    return suppressions


def is_suppressed(
    suppressions: set[tuple[str, str]], *, scanner: str, rule_id: str | None
) -> bool:
    """A finding is suppressed if (scanner, rule_id) is in the set.

    rule_id is None (anonymous finding) → never suppressed; require an explicit
    ID to suppress, so a rule-less finding won't be silently dropped.
    """
    if rule_id is None:
        return False
    return (scanner, rule_id) in suppressions
