/**
 * Description: Client island that fetches GET /tickers/{symbol}/technical and renders
 *              the full technical analysis UI for a given bar granularity:
 *                - TechnicalChart (candlestick + SMA/EMA/Bollinger overlays + S/R lines
 *                  + RSI/MACD native panes when enabled)
 *                - IndicatorSettingsDrawer to toggle/configure indicators
 *                - GranularityToggle (Daily / Weekly / Monthly) wired to the technical endpoint
 *                - ScoreBadge for the overall technical score
 *                - SubscoreChart for Trend / Momentum / Mean Rev. subscores
 *                - Ranked support/resistance level list
 *                - DataAsOfBadge for freshness
 *              Price bars are fetched once per symbol change (always daily).
 *              Indicators are fetched whenever symbol or indicator settings change (300ms debounce).
 *              The technical score + S/R levels re-fetch whenever granularity changes.
 * Last Modified By: bvela
 * Created: 2026-06-19
 * Last Modified:
 *     2026-06-19 - File created; TechnicalSection with score, S/R levels, granularity selector (Sprint 4-C1/C2).
 *     2026-06-19 - Added TechnicalChart with SMA50/SMA200 overlays + S/R price lines (Sprint 4-C3).
 *     2026-06-19 - Added RSI/MACD subpanes + IndicatorSettingsDrawer (Sprint 4-C4).
 */

"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import { DataAsOfBadge } from "@/components/data-as-of-badge";
import { GranularityToggle } from "@/components/granularity-toggle";
import {
  DEFAULT_INDICATOR_SETTINGS,
  IndicatorSettingsDrawer,
  type IndicatorSettings,
} from "@/components/indicator-settings-drawer";
import { ScoreBadge } from "@/components/score-badge";
import { SubscoreChart } from "@/components/subscore-chart";
import type { OverlayData, SubpaneData } from "@/components/technical-chart";
import { apiClient } from "@/lib/api";
import type { components } from "@/lib/api/schema.d.ts";
import { type Granularity } from "@/lib/types/granularity";
import { cn } from "@/lib/utils";

// ssr:false — lightweight-charts accesses window on module init.
const TechnicalChart = dynamic(
  () => import("@/components/technical-chart").then((m) => ({ default: m.TechnicalChart })),
  { ssr: false },
);

type TechnicalResponse = components["schemas"]["TechnicalResponse"];
type IndicatorsResponse = components["schemas"]["IndicatorsResponse"];
type SupportResistanceLevelResponse = components["schemas"]["SupportResistanceLevelResponse"];
type PriceBarItem = components["schemas"]["PriceBarItem"];

interface TechnicalSectionProps {
  symbol: string;
}

// ─── Indicator query builder ──────────────────────────────────────────────────

interface IndicatorsQueryParams {
  timeframe: string;
  indicators?: string | null;
  sma_periods?: string | null;
  ema_periods?: string | null;
  rsi_period?: number;
  bbands_period?: number;
  series: boolean;
}

function buildIndicatorsQuery(settings: IndicatorSettings): IndicatorsQueryParams {
  const names: string[] = [];
  if (settings.smaEnabled) names.push("sma");
  if (settings.emaEnabled) names.push("ema");
  if (settings.bbandsEnabled) names.push("bbands");
  if (settings.rsiEnabled) names.push("rsi");
  if (settings.macdEnabled) names.push("macd");
  if (names.length === 0) names.push("sma");

  return {
    timeframe: "1d",
    indicators: names.join(","),
    ...(settings.smaEnabled ? { sma_periods: settings.smaPeriods } : {}),
    ...(settings.emaEnabled ? { ema_periods: settings.emaPeriods } : {}),
    ...(settings.bbandsEnabled ? { bbands_period: settings.bbandsPeriod } : {}),
    ...(settings.rsiEnabled ? { rsi_period: settings.rsiPeriod } : {}),
    series: true,
  };
}

// ─── Overlay / subpane builders ───────────────────────────────────────────────

function buildOverlay(
  indicators: IndicatorsResponse | null,
  levels: SupportResistanceLevelResponse[],
): OverlayData | undefined {
  if (!indicators) return undefined;
  return { sma: indicators.sma, ema: indicators.ema, bbands: indicators.bbands, levels };
}

function buildSubpanes(indicators: IndicatorsResponse | null): SubpaneData | undefined {
  if (!indicators) return undefined;
  return {
    rsi: indicators.rsi ? { series: indicators.rsi.series, period: indicators.rsi.period } : null,
    macd: indicators.macd ?? null,
  };
}

// ─── Skeletons ────────────────────────────────────────────────────────────────

