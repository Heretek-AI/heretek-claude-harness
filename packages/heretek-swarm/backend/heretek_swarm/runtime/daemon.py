"""
Daemon module — PID file, Unix socket IPC, signal handling, and cleanup for
the Heretek Swarm background daemon.

Architecture
────────────
The daemon self-daemonises with a double-fork pattern (``os.fork()`` /
``os.setsid()``) to fully detach from the controlling terminal.  It writes a
PID file atomically (``O_CREAT | O_EXCL``) to prevent races, and opens a Unix
socket at a known path so the ``status`` command can query agent health
without hitting the HTTP API.

Windows is explicitly rejected — ``os.fork()`` is not available there, and the
daemon pattern assumes Unix PID semantics.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import signal
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# DaemonError — explicit exception for daemon lifecycle failures
# ---------------------------------------------------------------------------


class DaemonError(Exception):
    """Signals a fatal daemon lifecycle error that the CLI boundary must handle.

    Library code must never call ``sys.exit()`` directly — it crashes the
    calling process with no chance for cleanup.  Every fatal daemon error
    raises ``DaemonError`` so the CLI entry point (``cli.py``) can catch it,
    log it, and exit cleanly.
    """


# ---------------------------------------------------------------------------
# Constants — keep these central so both daemon.py and cli.py share them
# ---------------------------------------------------------------------------

DEFAULT_PID_FILE = Path("/var/run/heretek-swarm.pid")
DEFAULT_SOCKET_PATH = Path("/tmp/heretek-swarm.sock")


# ---------------------------------------------------------------------------
# DaemonContext
# ---------------------------------------------------------------------------


@dataclass
class DaemonContext:
    """Holds the paths and swarm reference needed by the daemon lifecycle.

    Attributes:
        pid_file:  Path to the PID file (default ``/var/run/heretek-swarm.pid``).
        socket_path:  Path to the Unix socket (default ``/tmp/heretek-swarm.sock``).
        swarm:  Optional reference to the running ``AutonomousSwarm`` instance
                so the IPC handler can answer status queries.
    """

    pid_file: Path = DEFAULT_PID_FILE
    socket_path: Path = DEFAULT_SOCKET_PATH
    swarm: Any | None = None  # AutonomousSwarm, typed as Any to avoid circular imports
    _server: asyncio.AbstractServer | None = field(default=None, repr=False, compare=False)


# ---------------------------------------------------------------------------
# Core daemonisation
# ---------------------------------------------------------------------------


def daemonize(swarm: Any, pid_file: Path | None = None, socket_path: Path | None = None) -> None:
    """Daemonize the current process: fork, setsid, write PID, bind socket.

    This function **prints** progress messages to stdout before the parent
    fork exits — the child inherits no stdout connection to the terminal.

    Args:
        swarm: Initialised ``AutonomousSwarm`` instance.
        pid_file: Path for the PID file (default ``DEFAULT_PID_FILE``).
        socket_path: Path for the Unix socket (default ``DEFAULT_SOCKET_PATH``).

    Raises:
        DaemonError: On fork OSError, PID conflict, socket bind failure,
                     or swarm initialization failure.
                     Never returns in the parent fork processes.
    """
    # --- Windows guard --------------------------------------------------------
    # Pre-bootstrap — no logger available, must exit
    if sys.platform == "win32":
        sys.exit(1)

    pid_file = pid_file or DEFAULT_PID_FILE
    socket_path = socket_path or DEFAULT_SOCKET_PATH

    ctx = DaemonContext(pid_file=pid_file, socket_path=socket_path, swarm=swarm)

    # --- First fork: detach from terminal ------------------------------------
    try:
        pid = os.fork()
    except OSError:
        raise DaemonError("First fork failed — cannot detach from terminal") from None

    if pid > 0:
        # Fork parent — no atexit handlers, no stdio flush
        os._exit(0)

    # --- Child continues ------------------------------------------------------
    # Become session leader (no controlling terminal).
    os.setsid()

    # Second fork to ensure the daemon cannot re-acquire a controlling terminal.
    try:
        pid2 = os.fork()
    except OSError:
        raise DaemonError("Second fork failed — cannot guarantee terminal detachment") from None

    if pid2 > 0:
        # Fork parent — no atexit handlers, no stdio flush
        os._exit(0)

    # --- Grandchild is the daemon process -------------------------------------
    _write_pid_file(pid_file)
    _clean_stale_socket(socket_path)

    # The socket is created INSIDE the event loop below, not here.
    # Set up fresh asyncio loop and run the swarm.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(_run_daemon_loop(ctx))
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _write_pid_file(pid_file: Path) -> None:
    """Atomically write the current PID to *pid_file*.

    Uses ``os.open()`` with ``O_CREAT | O_EXCL`` so that a race between two
    daemon instances is safely detected.
    """
    pid_dir = pid_file.parent
    pid_dir.mkdir(parents=True, exist_ok=True)

    try:
        fd = os.open(
            str(pid_file),
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o644,
        )
        with os.fdopen(fd, "w") as f:
            f.write(str(os.getpid()))
    except FileExistsError:
        # Another daemon appears to be running — check if it's alive.
        existing = read_pid_file(pid_file)
        if existing is not None and _is_pid_alive(existing):
            raise DaemonError(
                f"PID file {pid_file} exists with active PID {existing} - "
                "another daemon is already running"
            ) from None
        # Stale PID — overwrite.
        pid_file.write_text(str(os.getpid()))
    logger.info("pid_file_written", path=str(pid_file), pid=os.getpid())


def _is_pid_alive(pid: int) -> bool:
    """Return ``True`` if *pid* refers to a running process."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _clean_stale_socket(socket_path: Path) -> None:
    """Remove a stale socket file if present.

    TOCTOU-safe approach: unlink immediately before bind, not before this call.
    This function is a pre-unlink to ensure no leftover socket blocks bind().
    """
    socket_path.unlink(missing_ok=True)


