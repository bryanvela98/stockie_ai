/**
 * Description: A single row in the ticker search dropdown.
 *              Renders the exchange symbol (bold monospace), company name (muted),
 *              and two chips: asset type (color-coded) and exchange name.
 *              Accepts an onSelect callback so the parent (TickerSearchBar) owns
 *              navigation; this component is purely presentational.
 * Last Modified By: despinoza
 * Created: 2026-06-01
 * Last Modified:
 *     2026-06-01 - File created; TickerResultItem component.
 */

import { cn } from "@/lib/utils";
import type { components } from "@/lib/api/schema.d.ts";

type TickerSearchResult = components["schemas"]["TickerSearchResult"];

/** Map an asset_type value to a Tailwind colour pair for the chip. */
function assetTypeChipClass(assetType: string): string {
  switch (assetType.toUpperCase()) {
    case "EQUITY":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300";
    case "ETF":
      return "bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300";
    case "MUTUALFUND":
      return "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300";
    default:
      return "bg-muted text-muted-foreground";
  }
}

export interface TickerResultItemProps {
  ticker: TickerSearchResult;
  /** Whether this row is currently keyboard-highlighted. */
  highlighted: boolean;
  onSelect: (symbol: string) => void;
}

/**
 * Presentational row for a single ticker in the search dropdown.
 *
 * @param ticker - The ticker data to display.
 * @param highlighted - When true the row receives the `bg-accent` background.
 * @param onSelect - Called with the ticker symbol when the row is clicked.
 */
export function TickerResultItem({ ticker, highlighted, onSelect }: TickerResultItemProps) {
  return (
    <li
      role="option"
      aria-selected={highlighted}
      className={cn(
        "flex cursor-pointer items-center gap-3 px-4 py-2.5 text-sm",
        highlighted ? "bg-accent" : "hover:bg-accent/60",
      )}
      onMouseDown={(e) => {
        // Prevent the input from losing focus before onClick fires
        e.preventDefault();
        onSelect(ticker.symbol);
      }}
    >
      {/* Symbol */}
      <span className="w-14 shrink-0 font-mono font-semibold text-foreground">{ticker.symbol}</span>

      {/* Name */}
      <span className="min-w-0 flex-1 truncate text-muted-foreground">{ticker.name}</span>

      {/* Asset type chip + exchange */}
      <span className="flex shrink-0 items-center gap-1.5">
        <span
          className={cn(
            "rounded px-1.5 py-0.5 text-xs font-medium",
            assetTypeChipClass(ticker.asset_type),
          )}
        >
          {ticker.asset_type}
        </span>
        <span className="text-xs text-muted-foreground">{ticker.exchange}</span>
      </span>
    </li>
  );
}
