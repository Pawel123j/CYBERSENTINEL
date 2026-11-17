"""Static security invariants for the Stage 1 repository foundation."""

from __future__ import annotations

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = PROJECT_ROOT / "docker-compose.yml"
SECRET_PATTERNS = {".env", ".env.*", "*.key", "*.p12", "*.pem", "*.pfx"}


def read_lines(path: Path) -> set[str]:
    """Return non-empty, non-comment configuration lines."""

    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def load_compose() -> dict[str, object]:
    """Load the Compose document used by static invariant tests."""

    document = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def test_postgres_is_private_and_uses_internal_network() -> None:
    compose = load_compose()
    services = compose["services"]
    networks = compose["networks"]
    assert isinstance(services, dict)
    assert isinstance(networks, dict)

    postgres = services["postgres"]
    assert isinstance(postgres, dict)
    assert "ports" not in postgres
    assert postgres["networks"] == ["data"]
    assert networks["data"] == {"internal": True}


def test_host_ports_bind_only_to_loopback() -> None:
    compose = load_compose()
    services = compose["services"]
    assert isinstance(services, dict)

    for service_name in ("backend", "frontend"):
        service = services[service_name]
        assert isinstance(service, dict)
        ports = service["ports"]
        assert isinstance(ports, list)
        assert ports
        assert all(str(port).startswith("127.0.0.1:") for port in ports)


def test_database_password_is_required_for_both_consumers() -> None:
    compose = load_compose()
    services = compose["services"]
    assert isinstance(services, dict)

    for service_name in ("postgres", "backend"):
        service = services[service_name]
        assert isinstance(service, dict)
        environment = service["environment"]
        assert isinstance(environment, dict)
        password_expression = environment["POSTGRES_PASSWORD"]
        assert isinstance(password_expression, str)
        assert password_expression.startswith("${POSTGRES_PASSWORD:?")


def test_services_have_restart_policies_and_bounded_healthchecks() -> None:
    compose = load_compose()
    services = compose["services"]
    assert isinstance(services, dict)

    for service_name in ("postgres", "backend", "frontend"):
        service = services[service_name]
        assert isinstance(service, dict)
        assert service["restart"] == "unless-stopped"

        healthcheck = service["healthcheck"]
        assert isinstance(healthcheck, dict)
        assert healthcheck["test"]
        assert healthcheck["interval"]
        assert healthcheck["timeout"]
        assert healthcheck["retries"] > 0
        assert healthcheck["start_period"]


def test_service_startup_waits_for_healthy_dependencies() -> None:
    compose = load_compose()
    services = compose["services"]
    assert isinstance(services, dict)

    backend = services["backend"]
    frontend = services["frontend"]
    assert isinstance(backend, dict)
    assert isinstance(frontend, dict)
    assert backend["depends_on"] == {"postgres": {"condition": "service_healthy"}}
    assert frontend["depends_on"] == {"backend": {"condition": "service_healthy"}}


def test_secret_files_are_excluded_from_git_and_build_contexts() -> None:
    gitignore = read_lines(PROJECT_ROOT / ".gitignore")
    backend_dockerignore = read_lines(PROJECT_ROOT / "backend" / ".dockerignore")
    frontend_dockerignore = read_lines(PROJECT_ROOT / "frontend" / ".dockerignore")

    assert SECRET_PATTERNS <= gitignore
    assert SECRET_PATTERNS <= backend_dockerignore
    assert SECRET_PATTERNS <= frontend_dockerignore


def test_example_environment_contains_no_database_password() -> None:
    environment = read_lines(PROJECT_ROOT / ".env.example")
    assert "POSTGRES_PASSWORD=" in environment


def test_application_images_use_non_root_runtime_users() -> None:
    compose = load_compose()
    services = compose["services"]
    assert isinstance(services, dict)
    postgres = services["postgres"]
    assert isinstance(postgres, dict)

    backend_dockerfile = (PROJECT_ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    frontend_dockerfile = (PROJECT_ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")

    assert postgres["user"] == "postgres"
    assert "USER 10001:10001" in backend_dockerfile
    assert "RUN chown node:node /app" in frontend_dockerfile
    assert "USER node" in frontend_dockerfile
    assert "USER nginx" in frontend_dockerfile


def test_nginx_api_proxy_has_priority_and_refreshes_docker_dns() -> None:
    nginx_config = (PROJECT_ROOT / "frontend" / "nginx.conf").read_text(encoding="utf-8")

    assert "resolver 127.0.0.11" in nginx_config
    assert "location ^~ /api/" in nginx_config
    assert "proxy_pass $backend_origin$request_uri;" in nginx_config