def read_pid_file(pid_file: Path) -> int | None:
    """Read and return the PID from *pid_file*, or ``None`` if missing/invalid."""
    try:
        raw = pid_file.read_text().strip()
        return int(raw)
    except (FileNotFoundError, ValueError, OSError):
        return None


def send_stop(pid: int) -> bool:
    """Send ``SIGTERM`` to *pid*.

    Returns ``True`` if the signal was sent successfully.
    """
    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except ProcessLookupError:
        # Process already gone.
        return False
    except PermissionError:
        logger.warning("send_stop_permission_denied", pid=pid)
        return False


def cleanup_daemon(pid_file: Path, socket_path: Path) -> None:
    """Remove PID file and socket file.  Called during graceful shutdown."""
    try:
        pid_file.unlink(missing_ok=True)
        logger.info("pid_file_removed", path=str(pid_file))
    except OSError as exc:
        logger.warning("pid_file_removal_failed", path=str(pid_file), error=str(exc))

    try:
        socket_path.unlink(missing_ok=True)
        logger.info("socket_removed", path=str(socket_path))
    except OSError as exc:
        logger.warning("socket_removal_failed", path=str(socket_path), error=str(exc))


# ---------------------------------------------------------------------------
# Async daemon loop
# ---------------------------------------------------------------------------


