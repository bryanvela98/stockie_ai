"""
Description: Structural tests for the Docker Compose configuration.
             Verifies that all required services exist and are correctly
             wired — runs in CI without Docker installed.
Last Modified By: bvela
Created: 2026-06-07
Last Modified:
    2026-06-07 - File created; structural tests for worker/beat services.
"""

from pathlib import Path
from typing import Any

import yaml

COMPOSE_FILE = Path(__file__).parents[2] / "infra" / "docker-compose.yml"
DOCKERFILE = Path(__file__).parents[1] / "Dockerfile"


def _load_compose() -> dict[str, Any]:
    """Load and parse the docker-compose.yml file."""
    with COMPOSE_FILE.open() as fh:
        data: dict[str, Any] = yaml.safe_load(fh)
        return data


def test_compose_file_exists() -> None:
    """docker-compose.yml must exist in infra/."""
    assert COMPOSE_FILE.exists(), f"Missing: {COMPOSE_FILE}"


def test_dockerfile_exists() -> None:
    """backend/Dockerfile must exist so compose can build the worker image."""
    assert DOCKERFILE.exists(), f"Missing: {DOCKERFILE}"


def test_compose_has_worker_service() -> None:
    """Compose must declare a 'worker' service for the Celery worker."""
    data = _load_compose()
    assert "worker" in data["services"], "Missing 'worker' service in docker-compose.yml"


def test_compose_has_beat_service() -> None:
    """Compose must declare a 'beat' service for Celery beat scheduler."""
    data = _load_compose()
    assert "beat" in data["services"], "Missing 'beat' service in docker-compose.yml"


def test_worker_depends_on_redis() -> None:
    """Worker service must declare a dependency on 'redis'."""
    data = _load_compose()
    worker = data["services"]["worker"]
    depends = worker.get("depends_on", {})
    deps = list(depends.keys()) if isinstance(depends, dict) else depends
    assert "redis" in deps, "worker must depend_on redis"


def test_beat_depends_on_redis() -> None:
    """Beat service must declare a dependency on 'redis'."""
    data = _load_compose()
    beat = data["services"]["beat"]
    depends = beat.get("depends_on", {})
    deps = list(depends.keys()) if isinstance(depends, dict) else depends
    assert "redis" in deps, "beat must depend_on redis"


def test_worker_command_references_celery_app() -> None:
    """Worker command must point at app.workers.celery_app."""
    data = _load_compose()
    command = str(data["services"]["worker"].get("command", ""))
    assert "app.workers.celery_app" in command


def test_beat_command_references_celery_app() -> None:
    """Beat command must point at app.workers.celery_app."""
    data = _load_compose()
    command = str(data["services"]["beat"].get("command", ""))
    assert "app.workers.celery_app" in command
