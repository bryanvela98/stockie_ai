"""
Description: Celery application factory for Stockie AI background workers.
             All task modules import `celery_app` from here; the Docker worker
             and beat services point their `-A` flag at this module.
             Broker and result backend both use `settings.redis_url`; when that
             value is None (e.g. in unit tests without a live broker), both fall
             back to redis://localhost:6379/0 so that import-time code does not
             raise errors.
             Serialization is locked to JSON — pickle is never used.
Last Modified By: bvela
Created: 2026-06-07
Last Modified:
    2026-06-07 - File created; make_celery factory and module-level celery_app instance.
"""

from celery import Celery

from app.core.config import AppSettings, get_settings

_FALLBACK_BROKER = "redis://localhost:6379/0"


def make_celery(settings: AppSettings) -> Celery:
    """Create and configure a Celery application instance.

    Args:
        settings: Application settings; reads redis_url for broker/backend.

    Returns:
        A fully configured Celery instance with JSON serialization.
    """
    broker_url = settings.redis_url or _FALLBACK_BROKER

    app = Celery("stockie_ai", broker=broker_url, backend=broker_url)

    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        # Prevent tasks from running indefinitely on a lost worker.
        task_acks_late=True,
        worker_prefetch_multiplier=1,
    )

    return app


celery_app = make_celery(get_settings())