function ScoreSkeleton() {
  return (
    <div className="animate-pulse space-y-3" aria-busy="true" aria-label="Loading technical score">
      <div className="flex items-center gap-3">
        <div className="h-5 w-32 rounded bg-muted" />
        <div className="h-7 w-10 rounded bg-muted" />
      </div>
      <div className="space-y-2">
        {["Trend", "Momentum", "Mean Rev."].map((label) => (
          <div key={label} className="flex items-center gap-3">
            <div className="h-4 w-16 rounded bg-muted" />
            <div className="h-4 flex-1 rounded-full bg-muted" />
            <div className="h-4 w-8 rounded bg-muted" />
          </div>
        ))}
      </div>
    </div>
  );
}

function LevelsSkeleton() {
  return (
    <div className="animate-pulse space-y-1" aria-busy="true" aria-label="Loading S/R levels">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="flex justify-between">
          <div className="h-4 w-20 rounded bg-muted" />
          <div className="h-4 w-24 rounded bg-muted" />
        </div>
      ))}
    </div>
  );
}

// ─── S/R level list ───────────────────────────────────────────────────────────

function strengthLabel(strength: number): string {
  if (strength >= 3) return "Strong";
  if (strength >= 2) return "Moderate";
  return "Weak";
}

interface LevelRowProps {
  level: SupportResistanceLevelResponse;
}

function LevelRow({ level }: LevelRowProps) {
  const isSupport = level.kind === "support";
  return (
    <tr className="border-b border-border last:border-0">
      <td className="py-1.5 pr-4 text-xs tabular-nums font-medium">${level.price.toFixed(2)}</td>
      <td className="py-1.5 pr-4">
        <span
          className={cn(
            "inline-block rounded px-1.5 py-0.5 text-xs font-medium",
            isSupport
              ? "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300"
              : "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
          )}
        >
          {isSupport ? "Support" : "Resistance"}
        </span>
      </td>
      <td className="py-1.5 text-right text-xs text-muted-foreground">
        {strengthLabel(level.strength)}
      </td>
    </tr>
  );
}

// ─── Section helpers ──────────────────────────────────────────────────────────

function SectionHeading({ children }: { children: React.ReactNode }) {
  return <h2 className="text-sm font-semibold text-foreground">{children}</h2>;
}

function Divider() {
  return <hr className="border-border" />;
}

// ─── Main component ───────────────────────────────────────────────────────────

/**
 * Fetches and renders the full technical analysis view for a ticker.
 *
 * @param symbol - Ticker symbol (e.g. "AAPL").
 */
