/**
 * Description: Global ticker search bar with debounced API calls and a
 *              keyboard-navigable dropdown result list.
 *              Debounce is implemented with useEffect + clearTimeout (no
 *              external library) at a 300 ms delay.
 *              Keyboard navigation: ArrowDown/ArrowUp move the highlighted
 *              index, Enter selects, Escape closes.
 *              Accessibility: combobox/listbox ARIA pattern (WCAG 2.1 AA).
 *              Navigates to /tickers/[symbol] on selection using next/navigation.
 * Last Modified By: despinoza
 * Created: 2026-06-01
 * Last Modified:
 *     2026-06-01 - File created; TickerSearchBar with debounce, keyboard nav,
 *                  loading state, and empty state.
 */

"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { apiClient } from "@/lib/api";
import type { components } from "@/lib/api/schema.d.ts";
import { TickerResultItem } from "@/components/ticker-result-item";
import { cn } from "@/lib/utils";

type TickerSearchResult = components["schemas"]["TickerSearchResult"];

/**
 * Full-featured ticker search bar component.
 *
 * Renders a text input that queries GET /tickers/search after a 300 ms debounce
 * and displays results in a dropdown. Navigates to /tickers/[symbol] on selection.
 */
export function TickerSearchBar() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<TickerSearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  // ── Debounced search ──────────────────────────────────────────────────────

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < 1) {
      setResults([]);
      setIsOpen(false);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    const timer = setTimeout(async () => {
      const { data } = await apiClient.GET("/tickers/search", {
        params: { query: { q: trimmed, limit: 20 } },
      });
      setResults(data?.results ?? []);
      setIsOpen(true);
      setIsLoading(false);
      setHighlightedIndex(-1);
    }, 300);

    return () => clearTimeout(timer);
  }, [query]);

  // ── Click-outside to close ────────────────────────────────────────────────

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // ── Actions ───────────────────────────────────────────────────────────────

  function handleSelect(symbol: string) {
    setIsOpen(false);
    setQuery("");
    router.push(`/tickers/${symbol}`);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!isOpen) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightedIndex((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && highlightedIndex >= 0) {
      e.preventDefault();
      handleSelect(results[highlightedIndex].symbol);
    } else if (e.key === "Escape") {
      setIsOpen(false);
      inputRef.current?.blur();
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────

  const showDropdown = isOpen && (isLoading || results.length > 0 || query.trim().length >= 1);

  return (
    <div ref={containerRef} className="relative w-full max-w-md">
      {/* Input */}
      <div
        role="combobox"
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        aria-controls="ticker-search-listbox"
        className={cn(
          "flex items-center gap-2 rounded-lg border bg-background px-3 py-2 shadow-sm",
          "focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-1",
        )}
      >
        <svg
          className="size-4 shrink-0 text-muted-foreground"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
        <input
          ref={inputRef}
          type="search"
          className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          placeholder="Search tickers…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => results.length > 0 && setIsOpen(true)}
          aria-autocomplete="list"
          aria-controls="ticker-search-listbox"
          autoComplete="off"
        />
        {isLoading && (
          <svg
            className="size-4 shrink-0 animate-spin text-muted-foreground"
            fill="none"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 00-8 8h4z"
            />
          </svg>
        )}
      </div>

      {/* Dropdown */}
      {showDropdown && (
        <ul
          id="ticker-search-listbox"
          role="listbox"
          aria-label="Ticker search results"
          className={cn(
            "absolute left-0 right-0 top-full z-50 mt-1 overflow-hidden",
            "rounded-lg border bg-popover shadow-md",
          )}
        >
          {isLoading && results.length === 0 && (
            <li className="px-4 py-3 text-sm text-muted-foreground">Searching…</li>
          )}

          {!isLoading && results.length === 0 && query.trim().length >= 1 && (
            <li className="px-4 py-3 text-sm text-muted-foreground">
              No tickers found for &ldquo;{query}&rdquo;
            </li>
          )}

          {results.map((ticker, idx) => (
            <TickerResultItem
              key={ticker.symbol}
              ticker={ticker}
              highlighted={idx === highlightedIndex}
              onSelect={handleSelect}
            />
          ))}
        </ul>
      )}
    </div>
  );
}
