#!/usr/bin/env python3
"""
Database Migration Runner

Applies SQL migration files from the migrations/ directory in sequential order.
Tracks which migrations have been applied in a `schema_migrations` tracking table
to ensure idempotent execution.

Usage:
    python scripts/run_migrations.py                        # auto-detect DATABASE_URL
    python scripts/run_migrations.py --database-url postgresql://...
    python scripts/run_migrations.py --dry-run              # preview without applying
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import sqlalchemy
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

TRACKING_TABLE_DDL = """\
CREATE TABLE IF NOT EXISTS schema_migrations (
    version   VARCHAR(20) PRIMARY KEY,
    filename  VARCHAR(255),
    applied_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
"""

MIGRATION_FILE_RE = re.compile(r"^(\d{3})_.*\.sql$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_sync_url(url: str) -> str:
    """Convert an async driver URL to a sync equivalent."""
    if "+asyncpg" in url:
        return url.replace("+asyncpg", "")
    if "+aiopg" in url:
        return url.replace("+aiopg", "")
    return url


def _discover_migrations(directory: Path) -> list[tuple[str, Path]]:
    """Return sorted (version, path) pairs of SQL migration files."""
    migrations: list[tuple[str, Path]] = []
    for path in sorted(directory.iterdir()):
        match = MIGRATION_FILE_RE.match(path.name)
        if match:
            migrations.append((match.group(1), path))
    return migrations


def _get_applied_versions(conn: sqlalchemy.engine.Connection) -> set[str]:
    """Return set of migration versions already applied."""
    try:
        rows = conn.execute(text("SELECT version FROM schema_migrations")).fetchall()
        return {row[0] for row in rows}
    except Exception:
        # Table doesn't exist yet — no migrations applied
        conn.rollback()
        return set()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_migrations(
    database_url: str,
    *,
    dry_run: bool = False,
    migrations_dir: Path | None = None,
) -> int:
    """Apply pending migrations and return the number of migrations applied."""
    migrations_dir = migrations_dir or MIGRATIONS_DIR

    if not migrations_dir.is_dir():
        print(f"✗ Migrations directory not found: {migrations_dir}", file=sys.stderr)
        return -1

    sync_url = _to_sync_url(database_url)
    engine = create_engine(sync_url, echo=False)

    all_migrations = _discover_migrations(migrations_dir)
    if not all_migrations:
        print("✗ No migration files found.")
        return 0

    print(f"Found {len(all_migrations)} migration file(s) in {migrations_dir}")

    with engine.begin() as conn:
        # Ensure tracking table exists
        conn.execute(text(TRACKING_TABLE_DDL))

        applied = _get_applied_versions(conn)
        pending = [(ver, path) for ver, path in all_migrations if ver not in applied]

        if not pending:
            print("✓ Database is up to date — no pending migrations.")
            return 0

        print(f"  {len(applied)} already applied, {len(pending)} pending\n")

        applied_count = 0
        for version, path in pending:
            label = f"[{version}] {path.name}"
            if dry_run:
                print(f"  (dry-run) Would apply: {label}")
                applied_count += 1
                continue

            print(f"  Applying: {label} ... ", end="", flush=True)
            try:
                sql = path.read_text(encoding="utf-8")
                # Split on semicolons to handle multi-statement files,
                # but execute each statement individually
                for statement in _split_sql(sql):
                    if statement.strip():
                        conn.execute(text(statement))

                # Record in tracking table (upsert to handle self-registering migrations)
                conn.execute(
                    text(
                        "INSERT INTO schema_migrations (version, filename) "
                        "VALUES (:ver, :fname) "
                        "ON CONFLICT (version) DO UPDATE SET filename = :fname"
                    ),
                    {"ver": version, "fname": path.name},
                )
                print("OK")
                applied_count += 1
            except Exception as exc:
                print(f"FAILED\n    Error: {exc}")
                raise

    engine.dispose()

    status = "(dry-run) " if dry_run else ""
    print(f"\n✓ {status}{applied_count} migration(s) applied successfully.")
    return applied_count


def _split_sql(sql: str) -> list[str]:
    """
    Split a SQL file into individual statements.

    Handles $$ dollar-quoted blocks (PL/pgSQL functions) correctly,
    so semicolons inside function bodies are not treated as separators.
    """
    statements: list[str] = []
    current: list[str] = []
    in_dollar_quote = False
    dollar_tag = ""

    for line in sql.splitlines():
        stripped = line.strip()

        if not in_dollar_quote and (stripped.startswith("--") or stripped == ""):
            current.append(line)
            continue

        if not in_dollar_quote:
            in_dollar_quote, dollar_tag = _check_dollar_open(line, current)
            if dollar_tag:
                continue

        if in_dollar_quote:
            in_dollar_quote = _check_dollar_close(line, dollar_tag, current, statements)
            continue

        _handle_regular_line(stripped, line, current, statements)

    _flush_remaining(current, statements)
    return statements


def _check_dollar_open(line: str, current: list[str]) -> tuple[bool, str]:
    """Check for opening dollar-quote tag. Returns (in_quote, tag)."""
    match = re.search(r"(\$[a-zA-Z_]*\$)", line)
    if match:
        tag = match.group(1)
        count = line.count(tag)
        if count % 2 == 1:
            current.append(line)
            return True, tag
        current.append(line)
        return False, tag
    return False, ""


def _check_dollar_close(line: str, dollar_tag: str, current: list[str], statements: list[str]) -> bool:
    """Check for closing dollar-quote tag. Returns whether still in quote."""
    if dollar_tag in line:
        current.append(line)
        after_close = line.split(dollar_tag)[-1].strip()
        if after_close.endswith(";"):
            statements.append("\n".join(current))
            current.clear()
        return False
    current.append(line)
    return True


def _handle_regular_line(stripped: str, line: str, current: list[str], statements: list[str]) -> None:
    """Handle a regular (non-dollar-quoted) line."""
    if stripped.endswith(";"):
        current.append(line)
        statements.append("\n".join(current))
        current.clear()
    else:
        current.append(line)


def _flush_remaining(current: list[str], statements: list[str]) -> None:
    """Flush any remaining content as a final statement."""
    if current:
        remaining = "\n".join(current).strip()
        if remaining and not all(line.strip().startswith("--") or line.strip() == "" for line in current):
            statements.append(remaining)


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Heretek Swarm database migrations")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="PostgreSQL connection URL (default: $DATABASE_URL)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview migrations without applying them",
    )
    parser.add_argument(
        "--migrations-dir",
        type=Path,
        default=None,
        help=f"Migrations directory (default: {MIGRATIONS_DIR})",
    )
    args = parser.parse_args()

    if not args.database_url:
        print(
            "✗ DATABASE_URL not set. Pass --database-url or set the environment variable.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        count = run_migrations(
            args.database_url,
            dry_run=args.dry_run,
            migrations_dir=args.migrations_dir,
        )
        sys.exit(0 if count >= 0 else 1)
    except Exception as exc:
        print(f"\n✗ Migration failed: {exc}", file=sys.stderr)
        sys.exit(1)
