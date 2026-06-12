/**
 * Description: Timeframe type and date-range helper for the price chart toggle.
 *              Defines the seven chart window options visible in the UI and a
 *              pure function that converts each option to an absolute ISO date
 *              range relative to today.
 * Last Modified By: despinoza
 * Created: 2026-06-11
 * Last Modified:
 *     2026-06-11 - File created; Timeframe union type and timeframeToDateRange helper.
 */

export type Timeframe = "1D" | "1W" | "1M" | "3M" | "1Y" | "5Y" | "Max";

export const TIMEFRAMES: Timeframe[] = ["1D", "1W", "1M", "3M", "1Y", "5Y", "Max"];

/**
 * Converts a UI timeframe label into an absolute ISO date range.
 *
 * @param tf - One of the supported timeframe labels.
 * @returns An object with `from` and `to` as ISO date strings (YYYY-MM-DD),
 *          where `to` is always today and `from` is `today - window`.
 */
export function timeframeToDateRange(tf: Timeframe): { from: string; to: string } {
  const to = new Date();
  const from = new Date(to);

  switch (tf) {
    case "1D":
      from.setDate(from.getDate() - 1);
      break;
    case "1W":
      from.setDate(from.getDate() - 7);
      break;
    case "1M":
      from.setMonth(from.getMonth() - 1);
      break;
    case "3M":
      from.setMonth(from.getMonth() - 3);
      break;
    case "1Y":
      from.setFullYear(from.getFullYear() - 1);
      break;
    case "5Y":
      from.setFullYear(from.getFullYear() - 5);
      break;
    case "Max":
      // 20 years of history — the backend caps at 2000 bars server-side.
      from.setFullYear(from.getFullYear() - 20);
      break;
  }

  return {
    from: from.toISOString().slice(0, 10),
    to: to.toISOString().slice(0, 10),
  };
}
