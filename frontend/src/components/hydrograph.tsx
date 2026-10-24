import { useMemo } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { OperationalForecast, WellSeries } from "@/lib/research-data";
import { campaignLong, fmt } from "@/lib/research-data";

const MONTH: Record<string, number> = { Jan: 0, May: 4, Aug: 7, Nov: 10 };

/** Evenly spaced "nice" depth ticks (1, 2, 5 × 10ⁿ) covering the domain. */
function depthTicks([lo, hi]: [number, number]): number[] {
  const raw = (hi - lo) / 5;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((m) => m * mag).find((v) => v >= raw) ?? raw;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step)
    out.push(Number(v.toFixed(6)));
  return out;
}

/** Campaign label → fractional year, so the x-axis keeps real spacing. */
function toYear(label: string): number {
  const [y, s] = label.split("-");
  return Number(y) + (MONTH[s ?? ""] ?? 0) / 12;
}

interface Row {
  x: number;
  label: string;
  obs?: number;
  pred?: number;
  band?: [number, number];
  next?: number;
  nextBand?: [number, number];
}

interface HydrographProps {
  series: WellSeries;
  forecast?: OperationalForecast | undefined;
  /** Start the depth axis at the ground surface (0 m) instead of zooming to the data. */
  fromSurface?: boolean;
  height?: number;
  /** Only draw observations after this year (keeps the hero readable). */
  sinceYear?: number;
  /** The page draws the ground line directly above the chart, so y = 0 sits on it. */
  groundAbove?: boolean;
}

