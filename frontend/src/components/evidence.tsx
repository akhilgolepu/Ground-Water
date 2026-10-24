import { useEffect, useRef, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import type { Benchmark, HorizonKey } from "@/lib/research-data";
import { HORIZON_LABEL, fmt, int, pct } from "@/lib/research-data";

const axisTick = { fill: "var(--ink-2)", fontSize: 13 };

function ChartFrame({
  title,
  note,
  children,
}: {
  title: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <figure className="flex flex-col gap-3">
      <figcaption>
        <h3 className="type-heading text-[1.2rem] text-ink">{title}</h3>
        {note && <p className="mt-1 max-w-[62ch] text-[0.9375rem] text-ink-2">{note}</p>}
      </figcaption>
      {children}
    </figure>
  );
}

function TipBox({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-rule bg-panel px-3 py-2 text-[0.875rem] text-ink-2 shadow-sm">
      {children}
    </div>
  );
}

// ── Point skill ─────────────────────────────────────────────────────────────

const MODEL_ORDER = [
  "Persistence",
  "Seasonal naive",
  "Climatology",
  "Anomaly persistence",
  "XGBoost (memory-only)",
];
const MODEL_COPY: Record<string, string> = {
  Persistence: "Next value = current value",
  "Seasonal naive": "Same season last year",
  Climatology: "This well's average for the season",
  "Anomaly persistence": "Current anomaly carried forward",
  "XGBoost (memory-only)": "Global model, groundwater history only",
};

export function SkillChart({ data, h }: { data: Benchmark; h: HorizonKey }) {
  const res = data.horizons[h];
  if (!res) return null;
  const rows = MODEL_ORDER.filter((m) => res.metrics[m]).map((m) => ({
    model: m === "XGBoost (memory-only)" ? "XGBoost" : m,
    full: m,
    ...res.metrics[m]!,
  }));
  return (
    <ChartFrame
      title="Skill against persistence"
      note={`Share of persistence's squared error removed, on ${int(res.n_test)} test forecasts from ${int(res.n_test_wells)} wells (2019–2025). Zero means no better than repeating the last reading.`}
    >
      <div className="h-[260px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={rows}
            layout="vertical"
            margin={{ top: 0, right: 56, bottom: 0, left: 8 }}
            barCategoryGap={10}
          >
            <CartesianGrid horizontal={false} stroke="var(--rule)" />
            <XAxis
              type="number"
              domain={[-0.2, 0.7]}
              ticks={[-0.2, 0, 0.2, 0.4, 0.6]}
              tick={axisTick}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="model"
              width={150}
              tick={axisTick}
              axisLine={false}
              tickLine={false}
            />
            <ReferenceLine x={0} stroke="var(--ink-3)" />
            <Tooltip
              cursor={{ fill: "var(--sunk)" }}
              content={({ active, payload }) => {
                const r = payload?.[0]?.payload as (typeof rows)[number] | undefined;
                if (!active || !r) return null;
                return (
                  <TipBox>
                    <div className="font-semibold text-ink">{r.full}</div>
                    <div>{MODEL_COPY[r.full]}</div>
                    <div className="tnum">
                      RMSE {fmt(r.rmse)} m, MAE {fmt(r.mae)} m, bias {fmt(r.bias)} m
                    </div>
                  </TipBox>
                );
              }}
            />
            <Bar dataKey="skill_vs_persistence" radius={[0, 4, 4, 0]} isAnimationActive={false}>
              {rows.map((r) => (
                <Cell
                  key={r.full}
                  fill={r.full.startsWith("XGBoost") ? "var(--s1)" : "var(--ink-3)"}
                />
              ))}
              <LabelList
                dataKey="skill_vs_persistence"
                position="right"
                formatter={(v: number) => (v > 0 ? "+" : "") + v.toFixed(2)}
                style={{ fill: "var(--ink)", fontSize: 13, fontFeatureSettings: '"tnum"' }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartFrame>
  );
}

// ── Conditional coverage by depth class (headline finding) ──────────────────

const DEPTH_ROWS = ["< 5 m", "5–15 m", "15–40 m", "≥ 40 m"];

export function CoverageByDepth({ data, h }: { data: Benchmark; h: HorizonKey }) {
  const [hover, setHover] = useState<string | null>(null);
  const [W, setW] = useState(640);
  const wrapRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    // Size the SVG in real pixels so labels keep their size on narrow screens.
    const ro = new ResizeObserver(
      ([entry]) => entry && setW(Math.max(300, Math.min(720, entry.contentRect.width))),
    );
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const pick = (method: string, group: string) =>
    data.coverage.find(
      (c) => c.h === Number(h) && c.nominal === 0.8 && c.method === method && c.group === group,
    );
  const rowH = 52;
  const left = W < 480 ? 72 : 92;
  const right = 24;
  const top = 34;
  const H = top + rowH * DEPTH_ROWS.length + 26;
  const x = (v: number) => left + ((v - 0.3) / 0.7) * (W - left - right);
  const ticks = W < 480 ? [0.4, 0.6, 0.8, 1.0] : [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0];

  return (
    <ChartFrame
      title="A single interval width leaves deep wells uncovered"
      note="Share of test readings that fell inside the 80% interval, by how deep the water was at forecast time. Calibrating separately for each season and depth class brings every class close to the 80% target."
    >
      <ul className="flex flex-wrap gap-x-5 gap-y-1 text-[0.875rem] text-ink-2">
        <li className="flex items-center gap-2">
          <span className="inline-block h-3 w-3 rounded-full bg-s2" aria-hidden /> One width for all
          wells (split conformal)
        </li>
        <li className="flex items-center gap-2">
          <span className="inline-block h-3 w-3 rounded-full bg-s1" aria-hidden /> Width per season
          and depth class (Mondrian conformal)
        </li>
      </ul>
      <div ref={wrapRef} className="w-full">
        <svg
          width={W}
          height={H}
          viewBox={`0 0 ${W} ${H}`}
          role="img"
          aria-label="Coverage of 80% intervals by depth class for two calibration methods"
        >
          {ticks.map((t) => (
            <g key={t}>
              <line
                x1={x(t)}
                x2={x(t)}
                y1={top - 8}
                y2={H - 22}
                stroke={t === 0.8 ? "var(--ink)" : "var(--rule)"}
                strokeDasharray={t === 0.8 ? "4 3" : undefined}
              />
              <text
                x={x(t)}
                y={H - 4}
                textAnchor="middle"
                fontSize="13"
                fill="var(--ink-2)"
                className="tnum"
              >
                {Math.round(t * 100)}%
              </text>
            </g>
          ))}
          <text x={x(0.8)} y={top - 14} textAnchor="middle" fontSize="12" fill="var(--ink)">
            80% target
          </text>
          {DEPTH_ROWS.map((g, i) => {
            const split = pick("Split conformal", g);
            const mond = pick("Mondrian conformal", g);
            if (!split || !mond) return null;
            const cy = top + rowH * i + rowH / 2;
            const active = hover === g;
            return (
              <g
                key={g}
                onMouseEnter={() => setHover(g)}
                onMouseLeave={() => setHover(null)}
                onFocus={() => setHover(g)}
                onBlur={() => setHover(null)}
                tabIndex={0}
              >
                <rect
                  x={0}
                  y={cy - rowH / 2}
                  width={W}
                  height={rowH}
                  fill={active ? "var(--sunk)" : "transparent"}
                />
                <text x={left - 14} y={cy + 5} textAnchor="end" fontSize="14" fill="var(--ink)">
                  {g}
                </text>
                <line
                  x1={x(split.coverage)}
                  x2={x(mond.coverage)}
                  y1={cy}
                  y2={cy}
                  stroke="var(--rule-strong)"
                  strokeWidth="2"
                />
                <circle
                  cx={x(split.coverage)}
                  cy={cy}
                  r="7"
                  fill="var(--s2)"
                  stroke="var(--ground)"
                  strokeWidth="2"
                />
                <circle
                  cx={x(mond.coverage)}
                  cy={cy}
                  r="7"
                  fill="var(--s1)"
                  stroke="var(--ground)"
                  strokeWidth="2"
                />
                <text
                  x={x(split.coverage)}
                  y={cy - 12}
                  textAnchor="middle"
                  fontSize="12.5"
                  fill="var(--ink)"
                  className="tnum"
                >
                  {pct(split.coverage)}
                </text>
                <text
                  x={x(mond.coverage)}
                  y={cy + 23}
                  textAnchor="middle"
                  fontSize="12.5"
                  fill="var(--ink)"
                  className="tnum"
                >
                  {pct(mond.coverage)}
                </text>
                {active && (
                  <text
                    x={W - right}
                    y={cy + 5}
                    textAnchor="end"
                    fontSize="12"
                    fill="var(--ink-2)"
                    className="tnum"
                  >
                    widths {fmt(split.median_width_m, 1)} m vs {fmt(mond.median_width_m, 1)} m
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    </ChartFrame>
  );
}

// ── Calibration across nominal levels ───────────────────────────────────────

const CAL_METHODS = [
  { key: "Mondrian conformal", label: "Mondrian conformal", color: "var(--s1)" },
  { key: "Split conformal", label: "Split conformal", color: "var(--s2)" },
  { key: "Gaussian (train residuals)", label: "Gaussian", color: "var(--s3)" },
];

export function CalibrationChart({ data, h }: { data: Benchmark; h: HorizonKey }) {
  const levels = [0.5, 0.8, 0.9, 0.95];
  const rows = levels.map((lv) => {
    const row: Record<string, number> = { nominal: lv };
    for (const m of CAL_METHODS) {
      const c = data.coverage.find(
        (r) => r.h === Number(h) && r.nominal === lv && r.method === m.key && r.group === "All",
      );
      if (c) row[m.key] = c.coverage;
    }
    return row;
  });
  return (
    <ChartFrame
      title="Overall coverage at each confidence level"
      note="Points on the diagonal mean the stated confidence matches what happened. Overall coverage can look right while depth classes are wrong."
    >
      <ul className="flex flex-wrap gap-x-5 gap-y-1 text-[0.875rem] text-ink-2">
        {CAL_METHODS.map((m) => (
          <li key={m.key} className="flex items-center gap-2">
            <span
              className="inline-block h-[3px] w-5"
              style={{ background: m.color }}
              aria-hidden
            />{" "}
            {m.label}
          </li>
        ))}
      </ul>
      <div className="h-[260px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 8, right: 24, bottom: 8, left: 0 }}>
            <CartesianGrid stroke="var(--rule)" />
            <XAxis
              dataKey="nominal"
              type="number"
              domain={[0.45, 1]}
              ticks={levels}
              tickFormatter={(v: number) => pct(v)}
              tick={axisTick}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              type="number"
              domain={[0.4, 1]}
              ticks={[0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1]}
              tickFormatter={(v: number) => pct(v)}
              tick={axisTick}
              axisLine={false}
              tickLine={false}
              width={48}
            />
            <ReferenceLine
              segment={[
                { x: 0.45, y: 0.45 },
                { x: 1, y: 1 },
              ]}
              stroke="var(--ink-3)"
              strokeDasharray="4 3"
            />
            <Tooltip
              content={({ active, payload }) => {
                const r = payload?.[0]?.payload as Record<string, number> | undefined;
                if (!active || !r) return null;
                return (
                  <TipBox>
                    <div className="font-semibold text-ink">
                      Stated confidence {pct(r["nominal"] ?? 0)}
                    </div>
                    {CAL_METHODS.map((m) =>
                      r[m.key] !== undefined ? (
                        <div key={m.key} className="tnum">
                          {m.label}: {pct(r[m.key] ?? 0, 1)} covered
                        </div>
                      ) : null,
                    )}
                  </TipBox>
                );
              }}
            />
            {CAL_METHODS.map((m) => (
              <Line
                key={m.key}
                dataKey={m.key}
                stroke={m.color}
                strokeWidth={2}
                dot={{ r: 4, fill: m.color, stroke: "var(--ground)", strokeWidth: 2 }}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </ChartFrame>
  );
}

export function MethodTable({ data, h }: { data: Benchmark; h: HorizonKey }) {
  const rows = data.coverage.filter(
    (c) => c.h === Number(h) && c.nominal === 0.8 && c.group === "All",
  );
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[420px] text-left text-[0.9375rem]">
        <caption className="mb-2 text-left text-[0.9375rem] text-ink-2">
          All five interval methods at the 80% level, {HORIZON_LABEL[h]} ahead
        </caption>
        <thead>
          <tr className="border-b border-rule-strong text-ink-2">
            <th className="py-2 pr-4 font-medium">Method</th>
            <th className="py-2 pr-4 text-right font-medium">Covered</th>
            <th className="py-2 text-right font-medium">Median width</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.method} className="border-b border-rule">
              <td className="py-2 pr-4 text-ink">{r.method}</td>
              <td className="tnum py-2 pr-4 text-right text-ink">{pct(r.coverage, 1)}</td>
              <td className="tnum py-2 text-right text-ink">{fmt(r.median_width_m)} m</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Early warning reliability ───────────────────────────────────────────────

export function ReliabilityChart({ data, h }: { data: Benchmark; h: HorizonKey }) {
  const ew = data.horizons[h]?.early_warning;
  if (!ew) return null;
  const pts = ew.reliability.map((r) => ({ ...r }));
  return (
    <ChartFrame
      title="Do the warning probabilities mean what they say?"
      note={`Each point groups forecasts with similar probabilities. Brier skill against always forecasting the base rate: ${ew.brier_skill > 0 ? "+" : ""}${fmt(ew.brier_skill)} (${int(ew.n)} forecasts, event rate ${pct(ew.event_rate)}).`}
    >
      <div className="h-[260px]">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 24, bottom: 8, left: 0 }}>
            <CartesianGrid stroke="var(--rule)" />
            <XAxis
              dataKey="p_mean"
              type="number"
              domain={[0, 1]}
              ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]}
              tickFormatter={(v: number) => pct(v)}
              tick={axisTick}
              axisLine={false}
              tickLine={false}
              name="Forecast probability"
            />
            <YAxis
              dataKey="obs_freq"
              type="number"
              domain={[0, 1]}
              ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]}
              tickFormatter={(v: number) => pct(v)}
              tick={axisTick}
              axisLine={false}
              tickLine={false}
              width={48}
              name="Observed frequency"
            />
            <ZAxis dataKey="n" range={[60, 260]} />
            <ReferenceLine
              segment={[
                { x: 0, y: 0 },
                { x: 1, y: 1 },
              ]}
              stroke="var(--ink-3)"
              strokeDasharray="4 3"
            />
            <Tooltip
              cursor={false}
              content={({ active, payload }) => {
                const r = payload?.[0]?.payload as (typeof pts)[number] | undefined;
                if (!active || !r) return null;
                return (
                  <TipBox>
                    <div className="tnum">
                      Forecast {pct(r.p_mean)}, happened {pct(r.obs_freq)}
                    </div>
                    <div className="tnum">{int(r.n)} forecasts</div>
                  </TipBox>
                );
              }}
            />
            <Scatter
              data={pts}
              fill="var(--s1)"
              stroke="var(--ground)"
              strokeWidth={2}
              isAnimationActive={false}
            />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </ChartFrame>
  );
}

// ── Per-well skill distribution ─────────────────────────────────────────────

export function StationSkillChart({ data, h }: { data: Benchmark; h: HorizonKey }) {
  const ss = data.horizons[h]?.station_skill;
  if (!ss) return null;
  const rows = ss.histogram.map((count, i) => ({ x: -1 + i * 0.1 + 0.05, count }));
  return (
    <ChartFrame
      title="Skill varies from well to well"
      note={`XGBoost skill against persistence for each of ${int(ss.n_wells)} wells with six or more test forecasts. Median ${fmt(ss.median)}; ${pct(ss.share_positive)} of wells beat persistence. Values below −1 are grouped at the left edge.`}
    >
      <div className="h-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={rows}
            margin={{ top: 8, right: 16, bottom: 8, left: 0 }}
            barCategoryGap={2}
          >
            <CartesianGrid vertical={false} stroke="var(--rule)" />
            <XAxis
              dataKey="x"
              type="number"
              domain={[-1, 1]}
              ticks={[-1, -0.5, 0, 0.5, 1]}
              tick={axisTick}
              axisLine={false}
              tickLine={false}
            />
            <YAxis tick={axisTick} axisLine={false} tickLine={false} width={48} />
            <ReferenceLine x={0} stroke="var(--ink-3)" />
            <Tooltip
              cursor={{ fill: "var(--sunk)" }}
              content={({ active, payload }) => {
                const r = payload?.[0]?.payload as (typeof rows)[number] | undefined;
                if (!active || !r) return null;
                return (
                  <TipBox>
                    <div className="tnum">
                      Skill {fmt(r.x - 0.05, 1)} to {fmt(r.x + 0.05, 1)}: {int(r.count)} wells
                    </div>
                  </TipBox>
                );
              }}
            />
            <Bar dataKey="count" fill="var(--s1)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartFrame>
  );
}

// ── Feature contributions ───────────────────────────────────────────────────

export function ShapChart({ data, h }: { data: Benchmark; h: HorizonKey }) {
  const rows = (data.importance[h] ?? []).slice(0, 8);
  return (
    <ChartFrame
      title="What the model leans on"
      note="Average absolute TreeSHAP contribution to the forecast, in metres. Every input is groundwater history or season, because rainfall is not in the model yet."
    >
      <div className="h-[280px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={rows}
            layout="vertical"
            margin={{ top: 0, right: 56, bottom: 0, left: 8 }}
            barCategoryGap={8}
          >
            <CartesianGrid horizontal={false} stroke="var(--rule)" />
            <XAxis
              type="number"
              tick={axisTick}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v: number) => `${v} m`}
            />
            <YAxis
              type="category"
              dataKey="feature"
              width={190}
              tick={axisTick}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              cursor={{ fill: "var(--sunk)" }}
              content={({ active, payload }) => {
                const r = payload?.[0]?.payload as (typeof rows)[number] | undefined;
                if (!active || !r) return null;
                return (
                  <TipBox>
                    <div className="tnum">
                      {r.feature}: {fmt(r.mean_abs_shap_m, 3)} m on average
                    </div>
                  </TipBox>
                );
              }}
            />
            <Bar
              dataKey="mean_abs_shap_m"
              fill="var(--s1)"
              radius={[0, 4, 4, 0]}
              isAnimationActive={false}
            >
              <LabelList
                dataKey="mean_abs_shap_m"
                position="right"
                formatter={(v: number) => v.toFixed(2)}
                style={{ fill: "var(--ink)", fontSize: 13 }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartFrame>
  );
}
