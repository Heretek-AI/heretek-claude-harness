"""
Self-Maintenance Module for Heretek Swarm

Provides autonomous maintenance tasks that keep the system healthy:
- Log rotation: removes files older than 7 days, compresses files >10MB
- Database maintenance: VACUUM ANALYZE on critical tables, prune orphaned records
- Configuration drift detection: compares current config against stored baseline
- SelfMaintenanceScheduler: runs on interval and integrates with AutonomousRuntime lifecycle

Reference: EXPANSION_ROADMAP.md S-3 Self-Healing
"""

import asyncio
import gzip
import hashlib
import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger("self_maintenance")

# ------------------------------------------------------------------
# Configuration dataclasses
# ------------------------------------------------------------------


@dataclass
class LogRotationConfig:
    """Configuration for log rotation."""

    log_directory: Path = field(
        default_factory=lambda: Path(__file__).parent.parent.parent.parent / "logs"
    )
    max_age_days: int = 7  # Remove files older than this
    compress_above_mb: float = 10.0  # Compress files larger than this
    file_extensions: tuple[str, ...] = (".log", ".out", ".err")
    dry_run: bool = False  # If True, only report what would be done


@dataclass
class DatabaseMaintenanceConfig:
    """Configuration for database maintenance."""

    database_url: str | None = None
    vacuum_analyze_tables: tuple[str, ...] = (
        "agent_states",
        "agent_state_checkpoints",
        "domain_events",
    )
    prune_orphaned_older_than_hours: int = 24 * 7  # 7 days
    checkpoint_retention_count: int = 10  # Keep this many checkpoints per agent
    dry_run: bool = False


@dataclass
class DeploymentConfig:
    """Configuration for autonomous deployment pipeline (P3)."""

    run_interval_seconds: int = 21600  # Every 6 hours
    dry_run: bool = False  # If True, report what would deploy without deploying
    repo_path: str = "/home/john/Desktop/heretek-swarm"
    git_branch: str = "main"


@dataclass
class ConfigDriftConfig:
    """Configuration for configuration drift detection."""

    baseline_directory: Path = field(
        default_factory=lambda: Path.home() / ".heretek" / "config_baselines"
    )
    critical_keys: tuple[str, ...] = (
        "log_level",
        "monitoring_enabled",
        "auto_restart_enabled",
        "max_restart_attempts",
        "state_persistence_enabled",
        "auto_scaling_enabled",
    )
    hash_algorithm: str = "sha256"
    dry_run: bool = False


@dataclass
class DeploymentPipelineConfig:
    """Configuration for the self-deployment pipeline (P3, PLAN.md §4.3)."""

    repo_root: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent.parent
    )
    branch: str = "main"
    interval_seconds: int = 21_600  # Every 6 hours
    test_command: str = "python3 -m pytest tests/"
    integration_command: str = "python3 scripts/verify_integration.py"
    build_command: str = "docker compose build api"
    deploy_command: str = "docker compose up -d --force-recreate api"
    dry_run: bool = False


@dataclass
class SelfMaintenanceConfig:
    """Aggregated configuration for self-maintenance tasks."""

log_rotation: LogRotationConfig = field(default_factory=LogRotationConfig)
    db_maintenance: DatabaseMaintenanceConfig = field(default_factory=DatabaseMaintenanceConfig)
    config_drift: ConfigDriftConfig = field(default_factory=ConfigDriftConfig)
    deployment: DeploymentConfig = field(default_factory=DeploymentConfig)
    run_interval_seconds: int = 3600
    log_rotation_interval_seconds: int = 86400
    db_maintenance_interval_seconds: int = 43200
    config_drift_interval_seconds: int = 7200
    enabled: bool = True


# ------------------------------------------------------------------
# Log Rotation
# ------------------------------------------------------------------


