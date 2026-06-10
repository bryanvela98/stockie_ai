"""
Description: Repository layer for the Stockie AI backend.
             Repositories abstract all database access, accepting an AsyncSession
             via constructor injection so callers (FastAPI deps, Celery tasks)
             own the session lifecycle.
Last Modified By: bvela
Created: 2026-06-01
Last Modified:
    2026-06-01 - File created; barrel export for TickerRepository and
                 PriceRepository.
    2026-06-09 - Added CorporateActionRepository (Sprint 2-B Task 2).
    2026-06-09 - Added FundamentalsRepository (Sprint 2-B Task 3).
"""

from app.repositories.corporate_action_repository import CorporateActionRepository
from app.repositories.fundamentals_repository import FundamentalsRepository
from app.repositories.price_repository import PriceRepository
from app.repositories.ticker_repository import TickerRepository

__all__ = [
    "CorporateActionRepository",
    "FundamentalsRepository",
    "PriceRepository",
    "TickerRepository",
]
