"""Black-box smoke tests for a running Stage 1 Compose stack."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import urlsplit

import pytest

RUN_STACK_TESTS = os.getenv("CYBERSENTINEL_RUN_STACK_TESTS") == "1"
EXPECT_DATABASE_UNAVAILABLE = (
    os.getenv("CYBERSENTINEL_EXPECT_DATABASE_UNAVAILABLE") == "1"
)
FRONTEND_URL = os.getenv("CYBERSENTINEL_FRONTEND_URL", "http://127.0.0.1:3000")
BACKEND_URL = os.getenv("CYBERSENTINEL_BACKEND_URL", "http://127.0.0.1:8000")
PROJECT_ROOT = Path(__file__).resolve().parents[2]

SECURITY_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
    "content-security-policy": (
        "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; "
        "form-action 'self'; object-src 'none'; connect-src 'self'; "
        "img-src 'self' data:; font-src 'self'; style-src 'self'; script-src 'self'"
    ),
}

pytestmark = pytest.mark.skipif(
    not RUN_STACK_TESTS,
    reason="set CYBERSENTINEL_RUN_STACK_TESTS=1 for a running Compose stack",
)

requires_healthy_database = pytest.mark.skipif(
    EXPECT_DATABASE_UNAVAILABLE,
    reason="this check requires PostgreSQL to be available",
)
requires_database_outage = pytest.mark.skipif(
    not EXPECT_DATABASE_UNAVAILABLE,
    reason=(
        "stop PostgreSQL and set CYBERSENTINEL_EXPECT_DATABASE_UNAVAILABLE=1 "
        "to run the outage contract"
    ),
)


@dataclass(frozen=True)
class HttpResponse:
    status: int
    content_type: str
    headers: dict[str, str]
    body: bytes


def fetch(url: str, method: str = "GET") -> HttpResponse:
    """Fetch a local stack endpoint with a bounded timeout."""

    parsed = urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Stack smoke tests only allow local HTTP endpoints")

    connection = HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    target = parsed.path or "/"
    if parsed.query:
        target = f"{target}?{parsed.query}"

    try:
        connection.request(method, target, headers={"Accept": "application/json, text/html"})
        response = connection.getresponse()
        return HttpResponse(
            status=response.status,
            content_type=response.headers.get_content_type(),
            headers={name.lower(): value for name, value in response.getheaders()},
            body=response.read(),
        )
    finally:
        connection.close()


def run_local_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a bounded, read-only local command and surface infrastructure errors."""

    try:
        result = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        pytest.fail(f"required local command is unavailable: {command[0]}")
    except subprocess.TimeoutExpired:
        pytest.fail(f"local command timed out: {' '.join(command)}")

    if result.returncode != 0:
        pytest.fail(
            f"local command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout: {result.stdout.strip()}\nstderr: {result.stderr.strip()}"
        )

    return result


def find_docker_command() -> str:
    """Resolve one Docker executable without invoking a command shell."""

    configured_command = os.getenv("CYBERSENTINEL_DOCKER_COMMAND")
    if configured_command:
        configured_path = shutil.which(configured_command)
        if configured_path is None:
            pytest.fail(
                "CYBERSENTINEL_DOCKER_COMMAND does not resolve to a Docker executable"
            )
        return configured_path

    path_command = shutil.which("docker")
    if path_command is not None:
        return path_command

    local_app_data = os.getenv("LOCALAPPDATA")
    if os.name == "nt" and local_app_data:
        docker_desktop_command = (
            Path(local_app_data)
            / "Programs"
            / "DockerDesktop"
            / "resources"
            / "bin"
            / "docker.exe"
        )
        if docker_desktop_command.is_file():
            return str(docker_desktop_command.resolve())

    pytest.fail(
        "Docker CLI was not found in PATH, CYBERSENTINEL_DOCKER_COMMAND, "
        "or the standard per-user Docker Desktop installation"
    )


def test_frontend_serves_built_application() -> None:
    response = fetch(FRONTEND_URL)

    assert response.status == 200
    assert response.content_type == "text/html"
    assert b'<div id="root"></div>' in response.body


