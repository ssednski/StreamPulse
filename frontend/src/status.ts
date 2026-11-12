export type Status = "good" | "warning" | "critical";

// Thresholds are deliberately simple and mirrored by the Prometheus alert rules
// in observability/prometheus/alerts.yml.
export const errorRateStatus = (rate: number): Status =>
  rate >= 0.05 ? "critical" : rate >= 0.02 ? "warning" : "good";

export const startupStatus = (ms: number): Status =>
  ms >= 4000 ? "critical" : ms >= 2500 ? "warning" : "good";

export const adFillStatus = (rate: number, requests: number): Status => {
  if (requests === 0) return "good";
  return rate < 0.8 ? "critical" : rate < 0.9 ? "warning" : "good";
};

export const rebufferStatus = (ratio: number): Status =>
  ratio >= 0.02 ? "critical" : ratio >= 0.01 ? "warning" : "good";

// Status always ships as icon + word, never colour alone.
export const STATUS_LABEL: Record<Status, { icon: string; text: string }> = {
  good: { icon: "✓", text: "Healthy" },
  warning: { icon: "▲", text: "Watch" },
  critical: { icon: "✕", text: "Degraded" },
};
