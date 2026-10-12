/**
 * LivePolicySimulator – wired to POST /api/simulate.
 * Calls FastAPI with well_id + pumping/recharge sliders; renders baseline vs simulated.
 */
import { useState, useEffect, useCallback } from "react";
import { Check, Loader2, AlertCircle, Zap } from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { useSimulate } from "@/hooks/use-api";

interface Props {
  wellId: string | null;
}

function EmptyState() {
  return (
    <div className="flex h-64 flex-col items-center justify-center gap-3 rounded-2xl border bg-card text-center">
      <Zap className="size-8 text-muted-foreground/40" />
      <p className="text-sm text-muted-foreground">
        Select a well from the GIS map to run the policy simulator.
      </p>
    </div>
  );
}

export function LivePolicySimulator({ wellId }: Props) {
  const [pumping, setPumping] = useState([20]);
  const [recharge, setRecharge] = useState([10]);
  const [horizon, setHorizon] = useState(12);
  const { mutate, data, isPending, error, reset } = useSimulate();

  const runSim = useCallback(() => {
    if (!wellId) return;
    mutate({
      well_id: wellId,
      pumping_reduction_pct: pumping[0] ?? 20,
      recharge_enhancement_pct: recharge[0] ?? 10,
      forecast_horizon_months: horizon,
    });
  }, [wellId, pumping, recharge, horizon, mutate]);

  // auto-run on well change
  useEffect(() => {
    if (wellId) runSim();
    else reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wellId]);

  if (!wellId) return <EmptyState />;

  const chartData =
    data?.months.map((m, i) => ({
      month: m,
      baseline: data.baseline_q50[i],
      simulated: data.simulated_q50[i],
    })) ?? [];

  const saved = data?.water_saved_m3 ?? 0;

  return (
    <div className="space-y-5">
      {/* controls */}
      <div className="grid gap-5 rounded-2xl border bg-card p-5 sm:grid-cols-2">
        <div className="space-y-3">
          <div className="flex justify-between text-sm">
            <Label htmlFor="pump-slider">Pumping Restriction Quota</Label>
            <span className="font-semibold">{pumping[0]}%</span>
          </div>
          <Slider
            id="pump-slider"
            value={pumping}
            onValueChange={setPumping}
            min={0}
            max={50}
            step={1}
          />
        </div>
        <div className="space-y-3">
          <div className="flex justify-between text-sm">
            <Label htmlFor="recharge-slider">MAR Enhancement</Label>
            <span className="font-semibold">{recharge[0]}%</span>
          </div>
          <Slider
            id="recharge-slider"
            value={recharge}
            onValueChange={setRecharge}
            min={0}
            max={30}
            step={1}
          />
        </div>
        <div className="space-y-3">
          <Label>Forecast Horizon</Label>
          <div className="flex gap-2">
            {([3, 6, 12] as const).map((h) => (
              <button
                key={h}
                onClick={() => setHorizon(h)}
                className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-colors ${
                  horizon === h
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary text-secondary-foreground hover:bg-accent"
                }`}
              >
                {h} months
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-end">
          <Button
            onClick={runSim}
            disabled={isPending || !wellId}
            variant="hero"
            size="sm"
            className="w-full"
          >
            {isPending ? (
              <>
                <Loader2 className="size-4 animate-spin" /> Running…
              </>
            ) : (
              <>
                <Zap className="size-4" /> Run Simulation
              </>
            )}
          </Button>
        </div>
      </div>

      {/* result banner */}
      {data && !isPending && (
        <div className="flex items-center gap-2 rounded-xl border border-risk-low/30 bg-risk-low/10 px-4 py-3 text-sm font-semibold text-risk-low">
          <Check className="size-4 shrink-0" />
          <span>
            Simulation complete for <strong>{data.well_id}</strong> — saves ~
            {saved.toLocaleString("en-IN")} m³ over {horizon} months
          </span>
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertCircle className="size-4 shrink-0" />
          Simulation error: {error.message}
        </div>
      )}

      {/* chart */}
      {chartData.length > 0 && (
        <div className="rounded-2xl border bg-card p-4">
          <div className="mb-3 flex flex-wrap gap-5 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1.5">
              <span className="inline-block h-px w-8 border-b-2 border-dashed border-risk-high" />
              Baseline (no intervention)
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="inline-block h-px w-8 border-b-2 border-risk-low" />
              Simulated (with policy)
            </span>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={chartData} margin={{ left: -10, right: 10, top: 10, bottom: 0 }}>
              <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis
                dataKey="month"
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 10 }}
                interval="preserveStartEnd"
              />
              <YAxis
                reversed
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 10 }}
                label={{ value: "m bgl", angle: -90, position: "insideLeft", offset: 14, style: { fontSize: 10 } }}
              />
              <Tooltip
                formatter={(value: number, name: string) => [`${value.toFixed(2)} m`, name]}
                contentStyle={{
                  background: "var(--color-popover)",
                  border: "1px solid var(--color-border)",
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
              <Line
                type="monotone"
                dataKey="baseline"
                name="Baseline"
                stroke="var(--risk-high)"
                strokeWidth={2}
                strokeDasharray="6 3"
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="simulated"
                name="Simulated"
                stroke="var(--risk-low)"
                strokeWidth={2.5}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {isPending && (
        <div className="flex h-[280px] items-center justify-center gap-3 rounded-2xl border bg-card">
          <Loader2 className="size-5 animate-spin text-primary" />
          <span className="text-sm text-muted-foreground">Running TFT-constrained simulation…</span>
        </div>
      )}

      <p className="text-xs text-muted-foreground">
        Source: <code className="text-xs">POST /api/simulate</code> · Simulation uses TFT-derived
        baseline q₅₀ trajectory. Y-axis reversed: higher = deeper (more drawdown).
      </p>
    </div>
  );
}
