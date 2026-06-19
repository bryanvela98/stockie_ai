/**
 * Description: Bar-granularity type and label map for the technical analysis timeframe selector.
 *              "Granularity" controls the bar aggregation period sent to /tickers/{symbol}/technical
 *              and /tickers/{symbol}/indicators (?timeframe=). This is deliberately distinct from
 *              the price chart's Timeframe type (lib/types/timeframe.ts), which controls the date
 *              window shown; the two axes are orthogonal.
 * Last Modified By: bvela
 * Created: 2026-06-19
 * Last Modified:
 *     2026-06-19 - File created; Granularity union type + label map (Sprint 4-C2).
 */

/** Bar aggregation period accepted by the technical analysis endpoints. */
export type Granularity = "1d" | "1w" | "1mo";

export const GRANULARITIES: Granularity[] = ["1d", "1w", "1mo"];

export const GRANULARITY_LABELS: Record<Granularity, string> = {
  "1d": "Daily",
  "1w": "Weekly",
  "1mo": "Monthly",
};
