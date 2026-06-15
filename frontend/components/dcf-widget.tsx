/**
 * Description: Interactive DCF (Discounted Cash Flow) widget that lets the user
 *              adjust growth assumptions via sliders and sees the intrinsic value
 *              per share update live.
 *
 *              Slider state is debounced ~250 ms before calling the backend, keeping
 *              the UI responsive without hammering the endpoint on every pixel of drag.
 *              The invalid assumption terminal_growth >= discount_rate is caught
 *              client-side and surfaces an inline message without making a network call.
 *
 *              Per-year projected vs discounted FCF is displayed as proportional CSS bars
 *              (no additional chart library required).
 * Last Modified By: bvela
 * Created: 2026-06-15
 * Last Modified:
 *     2026-06-15 - File created; DCF widget with debounced sliders and FCF bar chart.
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Slider } from "@/components/ui/slider";
import { apiClient } from "@/lib/api";
import type { components } from "@/lib/api/schema.d.ts";
import { cn } from "@/lib/utils";

type DcfResponse = components["schemas"]["DcfResponse"];
type DcfYearItem = components["schemas"]["DcfYearItem"];

interface DcfWidgetProps {
  symbol: string;
}

interface DcfParams {
  growthRate: number;
  discountRate: number;
  terminalGrowth: number;
  years: number;
}

const DEBOUNCE_MS = 250;

const DEFAULT_PARAMS: DcfParams = {
  growthRate: 0.08,
  discountRate: 0.1,
  terminalGrowth: 0.03,
  years: 5,
};

function formatPct(val: number): string {
  return `${(val * 100).toFixed(1)} %`;
}

function formatYears(val: number): string {
  return `${val} yr${val === 1 ? "" : "s"}`;
}

function formatCurrency(val: number): string {
  if (Math.abs(val) >= 1e12) return `$${(val / 1e12).toFixed(2)}T`;
  if (Math.abs(val) >= 1e9) return `$${(val / 1e9).toFixed(2)}B`;
  if (Math.abs(val) >= 1e6) return `$${(val / 1e6).toFixed(2)}M`;
  return `$${val.toFixed(2)}`;
}

function FcfBarChart({ items }: { items: DcfYearItem[] }) {
  const maxFcf = Math.max(...items.map((y) => y.projected_fcf), 1);

  return (
    <div className="space-y-1.5" aria-label="FCF projection by year">
      {items.map((y) => {
        const projPct = (y.projected_fcf / maxFcf) * 100;
        const discPct = (y.discounted_fcf / maxFcf) * 100;

        return (
          <div key={y.year} className="flex items-center gap-2">
            <span className="w-8 shrink-0 text-right text-xs text-muted-foreground">
              Yr {y.year}
            </span>
            <div
              className="relative h-4 flex-1 overflow-hidden rounded bg-muted"
              title={`Year ${y.year}: projected ${formatCurrency(y.projected_fcf)}, discounted ${formatCurrency(y.discounted_fcf)}`}
            >
              {/* projected FCF (lighter background layer) */}
              <div
                className="absolute inset-y-0 left-0 rounded bg-primary/20"
                style={{ width: `${projPct}%` }}
              />
              {/* discounted FCF (darker foreground layer) */}
              <div
                className="absolute inset-y-0 left-0 rounded bg-primary/60"
                style={{ width: `${discPct}%` }}
              />
            </div>
            <span className="w-16 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
              {formatCurrency(y.discounted_fcf)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/**
 * Interactive DCF widget with adjustable assumption sliders.
 *
 * @param symbol - Ticker symbol used to call the DCF endpoint.
 */
export function DcfWidget({ symbol }: DcfWidgetProps) {
  const [params, setParams] = useState<DcfParams>(DEFAULT_PARAMS);
  const [result, setResult] = useState<DcfResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isInvalid = params.terminalGrowth >= params.discountRate;

  const fetchDcf = useCallback(
    async (p: DcfParams) => {
      if (p.terminalGrowth >= p.discountRate) return;

      setIsLoading(true);
      setError(null);

      const { data, error: apiError } = await apiClient.GET("/tickers/{symbol}/dcf", {
        params: {
          path: { symbol },
          query: {
            growth_rate: p.growthRate,
            discount_rate: p.discountRate,
            terminal_growth: p.terminalGrowth,
            years: p.years,
          },
        },
      });

      if (apiError || !data) {
        setError("Could not compute DCF — check that annual statements exist for this ticker.");
      } else {
        setResult(data);
      }
      setIsLoading(false);
    },
    [symbol],
  );

  // Debounce slider changes before calling the API.
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => void fetchDcf(params), DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [params, fetchDcf]);

  function updateParam(key: keyof DcfParams, value: number) {
    setParams((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <div className="space-y-5">
      {/* Sliders */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Slider
          id="dcf-growth"
          label="Growth rate"
          min={0}
          max={0.5}
          step={0.005}
          value={params.growthRate}
          onChange={(v) => updateParam("growthRate", v)}
          formatValue={formatPct}
        />
        <Slider
          id="dcf-discount"
          label="Discount rate (WACC)"
          min={0.03}
          max={0.3}
          step={0.005}
          value={params.discountRate}
          onChange={(v) => updateParam("discountRate", v)}
          formatValue={formatPct}
        />
        <Slider
          id="dcf-terminal"
          label="Terminal growth"
          min={0}
          max={0.1}
          step={0.005}
          value={params.terminalGrowth}
          onChange={(v) => updateParam("terminalGrowth", v)}
          formatValue={formatPct}
        />
        <Slider
          id="dcf-years"
          label="Projection years"
          min={1}
          max={15}
          step={1}
          value={params.years}
          onChange={(v) => updateParam("years", v)}
          formatValue={formatYears}
        />
      </div>

      {/* Validation error */}
      {isInvalid && (
        <p className="text-sm text-destructive" role="alert">
          Terminal growth rate must be less than the discount rate.
        </p>
      )}

      {/* API error */}
      {!isInvalid && error && (
        <p className="text-sm text-muted-foreground" role="alert">
          {error}
        </p>
      )}

      {/* Results */}
      {!isInvalid && result && (
        <div className={cn("space-y-4 transition-opacity", isLoading && "opacity-50")}>
          {/* Key figures */}
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-xs text-muted-foreground">Intrinsic / share</dt>
              <dd className="mt-0.5 text-lg font-bold tabular-nums">
                {result.intrinsic_value_per_share !== null &&
                result.intrinsic_value_per_share !== undefined
                  ? `$${result.intrinsic_value_per_share.toFixed(2)}`
                  : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Enterprise value</dt>
              <dd className="mt-0.5 font-medium tabular-nums">
                {formatCurrency(result.enterprise_value)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Equity value</dt>
              <dd className="mt-0.5 font-medium tabular-nums">
                {formatCurrency(result.equity_value)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Terminal value</dt>
              <dd className="mt-0.5 font-medium tabular-nums">
                {formatCurrency(result.terminal_value)}
              </dd>
            </div>
          </dl>

          {/* Per-year FCF bars */}
          {result.yearly_fcf.length > 0 && (
            <div>
              <p className="mb-2 text-xs text-muted-foreground">
                Per-year FCF — light bar: projected, dark bar: discounted (PV)
              </p>
              <FcfBarChart items={result.yearly_fcf} />
            </div>
          )}
        </div>
      )}

      {/* Loading overlay when no result yet */}
      {!isInvalid && isLoading && !result && (
        <div className="flex h-24 items-center justify-center">
          <span className="text-sm text-muted-foreground">Computing…</span>
        </div>
      )}
    </div>
  );
}
