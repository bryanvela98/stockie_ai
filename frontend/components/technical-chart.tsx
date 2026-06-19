/**
 * Description: Candlestick price chart with optional technical indicator overlays and
 *              support/resistance price lines. Extends the base price chart pattern
 *              (price-chart.tsx) to accept SMA/EMA/Bollinger LineSeries overlays,
 *              horizontal S/R price lines, and RSI/MACD as lightweight-charts v5 native
 *              panes so they share the same time axis without any synchronization glue.
 *              Overlay + subpane series are rebuilt atomically when the overlays/subpanes
 *              props change (remove all → recreate) to prevent stale chart state.
 *              Must be imported via `dynamic(..., { ssr: false })` — lightweight-charts
 *              accesses `window` at module init.
 * Last Modified By: bvela
 * Created: 2026-06-19
 * Last Modified:
 *     2026-06-19 - File created; TechnicalChart with SMA/EMA/Bollinger overlays + S/R price lines (Sprint 4-C3).
 *     2026-06-19 - Added RSI pane and MACD pane via v5 native pane API (Sprint 4-C4).
 */

"use client";

import {
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  LineStyle,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { useEffect, useRef } from "react";

import type { components } from "@/lib/api/schema.d.ts";

type PriceBarItem = components["schemas"]["PriceBarItem"];
type SupportResistanceLevelResponse = components["schemas"]["SupportResistanceLevelResponse"];
type IndicatorBlockResponse = components["schemas"]["IndicatorBlockResponse"];
type BollingerBlockResponse = components["schemas"]["BollingerBlockResponse"];

export interface OverlayData {
  sma: IndicatorBlockResponse[];
  ema: IndicatorBlockResponse[];
  bbands?: BollingerBlockResponse | null;
  levels: SupportResistanceLevelResponse[];
}

export interface SubpaneData {
  rsi?: { series: (number | null)[]; period: number } | null;
  macd?: {
    macd_series: (number | null)[];
    signal_series: (number | null)[];
    histogram_series: (number | null)[];
  } | null;
}

interface TechnicalChartProps {
  bars: PriceBarItem[];
  isLoading: boolean;
  overlays?: OverlayData;
  subpanes?: SubpaneData;
}

// ─── Color helpers ────────────────────────────────────────────────────────────

const SMA_COLORS: Record<number, string> = {
  20: "#f59e0b",
  50: "#3b82f6",
  200: "#8b5cf6",
};
const EMA_COLORS: Record<number, string> = { 12: "#10b981", 26: "#f97316" };
const BB_COLOR = "#94a3b8";

function smaColor(period: number): string {
  return SMA_COLORS[period] ?? "#64748b";
}
function emaColor(period: number): string {
  return EMA_COLORS[period] ?? "#6b7280";
}
function srColor(kind: string, strength: number): string {
  const alpha = Math.min(0.9, 0.35 + strength * 0.15).toFixed(2);
  return kind === "support" ? `rgba(34, 197, 94, ${alpha})` : `rgba(239, 68, 68, ${alpha})`;
}

// ─── Alignment helper ─────────────────────────────────────────────────────────

type ChartPoint = { time: UTCTimestamp };

/**
 * Zips a positional indicator series with sorted bar timestamps.
 * If the series is shorter than bars it covers the most-recent N bars.
 */
function zipWithBars(
  bars: ChartPoint[],
  series: (number | null)[],
): Array<{ time: UTCTimestamp; value: number }> {
  const offset = Math.max(0, bars.length - series.length);
  const result: Array<{ time: UTCTimestamp; value: number }> = [];
  for (let i = 0; i < series.length; i++) {
    const val = series[i];
    if (val === null) continue;
    const bar = bars[offset + i];
    if (!bar) continue;
    result.push({ time: bar.time, value: val });
  }
  return result;
}

/** Converts positional MACD histogram series to colored histogram data. */
function zipHistogram(
  bars: ChartPoint[],
  series: (number | null)[],
): Array<{ time: UTCTimestamp; value: number; color: string }> {
  const offset = Math.max(0, bars.length - series.length);
  const result: Array<{ time: UTCTimestamp; value: number; color: string }> = [];
  for (let i = 0; i < series.length; i++) {
    const val = series[i];
    if (val === null) continue;
    const bar = bars[offset + i];
    if (!bar) continue;
    result.push({
      time: bar.time,
      value: val,
      color: val >= 0 ? "rgba(34, 197, 94, 0.6)" : "rgba(239, 68, 68, 0.6)",
    });
  }
  return result;
}

// ─── Component ────────────────────────────────────────────────────────────────

const SUBPANE_HEIGHT = 95;

/**
 * Candlestick chart with SMA/EMA/Bollinger overlays, S/R price lines, and optional
 * RSI + MACD subpanes sharing the same time axis via lightweight-charts v5 panes.
 *
 * @param bars      - OHLCV bars from the prices API endpoint.
 * @param isLoading - Shows a skeleton placeholder when true.
 * @param overlays  - Optional SMA/EMA/Bollinger series + S/R levels to overlay on pane 0.
 * @param subpanes  - Optional RSI and/or MACD data to display in sub-panes 1/2.
 */
export function TechnicalChart({ bars, isLoading, overlays, subpanes }: TechnicalChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const candleSeriesRef = useRef<ISeriesApi<any> | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const overlaySeriesRef = useRef<ISeriesApi<any>[]>([]);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const priceLinesRef = useRef<any[]>([]);

  // Create chart and candlestick series on mount.
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
    candleSeriesRef.current = series;

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
      candleSeriesRef.current = null;
      overlaySeriesRef.current = [];
      priceLinesRef.current = [];
    };
  }, []);

  // Feed candle data whenever bars change.
  useEffect(() => {
    if (!candleSeriesRef.current || !chartRef.current) return;

    const data = bars
      .map((bar) => ({
        time: (new Date(bar.t).getTime() / 1000) as UTCTimestamp,
        open: bar.o,
        high: bar.h,
        low: bar.low,
        close: bar.c,
      }))
      .sort((a, b) => a.time - b.time);

    candleSeriesRef.current.setData(data);
    if (data.length > 0) chartRef.current.timeScale().fitContent();
  }, [bars]);

  // Rebuild all overlay series and subpanes whenever bars, overlays, or subpanes change.
  useEffect(() => {
    const chart = chartRef.current;
    const candleSeries = candleSeriesRef.current;
    if (!chart || !candleSeries) return;

    // Remove all overlay series from pane 0.
    for (const s of overlaySeriesRef.current) chart.removeSeries(s);
    overlaySeriesRef.current = [];

    // Remove all price lines from the candlestick series.
    for (const pl of priceLinesRef.current) candleSeries.removePriceLine(pl);
    priceLinesRef.current = [];

    // Remove all subpanes (indices ≥ 1) from highest to lowest to avoid index shift.
    const paneCount = chart.panes().length;
    for (let i = paneCount - 1; i >= 1; i--) {
      chart.removePane(i);
    }

    if (bars.length === 0) return;

    // Build sorted bar timestamps for series alignment.
    const sortedTimes: ChartPoint[] = bars
      .map((bar) => ({ time: (new Date(bar.t).getTime() / 1000) as UTCTimestamp }))
      .sort((a, b) => a.time - b.time);

    // ── Pane 0 overlays ────────────────────────────────────────────────────────

    if (overlays) {
      // SMA overlays.
      for (const sma of overlays.sma) {
        if (!sma.series.length) continue;
        const s = chart.addSeries(LineSeries, {
          color: smaColor(sma.period),
          lineWidth: 1,
          lineStyle: LineStyle.Solid,
          priceLineVisible: false,
          lastValueVisible: false,
          title: `SMA${sma.period}`,
        });
        s.setData(zipWithBars(sortedTimes, sma.series));
        overlaySeriesRef.current.push(s);
      }

      // EMA overlays.
      for (const ema of overlays.ema) {
        if (!ema.series.length) continue;
        const s = chart.addSeries(LineSeries, {
          color: emaColor(ema.period),
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          priceLineVisible: false,
          lastValueVisible: false,
          title: `EMA${ema.period}`,
        });
        s.setData(zipWithBars(sortedTimes, ema.series));
        overlaySeriesRef.current.push(s);
      }

      // Bollinger band overlays.
      if (overlays.bbands) {
        const bb = overlays.bbands;
        const bbBands: [(number | null)[], string][] = [
          [bb.upper_series, "BB Upper"],
          [bb.mid_series, "BB Mid"],
          [bb.lower_series, "BB Lower"],
        ];
        for (const [series, title] of bbBands) {
          const s = chart.addSeries(LineSeries, {
            color: BB_COLOR,
            lineWidth: 1,
            lineStyle: LineStyle.Dotted,
            priceLineVisible: false,
            lastValueVisible: false,
            title,
          });
          s.setData(zipWithBars(sortedTimes, series));
          overlaySeriesRef.current.push(s);
        }
      }

      // S/R horizontal price lines.
      for (const level of overlays.levels) {
        const pl = candleSeries.createPriceLine({
          price: level.price,
          color: srColor(level.kind, level.strength),
          lineWidth: level.strength >= 3 ? 2 : 1,
          lineStyle: level.kind === "support" ? LineStyle.Solid : LineStyle.Dashed,
          axisLabelVisible: true,
          title: level.kind === "support" ? "S" : "R",
        });
        priceLinesRef.current.push(pl);
      }
    }

    // ── Subpanes ───────────────────────────────────────────────────────────────

    let nextPane = 1;

    // RSI pane.
    if (subpanes?.rsi && subpanes.rsi.series.length > 0) {
      const rsiSeries = chart.addSeries(
        LineSeries,
        {
          color: "#8b5cf6",
          lineWidth: 1,
          lineStyle: LineStyle.Solid,
          priceLineVisible: false,
          lastValueVisible: true,
          title: `RSI${subpanes.rsi.period}`,
        },
        nextPane,
      );
      rsiSeries.setData(zipWithBars(sortedTimes, subpanes.rsi.series));
      // Overbought / oversold guide lines.
      rsiSeries.createPriceLine({
        price: 70,
        color: "rgba(239, 68, 68, 0.5)",
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: "OB",
      });
      rsiSeries.createPriceLine({
        price: 30,
        color: "rgba(34, 197, 94, 0.5)",
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: "OS",
      });
      chart.panes()[nextPane]?.setHeight(SUBPANE_HEIGHT);
      nextPane++;
    }

    // MACD pane.
    if (subpanes?.macd) {
      const { macd_series, signal_series, histogram_series } = subpanes.macd;

      const histSeries = chart.addSeries(
        HistogramSeries,
        {
          priceLineVisible: false,
          lastValueVisible: false,
          title: "MACD Hist",
        },
        nextPane,
      );
      histSeries.setData(zipHistogram(sortedTimes, histogram_series));

      const macdLineSeries = chart.addSeries(
        LineSeries,
        {
          color: "#3b82f6",
          lineWidth: 1,
          lineStyle: LineStyle.Solid,
          priceLineVisible: false,
          lastValueVisible: false,
          title: "MACD",
        },
        nextPane,
      );
      macdLineSeries.setData(zipWithBars(sortedTimes, macd_series));

      const signalLineSeries = chart.addSeries(
        LineSeries,
        {
          color: "#f97316",
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          priceLineVisible: false,
          lastValueVisible: false,
          title: "Signal",
        },
        nextPane,
      );
      signalLineSeries.setData(zipWithBars(sortedTimes, signal_series));

      chart.panes()[nextPane]?.setHeight(SUBPANE_HEIGHT);
      nextPane++;
    }

    // Update total chart height to match the container after pane additions.
    if (containerRef.current) {
      chart.applyOptions({ height: containerRef.current.clientHeight });
    }
  }, [bars, overlays, subpanes]);

  if (isLoading) {
    return (
      <div className="h-[280px] animate-pulse rounded-lg bg-muted md:h-[420px]" aria-busy="true" />
    );
  }

  if (bars.length === 0) {
    return (
      <div className="flex h-[280px] items-center justify-center rounded-lg border border-dashed border-muted-foreground/30 text-sm text-muted-foreground md:h-[420px]">
        No price data available
      </div>
    );
  }

  return <div ref={containerRef} className="h-[280px] w-full md:h-[420px]" />;
}
