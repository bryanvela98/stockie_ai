/**
 * Description: Small badge that shows the freshness timestamp of price data.
 *              Renders "Data as of <human-readable date>" when a valid ISO
 *              datetime string is provided, or a dimmed "Data unavailable"
 *              fallback when the value is null, undefined, or unparseable.
 *              Compatible with both server and client rendering (no browser APIs used).
 * Last Modified By: despinoza
 * Created: 2026-06-11
 * Last Modified:
 *     2026-06-11 - File created; DataAsOf badge component.
 */

interface DataAsOfBadgeProps {
  asOf?: string | null;
}

/**
 * Renders a muted freshness badge for the supplied ISO datetime string.
 *
 * @param asOf - ISO 8601 datetime string (e.g. "2026-06-06T18:00:00Z"), or
 *               null/undefined when no data is available.
 */
export function DataAsOfBadge({ asOf }: DataAsOfBadgeProps) {
  if (!asOf) {
    return <p className="text-xs text-muted-foreground/50">Data unavailable</p>;
  }

  let formatted: string;
  try {
    formatted = new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      timeZoneName: "short",
    }).format(new Date(asOf));
  } catch {
    return <p className="text-xs text-muted-foreground/50">Data unavailable</p>;
  }

  return <p className="text-xs text-muted-foreground">Data as of {formatted}</p>;
}
