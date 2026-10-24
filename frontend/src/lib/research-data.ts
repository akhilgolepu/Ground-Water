/**
 * Research artefacts produced by `python -m src.research.benchmark`
 * and served as static JSON from /data (frontend/public/data).
 */
import { useQuery } from "@tanstack/react-query";

// ── Types ────────────────────────────────────────────────────────────────────

export type RiskClass = "Alert" | "Watch" | "Normal" | "Insufficient history";

export interface Summary {
  generated: string;
  n_stations: number;
  n_manual: number;
  n_dwlr: number;
  n_obs: number;
  first_year: number;
  last_year: number;
  n_campaign_values: number;
  risk_counts: Partial<Record<RiskClass, number>>;
  trend: { n_wells: number; sig_deepening: number; sig_rising: number };
  season_names: string[];
}

export interface OperationalForecast {
  origin: string;
  target: string;
  now: number;
  q50: number;
  lo: number;
  hi: number;
  thr: number | null;
  p: number | null;
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
  trend?: number;
  trendP?: number;
  fc?: OperationalForecast;
  risk?: RiskClass;
}

export interface WellSeries {
  obs: [string, number][];
  pred: [string, number, number, number][];
}

export interface PointMetrics {
  rmse: number;
  mae: number;
  bias: number;
  skill_vs_persistence: number;
}

export interface HorizonResult {
  months_ahead: number;
  n_train: number;
  n_cal: number;
  n_test: number;
  n_test_wells: number;
  metrics: Record<string, PointMetrics>;
  station_skill: { n_wells: number; median: number; share_positive: number; histogram: number[] };
  early_warning: {
    event: string;
    n: number;
    event_rate: number;
    brier: number;
    brier_climatology: number;
    brier_skill: number;
    reliability: { p_mean: number; obs_freq: number; n: number }[];
  };
}

export interface CoverageRow {
  h: number;
  nominal: number;
  method: string;
  coverage: number;
  median_width_m: number;
  group: string;
}

export interface ImportanceRow {
  feature: string;
  key: string;
  mean_abs_shap_m: number;
}

export interface Benchmark {
  horizons: Record<string, HorizonResult>;
  split: { train_end_year: number; cal_end_year: number };
  coverage: CoverageRow[];
  importance: Record<string, ImportanceRow[]>;
}

// ── Hooks ────────────────────────────────────────────────────────────────────

async function fetchData<T>(name: string): Promise<T> {
  const res = await fetch(`/data/${name}.json`);
  if (!res.ok) {
    throw new Error(
      `Could not load ${name}.json (${res.status}). Run "python -m src.research.benchmark" to generate the dashboard data.`,
    );
  }
  return res.json() as Promise<T>;
}

const forever = { staleTime: Infinity, gcTime: Infinity } as const;

export const useSummary = () =>
  useQuery({
    queryKey: ["data", "summary"],
    queryFn: () => fetchData<Summary>("summary"),
    ...forever,
  });
export const useStations = () =>
  useQuery({
    queryKey: ["data", "stations"],
    queryFn: () => fetchData<Station[]>("stations"),
    ...forever,
  });
export const useSeries = () =>
  useQuery({
    queryKey: ["data", "series"],
    queryFn: () => fetchData<Record<string, WellSeries>>("series"),
    ...forever,
  });
export const useBenchmark = () =>
  useQuery({
    queryKey: ["data", "benchmark"],
    queryFn: () => fetchData<Benchmark>("benchmark"),
    ...forever,
  });

// ── Helpers ──────────────────────────────────────────────────────────────────

const SEASON_INDEX: Record<string, number> = { Jan: 0, May: 1, Aug: 2, Nov: 3 };
const SEASON_LONG: Record<string, string> = {
  Jan: "January",
  May: "May",
  Aug: "August",
  Nov: "November",
};
const SEASON_NOTE: Record<string, string> = {
  Jan: "",
  May: " (pre-monsoon)",
  Aug: " (monsoon)",
  Nov: " (post-monsoon)",
};

/** "2019-May" → year·4 + season, for sorting campaign labels. */
export function campaignIndex(label: string): number {
  const [year, season] = label.split("-");
  return Number(year) * 4 + (SEASON_INDEX[season ?? ""] ?? 0);
}

/** "2019-May" → "May 2019". */
export function campaignShort(label: string): string {
  const [year, season] = label.split("-");
  return `${season} ${year}`;
}

/** "2019-May" → "May 2019 (pre-monsoon)". */
export function campaignLong(label: string): string {
  const [year, season] = label.split("-");
  return `${SEASON_LONG[season ?? ""] ?? season} ${year}${SEASON_NOTE[season ?? ""] ?? ""}`;
}

export const HORIZON_KEYS = ["1", "2", "4"] as const;
export type HorizonKey = (typeof HORIZON_KEYS)[number];
export const HORIZON_LABEL: Record<HorizonKey, string> = {
  "1": "3 months",
  "2": "6 months",
  "4": "12 months",
};

export const fmt = (v: number, digits = 2) => v.toFixed(digits);
export const pct = (v: number, digits = 0) => `${(v * 100).toFixed(digits)}%`;
export const int = (v: number) => v.toLocaleString("en-IN");
