"""
Description: Celery workers package for Stockie AI background tasks.
             Import celery_app from app.workers.celery_app to register tasks
             or to invoke Celery CLI commands pointing at this package.
Last Modified By: bvela
Created: 2026-06-07
Last Modified:
    2026-06-07 - File created; barrel export for celery_app instance.
"""

from app.workers.celery_app import celery_app

__all__ = ["celery_app"]
