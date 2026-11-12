import { useState } from "react";
import { Bar, BarChart, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { BreakdownRow } from "../api";
import { formatInt, formatMs, formatPercent } from "../format";

type MetricKey = "errorRate" | "avgStartupMs" | "adFillRate" | "sessions";

const METRICS: Record<MetricKey, { label: string; format: (n: number) => string }> = {
  errorRate: { label: "Error rate", format: (n) => formatPercent(n) },
  avgStartupMs: { label: "Avg start time", format: formatMs },
  adFillRate: { label: "Ad fill rate", format: (n) => formatPercent(n) },
  sessions: { label: "Sessions", format: formatInt },
};

interface Props {
  byDevice: BreakdownRow[];
  byCdn: BreakdownRow[];
}

export function BreakdownCard({ byDevice, byCdn }: Props) {
  const [dimension, setDimension] = useState<"device" | "cdn">("cdn");
  const [metric, setMetric] = useState<MetricKey>("errorRate");
  const [view, setView] = useState<"chart" | "table">("chart");

  const rows = [...(dimension === "cdn" ? byCdn : byDevice)].sort(
    (a, b) => b[metric] - a[metric],
  );
  const { format, label } = METRICS[metric];

  return (
    <section className="card" aria-label="Breakdown">
      <header className="card-head card-head-row">
        <div>
          <h3>Breakdown</h3>
          <p>Compare {dimension === "cdn" ? "CDNs" : "devices"} to localise a problem</p>
        </div>
        <div className="controls">
          <div className="segmented" role="group" aria-label="Dimension">
            {(["cdn", "device"] as const).map((d) => (
              <button
                key={d}
                aria-pressed={dimension === d}
                onClick={() => setDimension(d)}
                type="button"
              >
                {d === "cdn" ? "CDN" : "Device"}
              </button>
            ))}
          </div>
          <div className="segmented" role="group" aria-label="View">
            {(["chart", "table"] as const).map((v) => (
              <button key={v} aria-pressed={view === v} onClick={() => setView(v)} type="button">
                {v === "chart" ? "Chart" : "Table"}
              </button>
            ))}
          </div>
        </div>
      </header>

      {view === "chart" ? (
        <>
          <label className="select-row">
            Metric
            <select value={metric} onChange={(e) => setMetric(e.target.value as MetricKey)}>
              {Object.entries(METRICS).map(([key, m]) => (
                <option key={key} value={key}>
                  {m.label}
                </option>
              ))}
            </select>
          </label>
          <div className="chart" role="img" aria-label={`${label} by ${dimension}`}>
            <ResponsiveContainer width="100%" height={Math.max(rows.length, 1) * 38 + 16}>
              <BarChart
                data={rows}
                layout="vertical"
                margin={{ top: 4, right: 64, bottom: 4, left: 0 }}
              >
                <XAxis type="number" hide domain={[0, "dataMax"]} />
                <YAxis
                  type="category"
                  dataKey="key"
                  width={92}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
                />
                <Tooltip
                  cursor={{ fill: "var(--grid)", opacity: 0.5 }}
                  formatter={(v) => [format(Number(v)), label]}
                  contentStyle={{
                    background: "var(--surface)",
                    border: "1px solid var(--axis)",
                    borderRadius: 8,
                    color: "var(--text-primary)",
                  }}
                />
                <Bar
                  dataKey={metric}
                  fill="var(--series-1)"
                  radius={[0, 4, 4, 0]}
                  barSize={14}
                  isAnimationActive={false}
                >
                  <LabelList
                    dataKey={metric}
                    position="right"
                    formatter={(v: unknown) => format(Number(v))}
                    fill="var(--text-primary)"
                    fontSize={12}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>{dimension === "cdn" ? "CDN" : "Device"}</th>
              <th>Sessions</th>
              <th>Error rate</th>
              <th>Avg start</th>
              <th>Ad fill</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key}>
                <th scope="row">{r.key}</th>
                <td>{formatInt(r.sessions)}</td>
                <td>{formatPercent(r.errorRate)}</td>
                <td>{formatMs(r.avgStartupMs)}</td>
                <td>{formatPercent(r.adFillRate)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
