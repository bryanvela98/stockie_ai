"""
Description: Exception hierarchy for the data_providers layer.
             All provider-level failures (network errors, missing symbols, rate
             limits) should raise one of these types so callers can handle them
             without parsing exception messages.
             Internal code may raise built-in exceptions; these types are reserved
             for failures that cross the provider boundary.
Last Modified By: bvela
Created: 2026-05-31
Last Modified:
    2026-05-31 - File created; added ProviderError and TickerNotFoundError.
"""


class ProviderError(Exception):
    """Base class for all data-provider failures.

    Covers transient failures (network timeouts, rate limits, parse errors)
    that are not caused by an invalid ticker symbol.
    """


class TickerNotFoundError(ProviderError):
    """Raised when a symbol does not exist in the provider's universe.

    Args:
        symbol: The ticker symbol that could not be resolved.
    """

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        super().__init__(f"Ticker not found: {symbol!r}")
