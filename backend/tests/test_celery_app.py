"""
Description: Unit tests for the Celery application factory.
             Verifies that celery_app is properly configured with JSON
             serialization and reads its broker/backend URLs from settings.
             Tests run without a live Redis broker.
Last Modified By: bvela
Created: 2026-06-07
Last Modified:
    2026-06-07 - File created; celery_app configuration tests.
"""


def test_celery_app_is_importable() -> None:
    """celery_app must be importable from app.workers.celery_app."""
    from app.workers.celery_app import celery_app  # noqa: F401

    assert celery_app is not None


def test_celery_app_uses_json_serializer() -> None:
    """Task serializer must be JSON (never pickle) for security."""
    from app.workers.celery_app import celery_app

    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_serializer == "json"
    assert "json" in celery_app.conf.accept_content


def test_celery_app_fallback_broker_when_redis_url_is_none() -> None:
    """When redis_url is None, broker falls back to redis://localhost:6379/0."""
    from app.core.config import AppSettings
    from app.workers.celery_app import make_celery

    app = make_celery(AppSettings(redis_url=None, database_url=None))
    assert app.conf.broker_url == "redis://localhost:6379/0"
    assert app.conf.result_backend == "redis://localhost:6379/0"


def test_celery_app_uses_redis_url_from_settings() -> None:
    """Broker and result backend are set from settings.redis_url when provided."""
    from app.core.config import AppSettings
    from app.workers.celery_app import make_celery

    fake_settings = AppSettings(redis_url="redis://testhost:6379/1", database_url=None)
    app = make_celery(fake_settings)

    assert app.conf.broker_url == "redis://testhost:6379/1"
    assert app.conf.result_backend == "redis://testhost:6379/1"


def test_celery_app_task_serializer_is_json_on_factory() -> None:
    """make_celery always configures JSON serialization regardless of settings."""
    from app.core.config import AppSettings
    from app.workers.celery_app import make_celery

    app = make_celery(AppSettings(database_url=None, redis_url=None))

    assert app.conf.task_serializer == "json"