class LogRotator:
    """
    Rotates and manages log files.

    Responsibilities:
    - Remove log files older than max_age_days
    - Compress log files larger than compress_above_mb MB
    """

    def __init__(self, config: LogRotationConfig):
        self.config = config
        self._stats = {
            "files_removed": 0,
            "files_compressed": 0,
            "bytes_freed": 0,
            "errors": 0,
        }

    async def _collect_files_for_rotation(
        self,
        log_dir: Path,
        cutoff: datetime,
        compress_threshold: int,
    ) -> tuple[list[Path], list[Path]]:
        """
        Scan log_directory and return files to remove and files to compress.

        Returns:
            (files_to_remove, files_to_compress)
        """
        files_to_remove: list[Path] = []
        files_to_compress: list[Path] = []

        try:
            for file_path in log_dir.iterdir():  # noqa: ASYNC240
                if not file_path.is_file():
                    continue
                if not file_path.name.endswith(self.config.file_extensions):
                    continue

                try:
                    age = datetime.fromtimestamp(file_path.stat().st_mtime, tz=UTC)
                    size = file_path.stat().st_size

                    # Check if file is already compressed
                    if file_path.suffix in (".gz", ".bz2"):
                        # Only remove old compressed files
                        if age < cutoff:
                            files_to_remove.append(file_path)
                    else:
                        # Check age for uncompressed files
                        if age < cutoff:
                            files_to_remove.append(file_path)
                        elif size > compress_threshold:
                            files_to_compress.append(file_path)

                except OSError:
                    logger.warning("Failed to stat log file {file_path}: {e}")
                    self._stats["errors"] += 1
        except OSError:
            logger.error("Failed to list log directory: {e}")
            self._stats["errors"] += 1

        return files_to_remove, files_to_compress

    async def _remove_old_files(self, files_to_remove: list[Path]) -> None:
        """Remove files marked for deletion, updating stats on success or error."""
        for file_path in files_to_remove:
            if self.config.dry_run:
                logger.info("[DRY RUN] Would remove {file_path}")
            else:
                try:
                    size = file_path.stat().st_size
                    file_path.unlink()
                    self._stats["files_removed"] += 1
                    self._stats["bytes_freed"] += size
                    logger.debug("Removed old log file: {file_path}")
                except OSError:
                    logger.error("Failed to remove {file_path}: {e}")
                    self._stats["errors"] += 1

    async def _compress_large_files(self, files_to_compress: list[Path]) -> None:
        """Compress files above the size threshold, updating stats on success or error."""
        for file_path in files_to_compress:
            compressed = file_path.with_suffix(file_path.suffix + ".gz")
            if compressed.exists():
                # Already compressed
                continue

            if self.config.dry_run:
                logger.info(
                    f"[DRY RUN] Would compress {file_path} "  # noqa: G004
                    f"({file_path.stat().st_size / 1024 / 1024:.1f}MB)"
                )
            else:
                try:
                    original_size = file_path.stat().st_size
                    with open(file_path, "rb") as f_in:  # noqa: ASYNC230,PTH123,SIM117
                        with gzip.open(compressed, "wb", compresslevel=6) as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    # Remove original after successful compression
                    file_path.unlink()
                    compressed_size = compressed.stat().st_size
                    self._stats["files_compressed"] += 1
                    self._stats["bytes_freed"] += original_size - compressed_size
                    logger.info(
                        f"Compressed log file: {file_path.name} "  # noqa: G004
                        f"({original_size / 1024 / 1024:.1f}MB -> "
                        f"{compressed_size / 1024 / 1024:.1f}MB)"
                    )
                except OSError:
                    logger.error("Failed to compress {file_path}: {e}")
                    self._stats["errors"] += 1

    async def rotate(self) -> dict[str, Any]:
        """
        Perform log rotation.

        Returns:
            Statistics about what was done
        """
        self._stats = {
            "files_removed": 0,
            "files_compressed": 0,
            "bytes_freed": 0,
            "errors": 0,
        }

        log_dir = Path(self.config.log_directory)
        if not log_dir.exists():  # noqa: ASYNC240
            logger.info("Log directory does not exist, skipping rotation", path=str(log_dir))
            return self._stats

        cutoff = datetime.now(UTC) - timedelta(days=self.config.max_age_days)
        compress_threshold = int(self.config.compress_above_mb * 1024 * 1024)

        files_to_remove, files_to_compress = await self._collect_files_for_rotation(
            log_dir, cutoff, compress_threshold
        )
        await self._remove_old_files(files_to_remove)
        await self._compress_large_files(files_to_compress)

        logger.info(
            "Log rotation complete",
            files_removed=self._stats["files_removed"],
            files_compressed=self._stats["files_compressed"],
            bytes_freed=self._stats["bytes_freed"],
            errors=self._stats["errors"],
        )
        return self._stats

    def get_stats(self) -> dict[str, Any]:
        """Return rotation statistics."""
        return {**self._stats}