export function Hydrograph({
  series,
  forecast,
  fromSurface = false,
  height = 340,
  sinceYear,
  groundAbove = false,
}: HydrographProps) {
  const { rows, domain, ticks } = useMemo(() => {
    const byLabel = new Map<string, Row>();
    const row = (label: string) => {
      let r = byLabel.get(label);
      if (!r) {
        r = { x: toYear(label), label };
        byLabel.set(label, r);
      }
      return r;
    };
    for (const [label, depth] of series.obs) row(label).obs = depth;
    for (const [label, q50, lo, hi] of series.pred) {
      const r = row(label);
      r.pred = q50;
      r.band = [lo, hi];
    }
    if (forecast) {
      const last = series.obs[series.obs.length - 1];
      if (last) {
        const r = row(last[0]);
        r.next = last[1];
        r.nextBand = [last[1], last[1]];
      }
      const t = row(forecast.target);
      t.next = forecast.q50;
      t.nextBand = [forecast.lo, forecast.hi];
    }
    let all = [...byLabel.values()].sort((a, b) => a.x - b.x);
    if (sinceYear !== undefined) all = all.filter((r) => r.x >= sinceYear);

    const values = all
      .flatMap((r) => [r.obs, ...(r.band ?? []), ...(r.nextBand ?? [])])
      .filter((v): v is number => v !== undefined);
    if (forecast?.thr != null) values.push(forecast.thr);
    const lo = Math.min(...values);
    const hi = Math.max(...values);
    const pad = Math.max(0.5, (hi - lo) * 0.08);
    const dom: [number, number] = fromSurface
      ? [Math.min(0, lo), Math.ceil(hi + pad)]
      : [Math.floor(lo - pad), Math.ceil(hi + pad)];

    const first = Math.ceil(all[0]?.x ?? 0);
    const lastX = Math.floor(all[all.length - 1]?.x ?? 0);
    const span = lastX - first;
    const step = span > 20 ? 5 : span > 8 ? 2 : 1;
    const t: number[] = [];
    for (let y = first; y <= lastX; y++) if ((y - first) % step === 0) t.push(y);
    return { rows: all, domain: dom, ticks: t };
  }, [series, forecast, fromSurface, sinceYear]);

  const showGround = domain[0] <= 0 && !groundAbove;
  const dense = rows.filter((r) => r.obs !== undefined).length > 70;

  return (
    <div className="w-full" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart
          data={rows}
          margin={{ top: groundAbove ? 0 : 8, right: 16, bottom: 4, left: 4 }}
        >
          <CartesianGrid stroke="var(--rule)" strokeDasharray="0" vertical={false} />
          <XAxis
            dataKey="x"
            type="number"
            domain={["dataMin", "dataMax"]}
            ticks={ticks}
            tickFormatter={(v: number) => String(v)}
            tick={{ fill: "var(--ink-2)", fontSize: 13 }}
            axisLine={{ stroke: "var(--rule-strong)" }}
            tickLine={false}
          />
          <YAxis
            reversed
            domain={domain}
            ticks={depthTicks(domain)}
            allowDataOverflow
            width={48}
            tick={{ fill: "var(--ink-2)", fontSize: 13 }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) => `${v} m`}
          />
          {showGround && (
            <ReferenceLine
              y={0}
              stroke="var(--soil)"
              strokeWidth={2}
              label={{
                value: "Ground surface",
                position: "insideTopLeft",
                fill: "var(--soil)",
                fontSize: 12,
              }}
            />
          )}
          {forecast?.thr != null && (
            <ReferenceLine
              y={forecast.thr}
              stroke="var(--ink-3)"
              strokeDasharray="5 4"
              label={{
                value: `Usual ${forecast.target.split("-")[1]} level (80th percentile)`,
                position: "insideBottomLeft",
                fill: "var(--ink-2)",
                fontSize: 12,
              }}
            />
          )}
          <Area
            dataKey="band"
            type="linear"
            stroke="none"
            fill="var(--band)"
            isAnimationActive={false}
            connectNulls={false}
            activeDot={false}
          />
          <Area
            dataKey="nextBand"
            type="linear"
            stroke="none"
            fill="var(--band)"
            isAnimationActive={false}
            connectNulls
            activeDot={false}
          />
          <Line
            dataKey="obs"
            type="linear"
            stroke="var(--ink-2)"
            strokeWidth={dense ? 1.5 : 2}
            dot={
              dense
                ? false
                : { r: 3.5, fill: "var(--ink)", stroke: "var(--ground)", strokeWidth: 2 }
            }
            activeDot={{ r: 5, fill: "var(--ink)", stroke: "var(--ground)", strokeWidth: 2 }}
            connectNulls
            isAnimationActive={false}
          />
          <Line
            dataKey="pred"
            type="linear"
            stroke="var(--s1)"
            strokeWidth={2}
            strokeDasharray="6 4"
            dot={false}
            activeDot={{ r: 4, fill: "var(--s1)", stroke: "var(--ground)", strokeWidth: 2 }}
            connectNulls={false}
            isAnimationActive={false}
          />
          <Line
            dataKey="next"
            type="linear"
            stroke="var(--s1)"
            strokeWidth={2}
            dot={(props: { cx?: number; cy?: number; index?: number }) =>
              props.index === rows.length - 1 && props.cx != null && props.cy != null ? (
                <circle
                  key="next-dot"
                  cx={props.cx}
                  cy={props.cy}
                  r={5}
                  fill="var(--s1)"
                  stroke="var(--ground)"
                  strokeWidth={2}
                />
              ) : (
                <g key={`n-${props.index}`} />
              )
            }
            connectNulls
            isAnimationActive={false}
          />
          <Tooltip content={<HydroTooltip />} cursor={{ stroke: "var(--rule-strong)" }} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function HydroTooltip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  const r = payload?.[0]?.payload;
  if (!active || !r) return null;
  const isNext = r.next !== undefined && r.obs === undefined;
  return (
    <div className="rounded-md border border-rule bg-panel px-3 py-2 text-[0.875rem] shadow-sm">
      <div className="font-semibold text-ink">{campaignLong(r.label)}</div>
      {r.obs !== undefined && (
        <div className="tnum text-ink-2">Observed: {fmt(r.obs)} m below ground</div>
      )}
      {r.pred !== undefined && r.band && (
        <div className="tnum text-ink-2">
          Forecast 3 months earlier: {fmt(r.pred)} m (80%: {fmt(r.band[0])}–{fmt(r.band[1])})
        </div>
      )}
      {isNext && r.nextBand && (
        <div className="tnum text-ink-2">
          After last reading: {fmt(r.next ?? 0)} m (80%: {fmt(r.nextBand[0])}–{fmt(r.nextBand[1])})
        </div>
      )}
    </div>
  );
}

export function HydrographLegend({ withNext = true }: { withNext?: boolean }) {
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-1 text-[0.875rem] text-ink-2">
      <li className="flex items-center gap-2">
        <svg width="22" height="10" aria-hidden>
          <line x1="0" y1="5" x2="22" y2="5" stroke="var(--ink-2)" strokeWidth="2" />
          <circle cx="11" cy="5" r="3.5" fill="var(--ink)" />
        </svg>
        Observed depth
      </li>
      <li className="flex items-center gap-2">
        <svg width="22" height="10" aria-hidden>
          <rect x="0" y="0" width="22" height="10" fill="var(--band)" />
          <line
            x1="0"
            y1="5"
            x2="22"
            y2="5"
            stroke="var(--s1)"
            strokeWidth="2"
            strokeDasharray="6 4"
          />
        </svg>
        Forecast made 3 months earlier, with 80% range
      </li>
      {withNext && (
        <li className="flex items-center gap-2">
          <svg width="22" height="10" aria-hidden>
            <line x1="0" y1="5" x2="16" y2="5" stroke="var(--s1)" strokeWidth="2" />
            <circle cx="17" cy="5" r="4" fill="var(--s1)" />
          </svg>
          Forecast after the last reading
        </li>
      )}
    </ul>
  );
}
