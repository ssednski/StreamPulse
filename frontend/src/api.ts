export interface Kpis {
  sessions: number;
  errors: number;
  errorRate: number;
  adRequests: number;
  adImpressions: number;
  adFillRate: number;
  avgStartupMs: number;
  rebufferRatio: number;
}

export interface Summary extends Kpis {
  p95StartupMs: number;
  avgBitrateKbps: number;
}

export interface TimePoint extends Kpis {
  ts: string;
}

export interface BreakdownRow extends Kpis {
  key: string;
}

export interface ErrorCount {
  errorCode: string;
  count: number;
}

export interface DashboardData {
  summary: Summary;
  timeseries: TimePoint[];
  byDevice: BreakdownRow[];
  byCdn: BreakdownRow[];
  topErrors: ErrorCount[];
}

export interface WindowOption {
  label: string;
  minutes: number;
  stepMinutes: number;
}

export const WINDOWS: WindowOption[] = [
  { label: "15 min", minutes: 15, stepMinutes: 1 },
  { label: "1 hour", minutes: 60, stepMinutes: 5 },
  { label: "6 hours", minutes: 360, stepMinutes: 15 },
  { label: "24 hours", minutes: 1440, stepMinutes: 60 },
];

const KPI_FIELDS = `sessions errors errorRate adRequests adImpressions adFillRate avgStartupMs rebufferRatio`;

// One round trip fetches everything the dashboard shows.
export const DASHBOARD_QUERY = `
query Dashboard($w: Int!, $step: Int!) {
  summary(windowMinutes: $w) { ${KPI_FIELDS} p95StartupMs avgBitrateKbps }
  timeseries(windowMinutes: $w, stepMinutes: $step) { ts ${KPI_FIELDS} }
  byDevice: breakdown(dimension: DEVICE, windowMinutes: $w) { key ${KPI_FIELDS} }
  byCdn: breakdown(dimension: CDN, windowMinutes: $w) { key ${KPI_FIELDS} }
  topErrors(windowMinutes: $w, limit: 5) { errorCode count }
}`;

export class ApiError extends Error {}

export async function fetchDashboard(
  window: WindowOption,
  signal?: AbortSignal,
): Promise<DashboardData> {
  const response = await fetch("/graphql", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query: DASHBOARD_QUERY,
      variables: { w: window.minutes, step: window.stepMinutes },
    }),
    signal,
  });
  if (!response.ok) {
    throw new ApiError(`API responded with HTTP ${response.status}`);
  }
  const body = await response.json();
  if (body.errors?.length) {
    throw new ApiError(body.errors[0].message);
  }
  return body.data as DashboardData;
}
