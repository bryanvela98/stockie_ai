/**
 * Description: Horizontal bar chart visualising the three fundamental subscores
 *              (Value / Quality / Growth). Each bar uses the same color thresholds as
 *              ScoreBadge so the visual language is consistent across the app.
 *              Handles null subscores gracefully — the bar is absent and the label
 *              shows a muted dash.
 * Last Modified By: bvela
 * Created: 2026-06-15
 * Last Modified:
 *     2026-06-15 - File created; SubscoreChart with colour-coded horizontal bars.
 */

import { cn } from "@/lib/utils";
import { SCORE_HIGH, SCORE_LOW } from "@/components/score-badge";

interface SubscoreChartProps {
  value: number | null;
  quality: number | null;
  growth: number | null;
}

interface BarRowProps {
  label: string;
  score: number | null;
}

function barColor(score: number): string {
  if (score >= SCORE_HIGH) return "bg-green-500 dark:bg-green-400";
  if (score >= SCORE_LOW) return "bg-amber-400 dark:bg-amber-300";
  return "bg-red-500 dark:bg-red-400";
}

/**
 * A single labeled horizontal bar row for one subscore.
 */
function BarRow({ label, score }: BarRowProps) {
  const pct = score !== null ? Math.max(0, Math.min(100, Math.round(score))) : 0;

  return (
    <div className="flex items-center gap-3">
      <span className="w-16 shrink-0 text-right text-xs font-medium text-muted-foreground">
        {label}
      </span>

      <div
        className="relative h-4 flex-1 overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-valuenow={score ?? 0}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${label} score: ${score !== null ? pct : "not available"}`}
      >
        {score !== null && (
          <div
            className={cn("h-full rounded-full transition-[width] duration-300", barColor(pct))}
            style={{ width: `${pct}%` }}
          />
        )}
      </div>

      <span
        className={cn(
          "w-8 shrink-0 text-xs font-semibold tabular-nums",
          score === null
            ? "text-muted-foreground"
            : pct >= SCORE_HIGH
              ? "text-green-700 dark:text-green-400"
              : pct >= SCORE_LOW
                ? "text-amber-700 dark:text-amber-300"
                : "text-red-700 dark:text-red-400",
        )}
      >
        {score !== null ? pct : "—"}
      </span>
    </div>
  );
}

/**
 * Renders Value, Quality, and Growth subscores as stacked horizontal bars.
 *
 * @param value   - Value subscore (0–100) or null.
 * @param quality - Quality subscore (0–100) or null.
 * @param growth  - Growth subscore (0–100) or null.
 */
export function SubscoreChart({ value, quality, growth }: SubscoreChartProps) {
  return (
    <div className="space-y-3" aria-label="Fundamental subscores">
      <BarRow label="Value" score={value} />
      <BarRow label="Quality" score={quality} />
      <BarRow label="Growth" score={growth} />
    </div>
  );
}
