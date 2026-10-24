import { useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Search } from "lucide-react";
import type { HorizonKey, Station, WellForecast } from "@/lib/research-data";
import {
  EVENT_SHORT,
  HORIZON_KEYS,
  HORIZON_LABEL,
  campaignLong,
  campaignShort,
  chance,
  fmt,
  int,
  pct,
  useWellDetail,
} from "@/lib/research-data";
import { Hydrograph, HydrographLegend } from "@/components/hydrograph";
import { StationSummary, type WarningSettings } from "@/components/network-map";
import { Input } from "@/components/ui/input";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

interface WellExplorerProps {
  stations: Station[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  warning: WarningSettings;
}

export function WellExplorer({ stations, selectedId, onSelect, warning }: WellExplorerProps) {
  const [query, setQuery] = useState("");
  const [h, setH] = useState<HorizonKey>("1");
  const [compare, setCompare] = useState(true);
  const byId = useMemo(() => new Map(stations.map((s) => [s.id, s])), [stations]);
  const station = selectedId ? byId.get(selectedId) : undefined;
  const { detail, isLoading, error } = useWellDetail(station);
  const forecast = detail?.ops?.[h];

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (q.length < 2) return [];
    return stations
      .filter((s) => s.id.toLowerCase().includes(q) || (s.state ?? "").toLowerCase().includes(q))
      .sort((a, b) => Number(!!b.ops) - Number(!!a.ops) || b.n - a.n)
      .slice(0, 8);
  }, [query, stations]);

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-2">
          <label htmlFor="well-search" className="text-[0.9375rem] font-medium text-ink">
            Find a well
          </label>
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3"
              aria-hidden
            />
            <Input
              id="well-search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Well ID or state, e.g. Rajasthan"
              className="h-10 border-rule-strong bg-panel pl-9 text-ink"
              autoComplete="off"
            />
          </div>
          {matches.length > 0 && (
            <ul
              className="divide-y divide-rule rounded-md border border-rule bg-panel"
              aria-label="Matching wells"
            >
              {matches.map((s) => (
                <li key={s.id}>
                  <button
                    type="button"
                    onClick={() => {
                      onSelect(s.id);
                      setQuery("");
                    }}
                    className="flex w-full items-baseline justify-between gap-3 px-3 py-2 text-left text-[0.875rem] hover:bg-sunk"
                  >
                    <span className="tnum text-ink">{s.id}</span>
                    <span className="truncate text-ink-2">
                      {s.state ?? "unknown state"}
                      {s.ops ? "" : ", no forecast"}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <p className="text-[0.875rem] text-ink-2">Or click any well on the map above.</p>
        </div>

        {station ? (
          <div className="flex flex-col gap-4 border-t border-rule pt-5">
            <div className="text-[0.875rem]">
              <StationSummary s={station} />
              <div className="tnum mt-0.5 text-ink-2">
                {fmt(station.lat, 3)}° N, {fmt(station.lon, 3)}° E
                {station.region ? `, ${station.region}` : ""}
              </div>
            </div>
            {detail?.ops ? (
              <>
                <ToggleGroup
                  type="single"
                  value={h}
                  onValueChange={(v) => v && setH(v as HorizonKey)}
                  className="w-full rounded-md border border-rule"
                  aria-label="Forecast horizon"
                >
                  {HORIZON_KEYS.map((k) => (
                    <ToggleGroupItem
                      key={k}
                      value={k}
                      className="flex-1 text-[0.875rem]"
                      disabled={!detail.ops?.[k]}
                    >
                      {HORIZON_LABEL[k]}
                    </ToggleGroupItem>
                  ))}
                </ToggleGroup>
                {forecast && <ForecastCard f={forecast} warning={warning} />}
              </>
            ) : (
              !isLoading && (
                <p className="text-[0.9375rem] text-ink-2">
                  No forecast for this well: its last manual reading is before 2019, or it is a
                  telemetry well. Telemetry wells are not in the model yet.
                </p>
              )
            )}
            {detail?.mae && <RainfallEffect mae={detail.mae} />}
          </div>
        ) : (
          <p className="text-[0.9375rem] text-ink-2">
            Choose a well to see its readings and forecasts.
          </p>
        )}
      </div>

      <div className="flex min-w-0 flex-col gap-3">
        {error ? (
          <p role="alert" className="text-ink">
            {(error as Error).message}
          </p>
        ) : detail ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <HydrographLegend
                withNext={!!forecast}
                showMemoryOnly={compare}
                thresholdSeason={
                  forecast?.thrE1 != null ? forecast.target.split("-")[1] : undefined
                }
              />
              <label className="flex items-center gap-2 text-[0.875rem] text-ink-2">
                <input
                  type="checkbox"
                  checked={compare}
                  onChange={(e) => setCompare(e.target.checked)}
                  className="h-4 w-4 accent-[var(--s1)]"
                />
                Show the forecast without rainfall
              </label>
            </div>
            <Hydrograph detail={detail} forecast={forecast} showMemoryOnly={compare} height={400} />
            {detail.obs.some((o) => o[2] === 1) && (
              <p className="text-[0.8125rem] text-ink-3">
                Open circles are readings added from India-WRIS after the research snapshot.
              </p>
            )}
          </>
        ) : (
          <div className="flex h-[400px] items-center justify-center rounded-md border border-dashed border-rule-strong px-6 text-center text-[0.9375rem] text-ink-2">
            {isLoading
              ? "Loading this well's readings…"
              : "The well's readings and forecasts will appear here."}
          </div>
        )}
      </div>
    </div>
  );
}

function ForecastCard({ f, warning }: { f: WellForecast; warning: WarningSettings }) {
  const pE1 = f.pE1;
  const flagged = pE1 != null && pE1 >= warning.trigger;
  const rainfallShift = f.m2 - f.m0;
  return (
    <div className="flex flex-col gap-3">
      <div className="text-[0.9375rem] text-ink-2">
        {campaignLong(f.target)}, forecast from the {campaignShort(f.origin)} reading (
        {fmt(f.now, 1)} m)
      </div>
      <div className="type-figure text-[2.6rem] leading-none text-ink">
        {fmt(f.m2, 1)} <span className="text-[1.1rem] font-medium text-ink-2">m below ground</span>
      </div>
      {f.lo != null && f.hi != null && (
        <div className="tnum text-[0.9375rem] text-ink-2">
          80% range {fmt(f.lo, 1)}–{fmt(f.hi, 1)} m. Without rainfall: {fmt(f.m0, 1)} m (
          {Math.abs(rainfallShift) < 0.05
            ? "no change"
            : `rainfall moves it ${fmt(Math.abs(rainfallShift), 1)} m ${rainfallShift > 0 ? "deeper" : "shallower"}`}
          )
        </div>
      )}
      <table className="w-full text-[0.9375rem]">
        <caption className="sr-only">Warning probabilities</caption>
        <tbody>
          <tr className="border-b border-rule">
            <th scope="row" className="py-1.5 pr-2 text-left font-normal text-ink">
              {EVENT_SHORT.E1}
              {f.thrE1 != null && (
                <span className="tnum text-ink-3"> (&gt; {fmt(f.thrE1, 1)} m)</span>
              )}
            </th>
            <td className="tnum py-1.5 text-right text-ink">{pE1 != null ? chance(pE1) : "—"}</td>
          </tr>
          <tr>
            <th scope="row" className="py-1.5 pr-2 text-left font-normal text-ink">
              {EVENT_SHORT.E3}
            </th>
            <td className="tnum py-1.5 text-right text-ink">
              {f.pE3 != null ? chance(f.pE3) : "not applicable"}
            </td>
          </tr>
        </tbody>
      </table>
      {pE1 != null && warning.event === "E1" && (
        <div className="flex items-center gap-2 text-[0.9375rem] text-ink">
          {flagged ? (
            <AlertTriangle className="h-4 w-4 text-critical" aria-hidden />
          ) : (
            <CheckCircle2 className="h-4 w-4 text-good" aria-hidden />
          )}
          {flagged ? "Warning" : "No warning"} at your trigger of {pct(warning.trigger)}
        </div>
      )}
      {f.advisory && (
        <p className="max-w-[60ch] text-[0.9375rem] leading-relaxed text-ink-2">{f.advisory}</p>
      )}
    </div>
  );
}

function RainfallEffect({
  mae,
}: {
  mae: NonNullable<ReturnType<typeof useWellDetail>["detail"]>["mae"];
}) {
  const rows = HORIZON_KEYS.flatMap((k) => (mae?.[k] ? [{ k, ...mae[k]! }] : []));
  if (!rows.length) return null;
  return (
    <div className="border-t border-rule pt-4">
      <h3 className="text-[0.9375rem] font-semibold text-ink">
        What rainfall changed at this well, 2019–2025
      </h3>
      <table className="mt-2 w-full text-[0.875rem]">
        <thead>
          <tr className="border-b border-rule-strong text-ink-2">
            <th className="py-1.5 text-left font-medium">Horizon</th>
            <th className="py-1.5 text-right font-medium">Error without</th>
            <th className="py-1.5 text-right font-medium">With rainfall</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.k} className="border-b border-rule">
              <td className="py-1.5 text-ink">
                {HORIZON_LABEL[r.k]} <span className="text-ink-3">({int(r.n)})</span>
              </td>
              <td className="tnum py-1.5 text-right text-ink">{fmt(r.m0)} m</td>
              <td className="tnum py-1.5 text-right text-ink">
                {fmt(r.m2)} m{" "}
                <span className="text-ink-2">
                  {r.m2 < r.m0 ? "better" : r.m2 > r.m0 ? "worse" : "same"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-[0.8125rem] text-ink-3">
        Mean absolute error of test forecasts; count in brackets.
      </p>
    </div>
  );
}
