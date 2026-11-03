const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
});

const currencyFormatterCompact = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

export function formatCurrency(value: number, compact = false): string {
  return compact ? currencyFormatterCompact.format(value) : currencyFormatter.format(value);
}

export function formatSignedCurrency(value: number): string {
  const formatted = formatCurrency(Math.abs(value));
  return value < 0 ? `−${formatted}` : `+${formatted}`;
}

const currencyFormatterAbbreviated = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 1,
});

/**
 * For tight spaces like a small map tile, e.g. "+$3.8K" or "+$138". Pair it with
 * the exact figure elsewhere. Under $1,000 it rounds to whole dollars, since
 * "$137.5" reads like a mistake rather than an abbreviation.
 */
export function formatSignedCurrencyAbbreviated(value: number): string {
  const size = Math.abs(value);
  const formatted =
    size < 1000 ? currencyFormatterCompact.format(size) : currencyFormatterAbbreviated.format(size);
  return value < 0 ? `−${formatted}` : `+${formatted}`;
}

export function formatPercent(value: number, digits = 2): string {
  return `${value.toFixed(digits)}%`;
}

export function formatSignedPercent(value: number, digits = 2): string {
  const formatted = formatPercent(Math.abs(value), digits);
  return value < 0 ? `−${formatted}` : `+${formatted}`;
}

export function formatAsOf(iso: string): string {
  const date = new Date(iso);
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  }).format(date);
}

/**
 * For date-only values (e.g. a filing date, no time-of-day component).
 * Formats in UTC so a plain "YYYY-MM-DD" string -- parsed as UTC
 * midnight -- doesn't roll back a day in timezones behind UTC.
 */
export function formatDate(isoDate: string): string {
  const date = new Date(isoDate);
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

export function formatRelativeToNow(iso: string, nowIso: string): string {
  const then = new Date(iso).getTime();
  const now = new Date(nowIso).getTime();
  const diffMs = now - then;
  const diffHours = Math.round(diffMs / (1000 * 60 * 60));
  if (diffHours < 1) return "just now";
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.round(diffHours / 24);
  return `${diffDays}d ago`;
}
