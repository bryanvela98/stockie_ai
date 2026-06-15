/**
 * Description: Client component that provides "Price" | "Fundamentals" tab navigation
 *              for the ticker detail page. TickerPriceSection is dynamically imported
 *              with ssr:false because lightweight-charts requires the browser DOM.
 *              FundamentalsSection is a standard client island (no DOM-only deps).
 * Last Modified By: bvela
 * Created: 2026-06-15
 * Last Modified:
 *     2026-06-15 - File created; tab switcher for Price and Fundamentals sections.
 */

"use client";

import dynamic from "next/dynamic";
import { useState } from "react";

import { FundamentalsSection } from "@/components/fundamentals-section";
import { cn } from "@/lib/utils";

// ssr:false is required because lightweight-charts accesses window on module init.
const TickerPriceSection = dynamic(
  () =>
    import("@/components/ticker-price-section").then((m) => ({ default: m.TickerPriceSection })),
  { ssr: false },
);

type Tab = "price" | "fundamentals";

const TABS: { id: Tab; label: string }[] = [
  { id: "price", label: "Price" },
  { id: "fundamentals", label: "Fundamentals" },
];

interface TickerTabsProps {
  symbol: string;
}

/**
 * Tab bar + panel switcher for the ticker detail page.
 *
 * @param symbol - Ticker symbol forwarded to each section component.
 */
export function TickerTabs({ symbol }: TickerTabsProps) {
  const [activeTab, setActiveTab] = useState<Tab>("price");

  return (
    <div>
      {/* Tab list */}
      <div role="tablist" aria-label="Ticker sections" className="mb-6 flex border-b border-border">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            id={`tab-${tab.id}`}
            aria-selected={activeTab === tab.id}
            aria-controls={`panel-${tab.id}`}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "relative px-4 pb-3 pt-1 text-sm font-medium transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
              activeTab === tab.id
                ? "text-foreground after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:rounded-full after:bg-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab panels — keep both mounted to preserve chart state on switch */}
      <div
        role="tabpanel"
        id="panel-price"
        aria-labelledby="tab-price"
        hidden={activeTab !== "price"}
      >
        <TickerPriceSection symbol={symbol} />
      </div>
      <div
        role="tabpanel"
        id="panel-fundamentals"
        aria-labelledby="tab-fundamentals"
        hidden={activeTab !== "fundamentals"}
      >
        <FundamentalsSection symbol={symbol} />
      </div>
    </div>
  );
}
