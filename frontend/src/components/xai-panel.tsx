/**
 * XAIPanel – wired to /api/xai.
 * Shows VSN feature importance, temporal attention weights, and NLG policy brief.
 */
import { Loader2, AlertCircle, BrainCircuit, FileText } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useXAI } from "@/hooks/use-api";

interface Props {
  wellId: string | null;
}

// Custom tooltip for bar charts
function BarTip({
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
      <p className="mb-1 font-semibold text-foreground truncate max-w-[220px]">{label}</p>
      {payload.map(
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (e: any) => (
          <p key={e.name} style={{ color: e.fill ?? e.color }}>
            {e.name}: {typeof e.value === "number" ? e.value.toFixed(4) : e.value}
          </p>
        ),
      )}
    </div>
  );
}

export function XAIPanel({ wellId }: Props) {
  const { data, isLoading, error } = useXAI(wellId);

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center gap-3 rounded-2xl border bg-card">
        <Loader2 className="size-5 animate-spin text-primary" />
        <span className="text-sm text-muted-foreground">Loading XAI analysis…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-40 items-center justify-center gap-2 rounded-2xl border bg-card">
        <AlertCircle className="size-5 text-destructive" />
        <span className="text-sm text-destructive">XAI API error: {error.message}</span>
      </div>
    );
  }

  if (!data) return null;

  const topFeatures = data.global_importance.slice(0, 10);
  const maxVsn = Math.max(...topFeatures.map((f) => f.vsn_score), 0.01);

  return (
    <div className="space-y-6">
      {/* Policy Brief */}
      <div className="rounded-2xl border border-primary/20 bg-primary/5 p-5">
        <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-primary">
          <FileText className="size-4" />
          NLG Policy Brief
          {wellId && (
            <span className="ml-2 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
              Well {wellId}
            </span>
          )}
        </div>
        <pre className="whitespace-pre-wrap text-xs leading-6 text-foreground/80 font-sans">
          {data.policy_brief}
        </pre>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* VSN Feature Importance */}
        <div className="rounded-2xl border bg-card p-5">
          <div className="mb-4 flex items-center gap-2">
            <BrainCircuit className="size-4 text-primary" />
            <h4 className="text-sm font-semibold">VSN Feature Importance (Top 10)</h4>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart
              data={topFeatures}
              layout="vertical"
              margin={{ left: 0, right: 16, top: 0, bottom: 0 }}
            >
              <CartesianGrid horizontal={false} strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis
                type="number"
                domain={[0, maxVsn * 1.1]}
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 10 }}
                tickFormatter={(v: number) => v.toFixed(2)}
              />
              <YAxis
                type="category"
                dataKey="feature"
                width={140}
                tick={{ fontSize: 9 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: string) =>
                  v.length > 22 ? v.slice(0, 20) + "…" : v
                }
              />
              <Tooltip content={<BarTip />} />
              <Bar dataKey="vsn_score" name="VSN Score" radius={[0, 4, 4, 0]}>
                {topFeatures.map((_, i) => (
                  <Cell
                    key={i}
                    fill={`oklch(${0.55 + i * 0.02} 0.16 ${248 - i * 8})`}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Temporal Attention Weights */}
        <div className="rounded-2xl border bg-card p-5">
          <div className="mb-4 flex items-center gap-2">
            <BrainCircuit className="size-4 text-aqua" />
            <h4 className="text-sm font-semibold">Temporal Attention (Lag Months)</h4>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart
              data={data.attention_weights}
              margin={{ left: -12, right: 8, top: 0, bottom: 0 }}
            >
              <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis
                dataKey="lag_month"
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 10 }}
                label={{ value: "Lag (months)", position: "insideBottom", offset: -2, style: { fontSize: 10 } }}
              />
              <YAxis
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 10 }}
                tickFormatter={(v: number) => v.toFixed(3)}
              />
              <Tooltip content={<BarTip />} />
              <Bar dataKey="attention_weight" name="Attention Weight" radius={[4, 4, 0, 0]}>
                {data.attention_weights.map((d, i) => (
                  <Cell
                    key={i}
                    fill={
                      d.lag_month === 3 || d.lag_month === 6 || d.lag_month === 12
                        ? "var(--aqua)"
                        : "var(--chart-blue)"
                    }
                    opacity={0.75 + d.attention_weight * 5}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p className="mt-2 text-xs text-muted-foreground">
            Aqua bars: seasonal lags (3, 6, 12 months) — typically most informative
          </p>
        </div>
      </div>

      {/* SHAP scores table */}
      <div className="rounded-2xl border bg-card overflow-hidden">
        <div className="border-b px-5 py-3 flex items-center gap-2">
          <BrainCircuit className="size-4 text-risk-medium" />
          <h4 className="text-sm font-semibold">SHAP Local Attribution (Top Features)</h4>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b bg-secondary/50 text-left text-muted-foreground">
                <th className="px-4 py-2 font-semibold">Feature</th>
                <th className="px-4 py-2 font-semibold text-right">VSN Score</th>
                <th className="px-4 py-2 font-semibold text-right">Mean |SHAP|</th>
                <th className="px-4 py-2 font-semibold">Relative Impact</th>
              </tr>
            </thead>
            <tbody>
              {topFeatures.map((f, i) => {
                const maxShap = Math.max(...topFeatures.map((x) => x.shap_score), 0.01);
                const pct = ((f.shap_score / maxShap) * 100).toFixed(0);
                return (
                  <tr key={i} className="border-b transition-colors hover:bg-secondary/30">
                    <td className="px-4 py-2 font-mono text-foreground/80">{f.feature}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{f.vsn_score.toFixed(4)}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{f.shap_score.toFixed(4)}</td>
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-2">
                        <div
                          className="h-1.5 rounded-full bg-primary/70"
                          style={{ width: `${pct}%`, minWidth: 4 }}
                        />
                        <span className="text-muted-foreground">{pct}%</span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <p className="text-xs text-muted-foreground">
        Source: <code className="text-xs">/api/xai</code> · VSN = Variable Selection Network weight from TFT ·
        SHAP = TreeSHAP mean absolute attribution
      </p>
    </div>
  );
}
