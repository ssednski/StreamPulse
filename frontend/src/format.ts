const intFormat = new Intl.NumberFormat("en-US");

export const formatInt = (n: number): string => intFormat.format(Math.round(n));

export const formatPercent = (ratio: number, digits = 1): string =>
  `${(ratio * 100).toFixed(digits)}%`;

export function formatMs(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)} s`;
  return `${Math.round(ms)} ms`;
}

export function formatClock(iso: string, withDate = false): string {
  const date = new Date(iso);
  const time = date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return withDate
    ? `${date.toLocaleDateString([], { month: "short", day: "numeric" })} ${time}`
    : time;
}

export function formatBitrate(kbps: number): string {
  return kbps >= 1000 ? `${(kbps / 1000).toFixed(1)} Mbps` : `${Math.round(kbps)} kbps`;
}
