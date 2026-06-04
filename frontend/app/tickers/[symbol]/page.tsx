/**
 * Description: Ticker detail page — server component.
 *              Fetches GET /tickers/{symbol} at request time and renders a
 *              metadata card (symbol, name, exchange, asset type, sector,
 *              industry) plus placeholder sections for the features arriving
 *              in future sprints (price chart, fundamentals, sentiment).
 *              Returns a descriptive 404 message when the symbol is unknown.
 * Last Modified By: despinoza
 * Created: 2026-06-01
 * Last Modified:
 *     2026-06-01 - File created; Sprint 1 skeleton with metadata card and
 *                  placeholder sections.
 */

import type { Metadata } from "next";
import Link from "next/link";

import { apiClient } from "@/lib/api";
import type { components } from "@/lib/api/schema.d.ts";
import { cn } from "@/lib/utils";

type TickerSearchResult = components["schemas"]["TickerSearchResult"];

// ── Metadata ──────────────────────────────────────────────────────────────────

export async function generateMetadata({
  params,
}: {
  params: { symbol: string };
}): Promise<Metadata> {
  return {
    title: params.symbol.toUpperCase(),
  };
}

// ── Sub-components ────────────────────────────────────────────────────────────

function AssetTypeChip({ assetType }: { assetType: string }) {
  const colours: Record<string, string> = {
    EQUITY: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
    ETF: "bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300",
    MUTUALFUND: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  };
  return (
    <span
      className={cn(
        "rounded px-2 py-0.5 text-xs font-medium",
        colours[assetType.toUpperCase()] ?? "bg-muted text-muted-foreground",
      )}
    >
      {assetType}
    </span>
  );
}

function TickerHeader({ ticker }: { ticker: TickerSearchResult }) {
  return (
    <div className="mb-8">
      <div className="mb-1 flex items-center gap-2">
        <h1 className="font-mono text-3xl font-bold tracking-tight">{ticker.symbol}</h1>
        <AssetTypeChip assetType={ticker.asset_type} />
        <span className="text-sm text-muted-foreground">{ticker.exchange}</span>
      </div>
      <p className="text-lg text-muted-foreground">{ticker.name}</p>
      {ticker.sector && (
        <p className="mt-1 text-sm text-muted-foreground">
          {ticker.sector}
          {ticker.industry ? ` · ${ticker.industry}` : ""}
        </p>
      )}
    </div>
  );
}

function PlaceholderSection({ title, sprint }: { title: string; sprint: string }) {
  return (
    <section className="mb-6">
      <h2 className="mb-2 text-base font-semibold">{title}</h2>
      <div className="flex min-h-48 items-center justify-center rounded-lg border border-dashed border-muted-foreground/30 text-sm text-muted-foreground">
        Coming in {sprint}
      </div>
    </section>
  );
}

function TickerNotFound({ symbol }: { symbol: string }) {
  return (
    <main className="mx-auto max-w-2xl px-4 py-16">
      <Link
        href="/"
        className="mb-8 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        ← Back
      </Link>
      <div className="rounded-xl border border-destructive/40 bg-destructive/5 px-6 py-8 text-center">
        <p className="text-lg font-semibold text-destructive">Ticker not found</p>
        <p className="mt-2 text-sm text-muted-foreground">
          <span className="font-mono font-medium">{symbol.toUpperCase()}</span> is not in the
          database. Try searching for another symbol.
        </p>
        <Link
          href="/"
          className="mt-4 inline-block text-sm font-medium text-foreground underline underline-offset-4"
        >
          Go back to search
        </Link>
      </div>
    </main>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

/**
 * Server component for the ticker detail page.
 * Fetches ticker metadata from the backend and renders a skeleton layout.
 */
export default async function TickerPage({ params }: { params: { symbol: string } }) {
  const symbol = params.symbol.toUpperCase();

  const { data, error } = await apiClient.GET("/tickers/{symbol}", {
    params: { path: { symbol } },
  });

  if (error || !data) {
    return <TickerNotFound symbol={symbol} />;
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-8">
      <Link
        href="/"
        className="mb-6 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        ← Back
      </Link>

      <TickerHeader ticker={data} />

      <PlaceholderSection title="Price Chart" sprint="Sprint 2" />
      <PlaceholderSection title="Fundamentals" sprint="Sprint 3" />
      <PlaceholderSection title="Sentiment" sprint="Sprint 5" />
    </main>
  );
}
