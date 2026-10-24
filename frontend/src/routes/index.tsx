import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Eye, HelpCircle } from "lucide-react";

import { SiteHeader } from "@/components/site-header";
import { Hydrograph, HydrographLegend } from "@/components/hydrograph";
import { LAYER_CLASSES, NetworkMap, layerCounts } from "@/components/network-map";
import type { MapLayer } from "@/components/network-map";
import { WellExplorer } from "@/components/well-explorer";
import {
  CalibrationChart,
  CoverageByDepth,
  MethodTable,
  ReliabilityChart,
  ShapChart,
  SkillChart,
  StationSkillChart,
} from "@/components/evidence";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { PAPER_TITLE, beyond, gaps } from "@/content/research";
import type { HorizonKey, Station, WellSeries } from "@/lib/research-data";
import {
  HORIZON_KEYS,
  HORIZON_LABEL,
  campaignLong,
  fmt,
  int,
  pct,
  useBenchmark,
  useSeries,
  useStations,
  useSummary,
} from "@/lib/research-data";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "AquaSense — Groundwater forecasts for India" },
      {
        name: "description",
        content:
          "Calibrated groundwater-level forecasts and early warnings for India's CGWB monitoring network.",
      },
    ],
  }),
  component: Index,
});

/** The hero well: a long record with a current warning, so the picture shows why it matters. */
function pickFeatured(stations: Station[], series: Record<string, WellSeries>): string | null {
  const candidates = stations
    .filter((s) => series[s.id] && s.fc && s.risk === "Alert" && s.yrs >= 15)
    .sort((a, b) => (b.fc?.p ?? 0) - (a.fc?.p ?? 0) || b.n - a.n);
  return candidates[0]?.id ?? Object.keys(series)[0] ?? null;
}

