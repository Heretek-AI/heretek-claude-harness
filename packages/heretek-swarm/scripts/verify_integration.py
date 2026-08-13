#!/usr/bin/env python3
"""Frontend <-> Backend integration verifier.

Probes a *running* Heretek Swarm stack and asserts that the React dashboard
(npm/nginx) and the FastAPI backend (docker/python) can actually talk to each
other. It is transport-only: it never needs a working LLM, so it is safe to run
against a freshly deployed stack with placeholder API keys.

Checks performed:

  1. Backend health         GET  {api}/api/health            -> 200, status key
  2. Backend liveness       GET  {api}/api/health/live        -> 200
  3. Auth required          GET  {api}/api/agents (no token)  -> 401
  4. Auth accepted          GET  {api}/api/agents (Bearer)    -> 200/2xx
  5. CORS preflight         OPTIONS {api}/api/health          -> ACAO header
  6. Dashboard served       GET  {dash}/                      -> 200, has <div id=root>
  7. Dashboard->API proxy   GET  {dash}/api/health            -> 200 (nginx -> api)
  8. Proxy redirect origin  GET  {dash}/api/agents (Bearer)   -> 2xx, or 3xx whose
                            Location stays same-origin as the dashboard

The dashboard proxy check (7) is the real production frontend->backend path and
is the highest-signal check: if the nginx proxy or path prefix is misconfigured
the browser app cannot reach the API even though the API itself is healthy.

Check (8) guards a subtler proxy failure: FastAPI 307-redirects a path that is
missing its trailing slash (e.g. /api/agents -> /api/agents/) and builds the
Location from the Host header. If nginx forwards a port-less Host the browser is
redirected to a different origin (http://localhost/ vs http://localhost:3000),
the redirect becomes opaque, and the dashboard's fetch fails even though curl
(which follows cross-origin redirects) would see a 200.

Usage:
    python scripts/verify_integration.py \
        --api-base http://localhost:8000 \
        --dashboard-base http://localhost:3000 \
        --api-key htsk_...

Environment fallbacks: API_BASE, DASHBOARD_BASE, HERETEK_API_KEY.

Exit code 0 if all required checks pass, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field

DEFAULT_API_BASE = "http://localhost:8000"
DEFAULT_DASHBOARD_BASE = "http://localhost:3000"


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    """Outcome of a single integration check."""

    name: str
    passed: bool
    detail: str
    required: bool = True


@dataclass
class Report:
    """Aggregated results of all checks."""

    results: list[CheckResult] = field(default_factory=list)

    def add(self, result: CheckResult) -> None:
        self.results.append(result)

    @property
    def ok(self) -> bool:
        """True if every *required* check passed."""
        return all(r.passed for r in self.results if r.required)

    def render(self) -> str:
        lines = []
        for r in self.results:
            icon = "PASS" if r.passed else ("FAIL" if r.required else "WARN")
            tag = "" if r.required else " (optional)"
            lines.append(f"  [{icon}] {r.name}{tag}: {r.detail}")
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        lines.append("")
        lines.append(f"  {passed}/{total} checks passed; overall: {'OK' if self.ok else 'FAILED'}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTTP helper (stdlib only — no third-party deps so it runs anywhere)
# ---------------------------------------------------------------------------


@dataclass
class HttpResponse:
    """Minimal HTTP response wrapper."""

    status: int
    body: str
    headers: dict[str, str]

    def json(self) -> object:
        return json.loads(self.body)


def _lower_headers(raw: object) -> dict[str, str]:
    """Normalise response header names to lowercase for case-insensitive lookup.

    Servers may emit header names in any case (and HTTP/2 lowercases them), so
    callers must always look up the lowercase form, e.g.
    ``headers.get("access-control-allow-origin")``.
    """
    if raw is None:
        return {}
    return {str(k).lower(): str(v) for k, v in raw.items()}


def http_request(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> HttpResponse:
    """Perform an HTTP request, returning an HttpResponse even for 4xx/5xx.

    Raises urllib.error.URLError only for transport failures (connection
    refused, DNS, timeout) — never for HTTP status codes.
    """
    req = urllib.request.Request(url, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return HttpResponse(resp.status, body, _lower_headers(resp.headers))
    except urllib.error.HTTPError as exc:  # 4xx/5xx are not failures here
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return HttpResponse(exc.code, body, _lower_headers(exc.headers))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Redirect handler that refuses to follow 3xx responses.

    Returning None from ``redirect_request`` tells urllib not to follow the
    redirect; the original 3xx is then raised as an ``HTTPError`` whose headers
    (including ``Location``) we can inspect.
    """

    def redirect_request(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None


def http_request_no_redirect(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> HttpResponse:
    """Like :func:`http_request` but never follows redirects.

    Lets callers inspect the ``Location`` header of a 3xx response instead of
    transparently following it (which is what hides cross-origin redirect bugs).
    """
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(url, method=method, headers=headers or {})
    try:
        with opener.open(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return HttpResponse(resp.status, body, _lower_headers(resp.headers))
    except urllib.error.HTTPError as exc:  # includes the 3xx we declined to follow
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return HttpResponse(exc.code, body, _lower_headers(exc.headers))


# ---------------------------------------------------------------------------
# Individual checks (each returns a CheckResult; never raises)
# ---------------------------------------------------------------------------


def _safe(fn, name: str, required: bool = True) -> CheckResult:
    """Run a check function, converting transport errors into a FAIL result."""
    try:
        result = fn()
        result.required = required
        return result
    except urllib.error.URLError as exc:
        return CheckResult(name, False, f"transport error: {exc.reason}", required)
    except Exception as exc:  # defensive: a check must never crash the whole run
        return CheckResult(name, False, f"unexpected error: {exc}", required)


def check_backend_health(api_base: str) -> CheckResult:
    name = "backend health (/api/health)"
    resp = http_request(f"{api_base}/api/health")
    if resp.status != 200:
        return CheckResult(name, False, f"expected 200, got {resp.status}")
    data = resp.json()
    status = data.get("status") if isinstance(data, dict) else None
    return CheckResult(name, True, f"200, status={status!r}, services={list((data or {}).get('services', {}))}")


def check_backend_liveness(api_base: str) -> CheckResult:
    name = "backend liveness (/api/health/live)"
    resp = http_request(f"{api_base}/api/health/live")
    ok = resp.status == 200
    return CheckResult(name, ok, f"got {resp.status}")


def check_auth_required(api_base: str) -> CheckResult:
    name = "auth required without token (/api/agents)"
    resp = http_request(f"{api_base}/api/agents")
    ok = resp.status == 401
    return CheckResult(name, ok, f"expected 401, got {resp.status}")


def check_auth_accepted(api_base: str, api_key: str) -> CheckResult:
    name = "auth accepted with Bearer token (/api/agents)"
    if not api_key:
        return CheckResult(name, False, "no API key provided")
    resp = http_request(f"{api_base}/api/agents", headers={"Authorization": f"Bearer {api_key}"})
    ok = 200 <= resp.status < 300
    return CheckResult(name, ok, f"expected 2xx, got {resp.status}")


def check_cors_preflight(api_base: str, origin: str) -> CheckResult:
    name = "CORS preflight on backend (/api/health)"
    headers = {
        "Origin": origin,
        "Access-Control-Request-Method": "GET",
    }
    resp = http_request(f"{api_base}/api/health", method="OPTIONS", headers=headers)
    acao = resp.headers.get("access-control-allow-origin")
    ok = acao is not None
    return CheckResult(name, ok, f"status={resp.status}, Access-Control-Allow-Origin={acao!r}")


def check_dashboard_served(dashboard_base: str) -> CheckResult:
    name = "dashboard served (/)"
    resp = http_request(f"{dashboard_base}/")
    if resp.status != 200:
        return CheckResult(name, False, f"expected 200, got {resp.status}")
    has_root = 'id="root"' in resp.body or "id='root'" in resp.body
    return CheckResult(name, has_root, f"200, root div present={has_root}")


def check_dashboard_api_proxy(dashboard_base: str) -> CheckResult:
    name = "dashboard -> API proxy (/api/health via dashboard)"
    resp = http_request(f"{dashboard_base}/api/health")
    if resp.status != 200:
        return CheckResult(
            name,
            False,
            f"expected 200 through nginx proxy, got {resp.status} (check nginx proxy_pass / /api prefix)",
        )
    try:
        status = resp.json().get("status") if isinstance(resp.json(), dict) else None
    except Exception:
        status = None
    return CheckResult(name, True, f"200 through proxy, status={status!r}")


def _same_origin(location: str, base: str) -> bool:
    """True if a redirect Location stays on the same origin as ``base``.

    Relative Locations ("/api/agents/") are always same-origin. Absolute ones
    must share scheme+host+port with the dashboard base, otherwise the browser
    treats the redirect as cross-origin (opaque) and the fetch fails.
    """
    if location.startswith("/") and not location.startswith("//"):
        return True
    from urllib.parse import urlsplit

    loc = urlsplit(location)
    ref = urlsplit(base)
    return (loc.scheme, loc.hostname, loc.port) == (ref.scheme, ref.hostname, ref.port)


def check_dashboard_proxy_redirect_same_origin(dashboard_base: str, api_key: str) -> CheckResult:
    name = "dashboard -> API proxy keeps redirects same-origin (/api/agents)"
    if not api_key:
        return CheckResult(name, False, "no API key provided")
    resp = http_request_no_redirect(
        f"{dashboard_base}/api/agents", headers={"Authorization": f"Bearer {api_key}"}
    )
    if 200 <= resp.status < 300:
        return CheckResult(name, True, f"{resp.status} (no redirect needed)")
    if 300 <= resp.status < 400:
        loc = resp.headers.get("location", "")
        ok = _same_origin(loc, dashboard_base)
        if ok:
            detail = f"{resp.status} -> Location={loc!r}; same-origin as {dashboard_base}"
        else:
            detail = (
                f"{resp.status} -> Location={loc!r}; CROSS-ORIGIN vs {dashboard_base} "
                "(port-less proxy Host header breaks the browser fetch)"
            )
        return CheckResult(name, ok, detail)
    return CheckResult(name, False, f"unexpected status {resp.status} (expected 2xx or same-origin 3xx)")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_checks(
    api_base: str,
    dashboard_base: str,
    api_key: str,
    check_dashboard: bool = True,
) -> Report:
    """Run all integration checks and return an aggregated Report."""
    origin = dashboard_base
    report = Report()
    report.add(_safe(lambda: check_backend_health(api_base), "backend health (/api/health)"))
    report.add(_safe(lambda: check_backend_liveness(api_base), "backend liveness (/api/health/live)"))
    report.add(_safe(lambda: check_auth_required(api_base), "auth required without token (/api/agents)"))
    report.add(_safe(lambda: check_auth_accepted(api_base, api_key), "auth accepted with Bearer token (/api/agents)"))
    report.add(
        _safe(lambda: check_cors_preflight(api_base, origin), "CORS preflight on backend (/api/health)", required=False)
    )
    if check_dashboard:
        report.add(_safe(lambda: check_dashboard_served(dashboard_base), "dashboard served (/)"))
        report.add(
            _safe(
                lambda: check_dashboard_api_proxy(dashboard_base),
                "dashboard -> API proxy (/api/health via dashboard)",
            )
        )
        report.add(
            _safe(
                lambda: check_dashboard_proxy_redirect_same_origin(dashboard_base, api_key),
                "dashboard -> API proxy keeps redirects same-origin (/api/agents)",
            )
        )
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify frontend <-> backend communication")
    parser.add_argument("--api-base", default=os.environ.get("API_BASE", DEFAULT_API_BASE))
    parser.add_argument("--dashboard-base", default=os.environ.get("DASHBOARD_BASE", DEFAULT_DASHBOARD_BASE))
    parser.add_argument("--api-key", default=os.environ.get("HERETEK_API_KEY", ""))
    parser.add_argument(
        "--no-dashboard",
        action="store_true",
        help="Skip dashboard checks (backend-only verification)",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_checks(
        api_base=args.api_base.rstrip("/"),
        dashboard_base=args.dashboard_base.rstrip("/"),
        api_key=args.api_key,
        check_dashboard=not args.no_dashboard,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "ok": report.ok,
                    "checks": [
                        {"name": r.name, "passed": r.passed, "detail": r.detail, "required": r.required}
                        for r in report.results
                    ],
                },
                indent=2,
            )
        )
    else:
        print("Frontend <-> Backend integration verification")
        print(f"  api-base       = {args.api_base}")
        print(f"  dashboard-base = {args.dashboard_base}")
        print("")
        print(report.render())
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
