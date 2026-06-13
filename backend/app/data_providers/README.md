# Data Providers — Quirks & Operational Notes

This file documents known behavioural quirks of each concrete provider, the
bugs we found and fixed while wiring them up, and guidance for anyone adding
a new provider.  Keep it updated whenever a new edge case is discovered.

---

## YFinanceProvider

`YFinanceProvider` wraps the **unofficial** Yahoo Finance API exposed by the
[yfinance](https://github.com/ranaroussi/yfinance) library.  Yahoo can
silently change field names or response shapes at any time without versioning.
Every field access uses `dict.get()` so a missing field degrades to `None`
rather than raising `KeyError`.

### Quirk 1 — `auto_adjust=False` is required; `"Adj Close"` may still be absent

**The bug (found and fixed during Sprint 2):**

The default `yfinance.Ticker.history()` call sets `auto_adjust=True`, which
silently replaces all OHLCV prices with their split/dividend-adjusted versions.
This means:

* The raw closing price is **not available** — only the adjusted price is.
* The `"Adj Close"` column does **not appear** in the returned DataFrame
  because every column is already adjusted.

We need both the raw close (for historical accuracy) *and* the adjusted close
(for return calculations), so we call with `auto_adjust=False`.

However, even with `auto_adjust=False`, the `"Adj Close"` column is **absent**
for some tickers — notably certain ETFs, trusts, and any symbol where Yahoo
Finance lacks a corporate-action adjustment series.

**Fix applied in `get_price_bars()`:**

```python
has_adj_close = "Adj Close" in df.columns
adj_close = _float_or_none(row.get("Adj Close")) if has_adj_close else None
```

Never access `row["Adj Close"]` directly; always guard with the column-presence
check first.

---

### Quirk 2 — NaN floats instead of null/None

yfinance returns `float('nan')` for missing numeric fields rather than `None`.
Pydantic models and SQLAlchemy columns reject NaN, so every float retrieved
from the `info` dict must be passed through `_float_or_none()` before use.

```python
# Safe:
pe_ratio = _float_or_none(raw.get("trailingPE"))

# Unsafe — will store NaN in the DB or raise a validation error:
pe_ratio = raw.get("trailingPE")
```

---

### Quirk 3 — `debtToEquity` is a percentage, not a decimal ratio

Yahoo Finance expresses `debtToEquity` as a **percentage** (e.g. `150` means
150 %), not the standard financial ratio (1.5).  The raw value is stored as-is
in the `fundamentals.debt_to_equity` column.

**The scoring layer must divide by 100** before comparing against benchmarks
or industry peers.  This is a known discrepancy from most financial data
definitions.

---

### Quirk 4 — Unknown symbols return a sparse dict, not an error

When a symbol is not recognised, yfinance returns an empty dict `{}` or a
partial dict without `quoteType`.  It does **not** raise an exception or return
an HTTP error code.

**Detection pattern used throughout the provider:**

```python
if not raw or raw.get("quoteType") is None:
    raise TickerNotFoundError(symbol)
```

Do not rely on catching exceptions to detect missing symbols.

---

### Quirk 5 — Zero-valued corporate-action entries are artefacts

`yf.Ticker.splits` and `yf.Ticker.dividends` occasionally contain entries with
a ratio or amount of `0.0`.  These are data artefacts from the unofficial API
(often alignment rows or placeholder entries near a re-listing).

**Filter applied in `get_corporate_actions()`:**

```python
if ratio and ratio > 0:   # skips 0.0 artefacts
    actions.append(...)
```

---

### Quirk 6 — `shortName` / `longName` fallback chain

The preferred display name field is `shortName`, but it is absent for some
instruments (e.g. certain ETFs and foreign-listed ADRs).  Fallback order:

```
shortName → longName → symbol
```

Code:

```python
name = raw.get("shortName") or raw.get("longName") or symbol
```

---

### Quirk 7 — All I/O is synchronous; wrap with `asyncio.to_thread`

yfinance has no async support.  Every call must be wrapped in
`asyncio.to_thread` to avoid blocking the FastAPI event loop:

```python
df = await asyncio.to_thread(lambda: yf.Ticker(symbol).history(...))
```

Calling yfinance directly in an `async def` without `to_thread` will block all
concurrent requests for the duration of the network round-trip (typically
200–800 ms per ticker).

---

### Quirk 8 — Annual statement row labels are inconsistent across tickers

`yf.Ticker.income_stmt`, `.balance_sheet`, and `.cashflow` are DataFrames where
**rows are line-item labels** and **columns are fiscal-year-end Timestamps**.
The same metric may appear under different labels for different tickers:

| Metric | Primary label | Alternative labels |
|--------|--------------|-------------------|
| Operating income | `"Operating Income"` | `"EBIT"` |
| Stockholders' equity | `"Stockholders Equity"` | `"Common Stock Equity"`, `"Total Equity Gross Minority Interest"` |
| Cash | `"Cash And Cash Equivalents"` | `"Cash Cash Equivalents And Short Term Investments"` |

**Pattern used in `get_annual_financials()`:**

```python
def _row(df, col, *labels):
    for label in labels:
        if label in df.index:
            return df.at[label, col]
    return None
```

Always pass the most specific / common label first, then fallbacks. A missing
label degrades to `None` rather than raising `KeyError`.

---

### Quirk 9 — `capital_expenditure` is negative in yfinance cashflow statements

Yahoo Finance reports capital expenditure as a **negative number** (cash
outflow convention). The raw value is stored as-is in `AnnualFinancials` and
`financial_statements.capital_expenditure`. Callers computing FCF must account
for this:

```python
# Correct: capex is already negative, so subtract it (adding a negative = subtracting)
fcf = operating_cash_flow + capital_expenditure

# Wrong: double-counting the sign
fcf = operating_cash_flow - capital_expenditure
```

The growth calculator in `services/fundamentals/growth.py` handles this correctly.

---

## PolygonProvider

Currently a stub that raises `NotImplementedError` on all methods.  It exists
to prove the `MarketDataProvider` / `FundamentalsProvider` abstractions are
swap-able without changing callers.

To implement:
1. Obtain a Polygon.io API key and add it to `.env` / `AppSettings`.
2. Replace each `raise NotImplementedError` with a call to the appropriate
   Polygon REST endpoint.
3. Map the Polygon response schema to the same `TickerInfo`, `PriceBar`,
   `Fundamentals`, and `CorporateActionDTO` value objects.
4. The repository layer and Celery tasks require no changes — they depend on
   the abstract interfaces, not the concrete class.

---

## Adding a new provider

1. Create `backend/app/data_providers/<name>_provider.py`.
2. Subclass `MarketDataProvider` and / or `FundamentalsProvider` from `base.py`.
3. Implement the required abstract methods.  Return the canonical DTO types from
   `models.py` — never leak provider-specific types past this layer.
4. Raise `TickerNotFoundError` (not a plain `ValueError`) when a symbol is
   unrecognised.
5. Wrap all synchronous I/O in `asyncio.to_thread`.
6. Add tests in `tests/data_providers/test_<name>_provider.py` that mock the
   underlying HTTP calls.
7. Document provider-specific quirks in a new section above.
