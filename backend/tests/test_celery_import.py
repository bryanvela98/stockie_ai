"""
Description: Smoke test verifying that Celery and the Redis transport are
             importable. This guards against accidental removal of the deps
             from pyproject.toml and runs in CI without a live broker.
Last Modified By: bvela
Created: 2026-06-07
Last Modified:
    2026-06-07 - File created; import smoke tests for celery and redis deps.
"""


def test_celery_is_importable() -> None:
    """Celery package must be importable (celery[redis] in runtime deps)."""
    import celery  # noqa: F401

    assert celery.__version__


def test_celery_redis_transport_is_importable() -> None:
    """kombu Redis transport (bundled with celery[redis]) must be importable."""
    from kombu.transport import redis as kombu_redis  # noqa: F401

    assert kombu_redis


def test_redis_client_is_importable() -> None:
    """redis-py package must be importable (redis>=5.0 in runtime deps)."""
    import redis  # noqa: F401

    assert redis.__version__
