"""
Description: Pure fundamental-analysis calculators for the Stockie AI backend.
             All functions in this sub-package are side-effect-free: no DB, no
             network, no mutations. They accept value objects from the ORM or
             data-provider layer and return typed dataclasses.
             Modules: ratios (valuation), quality (profitability/safety),
                      growth (CAGR metrics).
Last Modified By: bvela
Created: 2026-06-12
Last Modified:
    2026-06-12 - File created; package init for fundamentals service layer.
"""
