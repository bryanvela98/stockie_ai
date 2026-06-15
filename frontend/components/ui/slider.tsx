/**
 * Description: Accessible range slider primitive styled with Tailwind.
 *              Wraps a native <input type="range"> so keyboard navigation,
 *              screen-reader announcements, and all browser accessibility features
 *              work without extra ARIA wiring.
 *              Used by the DCF widget for growth-rate, discount-rate, terminal-growth,
 *              and projection-years controls.
 * Last Modified By: bvela
 * Created: 2026-06-15
 * Last Modified:
 *     2026-06-15 - File created; Slider primitive for DCF widget.
 */

import { cn } from "@/lib/utils";

interface SliderProps {
  id: string;
  label: string;
  min: number;
  max: number;
  step: number;
  value: number;
  onChange: (value: number) => void;
  /** Formats the displayed value label (e.g. "8.0 %" or "5 yrs"). */
  formatValue: (value: number) => string;
  className?: string;
}

/**
 * Labeled range slider that calls `onChange` with the numeric value on every change.
 *
 * @param id          - Unique id for the <input> (used to associate the <label>).
 * @param label       - Visible label text shown above the slider.
 * @param min         - Minimum allowed value.
 * @param max         - Maximum allowed value.
 * @param step        - Step increment.
 * @param value       - Controlled current value.
 * @param onChange    - Called with the new numeric value on every change event.
 * @param formatValue - Function that converts the numeric value to a display string.
 */
export function Slider({
  id,
  label,
  min,
  max,
  step,
  value,
  onChange,
  formatValue,
  className,
}: SliderProps) {
  return (
    <div className={cn("space-y-1", className)}>
      <div className="flex items-center justify-between">
        <label htmlFor={id} className="text-xs font-medium text-muted-foreground">
          {label}
        </label>
        <span className="text-xs font-semibold tabular-nums">{formatValue(value)}</span>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-muted accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1"
        aria-valuenow={value}
        aria-valuemin={min}
        aria-valuemax={max}
      />
    </div>
  );
}
