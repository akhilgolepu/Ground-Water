/**
 * API client hooks for AquaSense AI backend.
 * All endpoints proxied through /api (Vite dev proxy → FastAPI on :8000).
 */
import { useQuery, useMutation } from "@tanstack/react-query";

const BASE = "/api";

// ── Types ────────────────────────────────────────────────────────────────────

export interface WellOverview {
  well_id: string;
  latitude: number;
  longitude: number;
  current_depth_m: number;
  predicted_depth_m: number;
  risk_level: "Critical" | "Moderate" | "Stable";
  last_updated: string;
}

export interface ForecastPoint {
  timestamp: string;
  historical_m?: number | null;
  q10_m?: number | null;
  q50_m?: number | null;
  q90_m?: number | null;
}

export interface FeatureImportance {
  feature: string;
  vsn_score: number;
  shap_score: number;
}

export interface XAIResponse {
  global_importance: FeatureImportance[];
  attention_weights: { lag_month: number; attention_weight: number }[];
  policy_brief: string;
}

export interface SimulationRequest {
  well_id: string;
  pumping_reduction_pct: number;
  recharge_enhancement_pct: number;
  forecast_horizon_months: number;
}

export interface SimulationResponse {
  well_id: string;
  baseline_q50: number[];
  simulated_q50: number[];
  water_saved_m3: number;
  months: string[];
}

// ── Fetchers ─────────────────────────────────────────────────────────────────

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

async function postJSON<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

// ── Hooks ────────────────────────────────────────────────────────────────────

export function useWells() {
  return useQuery<WellOverview[]>({
    queryKey: ["wells"],
    queryFn: () => fetchJSON<WellOverview[]>(`${BASE}/wells`),
    staleTime: 60_000,
  });
}

export function useForecast(wellId: string | null) {
  return useQuery<ForecastPoint[]>({
    queryKey: ["forecast", wellId],
    queryFn: () => fetchJSON<ForecastPoint[]>(`${BASE}/forecast/${wellId}`),
    enabled: !!wellId,
    staleTime: 60_000,
  });
}

export function useXAI(wellId: string | null) {
  return useQuery<XAIResponse>({
    queryKey: ["xai", wellId],
    queryFn: () =>
      fetchJSON<XAIResponse>(`${BASE}/xai${wellId ? `?well_id=${wellId}` : ""}`),
    staleTime: 120_000,
  });
}

export function useSimulate() {
  return useMutation<SimulationResponse, Error, SimulationRequest>({
    mutationFn: (req) => postJSON<SimulationResponse>(`${BASE}/simulate`, req),
  });
}
