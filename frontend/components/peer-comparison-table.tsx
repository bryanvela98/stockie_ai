/**
 * Description: Client island that fetches GET /tickers/{symbol}/peers and renders
 *              a compact comparison table showing symbol, market cap, P/E, P/B, and
 *              overall fundamental score for each same-sector peer.
 *              An empty peers list (ticker with no sector, or no peers in DB) renders
 *              a graceful empty state — it is not an error.
 * Last Modified By: bvela
 * Created: 2026-06-15
 * Last Modified:
 *     2026-06-15 - File created; PeerComparisonTable client island.
 */

"use client";

import { useEffect, useState } from "react";

import { ScoreBadge } from "@/components/score-badge";
import { apiClient } from "@/lib/api";
import type { components } from "@/lib/api/schema.d.ts";

type PeerItem = components["schemas"]["PeerItem"];

interface PeerComparisonTableProps {
  symbol: string;
}

function formatMarketCap(cap: number | null | undefined): string {
  if (cap === null || cap === undefined) return "—";
  if (cap >= 1e12) return `$${(cap / 1e12).toFixed(1)}T`;
  if (cap >= 1e9) return `$${(cap / 1e9).toFixed(1)}B`;
  if (cap >= 1e6) return `$${(cap / 1e6).toFixed(1)}M`;
  return `$${cap.toFixed(0)}`;
}

function fmtMultiple(val: number | null | undefined): string {
  return val !== null && val !== undefined ? `${val.toFixed(1)}x` : "—";
}

function PeerTableSkeleton() {
  return (
    <div className="animate-pulse space-y-2" aria-busy="true" aria-label="Loading peers">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="h-8 rounded bg-muted" />
      ))}
    </div>
  );
}

/**
 * Fetches and renders the peer comparison table for a ticker.
 *
 * @param symbol - Subject ticker symbol (e.g. "AAPL").
 */
export function PeerComparisonTable({ symbol }: PeerComparisonTableProps) {
  const [peers, setPeers] = useState<PeerItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchPeers() {
      setIsLoading(true);
      setError(null);

      const { data, error: apiError } = await apiClient.GET("/tickers/{symbol}/peers", {
        params: { path: { symbol }, query: { limit: 5 } },
      });

      if (cancelled) return;

      if (apiError || !data) {
        setError("Could not load peer data.");
      } else {
        setPeers(data.peers);
      }
      setIsLoading(false);
    }

    void fetchPeers();
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  if (isLoading) return <PeerTableSkeleton />;

  if (error) {
    return (
      <p className="text-sm text-muted-foreground" role="alert">
        {error}
      </p>
    );
  }

  if (peers.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No same-sector peers found for {symbol}.</p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" aria-label={`Peers of ${symbol}`}>
        <thead>
          <tr className="border-b border-border text-left text-xs text-muted-foreground">
            <th scope="col" className="pb-2 pr-4 font-medium">
              Symbol
            </th>
            <th scope="col" className="pb-2 pr-4 font-medium">
              Market Cap
            </th>
            <th scope="col" className="pb-2 pr-4 text-right font-medium">
              P/E
            </th>
            <th scope="col" className="pb-2 pr-4 text-right font-medium">
              P/B
            </th>
            <th scope="col" className="pb-2 text-right font-medium">
              Score
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {peers.map((peer) => (
            <tr key={peer.symbol} className="py-1">
              <td className="py-2 pr-4 font-mono font-medium">{peer.symbol}</td>
              <td className="py-2 pr-4 text-muted-foreground">
                {formatMarketCap(peer.market_cap)}
              </td>
              <td className="py-2 pr-4 text-right tabular-nums">{fmtMultiple(peer.pe)}</td>
              <td className="py-2 pr-4 text-right tabular-nums">{fmtMultiple(peer.pb)}</td>
              <td className="py-2 text-right">
                <ScoreBadge
                  score={peer.overall_score ?? null}
                  label={`${peer.symbol} overall score`}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