function Index() {
  const summary = useSummary();
  const stations = useStations();
  const series = useSeries();
  const benchmark = useBenchmark();

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [layer, setLayer] = useState<MapLayer>("risk");
  const [horizon, setHorizon] = useState<HorizonKey>("1");

  const featuredId = useMemo(
    () => (stations.data && series.data ? pickFeatured(stations.data, series.data) : null),
    [stations.data, series.data],
  );
  useEffect(() => {
    if (!selectedId && featuredId) setSelectedId(featuredId);
  }, [featuredId, selectedId]);

  const featured = featuredId ? stations.data?.find((s) => s.id === featuredId) : undefined;
  const featuredSeries = featuredId ? series.data?.[featuredId] : undefined;
  const loadError = [summary, stations, series, benchmark].find((q) => q.error)?.error;

  const selectWell = (id: string) => {
    setSelectedId(id);
    document.getElementById("wells")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div id="top" className="min-h-screen bg-ground text-ink">
      <SiteHeader />

      <main>
        {/* ── Hero: a real hydrograph hanging below the ground line ── */}
        <section className="mx-auto max-w-[1200px] px-4 pt-14 sm:px-6 sm:pt-20">
          <h1 className="type-display max-w-[17ch] text-[clamp(2.4rem,5.6vw,4.4rem)] text-ink">
            Where India's groundwater is heading, and how sure we can be
          </h1>
          <div className="mt-6 grid gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] md:gap-12">
            <p className="max-w-[56ch] text-[1.1rem] leading-relaxed text-ink-2">
              Forecasts for wells in the Central Ground Water Board network, three to twelve months
              ahead. Each forecast comes with a range that has been checked against what actually
              happened, so a warning means what it says.
            </p>
            {summary.data && (
              <p className="tnum max-w-[48ch] text-[1.1rem] leading-relaxed text-ink-2">
                Built from {int(summary.data.n_obs)} readings at {int(summary.data.n_stations)}{" "}
                wells, {summary.data.first_year} to {summary.data.last_year}. From each well's
                latest reading (mostly 2022–2023), {int(summary.data.risk_counts.Alert ?? 0)} wells
                were heading for a deeper-than-usual level, and{" "}
                {int(summary.data.trend.sig_deepening)} show a significant long-term fall in the
                pre-monsoon water table.
              </p>
            )}
          </div>
        </section>

        <div className="mt-12" aria-hidden>
          <div className="ground-line" />
        </div>

        <section
          className="mx-auto -mt-[14px] max-w-[1200px] px-4 pb-6 sm:px-6"
          aria-label="Featured well"
        >
          {loadError ? (
            <p role="alert" className="py-10 text-ink">
              {(loadError as Error).message}
            </p>
          ) : featured && featuredSeries ? (
            <>
              <Hydrograph
                series={featuredSeries}
                forecast={featured.fc}
                fromSurface
                groundAbove
                height={380}
                sinceYear={2008}
              />
              <div className="mt-3 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <p className="max-w-[70ch] text-[0.9375rem] text-ink-2">
                  Well {featured.id} ({fmt(featured.lat, 2)}° N, {fmt(featured.lon, 2)}° E). Depth
                  below ground is drawn downward, the way the water sits under the surface.
                  {featured.fc?.p != null &&
                    ` For ${campaignLong(featured.fc.target)} the model gives a ${pct(featured.fc.p)} chance of a deeper-than-usual reading.`}
                </p>
                <HydrographLegend />
              </div>
            </>
          ) : (
            <div
              className="h-[360px] animate-pulse rounded-md bg-sunk"
              aria-label="Loading featured well"
            />
          )}
        </section>

        {/* ── Network ── */}
        <Section
          id="network"
          title="The monitoring network"
          lede="Every point is a well. Switch layers to see current warnings, long-term trends or how each well is measured."
        >
          {stations.data ? (
            <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_300px]">
              <div className="min-w-0">
                <NetworkMap
                  stations={stations.data}
                  layer={layer}
                  selectedId={selectedId}
                  onSelect={selectWell}
                />
                <p className="mt-2 text-[0.8125rem] text-ink-3">
                  Wells plotted by latitude and longitude. No boundary map is drawn.
                </p>
              </div>
              <div className="flex flex-col gap-5">
                <ToggleGroup
                  type="single"
                  value={layer}
                  onValueChange={(v) => v && setLayer(v as MapLayer)}
                  className="w-full flex-wrap justify-start rounded-md border border-rule"
                  aria-label="Map layer"
                >
                  <ToggleGroupItem value="risk" className="flex-1 px-3 text-[0.875rem]">
                    Warnings
                  </ToggleGroupItem>
                  <ToggleGroupItem value="trend" className="flex-1 px-3 text-[0.875rem]">
                    Trend
                  </ToggleGroupItem>
                  <ToggleGroupItem value="network" className="flex-1 px-3 text-[0.875rem]">
                    Type
                  </ToggleGroupItem>
                </ToggleGroup>
                <MapLegend stations={stations.data} layer={layer} />
                <p className="text-[0.875rem] text-ink-2">
                  {layer === "risk" &&
                    "Each warning compares the forecast for the campaign after a well's last reading with that well's own usual level for the season, so a deep well is not flagged just for being deep. Most manual records in this file end in 2022–2023."}
                  {layer === "trend" &&
                    "Sen's slope of May (pre-monsoon) depth for wells with at least eight years of May readings, tested with Mann–Kendall at the 5% level."}
                  {layer === "network" &&
                    "Manual wells are read in January, May, August and November. Telemetry wells report several times a day, mostly since 2023."}
                </p>
              </div>
            </div>
          ) : (
            <div className="h-[520px] animate-pulse rounded-md bg-sunk" />
          )}
        </Section>

        {/* ── Wells ── */}
        <Section
          id="wells"
          title="Look at one well"
          lede="Readings, the forecasts the model would have made for them, and the forecast for the campaign after the last reading."
        >
          {stations.data && series.data ? (
            <WellExplorer
              stations={stations.data}
              series={series.data}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          ) : (
            <div className="h-[420px] animate-pulse rounded-md bg-sunk" />
          )}
        </Section>

        {/* ── Evidence ── */}
        <Section
          id="evidence"
          title="How far to trust the forecasts"
          lede={`All results are on readings from 2019 to 2025, which the model never saw. It was trained on data up to ${benchmark.data?.split.train_end_year ?? 2015} and calibrated on ${(benchmark.data?.split.train_end_year ?? 2015) + 1}–${benchmark.data?.split.cal_end_year ?? 2018}.`}
        >
          {benchmark.data ? (
            <div className="flex flex-col gap-10">
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-[0.9375rem] text-ink-2" id="horizon-label">
                  Forecast horizon
                </span>
                <ToggleGroup
                  type="single"
                  value={horizon}
                  onValueChange={(v) => v && setHorizon(v as HorizonKey)}
                  className="rounded-md border border-rule"
                  aria-labelledby="horizon-label"
                >
                  {HORIZON_KEYS.map((k) => (
                    <ToggleGroupItem key={k} value={k} className="px-4 text-[0.875rem]">
                      {HORIZON_LABEL[k]}
                    </ToggleGroupItem>
                  ))}
                </ToggleGroup>
              </div>

              <CoverageByDepth data={benchmark.data} h={horizon} />

              <div className="grid gap-10 lg:grid-cols-2">
                <CalibrationChart data={benchmark.data} h={horizon} />
                <MethodTable data={benchmark.data} h={horizon} />
              </div>
              <div className="grid gap-10 lg:grid-cols-2">
                <SkillChart data={benchmark.data} h={horizon} />
                <StationSkillChart data={benchmark.data} h={horizon} />
              </div>
              <div className="grid gap-10 lg:grid-cols-2">
                <ReliabilityChart data={benchmark.data} h={horizon} />
                <ShapChart data={benchmark.data} h={horizon} />
              </div>
            </div>
          ) : (
            <div className="h-[420px] animate-pulse rounded-md bg-sunk" />
          )}
        </Section>

        {/* ── Agenda ── */}
        <Section
          id="agenda"
          title="Research agenda"
          lede={`Working paper: ${PAPER_TITLE}. G1 to G3 form the paper; the rest are follow-ups.`}
        >
          <ul className="grid gap-x-12 gap-y-8 md:grid-cols-2">
            {gaps.map((g) => (
              <li key={g.id} className="flex flex-col gap-2 border-t border-rule pt-4">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h3 className="type-heading text-[1.15rem] text-ink">
                    <span className="tnum mr-2 text-ink-3">{g.id}</span>
                    {g.title}
                  </h3>
                  <span className="rounded-md bg-sunk px-2 py-0.5 text-[0.8125rem] text-ink-2">
                    {g.status}
                  </span>
                </div>
                <p className="max-w-[62ch] text-[0.9375rem] text-ink">{g.question}</p>
                <p className="max-w-[62ch] text-[0.9375rem] text-ink-2">{g.why}</p>
              </li>
            ))}
          </ul>
          <h3 className="type-heading mt-14 text-[1.2rem] text-ink">Beyond this dataset</h3>
          <ul className="mt-4 grid gap-6 md:grid-cols-3">
            {beyond.map((b) => (
              <li key={b.title} className="flex flex-col gap-1.5">
                <span className="font-semibold text-ink">{b.title}</span>
                <span className="text-[0.9375rem] text-ink-2">{b.body}</span>
              </li>
            ))}
          </ul>
        </Section>
      </main>

      <footer className="mt-20 border-t border-rule">
        <div className="mx-auto flex max-w-[1200px] flex-col gap-3 px-4 py-10 text-[0.875rem] text-ink-2 sm:px-6">
          <p className="max-w-[80ch]">
            Data: CGWB groundwater levels from the public "Groundwater India Data" compilation
            (manual network 1994–2025, DWLR telemetry mostly 2023–2025), cleaned as described in
            docs/04. Most manual-well records in this file end in 2022–2023, so forecasts start from
            each well's last reading; a refresh from India-WRIS would make them current. Forecasts
            use groundwater history only; rainfall forcing is being added.
          </p>
          <p className="max-w-[80ch]">
            An earlier version of this dashboard showed results from a pipeline that trained on
            borehole depth instead of water level. Those numbers were withdrawn; see
            docs/01-project-audit.md.
          </p>
          {summary.data && <p>Data generated {summary.data.generated}.</p>}
        </div>
      </footer>
    </div>
  );
}

