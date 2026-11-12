import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatClock } from "../format";

interface Props<T extends { ts: string }> {
  title: string;
  subtitle: string;
  data: T[];
  value: (point: T) => number;
  format: (n: number) => string;
  /** Rates read best anchored at zero; counts too. */
  domain?: [number | "auto", number | "auto"];
}

interface TooltipProps {
  active?: boolean;
  payload?: { payload: { ts: string; v: number } }[];
  format: (n: number) => string;
  title: string;
}

function HoverTooltip({ active, payload, format, title }: TooltipProps) {
  if (!active || !payload?.length) return null;
  const { ts, v } = payload[0].payload;
  return (
    <div className="tooltip">
      <div className="tooltip-time">{formatClock(ts, true)}</div>
      <div>
        <span className="tooltip-key">{title}</span> <strong>{format(v)}</strong>
      </div>
    </div>
  );
}

/** One measure per chart: different scales get their own chart, never a second y-axis. */
export function LineChartCard<T extends { ts: string }>({
  title,
  subtitle,
  data,
  value,
  format,
  domain = [0, "auto"],
}: Props<T>) {
  const rows = data.map((p) => ({ ts: p.ts, v: value(p) }));
  return (
    <section className="card" aria-label={title}>
      <header className="card-head">
        <h3>{title}</h3>
        <p>{subtitle}</p>
      </header>
      <div className="chart" role="img" aria-label={`${title} over time`}>
        <ResponsiveContainer width="100%" height={170}>
          <LineChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis
              dataKey="ts"
              tickFormatter={(ts: string) => formatClock(ts)}
              tick={{ fill: "var(--text-muted)", fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: "var(--axis)" }}
              minTickGap={32}
            />
            <YAxis
              width={56}
              domain={domain}
              tickFormatter={format}
              tick={{ fill: "var(--text-muted)", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              cursor={{ stroke: "var(--axis)", strokeWidth: 1 }}
              content={<HoverTooltip format={format} title={title} />}
            />
            <Line
              type="monotone"
              dataKey="v"
              stroke="var(--series-1)"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, stroke: "var(--surface)", strokeWidth: 2 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
