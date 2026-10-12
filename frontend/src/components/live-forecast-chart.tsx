/**
 * LiveForecastChart – wired to /api/forecast/{well_id}.
 * Renders historical observed + TFT q10/q50/q90 bands.
 */
import { Loader2, AlertCircle, TrendingDown } from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend,
} from "recharts";
import { useForecast } from "@/hooks/use-api";

interface Props {
  wellId: string | null;
  horizon: 3 | 6 | 12;
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex h-[340px] flex-col items-center justify-center gap-3 rounded-2xl border bg-card text-center">
      <TrendingDown className="size-8 text-muted-foreground/40" />
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

// Custom tooltip
function ForecastTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border bg-popover px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-semibold text-foreground">{label}</p>
      {payload.map(
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (entry: any) =>
          entry.value != null && (
            <p key={entry.name} style={{ color: entry.color ?? entry.stroke }}>
              {entry.name}: {typeof entry.value === "number" ? entry.value.toFixed(2) : entry.value} m
            </p>
          ),
      )}
    </div>
  );
}

export function LiveForecastChart({ wellId, horizon }: Props) {
  const { data, isLoading, error } = useForecast(wellId);

  if (!wellId)
    return <EmptyState message="Select a well from the GIS map or table to load its forecast." />;
  if (isLoading)
    return (
      <div className="flex h-[340px] items-center justify-center gap-3 rounded-2xl border bg-card">
        <Loader2 className="size-5 animate-spin text-primary" />
        <span className="text-sm text-muted-foreground">
          Loading forecast for {wellId}…
        </span>
      </div>
    );
  if (error)
    return (
      <div className="flex h-[340px] items-center justify-center gap-2 rounded-2xl border bg-card">
        <AlertCircle className="size-5 text-destructive" />
        <span className="text-sm text-destructive">
          API error: {error.message}
        </span>
      </div>
    );
  if (!data || data.length === 0)
    return <EmptyState message="No forecast data returned for this well." />;

  // Split into historical (has historical_m) and forecast (has q50_m)
  const histPoints = data.filter((d) => d.historical_m != null).slice(-24);
  const fcastPoints = data.filter((d) => d.q50_m != null).slice(0, horizon);

  // Merge for the chart: use timestamp as key, carry q10/q50/q90 for forecast points
  const chartData = [
    ...histPoints.map((d) => ({
      ts: d.timestamp,
      observed: d.historical_m,
      q10: null as number | null,
      q50: null as number | null,
      q90: null as number | null,
      band: null as [number, number] | null,
    })),
    ...fcastPoints.map((d) => ({
      ts: d.timestamp,
      observed: null as number | null,
      q10: d.q10_m ?? null,
      q50: d.q50_m ?? null,
      q90: d.q90_m ?? null,
      band: d.q10_m != null && d.q90_m != null
        ? ([d.q10_m, d.q90_m - d.q10_m] as [number, number])
        : null,
    })),
  ];

  // For recharts AreaChart: stack band as [base, range]
  const areaData = chartData.map((d) => ({
    ...d,
    bandBase: d.q10,
    bandRange: d.q10 != null && d.q90 != null ? d.q90 - d.q10 : null,
  }));

  const lastObserved = histPoints.at(-1)?.historical_m;
  const lastForecast = fcastPoints.at(-1)?.q50_m;
  const delta = lastObserved != null && lastForecast != null
    ? lastForecast - lastObserved
    : null;

  return (
    <div className="space-y-3">
      {/* summary strip */}
      {delta != null && (
        <div
          className={`flex items-center gap-2 rounded-xl border px-4 py-3 text-sm font-medium ${
            delta > 1 ? "border-risk-high/30 bg-risk-high/10 text-risk-high"
            : delta > 0 ? "border-risk-medium/30 bg-risk-medium/10 text-risk-medium"
            : "border-risk-low/30 bg-risk-low/10 text-risk-low"
          }`}
        >
          <TrendingDown className="size-4 shrink-0" />
          <span>
            {horizon}-month outlook for <strong>{wellId}</strong>:{" "}
            {delta > 0
              ? `+${delta.toFixed(2)} m drawdown (deeper)`
              : `${delta.toFixed(2)} m recharge (shallower)`}
          </span>
        </div>
      )}

      {/* chart */}
      <div className="rounded-2xl border bg-card p-4">
        <div className="mb-3 flex flex-wrap gap-5 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-px w-8 border-b-2 border-[var(--chart-blue)] border-solid" />
            Observed
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-px w-8 border-b-2 border-[var(--aqua)] border-solid" />
            TFT q₅₀ forecast
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2 w-8 rounded bg-[var(--aqua)]/25" />
            80% band (q₁₀–q₉₀)
          </span>
        </div>

        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={areaData} margin={{ left: -10, right: 10, top: 10, bottom: 0 }}>
            <defs>
              <linearGradient id="bandGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--aqua)" stopOpacity={0.3} />
                <stop offset="100%" stopColor="var(--aqua)" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--color-border)" />
            <XAxis
              dataKey="ts"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              tick={{ fontSize: 11 }}
              interval="preserveStartEnd"
            />
            <YAxis
              reversed
              tickLine={false}
              axisLine={false}
              tickMargin={6}
              tick={{ fontSize: 11 }}
              label={{ value: "m bgl", angle: -90, position: "insideLeft", offset: 14, style: { fontSize: 10 } }}
            />
            <Tooltip content={<ForecastTooltip />} />

            {/* 80% band: stack bandBase + bandRange */}
            <Area
              type="monotone"
              dataKey="bandBase"
              stackId="band"
              stroke="none"
              fill="transparent"
              legendType="none"
              connectNulls
            />
            <Area
              type="monotone"
              dataKey="bandRange"
              stackId="band"
              stroke="none"
              fill="url(#bandGrad)"
              name="80% band (q₁₀–q₉₀)"
              connectNulls
            />
            {/* observed line */}
            <Line
              type="monotone"
              dataKey="observed"
              name="Observed"
              stroke="var(--chart-blue)"
              strokeWidth={2.5}
              dot={false}
              connectNulls={false}
            />
            {/* q50 median */}
            <Line
              type="monotone"
              dataKey="q50"
              name="TFT q₅₀ forecast"
              stroke="var(--aqua)"
              strokeWidth={2.5}
              strokeDasharray="6 3"
              dot={false}
              connectNulls
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <p className="text-xs text-muted-foreground">
        Source: <code className="text-xs">/api/forecast/{wellId}</code> · Depth in metres below
        ground level (m bgl) · Y-axis reversed: higher = deeper
      </p>
    </div>
  );
}
