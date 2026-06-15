/**
 * Description: Reusable 0–100 score badge used across Fundamental, Technical, and
 *              Sentiment modules. Color band thresholds (documented here as the
 *              single source of truth):
 *                green  ≥ 70  — strong
 *                amber  40–69 — moderate
 *                red    < 40  — weak
 *              A null score renders a muted "—" placeholder instead of 0 or NaN.
 * Last Modified By: bvela
 * Created: 2026-06-15
 * Last Modified:
 *     2026-06-15 - File created; ScoreBadge with color bands and null safety.
 */

import { cn } from "@/lib/utils";

// Thresholds are exported so consumers can reuse the same color logic.
export const SCORE_HIGH = 70;
export const SCORE_LOW = 40;

type ScoreSize = "sm" | "md";

interface ScoreBadgeProps {
  score: number | null;
  label?: string;
  size?: ScoreSize;
  className?: string;
}

function scoreColorClasses(score: number): string {
  if (score >= SCORE_HIGH) {
    return "bg-green-100 text-green-800 ring-green-600/20 dark:bg-green-900/40 dark:text-green-300";
  }
  if (score >= SCORE_LOW) {
    return "bg-amber-100 text-amber-800 ring-amber-600/20 dark:bg-amber-900/40 dark:text-amber-300";
  }
  return "bg-red-100 text-red-800 ring-red-600/20 dark:bg-red-900/40 dark:text-red-300";
}

function scoreCategory(score: number): "strong" | "moderate" | "weak" {
  if (score >= SCORE_HIGH) return "strong";
  if (score >= SCORE_LOW) return "moderate";
  return "weak";
}

const SIZE_CLASSES: Record<ScoreSize, string> = {
  sm: "px-1.5 py-0.5 text-xs",
  md: "px-2 py-1 text-sm",
};

/**
 * Color-coded badge displaying a 0–100 fundamental (or other) score.
 *
 * @param score  - Score value 0–100, or null when data is unavailable.
 * @param label  - Optional accessible label prefix (e.g. "Overall score").
 * @param size   - Badge size: "sm" (default) or "md".
 */
export function ScoreBadge({ score, label, size = "sm", className }: ScoreBadgeProps) {
  if (score === null || score === undefined) {
    return (
      <span
        aria-label={label ? `${label}: not available` : "Score not available"}
        className={cn(
          "inline-flex items-center rounded ring-1 ring-inset font-medium tabular-nums",
          "bg-muted text-muted-foreground ring-muted-foreground/20",
          SIZE_CLASSES[size],
          className,
        )}
      >
        —
      </span>
    );
  }

  const clamped = Math.max(0, Math.min(100, Math.round(score)));
  const category = scoreCategory(clamped);

  return (
    <span
      aria-label={
        label
          ? `${label}: ${clamped} out of 100, ${category}`
          : `${clamped} out of 100, ${category}`
      }
      className={cn(
        "inline-flex items-center rounded ring-1 ring-inset font-medium tabular-nums",
        scoreColorClasses(clamped),
        SIZE_CLASSES[size],
        className,
      )}
    >
      {clamped}
    </span>
  );
}
