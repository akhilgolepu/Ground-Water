/**
 * Research artefacts produced by `python -m src.research.export_dashboard`
 * and served as static JSON from /data (frontend/public/data). Every file names its source report.
 */
import { useQuery } from "@tanstack/react-query";

// ── Types ────────────────────────────────────────────────────────────────────

export type HorizonKey = "1" | "2" | "4";
export type EventKey = "E1" | "E3";

export interface Summary {
  generated: string;
  n_stations: number;
  n_manual: number;
  n_dwlr: number;
  n_obs: number;
  first_year: number;
  last_year: number;
  n_campaign_values: number;
  trend: { n_wells: number; sig_deepening: number; sig_rising: number };
  operational: { n_wells: number; latest_origin: string; origin_years: Record<string, number> };
  wris: {
    wris_used: boolean;
    wells_extended?: number;
    campaigns_added?: number;
    latest_campaign?: string | null;
  };
  sources: Record<string, string>;
}

/** Operational warning probabilities per horizon: target campaign, P(deeper than usual), P(below 8 m). */
export interface StationOps {
  t: string;
  e1: number | null;
  e3: number | null;
}

export interface Station {
  id: string;
  lat: number;
  lon: number;
  net: "manual" | "DWLR";
  n: number;
  yrs: number;
  first: string;
  last: string;
  median: number;
  state: string | null;
  region: string | null;
  b: number;
  trend?: number | null;
  trendP?: number | null;
  ops?: Partial<Record<HorizonKey, StationOps>>;
}

export interface WellForecast {
  origin: string;
  target: string;
  now: number;
  m0: number;
  m2: number;
  lo: number | null;
  hi: number | null;
  thrE1: number | null;
  pE1: number | null;
  pE3: number | null;
  advisory: string | null;
}

export interface WellDetail {
  /** [campaign, depth, 1 if added from India-WRIS] */
  obs: [string, number, number][];
  /** 3-month-ahead test forecasts: [target, memory-only, with rainfall, 80% low, 80% high] */
  test?: [string, number, number, number | null, number | null][];
  mae?: Partial<Record<HorizonKey, { n: number; m0: number; m2: number }>>;
  ops?: Partial<Record<HorizonKey, WellForecast>>;
}

export interface SkillPayload {
  source: string;
  skill: { h: number; arm: string; skill: number; lo: number; hi: number }[];
  metrics: {
    h: number;
    model: string;
    n: number;
    n_wells: number;
    rmse: number;
    mae: number;
    nse_median: number;
  }[];
  gains: {
    h: number;
    a: string;
    b: string;
    mse_reduction: number;
    mae_reduction: number;
    campaigns_b_better: number;
    campaigns: number;
    sign_p_value: number;
  }[];
  strata: {
    h: number;
    stratum: string;
    value: string;
    arm: string;
    n: number;
    mse_reduction_vs_M0: number;
  }[];
  reference: {
    h: number;
    model: string;
    n: number;
    rmse: number;
    mae: number;
    skill_vs_persistence: number;
  }[];
  robustness: {
    setting: string;
    h: number;
    a: string;
    b: string;
    mse_reduction: number;
    mae_reduction: number;
  }[];
}

export interface CalibrationPayload {
  source: string;
  coverage: {
    h: number;
    method: string;
    nominal: number;
    group_var: string;
    group: string;
    n: number;
    coverage: number;
    median_width: number;
    winkler: number;
  }[];
  drift: { h: number; year: number; median_residual: number; n: number }[];
  jjas_anomaly_pct: Record<string, number>;
}

export interface TriggerRow {
  h: number;
  event: string;
  trigger: number;
  warning_rate: number;
  hit_rate: number;
  false_alarm_rate: number;
  false_alarm_ratio: number;
  value: number;
  n: number;
}

export interface DecisionPayload {
  source: string;
  value: {
    h: number;
    event_id: string;
    arm: string;
    alpha: number;
    value: number;
    value_lo: number;
    value_hi: number;
  }[];
  triggers: TriggerRow[];
  scores: {
    h: number;
    event_id: string;
    arm: string;
    bss: number;
    roc_auc: number;
    event_rate: number;
    n: number;
  }[];
  case_study: {
    water_year: string;
    h: number;
    area: string;
    n: number;
    event_rate: number;
    mean_p: number;
    hit_rate: number;
    false_alarm_ratio: number;
  }[];
}

