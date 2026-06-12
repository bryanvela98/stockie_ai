/**
 * Description: Timeframe toggle bar for the price chart.
 *              Renders seven buttons (1D / 1W / 1M / 3M / 1Y / 5Y / Max)
 *              that control the date window fed to the prices API endpoint.
 *              The active button is visually highlighted using the `default`
 *              Button variant; inactive buttons use the `ghost` variant.
 * Last Modified By: despinoza
 * Created: 2026-06-11
 * Last Modified:
 *     2026-06-11 - File created; TimeframeToggle component.
 */

"use client";

import { Button } from "@/components/ui/button";
import { TIMEFRAMES, type Timeframe } from "@/lib/types/timeframe";

interface TimeframeToggleProps {
  value: Timeframe;
  onChange: (tf: Timeframe) => void;
}

/**
 * A segmented control that lets the user pick a chart date-window.
 *
 * @param value - The currently selected timeframe.
 * @param onChange - Called with the new timeframe when the user clicks a button.
 */
export function TimeframeToggle({ value, onChange }: TimeframeToggleProps) {
  return (
    <div className="flex flex-wrap gap-1" role="group" aria-label="Chart timeframe">
      {TIMEFRAMES.map((tf) => (
        <Button
          key={tf}
          size="xs"
          variant={tf === value ? "default" : "ghost"}
          onClick={() => onChange(tf)}
          aria-pressed={tf === value}
        >
          {tf}
        </Button>
      ))}
    </div>
  );
}
