import { useEffect, useMemo, useRef, useState } from "react";
import type { RiskClass, Station } from "@/lib/research-data";
import { fmt, int, pct } from "@/lib/research-data";
import { useCssColors } from "@/lib/theme";

export type MapLayer = "risk" | "trend" | "network";

const LON_MIN = 68;
const LON_MAX = 97.6;
const LAT_MIN = 7.6;
const LAT_MAX = 33;
const KX = Math.cos((22 * Math.PI) / 180);
const ASPECT = (LAT_MAX - LAT_MIN) / ((LON_MAX - LON_MIN) * KX);

const COLOR_VARS = [
  "critical",
  "warning",
  "good",
  "none",
  "rising",
  "deepening",
  "neutral-mid",
  "s1",
  "s2",
  "ink",
  "ground",
] as const;
type ColorVar = (typeof COLOR_VARS)[number];

interface ClassDef {
  key: string;
  label: string;
  color: ColorVar;
  faint?: boolean;
}

export const LAYER_CLASSES: Record<MapLayer, ClassDef[]> = {
  risk: [
    { key: "Alert", label: "Alert", color: "critical" },
    { key: "Watch", label: "Watch", color: "warning" },
    { key: "Normal", label: "Normal", color: "good" },
    { key: "Insufficient history", label: "Not enough history", color: "none" },
    { key: "none", label: "No forecast (record ends before 2022)", color: "none", faint: true },
  ],
  trend: [
    { key: "deepening", label: "Deepening (significant)", color: "deepening" },
    { key: "flat", label: "No significant trend", color: "neutral-mid" },
    { key: "rising", label: "Rising (significant)", color: "rising" },
    { key: "none", label: "Under 8 years of May readings", color: "none", faint: true },
  ],
  network: [
    { key: "manual", label: "Manual (4 campaigns a year)", color: "s1" },
    { key: "DWLR", label: "Telemetry (DWLR, daily)", color: "s2" },
  ],
};

export function classify(s: Station, layer: MapLayer): string {
  if (layer === "network") return s.net;
  if (layer === "risk") return s.risk ?? "none";
  if (s.trend === undefined || s.trendP === undefined) return "none";
  if (s.trendP >= 0.05) return "flat";
  return s.trend > 0 ? "deepening" : "rising";
}

const RISK_ORDER: Record<string, number> = {
  none: 0,
  "Insufficient history": 1,
  Normal: 2,
  Watch: 3,
  Alert: 4,
  flat: 1,
  rising: 2,
  deepening: 3,
  manual: 1,
  DWLR: 2,
};

