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
import type { WellDetail, WellForecast } from "@/lib/research-data";
import { campaignLong, campaignYear, fmt } from "@/lib/research-data";

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

interface Row {
  x: number;
  label: string;
  obs?: number;
  wris?: boolean;
  m0?: number;
  m2?: number;
  band?: [number, number];
  next?: number;
  nextBand?: [number, number];
}

interface HydrographProps {
  detail: WellDetail;
  forecast?: WellForecast | undefined;
  /** Show the memory-only model's test forecasts next to the rainfall-aware ones. */
  showMemoryOnly?: boolean;
  fromSurface?: boolean;
  height?: number;
  sinceYear?: number;
  /** The page draws the ground line directly above the chart, so y = 0 sits on it. */
  groundAbove?: boolean;
}

export function Hydrograph({
  detail,
  forecast,
  showMemoryOnly = false,
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
        r = { x: campaignYear(label), label };
        byLabel.set(label, r);
      }
      return r;
    };
    for (const [label, depth, wris] of detail.obs) {
      const r = row(label);
      r.obs = depth;
      r.wris = wris === 1;
    }
    for (const [label, m0, m2, lo, hi] of detail.test ?? []) {
      const r = row(label);
      r.m0 = m0;
      r.m2 = m2;
      if (lo != null && hi != null) r.band = [lo, hi];
    }
    if (forecast) {
      const o = row(forecast.origin);
      o.next = forecast.now;
      o.nextBand = [forecast.now, forecast.now];
      const t = row(forecast.target);
      t.next = forecast.m2;
      if (forecast.lo != null && forecast.hi != null) t.nextBand = [forecast.lo, forecast.hi];
    }
    let all = [...byLabel.values()].sort((a, b) => a.x - b.x);
    if (sinceYear !== undefined) all = all.filter((r) => r.x >= sinceYear);

    const values = all
      .flatMap((r) => [
        r.obs,
        ...(r.band ?? []),
        ...(r.nextBand ?? []),
        showMemoryOnly ? r.m0 : undefined,
        r.m2,
      ])
      .filter((v): v is number => v !== undefined && Number.isFinite(v));
    if (forecast?.thrE1 != null) values.push(forecast.thrE1);
    const lo = Math.min(...values);
    const hi = Math.max(...values);
    const pad = Math.max(0.5, (hi - lo) * 0.08);
    const dom: [number, number] = fromSurface
      ? [Math.min(0, lo), Math.ceil(hi + pad)]
      : [Math.floor(lo - pad), Math.ceil(hi + pad)];

    const first = Math.ceil(all[0]?.x ?? 0);
    const last = Math.floor(all[all.length - 1]?.x ?? 0);
    const span = last - first;
    const step = span > 20 ? 5 : span > 8 ? 2 : 1;
    const t: number[] = [];
    for (let y = first; y <= last; y++) if ((y - first) % step === 0) t.push(y);
    return { rows: all, domain: dom, ticks: t };
  }, [detail, forecast, fromSurface, sinceYear, showMemoryOnly]);

  const showGround = domain[0] <= 0 && !groundAbove;
  const dense = rows.filter((r) => r.obs !== undefined).length > 70;

  return (
    <div className="w-full" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart
          data={rows}
          margin={{ top: groundAbove ? 0 : 8, right: 16, bottom: 4, left: 4 }}
        >
          <CartesianGrid stroke="var(--rule)" vertical={false} />
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
          {forecast?.thrE1 != null && (
            <ReferenceLine y={forecast.thrE1} stroke="var(--ink-3)" strokeDasharray="5 4" />
          )}
          <Area
            dataKey="band"
            type="linear"
            stroke="none"
            fill="var(--band)"
            isAnimationActive={false}
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
                : (p: { cx?: number; cy?: number; index?: number; payload?: Row }) =>
                    p.cx != null && p.cy != null && p.payload?.obs !== undefined ? (
                      <circle
                        key={`o-${p.index}`}
                        cx={p.cx}
                        cy={p.cy}
                        r={3.5}
                        fill={p.payload.wris ? "var(--ground)" : "var(--ink)"}
                        stroke={p.payload.wris ? "var(--ink)" : "var(--ground)"}
                        strokeWidth={p.payload.wris ? 1.5 : 2}
                      />
                    ) : (
                      <g key={`o-${p.index}`} />
                    )
            }
            activeDot={{ r: 5, fill: "var(--ink)", stroke: "var(--ground)", strokeWidth: 2 }}
            connectNulls
            isAnimationActive={false}
          />
          {showMemoryOnly && (
            <Line
              dataKey="m0"
              type="linear"
              stroke="var(--s2)"
              strokeWidth={2}
              strokeDasharray="2 3"
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
          )}
          <Line
            dataKey="m2"
            type="linear"
            stroke="var(--s1)"
            strokeWidth={2}
            strokeDasharray="6 4"
            dot={false}
            connectNulls={false}
            isAnimationActive={false}
          />
          <Line
            dataKey="next"
            type="linear"
            stroke="var(--s1)"
            strokeWidth={2}
            dot={(p: { cx?: number; cy?: number; index?: number }) =>
              p.index === rows.length - 1 && p.cx != null && p.cy != null ? (
                <circle
                  key="next-dot"
                  cx={p.cx}
                  cy={p.cy}
                  r={5}
                  fill="var(--s1)"
                  stroke="var(--ground)"
                  strokeWidth={2}
                />
              ) : (
                <g key={`n-${p.index}`} />
              )
            }
            connectNulls
            isAnimationActive={false}
          />
          <Tooltip
            content={<HydroTooltip showMemoryOnly={showMemoryOnly} />}
            cursor={{ stroke: "var(--rule-strong)" }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function HydroTooltip({
  active,
  payload,
  showMemoryOnly,
}: {
  active?: boolean;
  payload?: { payload: Row }[];
  showMemoryOnly: boolean;
}) {
  const r = payload?.[0]?.payload;
  if (!active || !r) return null;
  const isNext = r.next !== undefined && r.obs === undefined;
  return (
    <div className="rounded-md border border-rule bg-panel px-3 py-2 text-[0.875rem] shadow-sm">
      <div className="font-semibold text-ink">{campaignLong(r.label)}</div>
      {r.obs !== undefined && (
        <div className="tnum text-ink-2">
          Observed: {fmt(r.obs)} m below ground{r.wris ? " (India-WRIS update)" : ""}
        </div>
      )}
      {r.m2 !== undefined && (
        <div className="tnum text-ink-2">
          Forecast 3 months earlier: {fmt(r.m2)} m
          {r.band ? ` (80%: ${fmt(r.band[0])}–${fmt(r.band[1])})` : ""}
        </div>
      )}
      {showMemoryOnly && r.m0 !== undefined && (
        <div className="tnum text-ink-2">Without rainfall: {fmt(r.m0)} m</div>
      )}
      {isNext && r.nextBand && (
        <div className="tnum text-ink-2">
          Latest forecast: {fmt(r.next ?? 0)} m (80%: {fmt(r.nextBand[0])}–{fmt(r.nextBand[1])})
        </div>
      )}
    </div>
  );
}

export function HydrographLegend({
  withNext = true,
  showMemoryOnly = false,
  thresholdSeason,
}: {
  withNext?: boolean;
  showMemoryOnly?: boolean;
  /** Season of the "usual level" line, e.g. "May"; omit when no threshold is drawn. */
  thresholdSeason?: string | undefined;
}) {
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
        Forecast made 3 months earlier, with rainfall, 80% range
      </li>
      {showMemoryOnly && (
        <li className="flex items-center gap-2">
          <svg width="22" height="10" aria-hidden>
            <line
              x1="0"
              y1="5"
              x2="22"
              y2="5"
              stroke="var(--s2)"
              strokeWidth="2"
              strokeDasharray="2 3"
            />
          </svg>
          Same forecast without rainfall
        </li>
      )}
      {thresholdSeason && (
        <li className="flex items-center gap-2">
          <svg width="22" height="10" aria-hidden>
            <line
              x1="0"
              y1="5"
              x2="22"
              y2="5"
              stroke="var(--ink-3)"
              strokeWidth="1.5"
              strokeDasharray="5 4"
            />
          </svg>
          Usual {thresholdSeason} level (80th percentile)
        </li>
      )}
      {withNext && (
        <li className="flex items-center gap-2">
          <svg width="22" height="10" aria-hidden>
            <line x1="0" y1="5" x2="16" y2="5" stroke="var(--s1)" strokeWidth="2" />
            <circle cx="17" cy="5" r="4" fill="var(--s1)" />
          </svg>
          Forecast after the latest reading
        </li>
      )}
    </ul>
  );
}
