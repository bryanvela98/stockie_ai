/**
 * Description: Accessible indicator settings drawer for the Technicals tab. Renders as a
 *              native <dialog> (built-in focus trap, Esc-to-close) styled as a right-side
 *              panel. Controls which indicators are active and their periods, driving the
 *              /indicators query in TechnicalSection. Exports IndicatorSettings type and
 *              DEFAULT_INDICATOR_SETTINGS so TechnicalSection owns the state.
 * Last Modified By: bvela
 * Created: 2026-06-19
 * Last Modified:
 *     2026-06-19 - File created; IndicatorSettingsDrawer with checkboxes + period inputs (Sprint 4-C4).
 */

"use client";

import { useEffect, useRef } from "react";

export interface IndicatorSettings {
  smaEnabled: boolean;
  smaPeriods: string;
  emaEnabled: boolean;
  emaPeriods: string;
  bbandsEnabled: boolean;
  bbandsPeriod: number;
  rsiEnabled: boolean;
  rsiPeriod: number;
  macdEnabled: boolean;
}

export const DEFAULT_INDICATOR_SETTINGS: IndicatorSettings = {
  smaEnabled: true,
  smaPeriods: "50,200",
  emaEnabled: false,
  emaPeriods: "12,26",
  bbandsEnabled: false,
  bbandsPeriod: 20,
  rsiEnabled: true,
  rsiPeriod: 14,
  macdEnabled: true,
};

interface IndicatorSettingsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  settings: IndicatorSettings;
  onSettingsChange: (s: IndicatorSettings) => void;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

interface CheckRowProps {
  id: string;
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  children?: React.ReactNode;
}

function CheckRow({ id, label, checked, onChange, children }: CheckRowProps) {
  return (
    <div className="space-y-1.5 rounded-md border border-border p-3">
      <label className="flex cursor-pointer items-center gap-2 text-sm font-medium" htmlFor={id}>
        <input
          id={id}
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="h-4 w-4 rounded accent-foreground"
        />
        {label}
      </label>
      {checked && children && <div className="ml-6 space-y-1.5">{children}</div>}
    </div>
  );
}

interface PeriodInputProps {
  id: string;
  label: string;
  value: string | number;
  onChange: (value: string) => void;
  placeholder?: string;
}

function PeriodInput({ id, label, value, onChange, placeholder }: PeriodInputProps) {
  return (
    <div className="flex items-center gap-2">
      <label htmlFor={id} className="min-w-[80px] text-xs text-muted-foreground">
        {label}
      </label>
      <input
        id={id}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-24 rounded border border-border bg-background px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
      />
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

/**
 * Side-panel drawer for configuring active indicators and their periods.
 *
 * @param isOpen           - Whether the drawer is visible.
 * @param onClose          - Called when the user closes the drawer (X button or Esc).
 * @param settings         - Current indicator settings.
 * @param onSettingsChange - Called with the updated settings object on any change.
 */
export function IndicatorSettingsDrawer({
  isOpen,
  onClose,
  settings,
  onSettingsChange,
}: IndicatorSettingsDrawerProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  // Sync open/close state with the native dialog element.
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (isOpen) {
      if (!dialog.open) dialog.showModal();
    } else {
      if (dialog.open) dialog.close();
    }
  }, [isOpen]);

  // Sync the native "cancel" event (Esc key) back to React state.
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    const handleCancel = () => onClose();
    dialog.addEventListener("cancel", handleCancel);
    return () => dialog.removeEventListener("cancel", handleCancel);
  }, [onClose]);

  function update(patch: Partial<IndicatorSettings>) {
    onSettingsChange({ ...settings, ...patch });
  }

  return (
    <dialog
      ref={dialogRef}
      aria-label="Indicator settings"
      className="fixed right-0 top-0 m-0 h-full w-80 max-w-full border-l border-border bg-background p-0 shadow-xl backdrop:bg-black/40"
      onClick={(e) => {
        // Close if the backdrop (::backdrop) is clicked — dialog element itself is the backdrop.
        if (e.target === dialogRef.current) onClose();
      }}
    >
      <div className="flex h-full flex-col overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="text-sm font-semibold">Indicator settings</h2>
          <button
            onClick={onClose}
            aria-label="Close indicator settings"
            className="rounded p-1 text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          >
            ✕
          </button>
        </div>

        {/* Controls */}
        <div className="flex-1 space-y-3 p-4">
          {/* SMA */}
          <CheckRow
            id="ind-sma"
            label="SMA"
            checked={settings.smaEnabled}
            onChange={(v) => update({ smaEnabled: v })}
          >
            <PeriodInput
              id="sma-periods"
              label="Periods"
              value={settings.smaPeriods}
              onChange={(v) => update({ smaPeriods: v })}
              placeholder="e.g. 50,200"
            />
          </CheckRow>

          {/* EMA */}
          <CheckRow
            id="ind-ema"
            label="EMA"
            checked={settings.emaEnabled}
            onChange={(v) => update({ emaEnabled: v })}
          >
            <PeriodInput
              id="ema-periods"
              label="Periods"
              value={settings.emaPeriods}
              onChange={(v) => update({ emaPeriods: v })}
              placeholder="e.g. 12,26"
            />
          </CheckRow>

          {/* Bollinger Bands */}
          <CheckRow
            id="ind-bbands"
            label="Bollinger Bands"
            checked={settings.bbandsEnabled}
            onChange={(v) => update({ bbandsEnabled: v })}
          >
            <PeriodInput
              id="bbands-period"
              label="Period"
              value={settings.bbandsPeriod}
              onChange={(v) => update({ bbandsPeriod: parseInt(v, 10) || settings.bbandsPeriod })}
              placeholder="20"
            />
          </CheckRow>

          {/* RSI */}
          <CheckRow
            id="ind-rsi"
            label="RSI"
            checked={settings.rsiEnabled}
            onChange={(v) => update({ rsiEnabled: v })}
          >
            <PeriodInput
              id="rsi-period"
              label="Period"
              value={settings.rsiPeriod}
              onChange={(v) => update({ rsiPeriod: parseInt(v, 10) || settings.rsiPeriod })}
              placeholder="14"
            />
          </CheckRow>

          {/* MACD */}
          <CheckRow
            id="ind-macd"
            label="MACD"
            checked={settings.macdEnabled}
            onChange={(v) => update({ macdEnabled: v })}
          >
            <p className="text-xs text-muted-foreground">12 / 26 / 9 (fixed)</p>
          </CheckRow>
        </div>

        {/* Footer */}
        <div className="border-t border-border px-4 py-3">
          <button
            onClick={onClose}
            className="w-full rounded-md bg-foreground px-3 py-1.5 text-sm font-medium text-background hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-ring"
          >
            Done
          </button>
        </div>
      </div>
    </dialog>
  );
}