# ------------------------------------------------------------------
# Database Maintenance
# ------------------------------------------------------------------


class DatabaseMaintenance:
    """
    Performs database maintenance tasks.

    Responsibilities:
    - Run VACUUM ANALYZE on critical tables
    - Prune orphaned records older than retention period
    - Manage checkpoint retention
    """

    def __init__(self, config: DatabaseMaintenanceConfig):
        self.config = config
        self._stats = {
            "vacuum_analyze_runs": 0,
            "orphaned_deleted": 0,
            "checkpoints_pruned": 0,
            "errors": 0,
        }

    async def run_maintenance(self) -> dict[str, Any]:
        """
        Run all database maintenance tasks.

        Returns:
            Statistics about maintenance performed
        """
        self._stats = {
            "vacuum_analyze_runs": 0,
            "orphaned_deleted": 0,
            "checkpoints_pruned": 0,
            "errors": 0,
        }

        db_url = self.config.database_url or os.environ.get("DATABASE_URL")
        if not db_url:
            logger.info("No database URL configured, skipping DB maintenance")
            return self._stats

        try:
            import asyncpg

            pool = await asyncpg.create_pool(
                db_url,
                min_size=1,
                max_size=2,
                command_timeout=300,
            )
        except ImportError:
            logger.warning("asyncpg not available, skipping DB maintenance")
            return self._stats
        except Exception:
            logger.error("Failed to connect to database: {e}")
            self._stats["errors"] += 1
            return self._stats

        try:
            await self._vacuum_analyze(pool)
            await self._prune_orphaned(pool)
            await self._prune_checkpoints(pool)
        finally:
            await pool.close()

        logger.info(
            "Database maintenance complete",
            vacuum_runs=self._stats["vacuum_analyze_runs"],
            orphaned_deleted=self._stats["orphaned_deleted"],
            checkpoints_pruned=self._stats["checkpoints_pruned"],
            errors=self._stats["errors"],
        )
        return self._stats

    async def _vacuum_analyze(self, pool: Any) -> None:
        """Run VACUUM ANALYZE on critical tables."""
        for table in self.config.vacuum_analyze_tables:
            try:
                async with pool.acquire() as conn:
                    # Use autovacuum-friendly VACUUM (no exclusive lock)
                    await conn.execute(f'VACUUM (ANALYZE) "{table}"')
                    self._stats["vacuum_analyze_runs"] += 1
                    logger.debug("VACUUM ANALYZE completed for {table}")
            except Exception:
                logger.error("VACUUM ANALYZE failed for {table}: {e}")
                self._stats["errors"] += 1

    async def _prune_orphaned(self, pool: Any) -> None:
        """Prune orphaned agent state records."""
        try:
            cutoff = datetime.now(UTC) - timedelta(
                hours=self.config.prune_orphaned_older_than_hours
            )
            async with pool.acquire() as conn:
                # Prune inactive agent states older than retention period
                result = await conn.execute(
                    """
                    UPDATE agent_states
                    SET is_active = false
                    WHERE is_active = true
                    AND updated_at < $1
                    AND NOT EXISTS (
                        SELECT 1 FROM agents WHERE agents.agent_id = agent_states.agent_id
                    )
                    """,
                    cutoff,
                )
                # result is "UPDATE N" where N is the count
                count = int(result.split()[-1]) if result != "UPDATE 0" else 0
                self._stats["orphaned_deleted"] += count
                logger.debug("Pruned {count} orphaned agent_states")
        except Exception:
            logger.error("Failed to prune orphaned records: {e}")
            self._stats["errors"] += 1

    async def _prune_checkpoints(self, pool: Any) -> None:
        """Prune old checkpoints keeping only the most recent N per agent."""
        try:
            async with pool.acquire() as conn:
                for table in ("agent_state_checkpoints",):
                    # Get agents with too many checkpoints
                    result = await conn.fetch(
                        f"""
                        DELETE FROM "{table}"
                        WHERE ctid IN (
                            SELECT ctid FROM (
                                SELECT ctid, ROW_NUMBER() OVER (
                                    PARTITION BY agent_id
                                    ORDER BY created_at DESC
                                ) as rn
                                FROM "{table}"
                            ) sub
                            WHERE rn > $1
                        )
                        """,
                        self.config.checkpoint_retention_count,
                    )
                    self._stats["checkpoints_pruned"] += len(result) if result else 0
                    logger.debug("Pruned excess checkpoints from {table}")
        except Exception:
            logger.error("Failed to prune checkpoints: {e}")
            self._stats["errors"] += 1

    def get_stats(self) -> dict[str, Any]:
        """Return maintenance statistics."""
        return {**self._stats}