async def _run_daemon_loop(ctx: DaemonContext) -> None:
    """Run the swarm inside the daemon process with socket IPC and signal
    handling.

    This is the top-level coroutine passed to ``loop.run_until_complete()``.
    """

    swarm = ctx.swarm
    pid_file = ctx.pid_file
    socket_path = ctx.socket_path

    logger.info("daemon_starting", pid=os.getpid(), socket_path=str(socket_path))

    # --- Register signal handlers --------------------------------------------
    shutdown_event = asyncio.Event()

    def _handle_shutdown_signal() -> None:
        logger.info("daemon_shutdown_signal_received")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, _handle_shutdown_signal)
    loop.add_signal_handler(signal.SIGINT, _handle_shutdown_signal)

    # --- Create Unix socket server -------------------------------------------
    socket_path.unlink(missing_ok=True)

    async def _client_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await handle_daemon_connection(reader, writer, swarm)
        if not writer.is_closing():
            writer.close()
            await writer.wait_closed()

    try:
        server = await asyncio.start_unix_server(_client_handler, path=str(socket_path))
        ctx._server = server
        # Make socket accessible to other processes (umask may restrict this).
        os.chmod(str(socket_path), 0o666)

        logger.info(
            "daemon_socket_listening",
            path=str(socket_path),
        )
    except OSError as exc:
        logger.error("daemon_socket_bind_failed", error=str(exc))
        cleanup_daemon(pid_file, socket_path)
        raise DaemonError(f"Unix socket bind at {socket_path} failed: {exc}") from exc

    # --- Initialise and run the swarm ----------------------------------------
    try:
        await swarm.initialize()
        logger.info("daemon_swarm_initialized")
    except Exception as exc:
        logger.error("daemon_swarm_initialize_failed", error=str(exc))
        cleanup_daemon(pid_file, socket_path)
        raise DaemonError(f"Swarm initialization failed: {exc}") from exc

    # Run the swarm run() in a background task so we can also wait for shutdown.
    swarm_task = asyncio.create_task(swarm.run())

    # Use the asyncio shutdown event instead of signal.getsignal
    # (loop.add_signal_handler already wired the event).
    await shutdown_event.wait()

    logger.info("daemon_shutting_down")

    # --- Graceful shutdown ---------------------------------------------------
    swarm_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await swarm_task

    # Stop the swarm (calls terminate_all, disconnect event mesh, etc.)
    try:
        await swarm.shutdown()
    except Exception as exc:
        logger.error("daemon_swarm_shutdown_error", error=str(exc))

    # Close the socket server.
    server.close()
    await server.wait_closed()

    # Clean up files.
    cleanup_daemon(pid_file, socket_path)
    logger.info("daemon_shutdown_complete")


# ---------------------------------------------------------------------------
# Unix socket IPC handler
# ---------------------------------------------------------------------------


async def handle_daemon_connection(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    swarm: Any,
) -> None:
    """Handle a single Unix socket connection from the status CLI command.

    Protocol
    --------
    The client sends a single JSON line (``\\n``-terminated).  The server
    parses the ``type`` field and responds with a JSON object on one line.

    Supported queries
    -----------------
    ``{"type": "status"}``
        Returns agent status information from ``swarm.supervisor.get_all_status()``.
    """
    peer = writer.get_extra_info("peername", "unknown")
    try:
        raw = await asyncio.wait_for(reader.readline(), timeout=10.0)
    except TimeoutError:
        logger.warning("daemon_socket_read_timeout", peer=peer)
        return
    except ConnectionResetError:
        logger.warning("daemon_socket_connection_reset", peer=peer)
        return

    if not raw:
        return

    try:
        query = json.loads(raw.decode("utf-8").strip())
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("daemon_socket_invalid_json", peer=peer, error=str(exc))
        response = {"error": f"Invalid JSON: {exc}"}
        _write_json_line(writer, response)
        return

    query_type = query.get("type")

    if query_type == "status":
        response = _build_status_response(swarm)
    else:
        response = {"error": f"Unknown query type: {query_type}"}

    _write_json_line(writer, response)