// ── Hooks ────────────────────────────────────────────────────────────────────

async function fetchData<T>(path: string): Promise<T> {
  const res = await fetch(`/data/${path}`);
  if (!res.ok) {
    throw new Error(
      `Could not load ${path} (${res.status}). Run "python -m src.research.export_dashboard" to generate the dashboard data.`,
    );
  }
  return res.json() as Promise<T>;
}

const forever = { staleTime: Infinity, gcTime: Infinity } as const;

export const useSummary = () =>
  useQuery({
    queryKey: ["data", "summary"],
    queryFn: () => fetchData<Summary>("summary.json"),
    ...forever,
  });
export const useStations = () =>
  useQuery({
    queryKey: ["data", "stations"],
    queryFn: () => fetchData<Station[]>("stations.json"),
    ...forever,
  });
export const useSkill = () =>
  useQuery({
    queryKey: ["data", "skill"],
    queryFn: () => fetchData<SkillPayload>("skill.json"),
    ...forever,
  });
export const useCalibration = () =>
  useQuery({
    queryKey: ["data", "calibration"],
    queryFn: () => fetchData<CalibrationPayload>("calibration.json"),
    ...forever,
  });
export const useDecision = () =>
  useQuery({
    queryKey: ["data", "decision"],
    queryFn: () => fetchData<DecisionPayload>("decision.json"),
    ...forever,
  });

/** Per-well detail lives in 64 bucket files (bucket = sum of character codes mod 64). */
export function useWellDetail(station: Station | undefined) {
  const bucket = station?.b;
  const query = useQuery({
    queryKey: ["data", "wells", bucket],
    queryFn: () => fetchData<Record<string, WellDetail>>(`wells/${bucket}.json`),
    enabled: bucket !== undefined,
    ...forever,
  });
  return { ...query, detail: station ? query.data?.[station.id] : undefined };
}

// ── Helpers ──────────────────────────────────────────────────────────────────

const SEASON_LONG: Record<string, string> = {
  Jan: "January",
  May: "May (pre-monsoon)",
  Aug: "August (monsoon)",
  Nov: "November (post-monsoon)",
};
const MONTH_OFFSET: Record<string, number> = { Jan: 0, May: 4, Aug: 7, Nov: 10 };

/** "2019-May" → "May 2019". */
export function campaignShort(label: string): string {
  const [year, season] = label.split("-");
  return `${season} ${year}`;
}

/** "2019-May" → "May (pre-monsoon) 2019". */
export function campaignLong(label: string): string {
  const [year, season] = label.split("-");
  return `${SEASON_LONG[season ?? ""] ?? season} ${year}`;
}

/** "2019-May" → 2019.33 (fractional year, for real spacing on time axes). */
export function campaignYear(label: string): number {
  const [year, season] = label.split("-");
  return Number(year) + (MONTH_OFFSET[season ?? ""] ?? 0) / 12;
}

export const HORIZON_KEYS: HorizonKey[] = ["1", "2", "4"];
export const HORIZON_LABEL: Record<HorizonKey, string> = {
  "1": "3 months",
  "2": "6 months",
  "4": "12 months",
};
export const EVENT_LABEL: Record<EventKey, string> = {
  E1: "Deeper than usual for the season",
  E3: "Water drops below 8 m",
};
export const EVENT_SHORT: Record<EventKey, string> = { E1: "Deeper than usual", E3: "Below 8 m" };
export const EVENT_HELP: Record<EventKey, string> = {
  E1: "Depth beyond the well's own 80th percentile for that season (readings up to 2018).",
  E3: "For wells now at 8 m or shallower: the water falls past the depth where surface pumps lose suction.",
};

export const fmt = (v: number, digits = 2) => v.toFixed(digits);
export const pct = (v: number, digits = 0) => `${(v * 100).toFixed(digits)}%`;
/** A probability for display: never claims certainty from a calibrated forecast. */
export const chance = (p: number) => (p >= 0.995 ? "> 99%" : p <= 0.005 ? "< 1%" : pct(p));
export const int = (v: number) => v.toLocaleString("en-IN");
export const signed = (v: number, digits = 1) =>
  `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(digits)}`;