# ------------------------------------------------------------------
# Configuration Drift Detection
# ------------------------------------------------------------------


class ConfigDriftDetector:
    """
    Detects configuration drift by comparing current config against a stored baseline.

    Responsibilities:
    - Store a baseline of critical configuration values
    - Compare current runtime config against baseline
    - Report any drift detected
    """

    def __init__(self, config: ConfigDriftConfig):
        self.config = config
        self._last_drift_result: dict[str, Any] | None = None

    def _get_baseline_path(self, config_name: str = "runtime") -> Path:
        """Get path to the baseline file for a given config."""
        self.config.baseline_directory.mkdir(parents=True, exist_ok=True)
        return self.config.baseline_directory / f"{config_name}.json"

    def store_baseline(self, config_data: dict[str, Any], config_name: str = "runtime") -> str:
        """
        Store current configuration as the baseline.

        Args:
            config_data: Dictionary of config key-value pairs
            config_name: Name for this configuration (e.g., "runtime", "scaling")

        Returns:
            Path where baseline was stored
        """
        # Extract only the critical keys (and their values) for the baseline
        baseline: dict[str, Any] = {}
        for key in self.config.critical_keys:
            if key in config_data:
                value = config_data[key]
                # Hash non-primitive values for reproducibility
                if not isinstance(value, (str, int, float, bool, type(None))):
                    value = hashlib.new(
                        self.config.hash_algorithm,
                        json.dumps(value, sort_keys=True, default=str).encode(),
                    ).hexdigest()
                baseline[key] = value

        # Add metadata
        baseline["_stored_at"] = datetime.now(UTC).isoformat()
        baseline["_hash_algorithm"] = self.config.hash_algorithm

        path = self._get_baseline_path(config_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(baseline, indent=2))

        logger.info("Configuration baseline stored at {path}", keys=len(baseline))
        return str(path)

    def _read_baseline(self, baseline_path: Path) -> dict[str, Any]:
        """
        Read and parse a baseline JSON file.

        Args:
            baseline_path: Path to the baseline file

        Returns:
            Parsed baseline dict (metadata keys included)

        Raises:
            OSError: If the file cannot be read
            json.JSONDecodeError: If the file is not valid JSON
        """
        return json.loads(baseline_path.read_text())

    def _classify_config_changes(
        self,
        baseline_keys: dict[str, Any],
        current_config: dict[str, Any],
    ) -> tuple[list[str], list[str], list[str]]:
        """
        Classify config changes into changed, added, and removed keys.

        Args:
            baseline_keys: Baseline key-value pairs (metadata stripped)
            current_config: Current runtime configuration

        Returns:
            (changed_keys, added_keys, removed_keys)
        """
        changed_keys: list[str] = []
        added_keys: list[str] = []
        removed_keys: list[str] = []

        # Check for changes and additions
        for key in self.config.critical_keys:
            if key not in current_config:
                continue

            current_value = current_config[key]
            if not isinstance(current_value, (str, int, float, bool, type(None))):
                current_value = hashlib.new(
                    self.config.hash_algorithm,
                    json.dumps(current_value, sort_keys=True, default=str).encode(),
                ).hexdigest()

            if key not in baseline_keys:
                added_keys.append(key)
            elif baseline_keys[key] != current_value:
                changed_keys.append(key)

        # Check for removed keys
        for key in baseline_keys:
            if key not in current_config:
                removed_keys.append(key)  # noqa: PERF401

        return changed_keys, added_keys, removed_keys

    async def detect_drift(
        self,
        current_config: dict[str, Any],
        config_name: str = "runtime",
    ) -> dict[str, Any]:
        """
        Detect drift between current config and stored baseline.

        Args:
            current_config: Current runtime configuration
            config_name: Name of the config to check

        Returns:
            Drift report with changed_keys, added_keys, removed_keys
        """
        baseline_path = self._get_baseline_path(config_name)

        if not baseline_path.exists():
            logger.warning("No baseline found at {baseline_path}, run store_baseline() first")
            self._last_drift_result = {
                "has_drift": False,
                "reason": "no_baseline",
                "baseline_path": str(baseline_path),
            }
            return self._last_drift_result

        try:
            baseline = self._read_baseline(baseline_path)
        except (OSError, json.JSONDecodeError) as e:
            logger.error("Failed to read baseline file: {e}")
            self._last_drift_result = {
                "has_drift": False,
                "reason": "baseline_read_error",
                "error": str(e),
            }
            return self._last_drift_result

        # Remove metadata keys from comparison
        baseline_keys = {k: v for k, v in baseline.items() if not k.startswith("_")}

        changed_keys, added_keys, removed_keys = self._classify_config_changes(
            baseline_keys, current_config
        )

        has_drift = bool(changed_keys or added_keys or removed_keys)

        result = {
            "has_drift": has_drift,
            "changed_keys": changed_keys,
            "added_keys": added_keys,
            "removed_keys": removed_keys,
            "baseline_path": str(baseline_path),
            "checked_at": datetime.now(UTC).isoformat(),
        }

        self._last_drift_result = result

        if has_drift:
            logger.warning(
                "Configuration drift detected",
                changed=changed_keys,
                added=added_keys,
                removed=removed_keys,
            )
        else:
            logger.debug("No configuration drift detected")

