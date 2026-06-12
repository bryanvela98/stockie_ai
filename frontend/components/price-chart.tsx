/**
 * Description: Candlestick price chart powered by TradingView Lightweight Charts v5.
 *              Must be rendered as a client component because the library requires
 *              access to the DOM (window / document).  Wrap with Next.js `dynamic()`
 *              and `{ ssr: false }` in any server component that imports this.
 *              Handles loading skeleton, empty-data state, and chart cleanup on unmount.
 * Last Modified By: despinoza
 * Created: 2026-06-11
 * Last Modified:
 *     2026-06-11 - File created; candlestick chart with loading skeleton and empty state.
 */

"use client";

import {
  CandlestickSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { useEffect, useRef } from "react";

import type { components } from "@/lib/api/schema.d.ts";

type PriceBarItem = components["schemas"]["PriceBarItem"];

interface PriceChartProps {
  bars: PriceBarItem[];
  isLoading: boolean;
}

/**
 * Renders an OHLCV candlestick chart for the supplied price bars.
 *
 * @param bars - Array of price bar items from the prices API endpoint.
 * @param isLoading - When true a skeleton placeholder is shown instead of the chart.
 */
export function PriceChart({ bars, isLoading }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const seriesRef = useRef<ISeriesApi<any> | null>(null);

  // Create / destroy the chart instance when the component mounts / unmounts.
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: "transparent" },
        textColor: "hsl(var(--muted-foreground))",
      },
      grid: {
        vertLines: { color: "hsl(var(--border))" },
        horzLines: { color: "hsl(var(--border))" },
      },
      timeScale: { borderColor: "hsl(var(--border))" },
      rightPriceScale: { borderColor: "hsl(var(--border))" },
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const resizeObserver = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  // Feed new data whenever bars change.
  useEffect(() => {
    if (!seriesRef.current || !chartRef.current) return;

    const data = bars
      .map((bar) => ({
        // lightweight-charts v5 expects a UTC timestamp in seconds
        time: (new Date(bar.t).getTime() / 1000) as UTCTimestamp,
        open: bar.o,
        high: bar.h,
        low: bar.low,
        close: bar.c,
      }))
      .sort((a, b) => a.time - b.time);

    seriesRef.current.setData(data);

    if (data.length > 0) {
      chartRef.current.timeScale().fitContent();
    }
  }, [bars]);

  if (isLoading) {
    return (
      <div className="h-[280px] animate-pulse rounded-lg bg-muted md:h-[400px]" aria-busy="true" />
    );
  }

  if (!isLoading && bars.length === 0) {
    return (
      <div className="flex h-[280px] items-center justify-center rounded-lg border border-dashed border-muted-foreground/30 text-sm text-muted-foreground md:h-[400px]">
        No price data available
      </div>
    );
  }

  return <div ref={containerRef} className="h-[280px] w-full md:h-[400px]" />;
}