@pytest.mark.parametrize(
    ("path", "expected_status"),
    [
        ("/api/health/live", "ok"),
        ("/api/health/ready", "ready"),
    ],
)
@pytest.mark.parametrize(
    "base_url",
    [BACKEND_URL, FRONTEND_URL],
    ids=["direct-backend", "frontend-proxy"],
)
@requires_healthy_database
def test_health_contract(base_url: str, path: str, expected_status: str) -> None:
    response = fetch(f"{base_url}{path}")
    payload = json.loads(response.body)

    assert response.status == 200
    assert response.content_type == "application/json"
    assert payload == {"status": expected_status, "version": "0.1.0"}


@pytest.mark.parametrize(
    "base_url",
    [BACKEND_URL, FRONTEND_URL],
    ids=["direct-backend", "frontend-proxy"],
)
@requires_database_outage
def test_database_outage_preserves_liveness_and_sanitizes_readiness(
    base_url: str,
) -> None:
    live_response = fetch(f"{base_url}/api/health/live")
    ready_response = fetch(f"{base_url}/api/health/ready")

    assert live_response.status == 200
    assert live_response.content_type == "application/json"
    assert json.loads(live_response.body) == {"status": "ok", "version": "0.1.0"}

    assert ready_response.status == 503
    assert ready_response.content_type == "application/json"
    assert ready_response.headers.get("retry-after") == "5"
    assert json.loads(ready_response.body) == {"detail": "Service is not ready"}

    sanitized_body = ready_response.body.lower()
    for forbidden_fragment in (
        b"traceback",
        b"sqlalchemy",
        b"asyncpg",
        b"postgresql",
        b"postgres:5432",
        b"password",
    ):
        assert forbidden_fragment not in sanitized_body


@pytest.mark.parametrize("path", ["/api/health/live", "/api/health/ready"])
@pytest.mark.parametrize(
    "base_url",
    [BACKEND_URL, FRONTEND_URL],
    ids=["direct-backend", "frontend-proxy"],
)
def test_health_endpoints_reject_unsupported_methods(base_url: str, path: str) -> None:
    response = fetch(f"{base_url}{path}", method="POST")

    assert response.status == 405
    assert response.content_type == "application/json"
    assert response.headers.get("allow") == "GET"
    assert json.loads(response.body) == {"detail": "Method Not Allowed"}


@pytest.mark.parametrize(
    "base_url",
    [BACKEND_URL, FRONTEND_URL],
    ids=["direct-backend", "frontend-proxy"],
)
def test_unknown_api_route_returns_json_404(base_url: str) -> None:
    response = fetch(f"{base_url}/api/route-that-does-not-exist")

    assert response.status == 404
    assert response.content_type == "application/json"
    assert json.loads(response.body) == {"detail": "Not Found"}


@pytest.mark.parametrize(
    ("path", "expected_status"),
    [
        ("/", 200),
        ("/api/health/live", 200),
        ("/api/route-that-does-not-exist", 404),
    ],
)
def test_nginx_adds_security_headers_to_all_response_classes(
    path: str,
    expected_status: int,
) -> None:
    response = fetch(f"{FRONTEND_URL}{path}")

    assert response.status == expected_status
    for header_name, expected_value in SECURITY_HEADERS.items():
        assert response.headers.get(header_name) == expected_value

    server_header = response.headers.get("server")
    assert server_header is None or "/" not in server_header


@requires_healthy_database
def test_postgres_has_no_published_host_port() -> None:
    docker_command = find_docker_command()
    compose_result = run_local_command(
        [docker_command, "compose", "ps", "--all", "--quiet", "postgres"]
    )
    container_ids = [line for line in compose_result.stdout.splitlines() if line]
    assert len(container_ids) == 1, "expected exactly one PostgreSQL Compose container"

    inspect_result = run_local_command(
        [
            docker_command,
            "inspect",
            "--format",
            "{{json .NetworkSettings.Ports}}",
            container_ids[0],
        ]
    )
    port_bindings = json.loads(inspect_result.stdout)
    assert isinstance(port_bindings, dict)
    assert port_bindings.get("5432/tcp") is None
