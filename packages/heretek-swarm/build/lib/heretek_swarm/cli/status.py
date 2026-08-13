"""
``status`` command — check Heretek Swarm health (daemon or API).
"""

from __future__ import annotations

import asyncio
import json as json_mod
import sys
import time
from typing import Any

import click
import httpx
import structlog

from heretek_swarm.cli.health import _check_service_health
from heretek_swarm.config.models import InfrastructureService
import datetime as _dt

logger = structlog.get_logger("cli.status")

DEFAULT_API_BASE = "http://localhost:8000"


# ---------------------------------------------------------------------------
# Daemon socket helpers
# ---------------------------------------------------------------------------


def _query_daemon_socket() -> dict | None:
    """Connect to the daemon's Unix socket and send a status query.

    Returns the parsed JSON response dict, or ``None`` if the socket is
    unreachable or the exchange fails.
    """
    import json
    import socket as sock_mod

    from heretek_swarm.runtime.daemon import DEFAULT_SOCKET_PATH

    socket_path = DEFAULT_SOCKET_PATH
    if not socket_path.exists():
        return None

    try:
        s = sock_mod.socket(sock_mod.AF_UNIX, sock_mod.SOCK_STREAM)
        s.settimeout(5.0)
        s.connect(str(socket_path))
        s.sendall(json.dumps({"type": "status"}).encode("utf-8") + b"\n")

        data = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\n" in data:
                break
        s.close()

        return json.loads(data.decode("utf-8").strip())
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("daemon_socket_query_failed", error=str(exc))
        return None


def _display_daemon_status(agent_data: dict, pid: int, output_json: bool) -> None:
    """Print agent status from the daemon to stdout."""
    import json

    agents = agent_data.get("agents", [])
    consciousness = agent_data.get("consciousness", {})

    if output_json:
        result: dict[str, Any] = {
            "daemon_pid": pid,
            "agents": agents,
            "agent_count": len(agents),
        }
        if consciousness:
            result["consciousness"] = consciousness
        click.echo(json.dumps(result))
        return

    click.echo("Heretek Swarm Status (daemon)")
    click.echo("=" * 40)
    click.echo(f"  Daemon PID: {pid}")
    click.echo("")

    if not agents:
        click.echo("  No agent data available from daemon.")
        return

    id_w = max(max(len(a.get("agent_id", "")) for a in agents) + 2, 12)
    state_w = 12
    mb_w = 8
    msg_w = 10
    err_w = 6

    header = (
        f"  {'Agent ID':<{id_w}} {'State':<{state_w}} "
        f"{'Mailbox':<{mb_w}} {'Messages':<{msg_w}} {'Errors':<{err_w}} Last Activity"
    )
    click.echo(header)
    click.echo("  " + "-" * len(header))

    for a in agents:
        aid = a.get("agent_id", "?")
        state = a.get("state", "?")
        mb = a.get("mailbox_size", 0)
        msgs = a.get("message_count", 0)
        errs = a.get("error_count", 0)
        last_act = a.get("last_activity", "")
        click.echo(
            f"  {aid:<{id_w}} {state:<{state_w}} "
            f"{mb:<{mb_w}} {msgs:<{msg_w}} {errs:<{err_w}} {last_act}"
        )

    click.echo("")
    click.echo(f"  ✓ {len(agents)} agent(s) running")

    # --- Consciousness Metrics section (human-readable) --------------------
    if consciousness and consciousness.get("phi_avg", 0) > 0:
        click.echo("")
        click.echo("Consciousness Metrics:")
        click.echo("-" * 30)
        click.echo(f"  Phi (avg/max/min): "
                   f"{consciousness['phi_avg']:.3f} / "
                   f"{consciousness['phi_max']:.3f} / "
                   f"{consciousness['phi_min']:.3f}")
        click.echo(f"  Integration:       {consciousness['integration_level']:.3f}")
        click.echo(f"  Differentiation:   {consciousness['differentiation_level']:.3f}")
        click.echo(f"  Free Energy (avg): {consciousness['free_energy_avg']:.3f}")
        click.echo(f"  Free Energy (var): {consciousness['free_energy_variance']:.3f}")


