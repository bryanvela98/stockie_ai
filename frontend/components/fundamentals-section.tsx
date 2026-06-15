/**
 * Description: Client island that fetches GET /tickers/{symbol}/fundamentals and
 *              renders the full fundamental analysis UI:
 *                - Valuation ratios table
 *                - Quality / profitability metrics table
 *                - Growth rates table (revenue, EPS, FCF × 1/3/5yr)
 *                - SubscoreChart (Value / Quality / Growth bars)
 *                - ScoreBadge for the overall score
 *                - PeerComparisonTable
 *                - DcfWidget
 *
 *              Growth rates come from the API as decimal ratios (0.08 = 8 %);
 *              multiply by 100 before display.
 * Last Modified By: bvela
 * Created: 2026-06-15
 * Last Modified:
 *     2026-06-15 - File created; full fundamentals section composed from sub-components.
 */

"use client";

import { useEffect, useState } from "react";

import { DcfWidget } from "@/components/dcf-widget";
import { PeerComparisonTable } from "@/components/peer-comparison-table";
import { ScoreBadge } from "@/components/score-badge";
import { SubscoreChart } from "@/components/subscore-chart";
import { apiClient } from "@/lib/api";
import type { components } from "@/lib/api/schema.d.ts";

type FundamentalsResponse = components["schemas"]["FundamentalsResponse"];
type RatioBlock = components["schemas"]["RatioBlock"];
type QualityBlock = components["schemas"]["QualityBlock"];
type GrowthBlock = components["schemas"]["GrowthBlock"];

interface FundamentalsSectionProps {
  symbol: string;
}

// ─── Formatters ──────────────────────────────────────────────────────────────

function fmtMultiple(val: number | null | undefined): string {
  return val !== null && val !== undefined ? `${val.toFixed(1)}x` : "—";
}

function fmtPct(val: number | null | undefined): string {
  return val !== null && val !== undefined ? `${(val * 100).toFixed(1)} %` : "—";
}

function fmtRatio(val: number | null | undefined): string {
  return val !== null && val !== undefined ? val.toFixed(2) : "—";
}

// ─── Skeletons ────────────────────────────────────────────────────────────────

function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="animate-pulse space-y-2" aria-busy="true" aria-label="Loading data">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex justify-between">
          <div className="h-4 w-1/3 rounded bg-muted" />
          <div className="h-4 w-1/4 rounded bg-muted" />
        </div>
      ))}
    </div>
  );
}

// ─── Sub-tables ───────────────────────────────────────────────────────────────

interface MetricRowProps {
  label: string;
  value: string;
}

function MetricRow({ label, value }: MetricRowProps) {
  return (
    <tr className="border-b border-border last:border-0">
      <td className="py-2 pr-4 text-xs text-muted-foreground">{label}</td>
      <td className="py-2 text-right text-xs tabular-nums font-medium">{value}</td>
    </tr>
  );
}

interface MetricTableProps {
  caption: string;
  children: React.ReactNode;
}

function MetricTable({ caption, children }: MetricTableProps) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {caption}
      </h3>
      <table className="w-full text-sm">
        <caption className="sr-only">{caption}</caption>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

function RatiosTable({ r }: { r: RatioBlock }) {
  return (
    <MetricTable caption="Valuation ratios">
      <MetricRow label="P/E" value={fmtMultiple(r.pe)} />
      <MetricRow label="P/B" value={fmtMultiple(r.pb)} />
      <MetricRow label="P/S" value={fmtMultiple(r.ps)} />
      <MetricRow label="EV / EBITDA" value={fmtMultiple(r.ev_ebitda)} />
      <MetricRow label="PEG" value={fmtRatio(r.peg)} />
      <MetricRow label="Dividend yield" value={fmtPct(r.dividend_yield)} />
    </MetricTable>
  );
}

