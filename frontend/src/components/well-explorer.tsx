import { useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Eye, HelpCircle } from "lucide-react";
import type { RiskClass, Station, WellSeries } from "@/lib/research-data";
import { campaignLong, campaignShort, fmt, int, pct } from "@/lib/research-data";
import { Hydrograph, HydrographLegend } from "@/components/hydrograph";
import { RISK_COPY, StationSummary } from "@/components/network-map";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

const RISK_STYLE: Record<RiskClass, { icon: typeof AlertTriangle; color: string }> = {
  Alert: { icon: AlertTriangle, color: "var(--critical)" },
  Watch: { icon: Eye, color: "var(--warning)" },
  Normal: { icon: CheckCircle2, color: "var(--good)" },
  "Insufficient history": { icon: HelpCircle, color: "var(--none)" },
};
const RISK_RANK: Record<string, number> = {
  Alert: 0,
  Watch: 1,
  Normal: 2,
  "Insufficient history": 3,
};

export function RiskBadge({ risk }: { risk: RiskClass }) {
  const { icon: Icon, color } = RISK_STYLE[risk];
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md border border-rule bg-panel px-2 py-0.5 text-[0.875rem] text-ink">
      <Icon className="h-4 w-4" style={{ color }} aria-hidden />
      {risk === "Insufficient history" ? "Not enough history" : risk}
    </span>
  );
}

/** Plain-language summary built only from the calibrated outputs. */
export function forecastBrief(s: Station): string | null {
  const fc = s.fc;
  if (!fc) return null;
  const change = fc.q50 - fc.now;
  const dir =
    Math.abs(change) < 0.1
      ? "about the same as the last reading"
      : change > 0
        ? `${fmt(change)} m deeper than the last reading`
        : `${fmt(-change)} m shallower than the last reading`;
  let text = `Starting from the last reading in the file (${campaignShort(fc.origin)}), the reading for ${campaignLong(fc.target)} is expected at ${fmt(fc.q50)} m below ground, ${dir}. The 80% range is ${fmt(fc.lo)} to ${fmt(fc.hi)} m; past ranges built this way held about 8 times in 10.`;
  if (fc.thr != null && fc.p != null) {
    text += ` There is a ${pct(fc.p)} chance it will be deeper than this well's usual level for the season (${fmt(fc.thr)} m, the 80th percentile of past readings).`;
  }
  return text;
}

interface WellExplorerProps {
  stations: Station[];
  series: Record<string, WellSeries>;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function WellExplorer({ stations, series, selectedId, onSelect }: WellExplorerProps) {
  const [zoom, setZoom] = useState<"data" | "surface">("data");
  const byId = useMemo(() => new Map(stations.map((s) => [s.id, s])), [stations]);
  const options = useMemo(
    () =>
      Object.keys(series)
        .map((id) => byId.get(id))
        .filter((s): s is Station => !!s)
        .sort(
          (a, b) => (RISK_RANK[a.risk ?? ""] ?? 4) - (RISK_RANK[b.risk ?? ""] ?? 4) || b.n - a.n,
        ),
    [series, byId],
  );

  const station = selectedId ? byId.get(selectedId) : undefined;
  const ws = selectedId ? series[selectedId] : undefined;
  const brief = station ? forecastBrief(station) : null;

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,340px)_minmax(0,1fr)]">
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-2">
          <label htmlFor="well-select" className="text-[0.9375rem] font-medium text-ink">
            Well
          </label>
          <Select value={ws && selectedId ? selectedId : ""} onValueChange={onSelect}>
            <SelectTrigger
              id="well-select"
              className="h-10 w-full border-rule-strong bg-panel text-ink"
            >
              <SelectValue
                placeholder={station ? `Well ${station.id} (map selection)` : "Choose a well"}
              />
            </SelectTrigger>
            <SelectContent className="max-h-[320px]">
              {options.map((s) => (
                <SelectItem key={s.id} value={s.id}>
                  <span className="tnum">{s.id}</span>
                  <span className="ml-2 text-ink-2">
                    {s.risk === "Insufficient history"
                      ? "not enough history"
                      : s.risk?.toLowerCase()}
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-[0.875rem] text-ink-2">
            {int(options.length)} wells with full histories, chosen to cover the country. Any well
            on the map can be opened.
          </p>
        </div>

        {station ? (
          <div className="flex flex-col gap-4 border-t border-rule pt-5">
            {station.fc ? (
              <div className="flex flex-col gap-2">
                <div className="text-[0.9375rem] text-ink-2">
                  Forecast for {campaignLong(station.fc.target)}, made from the{" "}
                  {campaignShort(station.fc.origin)} reading
                </div>
                <div className="type-figure text-[2.6rem] leading-none text-ink">
                  {fmt(station.fc.q50, 1)}{" "}
                  <span className="text-[1.1rem] font-medium text-ink-2">m below ground</span>
                </div>
                <div className="tnum text-[0.9375rem] text-ink-2">
                  80% range {fmt(station.fc.lo, 1)}–{fmt(station.fc.hi, 1)} m, last reading{" "}
                  {fmt(station.fc.now, 1)} m
                </div>
                {station.risk && (
                  <div className="mt-1 flex flex-col gap-1.5">
                    <RiskBadge risk={station.risk} />
                    <p className="text-[0.875rem] text-ink-2">{RISK_COPY[station.risk]}</p>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-[0.9375rem] text-ink-2">
                No forecast for this well. Forecasts are made for manual wells with a reading in
                2022 or later; telemetry wells join the model in a later phase.
              </p>
            )}
            {brief && (
              <p className="max-w-[60ch] text-[0.9375rem] leading-relaxed text-ink">{brief}</p>
            )}
            <div className="text-[0.875rem]">
              <StationSummary s={station} />
              <div className="tnum mt-0.5 text-ink-2">
                {fmt(station.lat, 3)}° N, {fmt(station.lon, 3)}° E
              </div>
            </div>
          </div>
        ) : (
          <p className="text-[0.9375rem] text-ink-2">
            Choose a well from the list or click one on the map.
          </p>
        )}
      </div>

      <div className="flex min-w-0 flex-col gap-3">
        {ws ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <HydrographLegend withNext={!!station?.fc} />
              <ToggleGroup
                type="single"
                value={zoom}
                onValueChange={(v) => v && setZoom(v as "data" | "surface")}
                className="rounded-md border border-rule"
                aria-label="Depth axis range"
              >
                <ToggleGroupItem value="data" className="px-3 text-[0.875rem]">
                  Fit to data
                </ToggleGroupItem>
                <ToggleGroupItem value="surface" className="px-3 text-[0.875rem]">
                  From ground surface
                </ToggleGroupItem>
              </ToggleGroup>
            </div>
            <Hydrograph
              series={ws}
              forecast={station?.fc}
              fromSurface={zoom === "surface"}
              height={380}
            />
          </>
        ) : (
          <div className="flex h-[380px] items-center justify-center rounded-md border border-dashed border-rule-strong px-6 text-center text-[0.9375rem] text-ink-2">
            {station
              ? "This well's full reading history is not in the dashboard sample. Its summary and forecast are on the left."
              : "The well's readings and forecasts will appear here."}
          </div>
        )}
      </div>
    </div>
  );
}