# ---------------------------------------------------------------------------
# Click command
# ---------------------------------------------------------------------------


@click.command()
@click.option("--api-base", default=DEFAULT_API_BASE, help="API base URL")
@click.option("--timeout", default=30, type=int, help="Health check timeout in seconds")
@click.option("--json", "output_json", is_flag=True, help="Output results as JSON")
def status(api_base: str, timeout: int, output_json: bool) -> None:
    """
    Check Heretek Swarm status.

    If the background daemon is running, queries it via the Unix socket
    for agent status.  Otherwise falls back to fetching infrastructure
    configuration from the HTTP API and performing health checks.
    """
    logger.info("status_command", api_base=api_base, timeout=timeout)

    from heretek_swarm.runtime.daemon import DEFAULT_PID_FILE, read_pid_file

    pid = read_pid_file(DEFAULT_PID_FILE)
    if pid is not None:
        agent_data = _query_daemon_socket()
        if agent_data is not None:
            _display_daemon_status(agent_data, pid, output_json)
            return

    _run_api_fallback(api_base, timeout, output_json)


def _run_api_fallback(api_base: str, timeout: int, output_json: bool) -> None:
    """Fallback: API-based health check."""
    if not output_json:
        click.echo("Heretek Swarm Status")
        click.echo("=" * 40)

    start_time = time.perf_counter()

    if not output_json:
        click.echo(f"\nFetching infrastructure configuration from {api_base}...")

    data = _fetch_infrastructure(api_base, output_json)
    configs = data.get("infrastructure", [])

    if not configs:
        _handle_no_configs(output_json, start_time)
        return

    if not output_json:
        click.echo(f"  Found {len(configs)} configured service(s)")
        click.echo("\nPerforming health checks...")

    results = asyncio.run(_run_health_checks_async(configs, timeout))
    healthy_count = sum(1 for r in results if r.get("status") == "healthy")
    unhealthy_count = sum(1 for r in results if r.get("status") == "unhealthy")
    unknown_count = sum(1 for r in results if r.get("status") not in ("healthy", "unhealthy"))

    if output_json:
        _output_json_status(results, healthy_count, unhealthy_count, unknown_count, start_time)
        sys.exit(1 if unhealthy_count > 0 else 0)

    _output_human_status(results, healthy_count, unhealthy_count, unknown_count, start_time)


def _fetch_infrastructure(api_base: str, output_json: bool) -> dict[str, Any]:
    """Fetch infrastructure config from API, exiting on failure."""
    try:
        response = httpx.get(f"{api_base}/api/wizard/infrastructure", timeout=5.0)
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        if output_json:
            click.echo(json_mod.dumps({"error": f"Cannot connect to API server at {api_base}"}))
            sys.exit(2)
        click.echo("  ✗ Cannot connect to API server")
        click.echo("  No running daemon or API server found")
        sys.exit(1)
    except httpx.HTTPError as e:
        if output_json:
            click.echo(json_mod.dumps({"error": f"API error: {e}"}))
            sys.exit(2)
        click.echo(f"  ✗ API error: {e}")
        sys.exit(1)


