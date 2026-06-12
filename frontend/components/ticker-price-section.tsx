/**
 * Description: Client island that fetches and displays the price chart for a
 *              single ticker. Holds timeframe state, derives the date range,
 *              calls GET /tickers/{symbol}/prices, and composes the
 *              TimeframeToggle, PriceChart, and DataAsOf badge components.
 *              Must be a "use client" component because it manages state and
 *              calls the API on the browser side. Rendered as a dynamic import
 *              (ssr: false) from the server-side ticker page to avoid SSR issues
 *              with lightweight-charts.
 * Last Modified By: despinoza
 * Created: 2026-06-11
 * Last Modified:
 *     2026-06-11 - File created; price section client island for the ticker detail page.
 */

"use client";

import { useCallback, useEffect, useState } from "react";

import { DataAsOfBadge } from "@/components/data-as-of-badge";
import { PriceChart } from "@/components/price-chart";
import { TimeframeToggle } from "@/components/timeframe-toggle";
import { apiClient } from "@/lib/api";
import type { components } from "@/lib/api/schema.d.ts";
import { timeframeToDateRange, type Timeframe } from "@/lib/types/timeframe";

type PriceBarItem = components["schemas"]["PriceBarItem"];

interface TickerPriceSectionProps {
  symbol: string;
}

/**
 * Fetches and renders the price chart section for a ticker detail page.
 *
 * @param symbol - The ticker symbol to fetch prices for (e.g. "AAPL").
 */
export function TickerPriceSection({ symbol }: TickerPriceSectionProps) {
  const [timeframe, setTimeframe] = useState<Timeframe>("1Y");
  const [bars, setBars] = useState<PriceBarItem[]>([]);
  const [dataAsOf, setDataAsOf] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchPrices = useCallback(
    async (tf: Timeframe) => {
      setIsLoading(true);
      const { from, to } = timeframeToDateRange(tf);

      const { data } = await apiClient.GET("/tickers/{symbol}/prices", {
        params: {
          path: { symbol },
          query: { from, to, timeframe: "1d", limit: 500 },
        },
      });

      setBars(data?.bars ?? []);
      setDataAsOf(data?.data_as_of ?? null);
      setIsLoading(false);
    },
    [symbol],
  );

  useEffect(() => {
    fetchPrices(timeframe);
  }, [timeframe, fetchPrices]);

  const handleTimeframeChange = (tf: Timeframe) => {
    setTimeframe(tf);
  };

  return (
    <section className="mb-6">
      <div className="mb-3 flex items-center justify-between gap-4">
        <h2 className="text-base font-semibold">Price Chart</h2>
        <TimeframeToggle value={timeframe} onChange={handleTimeframeChange} />
      </div>

      <PriceChart bars={bars} isLoading={isLoading} />

      <div className="mt-2 flex justify-end">
        <DataAsOfBadge asOf={dataAsOf} />
      </div>
    </section>
  );
}