interface NetworkMapProps {
  stations: Station[];
  layer: MapLayer;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function NetworkMap({ stations, layer, selectedId, onSelect }: NetworkMapProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [width, setWidth] = useState(0);
  const [hover, setHover] = useState<{ s: Station; x: number; y: number } | null>(null);
  const colors = useCssColors(COLOR_VARS);
  const height = Math.round(width * ASPECT);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => entry && setWidth(entry.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const project = useMemo(() => {
    const sx = width / ((LON_MAX - LON_MIN) * KX);
    return (lon: number, lat: number): [number, number] => [
      (lon - LON_MIN) * KX * sx,
      (LAT_MAX - lat) * sx,
    ];
  }, [width]);

  // Draw low-priority classes first so alerts and significant trends sit on top.
  const ordered = useMemo(
    () =>
      [...stations].sort(
        (a, b) => (RISK_ORDER[classify(a, layer)] ?? 0) - (RISK_ORDER[classify(b, layer)] ?? 0),
      ),
    [stations, layer],
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || width === 0) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    const defs = Object.fromEntries(LAYER_CLASSES[layer].map((c) => [c.key, c]));
    const r = width < 520 ? 1.8 : 2.6;
    for (const s of ordered) {
      const def = defs[classify(s, layer)];
      if (!def) continue;
      const [x, y] = project(s.lon, s.lat);
      ctx.globalAlpha = def.faint ? 0.35 : 0.92;
      ctx.fillStyle = colors[def.color];
      ctx.beginPath();
      ctx.arc(x, y, def.faint ? r * 0.75 : r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
    const sel = selectedId ? stations.find((s) => s.id === selectedId) : undefined;
    if (sel) {
      const [x, y] = project(sel.lon, sel.lat);
      ctx.lineWidth = 2;
      ctx.strokeStyle = colors.ground;
      ctx.beginPath();
      ctx.arc(x, y, 9, 0, Math.PI * 2);
      ctx.stroke();
      ctx.strokeStyle = colors.ink;
      ctx.beginPath();
      ctx.arc(x, y, 7.5, 0, Math.PI * 2);
      ctx.stroke();
    }
  }, [ordered, layer, width, height, project, colors, selectedId, stations]);

  const nearest = (clientX: number, clientY: number) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return null;
    const mx = clientX - rect.left;
    const my = clientY - rect.top;
    let best: Station | null = null;
    let bestD = 64; // 8 px radius
    for (const s of stations) {
      const [x, y] = project(s.lon, s.lat);
      const d = (x - mx) ** 2 + (y - my) ** 2;
      if (d < bestD) {
        bestD = d;
        best = s;
      }
    }
    return best ? { s: best, x: mx, y: my } : null;
  };

  return (
    <div ref={wrapRef} className="relative w-full">
      <canvas
        ref={canvasRef}
        style={{ width, height }}
        className="block cursor-crosshair"
        role="img"
        aria-label={`Map of ${stations.length} monitoring wells coloured by ${layer === "risk" ? "early-warning class" : layer === "trend" ? "long-term trend" : "monitoring type"}. Use the well selector below for keyboard access.`}
        onMouseMove={(e) => setHover(nearest(e.clientX, e.clientY))}
        onMouseLeave={() => setHover(null)}
        onClick={(e) => {
          const hit = nearest(e.clientX, e.clientY);
          if (hit) onSelect(hit.s.id);
        }}
      />
      {hover && (
        <div
          className="pointer-events-none absolute z-10 w-64 rounded-md border border-rule bg-panel px-3 py-2 text-[0.8125rem] shadow-sm"
          style={{
            left: Math.min(hover.x + 14, Math.max(0, width - 260)),
            top: Math.max(0, hover.y - 10),
          }}
        >
          <StationSummary s={hover.s} />
          <div className="mt-1 text-ink-3">Click to open this well</div>
        </div>
      )}
    </div>
  );
}

export function StationSummary({ s }: { s: Station }) {
  return (
    <>
      <div className="font-semibold text-ink">Well {s.id}</div>
      <div className="tnum text-ink-2">
        {s.net === "DWLR" ? "Telemetry well" : "Manual well"}, {int(s.n)} readings, {s.first}–
        {s.last}
      </div>
      <div className="tnum text-ink-2">Typical depth {fmt(s.median, 1)} m below ground</div>
      {s.trend !== undefined && s.trendP !== undefined && (
        <div className="tnum text-ink-2">
          Pre-monsoon trend {s.trend > 0 ? "+" : ""}
          {fmt(s.trend)} m/yr {s.trendP < 0.05 ? "(significant)" : "(not significant)"}
        </div>
      )}
      {s.fc?.p != null && (
        <div className="tnum text-ink-2">
          Chance of deeper-than-usual level: {pct(s.fc.p)} ({s.risk})
        </div>
      )}
    </>
  );
}

export function layerCounts(stations: Station[], layer: MapLayer): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const s of stations) {
    const k = classify(s, layer);
    counts[k] = (counts[k] ?? 0) + 1;
  }
  return counts;
}

export const RISK_COPY: Record<RiskClass, string> = {
  Alert:
    "60% or higher chance the forecast reading is deeper than this well's usual level for the season.",
  Watch: "30–60% chance the forecast reading is deeper than usual.",
  Normal: "Under 30% chance the forecast reading is deeper than usual.",
  "Insufficient history":
    "Fewer than four past readings for that season, so there is no usual level to compare against.",
};