export function TechnicalSection({ symbol }: TechnicalSectionProps) {
  const [granularity, setGranularity] = useState<Granularity>("1d");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [indicatorSettings, setIndicatorSettings] = useState<IndicatorSettings>(
    DEFAULT_INDICATOR_SETTINGS,
  );

  // Chart data — price bars fetched once per symbol (always daily).
  const [bars, setBars] = useState<PriceBarItem[]>([]);
  const [barsLoading, setBarsLoading] = useState(true);

  // Indicator series — re-fetched on symbol or settings change (300ms debounce).
  const [indicatorsData, setIndicatorsData] = useState<IndicatorsResponse | null>(null);

  // Score / S/R — re-fetched on symbol or granularity change.
  const [techData, setTechData] = useState<TechnicalResponse | null>(null);
  const [techLoading, setTechLoading] = useState(true);
  const [techError, setTechError] = useState<string | null>(null);

  // Fetch price bars whenever symbol changes (no settings dependency — always daily).
  useEffect(() => {
    let cancelled = false;
    setBarsLoading(true);
    setBars([]);

    async function fetchBars() {
      const today = new Date();
      const from = new Date(today);
      from.setFullYear(from.getFullYear() - 5);

      const { data } = await apiClient.GET("/tickers/{symbol}/prices", {
        params: {
          path: { symbol },
          query: {
            from: from.toISOString().slice(0, 10),
            to: today.toISOString().slice(0, 10),
            timeframe: "1d",
            limit: 500,
          },
        },
      });

      if (cancelled) return;
      setBars(data?.bars ?? []);
      setBarsLoading(false);
    }

    void fetchBars();
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  // Fetch indicators whenever symbol or settings change, with a 300ms debounce to
  // avoid a round-trip on every keystroke in the period inputs.
  useEffect(() => {
    let cancelled = false;
    setIndicatorsData(null);

    const timer = setTimeout(async () => {
      const query = buildIndicatorsQuery(indicatorSettings);

      const { data: resp } = await apiClient.GET("/tickers/{symbol}/indicators", {
        params: { path: { symbol }, query },
      });

      if (cancelled) return;
      setIndicatorsData(resp ?? null);
    }, 300);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [symbol, indicatorSettings]);

  // Fetch technical score + S/R levels whenever symbol or granularity changes.
  useEffect(() => {
    let cancelled = false;
    setTechLoading(true);
    setTechError(null);

    async function fetchTechnical() {
      const { data: resp, error: apiError } = await apiClient.GET("/tickers/{symbol}/technical", {
        params: { path: { symbol }, query: { timeframe: granularity } },
      });

      if (cancelled) return;

      if (apiError || !resp) {
        setTechError("Technical data is not available for this ticker yet.");
      } else {
        setTechData(resp);
      }
      setTechLoading(false);
    }

    void fetchTechnical();
    return () => {
      cancelled = true;
    };
  }, [symbol, granularity]);

  const { score } = techData ?? {};
  const levels = techData?.levels ?? [];

  const hasInsufficientData =
    !techLoading &&
    !techError &&
    techData &&
    score?.overall === null &&
    score?.trend === null &&
    score?.momentum === null &&
    score?.mean_reversion === null;

  const overlays = buildOverlay(indicatorsData, levels);
  const subpanes = buildSubpanes(indicatorsData);

  // Active overlay legend items for the chart footer.
  const legendItems: { label: string; color: string }[] = [];
  if (indicatorSettings.smaEnabled) {
    if (indicatorSettings.smaPeriods.includes("50"))
      legendItems.push({ label: "SMA 50", color: "#3b82f6" });
    if (indicatorSettings.smaPeriods.includes("200"))
      legendItems.push({ label: "SMA 200", color: "#8b5cf6" });
  }
  if (indicatorSettings.bbandsEnabled) legendItems.push({ label: "BB", color: "#94a3b8" });
  legendItems.push({ label: "Support", color: "#22c55e" });
  legendItems.push({ label: "Resistance", color: "#ef4444" });

  return (
    <div className="space-y-8">
      {/* Settings drawer */}
      <IndicatorSettingsDrawer
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        settings={indicatorSettings}
        onSettingsChange={setIndicatorSettings}
      />

      {/* Chart with overlays */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <SectionHeading>Price &amp; Indicators</SectionHeading>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Granularity</span>
            <GranularityToggle value={granularity} onChange={setGranularity} />
            <button
              onClick={() => setDrawerOpen(true)}
              aria-label="Open indicator settings"
              title="Indicator settings"
              className="ml-1 rounded p-1 text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            >
              ⚙
            </button>
          </div>
        </div>

        <TechnicalChart
          bars={bars}
          isLoading={barsLoading}
          overlays={overlays}
          subpanes={subpanes}
        />

        {/* Legend */}
        <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
          {legendItems.map((item) => (
            <span key={item.label} className="flex items-center gap-1">
              <span
                className="inline-block h-2 w-4 rounded-sm opacity-80"
                style={{ backgroundColor: item.color }}
              />
              {item.label}
            </span>
          ))}
        </div>
      </div>

      <Divider />

      {/* Score section */}
      <div className="space-y-3">
        {techLoading ? (
          <ScoreSkeleton />
        ) : techError ? (
          <p className="text-sm text-muted-foreground" role="alert">
            {techError}
          </p>
        ) : techData ? (
          <>
            <div className="flex items-center gap-3">
              <SectionHeading>Technical score</SectionHeading>
              <ScoreBadge
                score={score?.overall ?? null}
                label="Overall technical score"
                size="md"
              />
            </div>

            {hasInsufficientData ? (
              <p className="text-xs text-muted-foreground">
                Insufficient price history at this granularity to compute subscores.
              </p>
            ) : (
              <SubscoreChart
                value={score?.trend ?? null}
                quality={score?.momentum ?? null}
                growth={score?.mean_reversion ?? null}
                labels={["Trend", "Momentum", "Mean Rev."]}
              />
            )}

            <p className="text-xs text-muted-foreground">weights {score?.weights_version}</p>
            <DataAsOfBadge asOf={techData.data_as_of} />
          </>
        ) : null}
      </div>

      <Divider />

      {/* Support / Resistance levels */}
      <div className="space-y-3">
        <SectionHeading>Support &amp; Resistance</SectionHeading>

        {techLoading ? (
          <LevelsSkeleton />
        ) : techError ? null : techData && levels.length === 0 ? (
          <p className="text-xs text-muted-foreground">No levels detected.</p>
        ) : techData ? (
          <table className="w-full text-sm">
            <caption className="sr-only">Support and resistance price levels</caption>
            <thead>
              <tr className="border-b border-border">
                <th className="pb-1 text-left text-xs font-semibold text-muted-foreground">
                  Price
                </th>
                <th className="pb-1 text-left text-xs font-semibold text-muted-foreground">Kind</th>
                <th className="pb-1 text-right text-xs font-semibold text-muted-foreground">
                  Strength
                </th>
              </tr>
            </thead>
            <tbody>
              {levels.map((level, i) => (
                <LevelRow key={i} level={level} />
              ))}
            </tbody>
          </table>
        ) : null}
      </div>
    </div>
  );
}
