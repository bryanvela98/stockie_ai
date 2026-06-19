/**
 * Description: Segmented control for selecting bar granularity (Daily / Weekly / Monthly)
 *              on the Technicals tab. Controls the ?timeframe= parameter sent to the technical
 *              analysis and indicators endpoints. Modelled on timeframe-toggle.tsx but distinct —
 *              this selects aggregation period, not the chart date window.
 * Last Modified By: bvela
 * Created: 2026-06-19
 * Last Modified:
 *     2026-06-19 - File created; GranularityToggle component (Sprint 4-C2).
 */

"use client";

import { Button } from "@/components/ui/button";
import { GRANULARITIES, GRANULARITY_LABELS, type Granularity } from "@/lib/types/granularity";

interface GranularityToggleProps {
  value: Granularity;
  onChange: (g: Granularity) => void;
}

/**
 * A segmented control that lets the user select the bar aggregation period.
 *
 * @param value    - Currently selected granularity.
 * @param onChange - Called with the new granularity when the user clicks a button.
 */
export function GranularityToggle({ value, onChange }: GranularityToggleProps) {
  return (
    <div className="flex gap-1" role="group" aria-label="Bar granularity">
      {GRANULARITIES.map((g) => (
        <Button
          key={g}
          size="xs"
          variant={g === value ? "default" : "ghost"}
          onClick={() => onChange(g)}
          aria-pressed={g === value}
        >
          {GRANULARITY_LABELS[g]}
        </Button>
      ))}
    </div>
  );
}