return result


# ------------------------------------------------------------------
# Deployment Pipeline (P3 — PLAN.md §4.3 Workflow 1)
# ------------------------------------------------------------------


class DeploymentPipeline:
    """Autonomous deployment pipeline.  Pulls ``main``, runs the test
    suite, builds images, and redeploys the api on green.  Default
    6-hour interval integrated into ``SelfMaintenanceScheduler``.
    """

    def __init__(self, config: DeploymentConfig):
        self.config = config
        self._last_result: dict[str, Any] = {"ran_at": None}
        self._last_green_deploy: datetime | None = None

    async def run_once(self) -> dict[str, Any]:
        """One deployment cycle: git pull -> test -> build -> deploy."""
        result: dict[str, Any] = {
            "ran_at": datetime.now(UTC).isoformat(),
            "git_pulled": False,
            "tests_passed": False,
            "integration_passed": False,
            "build_succeeded": False,
            "deployed": False,
            "error": None,
        }
        try:
            if self.config.dry_run:
                logger.info("deployment_dry_run", branch=self.config.branch)
                result["git_pulled"] = True
            else:
                proc = await asyncio.create_subprocess_exec(
                    "git", "pull", "--ff-only", "origin", self.config.branch,
                    cwd=str(self.config.repo_root),
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                if proc.returncode != 0:
                    result["error"] = "git pull failed"
                    logger.error("deployment_git_failed", rc=proc.returncode)
                    return result
                result["git_pulled"] = True
                logger.info("deployment_git_pulled")

            # Run tests
            t = await asyncio.create_subprocess_exec(
                "python3", "-m", "pytest", "tests/",
                cwd=str(self.config.repo_root),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await t.communicate()
            if t.returncode != 0:
                result["error"] = "tests failed"
                logger.error("deployment_tests_failed")
                return result
            result["tests_passed"] = True

            # Integration
            i = await asyncio.create_subprocess_exec(
                "python3", "scripts/verify_integration.py",
                cwd=str(self.config.repo_root),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await i.communicate()
            if i.returncode != 0:
                result["error"] = "integration failed"
                logger.error("deployment_integration_failed")
                return result
            result["integration_passed"] = True

            # Build + deploy
            if not self.config.dry_run:
                b = await asyncio.create_subprocess_exec(
                    "docker", "compose", "build", "api",
                    cwd=str(self.config.repo_root),
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                await b.communicate()
                if b.returncode != 0:
                    result["error"] = "build failed"
                    logger.error("deployment_build_failed")
                    return result
                result["build_succeeded"] = True

                d = await asyncio.create_subprocess_exec(
                    "docker", "compose", "up", "-d", "--force-recreate", "api",
                    cwd=str(self.config.repo_root),
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                await d.communicate()
                if d.returncode != 0:
                    result["error"] = "deploy failed"
                    logger.error("deployment_deploy_failed")
                    return result
                result["deployed"] = True
                self._last_green_deploy = datetime.now(UTC)
                logger.info("deployment_succeeded")
            return result
        except Exception as e:
            result["error"] = str(e)
            logger.error("deployment_error", error=str(e))
            return result

    def get_last_result(self) -> dict[str, Any]:
        return self._last_result

    def get_last_green_deploy(self) -> datetime | None:
        return self._last_green_deploy


# ------------------------------------------------------------------
# Deployment Pipeline (P3 — PLAN.md §4.3 Workflow 1)
# ------------------------------------------------------------------


class DeploymentPipeline:
...

# ------------------------------------------------------------------
# Self-Maintenance Scheduler
# ------------------------------------------------------------------


class SelfMaintenanceScheduler:
    """
    Orchestrates all self-maintenance tasks on configurable intervals.

    Integrates with AutonomousRuntime lifecycle:
    - Starts all background maintenance loops when runtime starts
    - Stops cleanly when runtime stops
    - Provides status via get_status()
    """

    def __init__(
        self,
        config: SelfMaintenanceConfig,
        runtime_ref: Any = None,
    ):
        """
        Initialize the maintenance scheduler.

        Args:
            config: Self-maintenance configuration
            runtime_ref: Optional reference to AutonomousRuntime (for integration)
        """
        self.config = config
        self.runtime_ref = runtime_ref
        self._running = False
        self._shutdown_event = asyncio.Event()

        # Individual task runners
        self._log_rotator = LogRotator(self.config.log_rotation)
        self._db_maintenance = DatabaseMaintenance(self.config.db_maintenance)
        self._drift_detector = ConfigDriftDetector(self.config.config_drift)
        self._deployment = DeploymentPipeline(self.config.deployment)
        self._deployment = DeploymentPipeline(self.config.deployment)

        # Stats
        self._stats: dict[str, Any] = {
            "log_rotation": self._log_rotator.get_stats(),
            "db_maintenance": self._db_maintenance.get_stats(),
            "last_drift_result": None,
            "loops_run": 0,
        }

        # Tracking for interval-based scheduling
        self._last_log_rotation: datetime | None = None
        self._last_db_maintenance: datetime | None = None
        self._last_drift_check: datetime | None = None

    async def start(self) -> None:
        """Start all maintenance loops."""
        if not self.config.enabled:
            logger.info("Self-maintenance scheduler is disabled")
            return

        logger.info("Starting self-maintenance scheduler...")
        self._running = True
        self._shutdown_event.clear()

        # Run each task on its own interval
        maintenance_tasks = [
            self._maintenance_loop(),
            self._log_rotation_loop(),
            self._db_maintenance_loop(),
            self._drift_loop(),
            self._deployment_loop(),
        ]

        deployment_tasks = [self._deployment_loop()] if self.config.deployment.interval_seconds > 0 else []
        await asyncio.gather(*[asyncio.create_task(t) for t in maintenance_tasks + deployment_tasks])

    async def stop(self) -> None:
        """Stop all maintenance loops gracefully."""
        logger.info("Stopping self-maintenance scheduler...")
        self._running = False
        self._shutdown_event.set()

        # Run final rotation before shutdown
        try:
            await self._log_rotator.rotate()
        except Exception:
            logger.error("Final log rotation failed: {e}")

    # -------------------------------------------------------------------------
    # Individual maintenance loops
    # -------------------------------------------------------------------------

    async def _maintenance_loop(self) -> None:
        """
        Master loop that runs all tasks on the configured interval.

        This is the primary entry point integrated with AutonomousRuntime.
        """
        while self._running and not self._shutdown_event.is_set():
            try:
                if not self.config.enabled:
                    break

                # Run all tasks sequentially for simplicity
                await self._run_all_tasks()

                self._stats["loops_run"] += 1

                # Wait for next interval
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self.config.run_interval_seconds,
                )
                # If we get here without timeout, shutdown was requested
                break

            except TimeoutError:
                # Normal interval elapsed, loop continues
                logger.debug("Maintenance interval elapsed, looping")
            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("Maintenance loop error: {e}")
                await asyncio.sleep(60)

    async def _run_all_tasks(self) -> None:
        """Run all maintenance tasks in sequence."""
        # Log rotation
        await self._log_rotator.rotate()
        self._stats["log_rotation"] = self._log_rotator.get_stats()

        # Database maintenance
        await self._db_maintenance.run_maintenance()
        self._stats["db_maintenance"] = self._db_maintenance.get_stats()

        # Config drift detection (no config object needed for read-only check)
        drift_result = await self._drift_detector.detect_drift(self._get_runtime_config())
        self._stats["last_drift_result"] = drift_result

        self._stats["loops_run"] += 1

        logger.info("All maintenance tasks completed", loops_run=self._stats["loops_run"])

    def _get_runtime_config(self) -> dict[str, Any]:
        """Extract current runtime config values for drift detection."""
        if self.runtime_ref and hasattr(self.runtime_ref, "config"):
            cfg = self.runtime_ref.config
            return {
                "log_level": getattr(cfg, "log_level", None),
                "monitoring_enabled": getattr(cfg, "monitoring_enabled", None),
                "auto_restart_enabled": getattr(cfg, "auto_restart_enabled", None),
                "max_restart_attempts": getattr(cfg, "max_restart_attempts", None),
                "state_persistence_enabled": getattr(cfg, "state_persistence_enabled", None),
                "auto_scaling_enabled": getattr(cfg, "auto_scaling_enabled", None),
            }
        return {}

    async def _log_rotation_loop(self) -> None:
        """Dedicated log rotation loop with its own interval."""
        while self._running and not self._shutdown_event.is_set():
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self.config.log_rotation_interval_seconds,
                )
                break
            except TimeoutError:
                now = datetime.now(UTC)
                if (
                    self._last_log_rotation is None
                    or (now - self._last_log_rotation).total_seconds()
                    >= self.config.log_rotation_interval_seconds
                ):
                    await self._log_rotator.rotate()
                    self._stats["log_rotation"] = self._log_rotator.get_stats()
                    self._last_log_rotation = now

    async def _db_maintenance_loop(self) -> None:
        """Dedicated DB maintenance loop with its own interval."""
        while self._running and not self._shutdown_event.is_set():
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self.config.db_maintenance_interval_seconds,
                )
                break
            except TimeoutError:
                now = datetime.now(UTC)
                if (
                    self._last_db_maintenance is None
                    or (now - self._last_db_maintenance).total_seconds()
                    >= self.config.db_maintenance_interval_seconds
                ):
                    await self._db_maintenance.run_maintenance()
                    self._stats["db_maintenance"] = self._db_maintenance.get_stats()
                    self._last_db_maintenance = now

    async def _drift_loop(self) -> None:
        """Dedicated config drift detection loop with its own interval."""
        while self._running and not self._shutdown_event.is_set():
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self.config.config_drift_interval_seconds,
                )
                break
            except TimeoutError:
                now = datetime.now(UTC)
                if (
                    self._last_drift_check is None
                    or (now - self._last_drift_check).total_seconds()
                    >= self.config.config_drift_interval_seconds
                ):
                    result = await self._drift_detector.detect_drift(self._get_runtime_config())
                    self._stats["last_drift_result"] = result
self._last_drift_check = now

    async def _deployment_loop(self) -> None:
        """Dedicated deployment pipeline loop (6h interval)."""
        interval = self.config.deployment.interval_seconds
        if interval <= 0:
            return
        while self._running and not self._shutdown_event.is_set():
            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=interval)
                break
            except TimeoutError:
                result = await self._deployment.run_once()
                self._stats["last_deployment"] = result

    async def store_current_as_baseline(self, config_name: str = "runtime") -> str:
        """
        Store the current runtime configuration as the baseline.

        Args:
            config_name: Name for the baseline

        Returns:
            Path where baseline was stored
        """
        return self._drift_detector.store_baseline(self._get_runtime_config(), config_name)

    def get_status(self) -> dict[str, Any]:
        """
        Get current maintenance scheduler status.

        Returns:
            Status dictionary with enabled, running, stats
        """
        return {
            "enabled": self.config.enabled,
            "running": self._running,
            "loops_run": self._stats["loops_run"],
            "log_rotation_stats": self._stats["log_rotation"],
            "db_maintenance_stats": self._stats["db_maintenance"],
            "last_drift_result": self._stats["last_drift_result"],
            "last_deployment": self._stats.get("last_deployment"),
            "integration": ("autonomous_runtime" if self.runtime_ref is not None else "standalone"),
        }

    # Convenience accessors for individual components
    @property
    def log_rotator(self) -> LogRotator:
        """Access the log rotator."""
        return self._log_rotator

    @property
    def db_maintenance(self) -> DatabaseMaintenance:
        """Access the database maintenance runner."""
        return self._db_maintenance

    @property
    def drift_detector(self) -> ConfigDriftDetector:
        """Access the config drift detector."""
        return self._drift_detector
