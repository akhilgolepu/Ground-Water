import { useMemo, useState } from "react";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  ErrorBar,
  LabelList,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type {
  CalibrationPayload,
  DecisionPayload,
  EventKey,
  HorizonKey,
  SkillPayload,
  Station,
} from "@/lib/research-data";
import {
  EVENT_HELP,
  EVENT_LABEL,
  HORIZON_KEYS,
  HORIZON_LABEL,
  fmt,
  int,
  pct,
  signed,
} from "@/lib/research-data";
import type { WarningSettings } from "@/components/network-map";
import { warningProbability } from "@/components/network-map";
import { Slider } from "@/components/ui/slider";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

const axisTick = { fill: "var(--ink-2)", fontSize: 13 };

function Figure({
  title,
  note,
  source,
  children,
}: {
  title: string;
  note?: string;
  source: string;
  children: React.ReactNode;
}) {
  return (
    <figure className="flex min-w-0 flex-col gap-3">
      <figcaption>
        <h3 className="type-heading text-[1.2rem] text-ink">{title}</h3>
        {note && <p className="mt-1 max-w-[64ch] text-[0.9375rem] text-ink-2">{note}</p>}
      </figcaption>
      {children}
      <p className="text-[0.8125rem] text-ink-3 [overflow-wrap:anywhere]">Source: {source}</p>
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

export function HorizonPicker({
  value,
  onChange,
  id,
}: {
  value: HorizonKey;
  onChange: (h: HorizonKey) => void;
  id: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <span className="text-[0.9375rem] text-ink-2" id={id}>
        Forecast horizon
      </span>
      <ToggleGroup
        type="single"
        value={value}
        onValueChange={(v) => v && onChange(v as HorizonKey)}
        className="rounded-md border border-rule"
        aria-labelledby={id}
      >
        {HORIZON_KEYS.map((k) => (
          <ToggleGroupItem key={k} value={k} className="px-4 text-[0.875rem]">
            {HORIZON_LABEL[k]}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  );
}

// ── RQ1: does rainfall help? ────────────────────────────────────────────────

const ARM_SHOWN = [
  { key: "M0 memory", label: "Water levels only", color: "var(--ink-3)" },
  { key: "C snapshot control", label: "+ file's one-day rainfall", color: "var(--neutral-mid)" },
  { key: "M1 + past forcing", label: "+ past rainfall", color: "var(--s2)" },
  { key: "M2 + ENSO/IOD", label: "+ past rainfall, El Niño, IOD", color: "var(--s1)" },
  { key: "M3 + oracle rain", label: "+ the rain that actually fell next", color: "var(--s3)" },
];

export function RainfallFindings({ data, h }: { data: SkillPayload; h: HorizonKey }) {
  const rows = ARM_SHOWN.map((a) => {
    const s = data.skill.find((r) => r.h === Number(h) && r.arm === a.key);
    return s
      ? {
          ...a,
          skill: s.skill,
          err: [s.skill - s.lo, s.hi - s.skill] as [number, number],
          lo: s.lo,
          hi: s.hi,
        }
      : null;
  }).filter((r): r is NonNullable<typeof r> => r !== null);
  const gain = data.gains.find(
    (g) => g.h === Number(h) && g.a === "M0 memory" && g.b === "M2 + ENSO/IOD",
  );
  const oracle = data.gains.find(
    (g) => g.h === Number(h) && g.a === "M2 + ENSO/IOD" && g.b === "M3 + oracle rain",
  );
  const seasons = ["Jan", "May", "Aug", "Nov"].map((v) => {
    const m2 = data.strata.find(
      (s) =>
        s.h === Number(h) &&
        s.stratum === "target_season" &&
        s.value === v &&
        s.arm === "M2 + ENSO/IOD",
    );
    const m3 = data.strata.find(
      (s) =>
        s.h === Number(h) &&
        s.stratum === "target_season" &&
        s.value === v &&
        s.arm === "M3 + oracle rain",
    );
    return { season: v, m2: m2?.mse_reduction_vs_M0 ?? 0, m3: m3?.mse_reduction_vs_M0 ?? 0 };
  });

  return (
    <div className="grid gap-10 lg:grid-cols-2">
      <Figure
        title="Skill against repeating the last reading"
        note={`Share of the squared error of "next reading = this reading" that each model removes, 2019–2025 (95% interval over wells).${
          gain
            ? ` Adding rainfall and El Niño/IOD to water levels cuts error by ${pct(gain.mse_reduction, 1)} and wins ${gain.campaigns_b_better} of ${gain.campaigns} test campaigns.`
            : ""
        }`}
        source={data.source}
      >
        <div className="h-[260px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={rows}
              layout="vertical"
              margin={{ top: 0, right: 64, bottom: 0, left: 8 }}
              barCategoryGap={8}
            >
              <CartesianGrid horizontal={false} stroke="var(--rule)" />
              <XAxis
                type="number"
                domain={[0, 0.8]}
                ticks={[0, 0.2, 0.4, 0.6]}
                tick={axisTick}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="label"
                width={150}
                tick={{ ...axisTick, fontSize: 12 }}
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
                      <div className="font-semibold text-ink">{r.label}</div>
                      <div className="tnum">
                        Skill {fmt(r.skill, 3)} (95%: {fmt(r.lo, 3)}–{fmt(r.hi, 3)})
                      </div>
                    </TipBox>
                  );
                }}
              />
              <Bar dataKey="skill" radius={[0, 4, 4, 0]} isAnimationActive={false}>
                {rows.map((r) => (
                  <Cell key={r.key} fill={r.color} />
                ))}
                <ErrorBar
                  dataKey="err"
                  width={4}
                  strokeWidth={1.5}
                  stroke="var(--ink)"
                  direction="x"
                />
                <LabelList
                  dataKey="skill"
                  position="right"
                  offset={30}
                  formatter={(v: number) => v.toFixed(2)}
                  style={{ fill: "var(--ink)", fontSize: 13, fontFeatureSettings: '"tnum"' }}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Figure>

      <Figure
        title="Rainfall matters most for the forecast across the monsoon"
        note={`Error reduction over water levels alone, by the month being forecast.${
          oracle
            ? ` Knowing the actual rain would cut a further ${pct(oracle.mse_reduction, 1)}.`
            : ""
        }`}
        source={data.source}
      >
        <ul className="flex flex-wrap gap-x-5 gap-y-1 text-[0.875rem] text-ink-2">
          <li className="flex items-center gap-2">
            <span className="inline-block h-3 w-3 rounded-sm bg-s1" aria-hidden /> Past rainfall, El
            Niño, IOD
          </li>
          <li className="flex items-center gap-2">
            <span className="inline-block h-3 w-3 rounded-sm bg-s3" aria-hidden /> Plus the rain
            that actually fell
          </li>
        </ul>
        <div className="h-[230px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={seasons} margin={{ top: 16, right: 8, bottom: 0, left: 0 }} barGap={2}>
              <CartesianGrid vertical={false} stroke="var(--rule)" />
              <XAxis dataKey="season" tick={axisTick} axisLine={false} tickLine={false} />
              <YAxis
                tickFormatter={(v: number) => pct(v)}
                tick={axisTick}
                axisLine={false}
                tickLine={false}
                width={44}
              />
              <ReferenceLine y={0} stroke="var(--ink-3)" />
              <Tooltip
                cursor={{ fill: "var(--sunk)" }}
                content={({ active, payload }) => {
                  const r = payload?.[0]?.payload as (typeof seasons)[number] | undefined;
                  if (!active || !r) return null;
                  return (
                    <TipBox>
                      <div className="font-semibold text-ink">{r.season} target</div>
                      <div className="tnum">With past rainfall: {signed(r.m2 * 100)}%</div>
                      <div className="tnum">With actual rain: {signed(r.m3 * 100)}%</div>
                    </TipBox>
                  );
                }}
              />
              <Bar dataKey="m2" fill="var(--s1)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
              <Bar dataKey="m3" fill="var(--s3)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Figure>
    </div>
  );
}

// ── RQ2: how sure? ──────────────────────────────────────────────────────────

const DEPTHS = ["< 5 m", "5–15 m", "15–40 m", "≥ 40 m"];
const METHODS = [
  { key: "Split conformal", label: "One width for every well", color: "var(--s2)" },
  { key: "Mondrian D×R", label: "Per depth and region, fixed", color: "var(--ink-3)" },
  {
    key: "Mondrian D×R + recal + ACI",
    label: "Per depth and region, updated as readings arrive",
    color: "var(--s1)",
  },
];

export function CoverageFindings({ data, h }: { data: CalibrationPayload; h: HorizonKey }) {
  const W = 640;
  const rowH = 48;
  const left = 92;
  const right = 24;
  const top = 30;
  const H = top + rowH * DEPTHS.length + 26;
  const x = (v: number) => left + ((v - 0.3) / 0.7) * (W - left - right);
  const ticks = [0.4, 0.6, 0.8, 1.0];
  const pick = (m: string, g: string) =>
    data.coverage.find(
      (c) =>
        c.h === Number(h) &&
        c.nominal === 0.8 &&
        c.method === m &&
        c.group === g &&
        c.group_var === "Depth",
    );

  const drift = data.drift
    .filter((d) => d.h === Number(h))
    .map((d) => ({
      year: d.year,
      residual: d.median_residual,
      rain: data.jjas_anomaly_pct[String(d.year)] ?? null,
    }));

  return (
    <div className="grid gap-10 lg:grid-cols-2">
      <Figure
        title="Ranges that hold for shallow and deep wells alike"
        note="Share of readings that fell inside the 80% range, by depth at forecast time. The target is 80% in every class."
        source={data.source.split(";")[0] ?? data.source}
      >
        <ul className="flex flex-col gap-1 text-[0.875rem] text-ink-2">
          {METHODS.map((m) => (
            <li key={m.key} className="flex items-center gap-2">
              <span
                className="inline-block h-3 w-3 rounded-full"
                style={{ background: m.color }}
                aria-hidden
              />{" "}
              {m.label}
            </li>
          ))}
        </ul>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full"
          role="img"
          aria-label="Coverage of 80% ranges by depth class for three methods"
        >
          {ticks.map((t) => (
            <g key={t}>
              <line
                x1={x(t)}
                x2={x(t)}
                y1={top - 6}
                y2={H - 22}
                stroke={t === 0.8 ? "var(--ink)" : "var(--rule)"}
                strokeDasharray={t === 0.8 ? "4 3" : undefined}
              />
              <text x={x(t)} y={H - 4} textAnchor="middle" fontSize="13" fill="var(--ink-2)">
                {Math.round(t * 100)}%
              </text>
            </g>
          ))}
          <rect
            x={x(0.77)}
            y={top - 6}
            width={x(0.83) - x(0.77)}
            height={H - 22 - top + 6}
            fill="var(--sunk)"
            opacity={0.7}
          />
          {DEPTHS.map((g, i) => {
            const cy = top + rowH * i + rowH / 2;
            return (
              <g key={g}>
                <text x={left - 14} y={cy + 5} textAnchor="end" fontSize="14" fill="var(--ink)">
                  {g}
                </text>
                {METHODS.map((m, j) => {
                  const c = pick(m.key, g);
                  if (!c) return null;
                  return (
                    <g key={m.key}>
                      <title>{`${m.label}: ${pct(c.coverage, 1)} covered, median width ${fmt(c.median_width, 1)} m`}</title>
                      <circle
                        cx={x(c.coverage)}
                        cy={cy + (j - 1) * 9}
                        r="6"
                        fill={m.color}
                        stroke="var(--ground)"
                        strokeWidth="2"
                      />
                    </g>
                  );
                })}
              </g>
            );
          })}
        </svg>
      </Figure>

      <Figure
        title="Why fixed ranges drift"
        note="Median of observed minus forecast depth by target year (below zero: water came in shallower than forecast), with the all-India monsoon departure as bars. Ranges were calibrated on 2016–2018, after two dry monsoons; the strong 2019–2022 monsoons then left water shallower than they allowed for."
        source={data.source.split(";").slice(1).join(";").trim() || data.source}
      >
        <div className="h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={drift} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid vertical={false} stroke="var(--rule)" />
              <XAxis dataKey="year" tick={axisTick} axisLine={false} tickLine={false} />
              <YAxis
                yAxisId="r"
                domain={[-0.8, 0.8]}
                tickFormatter={(v: number) => `${v} m`}
                tick={axisTick}
                axisLine={false}
                tickLine={false}
                width={52}
              />
              <YAxis
                yAxisId="j"
                orientation="right"
                domain={[-16, 16]}
                tickFormatter={(v: number) => `${v}%`}
                tick={axisTick}
                axisLine={false}
                tickLine={false}
                width={44}
              />
              <ReferenceLine yAxisId="r" y={0} stroke="var(--ink-3)" />
              <Bar
                yAxisId="j"
                dataKey="rain"
                fill="var(--neutral-mid)"
                radius={[3, 3, 0, 0]}
                isAnimationActive={false}
              />
              <Line
                yAxisId="r"
                dataKey="residual"
                stroke="var(--s1)"
                strokeWidth={2}
                dot={{ r: 4, fill: "var(--s1)", stroke: "var(--ground)", strokeWidth: 2 }}
                isAnimationActive={false}
              />
              <Tooltip
                content={({ active, payload }) => {
                  const r = payload?.[0]?.payload as (typeof drift)[number] | undefined;
                  if (!active || !r) return null;
                  return (
                    <TipBox>
                      <div className="font-semibold text-ink">{r.year}</div>
                      <div className="tnum">Median observed − forecast: {fmt(r.residual)} m</div>
                      {r.rain != null && (
                        <div className="tnum">Monsoon vs 1994–2015: {signed(r.rain)}%</div>
                      )}
                    </TipBox>
                  );
                }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </Figure>
    </div>
  );
}

// ── RQ3: is it worth acting on? (decision panel) ────────────────────────────

const VALUE_ARMS = [
  { key: "M0 memory", label: "Water levels only", color: "var(--ink-3)" },
  { key: "M2 + ENSO/IOD", label: "With rainfall, El Niño, IOD", color: "var(--s1)" },
  { key: "M3 + oracle rain", label: "With a perfect rainfall forecast", color: "var(--s3)" },
];

interface DecisionPanelProps {
  data: DecisionPayload;
  stations: Station[];
  warning: WarningSettings;
  onChange: (w: WarningSettings) => void;
}

export function DecisionPanel({ data, stations, warning, onChange }: DecisionPanelProps) {
  const [showOracle, setShowOracle] = useState(true);
  const row = data.triggers.find(
    (t) =>
      t.h === Number(warning.h) &&
      t.event === warning.event &&
      Math.abs(t.trigger - warning.trigger) < 1e-6,
  );
  const curve = useMemo(() => {
    const byAlpha = new Map<number, Record<string, number | [number, number]>>();
    for (const v of data.value) {
      if (v.h !== Number(warning.h) || v.event_id !== warning.event) continue;
      const r = byAlpha.get(v.alpha) ?? { alpha: v.alpha };
      r[v.arm] = v.value;
      r[`${v.arm}|ci`] = [v.value_lo, v.value_hi];
      byAlpha.set(v.alpha, r);
    }
    return [...byAlpha.values()].sort((a, b) => (a["alpha"] as number) - (b["alpha"] as number));
  }, [data.value, warning.h, warning.event]);
  const ci = data.value.find(
    (v) =>
      v.h === Number(warning.h) &&
      v.event_id === warning.event &&
      v.arm === "M2 + ENSO/IOD" &&
      Math.abs(v.alpha - warning.trigger) < 1e-6,
  );
  const flagged = stations.filter((s) => {
    const p = warningProbability(s, warning);
    return p != null && p >= warning.trigger;
  }).length;
  const eligible = stations.filter((s) => warningProbability(s, warning) != null).length;

  return (
    <div className="grid gap-10 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-2">
          <span className="text-[0.9375rem] font-medium text-ink" id="event-label">
            What to warn about
          </span>
          <ToggleGroup
            type="single"
            value={warning.event}
            onValueChange={(v) => v && onChange({ ...warning, event: v as EventKey })}
            className="w-full rounded-md border border-rule"
            aria-labelledby="event-label"
          >
            {(["E1", "E3"] as EventKey[]).map((e) => (
              <ToggleGroupItem key={e} value={e} className="flex-1 px-2 text-[0.875rem]">
                {EVENT_LABEL[e]}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          <p className="text-[0.875rem] text-ink-2">{EVENT_HELP[warning.event]}</p>
        </div>
        <HorizonPicker
          value={warning.h}
          onChange={(h) => onChange({ ...warning, h })}
          id="decision-horizon"
        />
        <div className="flex flex-col gap-3">
          <div className="flex items-baseline justify-between gap-3">
            <label htmlFor="cost-loss" className="text-[0.9375rem] font-medium text-ink">
              Cost of acting, as a share of the loss avoided
            </label>
            <span className="type-figure text-[1.4rem] text-ink">{pct(warning.trigger)}</span>
          </div>
          <Slider
            id="cost-loss"
            min={0.02}
            max={0.98}
            step={0.02}
            value={[warning.trigger]}
            onValueChange={([v]) =>
              v !== undefined && onChange({ ...warning, trigger: Math.round(v * 100) / 100 })
            }
            aria-label="Cost of acting as a share of the loss avoided"
          />
          <p className="text-[0.875rem] text-ink-2">
            Acting pays off when the chance of the event is at least this share, so this is also the
            warning trigger. Use about 30% for seasonal planning and 20% for pump decisions six
            months ahead (docs/10).
          </p>
        </div>
        {row && (
          <dl className="grid grid-cols-2 gap-x-6 gap-y-4 border-t border-rule pt-5">
            <Stat label="Warnings issued" value={pct(row.warning_rate)} />
            <Stat label="Events that were warned" value={pct(row.hit_rate)} />
            <Stat label="Warnings that did not happen" value={pct(row.false_alarm_ratio)} />
            <Stat
              label="Value vs no forecast"
              value={fmt(row.value, 2)}
              sub={ci ? `95%: ${fmt(ci.value_lo, 2)}–${fmt(ci.value_hi, 2)}` : undefined}
            />
            <Stat
              label="Wells warned at their latest forecast"
              value={int(flagged)}
              sub={`of ${int(eligible)} with a forecast`}
            />
          </dl>
        )}
        <p className="text-[0.8125rem] text-ink-3 [overflow-wrap:anywhere]">
          Rates from {row ? int(row.n) : "—"} test forecasts, 2019–2025. Value 1 = a perfect
          forecast, 0 = no better than always or never acting. Source: {data.source}
        </p>
      </div>

      <figure className="flex min-w-0 flex-col gap-3">
        <figcaption>
          <h3 className="type-heading text-[1.2rem] text-ink">
            Value of the warnings for every cost of acting
          </h3>
          <p className="mt-1 max-w-[64ch] text-[0.9375rem] text-ink-2">
            Bands are 95% intervals over wells. The gap to the top line is what a better monsoon
            forecast could add.
          </p>
        </figcaption>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <ul className="flex flex-wrap gap-x-5 gap-y-1 text-[0.875rem] text-ink-2">
            {VALUE_ARMS.filter((a) => showOracle || a.key !== "M3 + oracle rain").map((a) => (
              <li key={a.key} className="flex items-center gap-2">
                <span
                  className="inline-block h-[3px] w-5"
                  style={{ background: a.color }}
                  aria-hidden
                />{" "}
                {a.label}
              </li>
            ))}
          </ul>
          <label className="flex items-center gap-2 text-[0.875rem] text-ink-2">
            <input
              type="checkbox"
              checked={showOracle}
              onChange={(e) => setShowOracle(e.target.checked)}
              className="h-4 w-4 accent-[var(--s1)]"
            />
            Show perfect-rainfall bound
          </label>
        </div>
        <div className="h-[340px]">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={curve} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
              <CartesianGrid stroke="var(--rule)" />
              <XAxis
                dataKey="alpha"
                type="number"
                domain={[0, 1]}
                ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]}
                tickFormatter={(v: number) => pct(v)}
                tick={axisTick}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                domain={[-0.1, 0.8]}
                ticks={[0, 0.2, 0.4, 0.6, 0.8]}
                tick={axisTick}
                axisLine={false}
                tickLine={false}
                width={40}
              />
              <ReferenceLine y={0} stroke="var(--ink-3)" />
              <ReferenceLine x={warning.trigger} stroke="var(--ink)" strokeDasharray="4 3" />
              {VALUE_ARMS.filter((a) => showOracle || a.key !== "M3 + oracle rain").map((a) => (
                <Area
                  key={`${a.key}-ci`}
                  dataKey={`${a.key}|ci`}
                  stroke="none"
                  fill={a.color}
                  fillOpacity={0.14}
                  isAnimationActive={false}
                  activeDot={false}
                />
              ))}
              {VALUE_ARMS.filter((a) => showOracle || a.key !== "M3 + oracle rain").map((a) => (
                <Line
                  key={a.key}
                  dataKey={a.key}
                  stroke={a.color}
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              ))}
              <Tooltip
                content={({ active, payload }) => {
                  const r = payload?.[0]?.payload as Record<string, number> | undefined;
                  if (!active || !r) return null;
                  return (
                    <TipBox>
                      <div className="font-semibold text-ink">
                        Cost of acting {pct(r["alpha"] ?? 0)} of the loss
                      </div>
                      {VALUE_ARMS.map((a) =>
                        r[a.key] !== undefined ? (
                          <div key={a.key} className="tnum">
                            {a.label}: {fmt(r[a.key] ?? 0, 2)}
                          </div>
                        ) : null,
                      )}
                    </TipBox>
                  );
                }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </figure>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string | undefined }) {
  return (
    <div>
      <dt className="text-[0.875rem] text-ink-2">{label}</dt>
      <dd className="type-figure text-[1.6rem] leading-tight text-ink">{value}</dd>
      {sub && <dd className="tnum text-[0.8125rem] text-ink-3">{sub}</dd>}
    </div>
  );
}

export { HORIZON_LABEL };
