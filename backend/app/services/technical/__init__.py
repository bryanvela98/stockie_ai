"""
Description: Technical analysis services package. Exports pure, side-effect-free
             calculators for indicators, multi-timeframe resampling, and
             support/resistance detection. No DB or network access in this layer.

             Indicator backend: pandas-ta-classic (numpy 2.x-compatible fork).
             Upstream pandas-ta 0.3.14b breaks on numpy >= 2.0 due to use of
             numpy.NaN, which was removed. pandas-ta-classic resolves this;
             pinned in pyproject.toml.

Last Modified By: bvela
Created: 2026-06-17
Last Modified:
    2026-06-17 - File created; package scaffold for Sprint 4-A.
"""