function QualityTable({ q }: { q: QualityBlock }) {
  return (
    <MetricTable caption="Quality & profitability">
      <MetricRow label="ROE" value={fmtPct(q.roe)} />
      <MetricRow label="ROIC" value={fmtPct(q.roic)} />
      <MetricRow label="Gross margin" value={fmtPct(q.gross_margin)} />
      <MetricRow label="Operating margin" value={fmtPct(q.operating_margin)} />
      <MetricRow label="Net margin" value={fmtPct(q.net_margin)} />
      <MetricRow label="Debt / equity" value={fmtRatio(q.debt_to_equity)} />
      <MetricRow label="Interest coverage" value={fmtRatio(q.interest_coverage)} />
    </MetricTable>
  );
}

function GrowthTable({ g }: { g: GrowthBlock }) {
  return (
    <MetricTable caption="Growth rates">
      <MetricRow label="Revenue 1yr" value={fmtPct(g.revenue_cagr_1y)} />
      <MetricRow label="Revenue 3yr CAGR" value={fmtPct(g.revenue_cagr_3y)} />
      <MetricRow label="Revenue 5yr CAGR" value={fmtPct(g.revenue_cagr_5y)} />
      <MetricRow label="EPS 1yr" value={fmtPct(g.eps_cagr_1y)} />
      <MetricRow label="EPS 3yr CAGR" value={fmtPct(g.eps_cagr_3y)} />
      <MetricRow label="EPS 5yr CAGR" value={fmtPct(g.eps_cagr_5y)} />
      <MetricRow label="FCF 1yr" value={fmtPct(g.fcf_cagr_1y)} />
      <MetricRow label="FCF 3yr CAGR" value={fmtPct(g.fcf_cagr_3y)} />
      <MetricRow label="FCF 5yr CAGR" value={fmtPct(g.fcf_cagr_5y)} />
    </MetricTable>
  );
}

// ─── Section divider ──────────────────────────────────────────────────────────

function SectionHeading({ children }: { children: React.ReactNode }) {
  return <h2 className="text-sm font-semibold text-foreground">{children}</h2>;
}

function Divider() {
  return <hr className="border-border" />;
}

// ─── Main component ───────────────────────────────────────────────────────────

/**
 * Fetches and renders the full fundamental analysis view for a ticker.
 *
 * @param symbol - Ticker symbol (e.g. "AAPL").
 */
export function FundamentalsSection({ symbol }: FundamentalsSectionProps) {
  const [data, setData] = useState<FundamentalsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchFundamentals() {
      setIsLoading(true);
      setError(null);

      const { data: resp, error: apiError } = await apiClient.GET(
        "/tickers/{symbol}/fundamentals",
        { params: { path: { symbol } } },
      );

      if (cancelled) return;

      if (apiError || !resp) {
        setError("Fundamental data is not available for this ticker yet.");
      } else {
        setData(resp);
      }
      setIsLoading(false);
    }

    void fetchFundamentals();
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <TableSkeleton rows={6} />
        <TableSkeleton rows={7} />
        <TableSkeleton rows={9} />
      </div>
    );
  }

  if (error) {
    return (
      <p className="text-sm text-muted-foreground" role="alert">
        {error}
      </p>
    );
  }

  if (!data) return null;

  const { ratios, quality, growth, scores } = data;

  return (
    <div className="space-y-8">
      {/* Overall score + subscores */}
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <SectionHeading>Overall score</SectionHeading>
          <ScoreBadge score={scores.overall ?? null} label="Overall fundamental score" size="md" />
        </div>
        <SubscoreChart
          value={scores.value ?? null}
          quality={scores.quality ?? null}
          growth={scores.growth ?? null}
        />
        <p className="text-xs text-muted-foreground">
          Data as of {data.data_as_of} · weights {scores.weights_version}
        </p>
      </div>

      <Divider />

      {/* Metric tables in a responsive two-column layout */}
      <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
        <RatiosTable r={ratios} />
        <QualityTable q={quality} />
        <GrowthTable g={growth} />
      </div>

      <Divider />

      {/* Peer comparison */}
      <div className="space-y-3">
        <SectionHeading>Sector peers</SectionHeading>
        <PeerComparisonTable symbol={symbol} />
      </div>

      <Divider />

      {/* DCF */}
      <div className="space-y-3">
        <SectionHeading>DCF intrinsic value</SectionHeading>
        <DcfWidget symbol={symbol} />
      </div>
    </div>
  );
}