def _handle_no_configs(output_json: bool, start_time: float) -> None:
    """Handle case where no infrastructure services are configured."""
    if output_json:
        result = {
            "services": [],
            "summary": {
                "total": 0, "healthy": 0, "unhealthy": 0, "unknown": 0,
                "duration_ms": round((time.perf_counter() - start_time) * 1000, 1),
            },
            "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        click.echo(json_mod.dumps(result))
        sys.exit(0)
    click.echo("  ⚠ No infrastructure services configured")
    click.echo("\nRun 'heretek-swarm deploy' or use the wizard to configure services.")
    sys.exit(0)


async def _run_health_checks_async(
    configs: list[dict[str, Any]], timeout: int
) -> list[dict[str, Any]]:
    """Run health checks for all configured services."""
    checks = []
    for c in configs:
        service_str = c.get("service")
        try:
            svc = InfrastructureService(service_str)
        except ValueError:
            click.echo(f"  ⚠ Unknown service: {service_str}")
            continue
        checks.append(
            _check_service_health(
                service=svc, host=c.get("host", "localhost"),
                port=c.get("port", 0), timeout=float(timeout),
            )
        )
    return await asyncio.gather(*checks)


def _output_json_status(
    results: list[dict[str, Any]], healthy: int, unhealthy: int, unknown: int, start_time: float
) -> None:
    """Output status as JSON."""
    total_time_ms = (time.perf_counter() - start_time) * 1000
    result: dict[str, Any] = {
        "services": [
            {
                "service": r.get("service", "unknown"),
                "status": r.get("status", "unknown"),
                "latency_ms": round(r.get("latency_ms", 0), 1),
                "error": r.get("error"),
            }
            for r in results
        ],
        "summary": {
            "total": len(results), "healthy": healthy,
            "unhealthy": unhealthy, "unknown": unknown,
            "duration_ms": round(total_time_ms, 1),
        },
        "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    _maybe_add_consciousness_metrics(result)
    click.echo(json_mod.dumps(result))


def _maybe_add_consciousness_metrics(result: dict[str, Any]) -> None:
    """Add consciousness metrics to result if collector has agent data."""
    try:
        from heretek_swarm.observability.metrics import get_metrics_collector
        collector = get_metrics_collector()
        if not collector.get_all_agent_metrics():
            return
        consciousness = collector.collect_consciousness_metrics()
        agent_phi = consciousness.agent_phi_scores
        top_phi = dict(sorted(agent_phi.items(), key=lambda kv: kv[1], reverse=True)[:5])
        agent_fep = consciousness.agent_fep_scores
        top_fep = dict(sorted(agent_fep.items(), key=lambda kv: kv[1], reverse=True)[:5])
        result["consciousness"] = {
            "phi_avg": consciousness.phi_avg,
            "phi_max": consciousness.phi_max,
            "phi_min": consciousness.phi_min,
            "integration_level": consciousness.integration_level,
            "differentiation_level": consciousness.differentiation_level,
            "free_energy_avg": consciousness.free_energy_avg,
            "free_energy_variance": consciousness.free_energy_variance,
            "agent_phi_scores": top_phi,
            "agent_fep_scores": top_fep,
        }
    except Exception:
        logger.warning("api_fallback_consciousness_failed", exc_info=True)


def _output_human_status(
    results: list[dict[str, Any]], healthy: int, unhealthy: int, unknown: int, start_time: float
) -> None:
    """Output status as human-readable table."""
    click.echo("\n" + "-" * 60)
    click.echo(f"{'Service':<12} {'Status':<12} {'Latency':<12} Details")
    click.echo("-" * 60)

    for r in results:
        service_val = r.get("service", "unknown")
        status_val = r.get("status", "unknown")
        latency = r.get("latency_ms", 0)
        error = r.get("error")

        icon = "✓" if status_val == "healthy" else ("✗" if status_val == "unhealthy" else "?")
        latency_str = f"{latency:.1f}ms" if latency < 1000 else f"{latency / 1000:.2f}s"
        status_display = f"{icon} {status_val.upper()}"
        click.echo(f"{service_val:<12} {status_display:<12} {latency_str:<12} {error or ''}")

        logger.info(
            "health_check_result", service=service_val, status=status_val,
            latency_ms=latency, error=error,
        )

    click.echo("-" * 60)
    total_time = time.perf_counter() - start_time
    click.echo(f"\nSummary: {healthy} healthy, {unhealthy} unhealthy, {unknown} unknown")
    click.echo(f"Total time: {total_time:.2f}s")

    if unhealthy > 0:
        click.echo("\n⚠ Some services are unhealthy. Run 'heretek-swarm deploy' for setup instructions.")
        sys.exit(1)
    elif unknown > 0:
        click.echo("\n⚠ Some services have unknown status.")
        sys.exit(1)
    else:
        click.echo("\n✓ All services healthy")