def _build_status_response(swarm: Any) -> dict[str, Any]:
    """Build the status response dict from swarm supervisor state.

    Returns a dict with an ``"agents"`` list, each containing:
    ``agent_id``, ``state``, ``mailbox_size``, ``message_count``,
    ``last_activity``, ``error_count``.

    Also includes a ``"consciousness"`` dict with live IIT Phi / FEP
    metrics read from the ``prometheus_native`` gauges (populated by
    the in-house :class:`PhiCalculator` / :class:`FreeEnergyCalculator`
    via ``record_phi_score`` / ``record_free_energy``). On collection
    failure, the field is an empty dict and a structured
    ``consciousness_collection_failed`` warning is emitted.
    """
    if swarm is None or swarm.supervisor is None:
        return {"agents": [], "error": "Swarm supervisor not available"}

    try:
        all_status = swarm.supervisor.get_all_status()
    except Exception as exc:
        logger.warning("daemon_get_all_status_failed", error=str(exc))
        return {"agents": [], "error": str(exc)}

    agents = []
    for agent_id, status in all_status.items():
        agents.append(
            {
                "agent_id": agent_id,
                "state": status.state.value
                if hasattr(status.state, "value")
                else str(status.state),
                "mailbox_size": status.mailbox_size,
                "message_count": status.message_count,
                "last_activity": status.last_activity or "",
                "error_count": status.error_count,
            }
        )

    response: dict[str, Any] = {"agents": agents}

    # --- Collect consciousness metrics (IIT Phi + FEP) ---------------------
    # Phase 2A.3 cutover: read per-agent phi / free-energy values from
    # the ``prometheus_native`` gauges (populated by the in-house
    # :class:`PhiCalculator` / :class:`FreeEnergyCalculator` via
    # ``record_phi_score`` / ``record_free_energy``) and compute the
    # same aggregates the legacy ``SwarmMetricsCollector`` did. The
    # ``observability/metrics.py`` module is deleted in commit 9.
    try:
        from heretek_swarm.observability.prometheus_native import (
            FREE_ENERGY,
            PHI_SCORE,
            read_metric_samples,
        )

        phi_samples = read_metric_samples(PHI_SCORE)
        if not phi_samples:
            response["consciousness"] = {}
            return response
        phi_values = list(phi_samples.values())
        phi_avg = sum(phi_values) / len(phi_values)
        phi_max = max(phi_values)
        phi_min = min(phi_values)

        if phi_avg >= 0.9:
            integration_level = "very_high"
        elif phi_avg >= 0.75:
            integration_level = "high"
        elif phi_avg >= 0.5:
            integration_level = "moderate"
        elif phi_avg >= 0.25:
            integration_level = "low"
        else:
            integration_level = "minimal"
        if len(phi_values) < 2:
            differentiation_level = "minimal"
        else:
            std_dev = (
                sum((x - phi_avg) ** 2 for x in phi_values) / len(phi_values)
            ) ** 0.5
            if std_dev > 0.3:
                differentiation_level = "high"
            elif std_dev > 0.2:
                differentiation_level = "moderate"
            elif std_dev > 0.1:
                differentiation_level = "low"
            else:
                differentiation_level = "minimal"

        fep_samples = read_metric_samples(FREE_ENERGY)
        fep_values = list(fep_samples.values()) if fep_samples else []
        fep_avg = sum(fep_values) / len(fep_values) if fep_values else 0.0
        fep_variance = (
            sum((x - fep_avg) ** 2 for x in fep_values) / len(fep_values)
            if fep_values
            else 0.0
        )

        response["consciousness"] = {
            "phi_avg": phi_avg,
            "phi_max": phi_max,
            "phi_min": phi_min,
            "integration_level": integration_level,
            "differentiation_level": differentiation_level,
            "free_energy_avg": fep_avg,
            "free_energy_variance": fep_variance,
            "agent_phi_scores": dict(
                sorted(phi_samples.items(), key=lambda kv: kv[1], reverse=True)[:5]
            ),
            "agent_fep_scores": dict(
                sorted(fep_samples.items(), key=lambda kv: kv[1], reverse=True)[:5]
            ),
        }
    except Exception as exc:
        logger.warning("consciousness_collection_failed", error=str(exc))
        response["consciousness"] = {}

    return response


def _write_json_line(writer: asyncio.StreamWriter, data: dict[str, Any]) -> None:
    """Encode *data* as JSON, write it to *writer*, and drain."""
    try:
        line = json.dumps(data, default=str) + "\n"
        writer.write(line.encode("utf-8"))
    except Exception as exc:
        logger.warning("daemon_socket_write_error", error=str(exc))
