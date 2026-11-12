import { useState } from "react";
import { WINDOWS } from "./api";
import { BreakdownCard } from "./components/BreakdownCard";
import { LineChartCard } from "./components/LineChartCard";
import { StatTile } from "./components/StatTile";
import { TopErrors } from "./components/TopErrors";
import { trimPartialBuckets } from "./series";
import { formatBitrate, formatClock, formatInt, formatMs, formatPercent } from "./format";
import {
  adFillStatus,
  errorRateStatus,
  rebufferStatus,
  startupStatus,
  type Status,
} from "./status";
import { useDashboard } from "./useDashboard";

const worst = (...statuses: Status[]): Status =>
  statuses.includes("critical") ? "critical" : statuses.includes("warning") ? "warning" : "good";

export default function App() {
  const [windowIndex, setWindowIndex] = useState(1);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [view, setView] = useState<"charts" | "table">("charts");
  const window = WINDOWS[windowIndex];
  const { data, error, loading, updatedAt } = useDashboard(window, autoRefresh);

  const summary = data?.summary;
  const chartPoints = data ? trimPartialBuckets(data.timeseries) : [];
  const overall = summary
    ? worst(
        errorRateStatus(summary.errorRate),
        startupStatus(summary.avgStartupMs),
        adFillStatus(summary.adFillRate, summary.adRequests),
        rebufferStatus(summary.rebufferRatio),
      )
    : "good";

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <h1>StreamPulse</h1>
          <p className="subtitle">Playback quality and ad delivery</p>
        </div>
        <div className="controls">
          <div className="segmented" role="group" aria-label="Time window">
            {WINDOWS.map((w, i) => (
              <button
                key={w.minutes}
                aria-pressed={i === windowIndex}
                onClick={() => setWindowIndex(i)}
                type="button"
              >
                {w.label}
              </button>
            ))}
          </div>
          <label className="toggle">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            Auto-refresh
          </label>
          <span className="updated" aria-live="polite">
            {updatedAt ? `Updated ${formatClock(updatedAt.toISOString())}` : "Loading…"}
          </span>
        </div>
      </header>

      {error && (
        <div className="banner banner-critical" role="alert">
          <span aria-hidden="true">✕</span> Could not load data: {error}
        </div>
      )}
      {summary && overall !== "good" && (
        <div className={`banner banner-${overall}`} role="status">
          <span aria-hidden="true">{overall === "critical" ? "✕" : "▲"}</span>{" "}
          {overall === "critical" ? "Service quality is degraded" : "Some metrics need attention"}{" "}
          — check the CDN breakdown below.
        </div>
      )}

      {loading && !data && <p className="empty">Loading dashboard…</p>}

      {summary && data && (
        <>
          <div className="tiles">
            <StatTile
              label="Sessions"
              value={formatInt(summary.sessions)}
              detail={`${formatBitrate(summary.avgBitrateKbps)} avg bitrate`}
            />
            <StatTile
              label="Error rate"
              value={formatPercent(summary.errorRate)}
              status={errorRateStatus(summary.errorRate)}
              detail={`${formatInt(summary.errors)} errors`}
            />
            <StatTile
              label="Avg start time"
              value={formatMs(summary.avgStartupMs)}
              status={startupStatus(summary.avgStartupMs)}
              detail={`p95 ${formatMs(summary.p95StartupMs)}`}
            />
            <StatTile
              label="Ad fill rate"
              value={formatPercent(summary.adFillRate)}
              status={adFillStatus(summary.adFillRate, summary.adRequests)}
              detail={`${formatInt(summary.adImpressions)} of ${formatInt(summary.adRequests)}`}
            />
            <StatTile
              label="Rebuffer ratio"
              value={formatPercent(summary.rebufferRatio, 2)}
              status={rebufferStatus(summary.rebufferRatio)}
              detail="stall time / watch time"
            />
          </div>

          <div className="section-head">
            <h2>Trends</h2>
            <div className="segmented" role="group" aria-label="Trend view">
              {(["charts", "table"] as const).map((v) => (
                <button key={v} aria-pressed={view === v} onClick={() => setView(v)} type="button">
                  {v === "charts" ? "Charts" : "Table"}
                </button>
              ))}
            </div>
          </div>

          {view === "charts" ? (
            <div className="grid-2">
              <LineChartCard
                title="Sessions"
                subtitle={`Started per ${window.stepMinutes} min (partial edge buckets hidden)`}
                data={chartPoints}
                value={(p) => p.sessions}
                format={formatInt}
              />
              <LineChartCard
                title="Error rate"
                subtitle="Errors per session started"
                data={chartPoints}
                value={(p) => p.errorRate}
                format={(n) => formatPercent(n)}
              />
              <LineChartCard
                title="Avg start time"
                subtitle="Time to first frame"
                data={chartPoints}
                value={(p) => p.avgStartupMs}
                format={formatMs}
              />
              <LineChartCard
                title="Ad fill rate"
                subtitle="Impressions per ad request"
                data={chartPoints}
                value={(p) => p.adFillRate}
                format={(n) => formatPercent(n, 0)}
                domain={[0, 1]}
              />
            </div>
          ) : (
            <div className="card table-scroll">
              <table className="table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Sessions</th>
                    <th>Error rate</th>
                    <th>Avg start</th>
                    <th>Ad fill</th>
                  </tr>
                </thead>
                <tbody>
                  {[...data.timeseries].reverse().map((p) => (
                    <tr key={p.ts}>
                      <th scope="row">{formatClock(p.ts, true)}</th>
                      <td>{formatInt(p.sessions)}</td>
                      <td>{formatPercent(p.errorRate)}</td>
                      <td>{formatMs(p.avgStartupMs)}</td>
                      <td>{formatPercent(p.adFillRate)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="grid-2">
            <BreakdownCard byDevice={data.byDevice} byCdn={data.byCdn} />
            <TopErrors errors={data.topErrors} />
          </div>
        </>
      )}
    </div>
  );
}