function Section({
  id,
  title,
  lede,
  children,
}: {
  id: string;
  title: string;
  lede: string;
  children: React.ReactNode;
}) {
  return (
    <section
      id={id}
      className="mx-auto max-w-[1200px] px-4 pt-20 sm:px-6"
      aria-labelledby={`${id}-title`}
    >
      <div className="mb-8 border-t border-rule-strong pt-6">
        <h2 id={`${id}-title`} className="type-heading text-[clamp(1.6rem,3vw,2.1rem)] text-ink">
          {title}
        </h2>
        <p className="mt-2 max-w-[68ch] text-[1.0625rem] text-ink-2">{lede}</p>
      </div>
      {children}
    </section>
  );
}

const LEGEND_ICON: Record<string, typeof AlertTriangle> = {
  Alert: AlertTriangle,
  Watch: Eye,
  Normal: CheckCircle2,
  "Insufficient history": HelpCircle,
};

function MapLegend({ stations, layer }: { stations: Station[]; layer: MapLayer }) {
  const counts = layerCounts(stations, layer);
  return (
    <table className="w-full text-[0.9375rem]">
      <caption className="sr-only">Wells per class</caption>
      <tbody>
        {LAYER_CLASSES[layer].map((c) => {
          const Icon = layer === "risk" ? LEGEND_ICON[c.key] : undefined;
          return (
            <tr key={c.key} className="border-b border-rule last:border-0">
              <td className="py-1.5 pr-2">
                <span className="flex items-center gap-2 text-ink">
                  <span
                    className="inline-block h-3 w-3 shrink-0 rounded-full"
                    style={{ background: `var(--${c.color})`, opacity: c.faint ? 0.45 : 1 }}
                    aria-hidden
                  />
                  {Icon && <Icon className="h-3.5 w-3.5 text-ink-2" aria-hidden />}
                  {c.label}
                </span>
              </td>
              <td className="tnum py-1.5 text-right text-ink-2">{int(counts[c.key] ?? 0)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
