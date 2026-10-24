import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";

import { SiteHeader } from "@/components/site-header";
import { Hydrograph, HydrographLegend } from "@/components/hydrograph";
import { NetworkMap, layerClasses, layerCounts } from "@/components/network-map";
import type { MapLayer, WarningSettings } from "@/components/network-map";
import { WellExplorer } from "@/components/well-explorer";
import {
  CoverageFindings,
  DecisionPanel,
  HorizonPicker,
  RainfallFindings,
} from "@/components/findings";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { PAPER_TITLE, beyond, gaps } from "@/content/research";
import type { HorizonKey, Station } from "@/lib/research-data";
import {
  EVENT_SHORT,
  HORIZON_LABEL,
  campaignLong,
  campaignShort,
  chance,
  fmt,
  int,
  pct,
  useCalibration,
  useDecision,
  useSkill,
  useStations,
  useSummary,
  useWellDetail,
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

/** The hero well: a long record whose latest forecast carries a warning. */
function pickFeatured(stations: Station[]): Station | undefined {
  return stations
    .filter((s) => s.net === "manual" && s.yrs >= 15 && (s.ops?.["1"]?.e1 ?? 0) >= 0.6)
    .sort((a, b) => (b.ops?.["1"]?.e1 ?? 0) - (a.ops?.["1"]?.e1 ?? 0) || b.n - a.n)[0];
}

const DEFAULT_WARNING: WarningSettings = { event: "E1", h: "1", trigger: 0.3 };

function Index() {
  const summary = useSummary();
  const stations = useStations();
  const skill = useSkill();
  const calibration = useCalibration();
  const decision = useDecision();

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [layer, setLayer] = useState<MapLayer>("warnings");
  const [warning, setWarning] = useState<WarningSettings>(DEFAULT_WARNING);
  const [horizon, setHorizon] = useState<HorizonKey>("2");

  const featured = useMemo(
    () => (stations.data ? pickFeatured(stations.data) : undefined),
    [stations.data],
  );
  const featuredDetail = useWellDetail(featured);
  useEffect(() => {
    if (!selectedId && featured) setSelectedId(featured.id);
  }, [featured, selectedId]);

  const loadError = [summary, stations, skill, calibration, decision].find((q) => q.error)?.error;
  const gain6 = skill.data?.gains.find(
    (g) => g.h === 2 && g.a === "M0 memory" && g.b === "M2 + ENSO/IOD",
  );
  const value3 = decision.data?.triggers.find(
    (t) => t.h === 1 && t.event === "E1" && Math.abs(t.trigger - 0.3) < 1e-6,
  );

  const selectWell = (id: string) => {
    setSelectedId(id);
    document.getElementById("wells")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  const fc = featuredDetail.detail?.ops?.["1"];

  return (
    <div id="top" className="min-h-screen bg-ground text-ink">
      <SiteHeader />

      <main>
        {/* ── Hero: a real hydrograph hanging below the ground line ── */}
        <section className="mx-auto max-w-[1200px] px-4 pt-14 sm:px-6 sm:pt-20">
          <h1 className="type-display max-w-[17ch] text-[clamp(2.4rem,5.6vw,4.4rem)] text-ink">
            Where India's groundwater is heading, and how sure we can be
          </h1>
          <div className="mt-6 grid gap-6 md:grid-cols-2 md:gap-12">
            <p className="max-w-[56ch] text-[1.1rem] leading-relaxed text-ink-2">
              Forecasts for wells in the Central Ground Water Board network, three to twelve months
              ahead, with ranges and warning probabilities checked against what actually happened in
              2019–2025.
            </p>
            {summary.data && gain6 && value3 && (
              <p className="tnum max-w-[50ch] text-[1.1rem] leading-relaxed text-ink-2">
                Built from {int(summary.data.n_obs)} readings at {int(summary.data.n_stations)}{" "}
                wells. Monsoon rainfall and El Niño/IOD cut the squared error of six-month forecasts
                by {pct(gain6.mse_reduction, 0)}. Acting on three-month warnings at a 30% trigger
                recovers {pct(value3.value, 0)} of a perfect forecast's value.
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
          ) : featured && featuredDetail.detail ? (
            <>
              <Hydrograph
                detail={featuredDetail.detail}
                forecast={fc}
                fromSurface
                groundAbove
                height={380}
                sinceYear={2008}
              />
              <div className="mt-3 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <p className="max-w-[70ch] text-[0.9375rem] text-ink-2">
                  Well {featured.id}
                  {featured.state ? `, ${featured.state}` : ""} ({fmt(featured.lat, 2)}° N,{" "}
                  {fmt(featured.lon, 2)}° E). Depth below ground is drawn downward, the way the
                  water sits under the surface.
                  {fc?.pE1 != null &&
                    ` For ${campaignLong(fc.target)} the chance of a deeper-than-usual reading is ${chance(fc.pE1)}.`}
                </p>
                <HydrographLegend
                  thresholdSeason={fc?.thrE1 != null ? fc.target.split("-")[1] : undefined}
                />
              </div>
            </>
          ) : (
            <div
              className="h-[380px] animate-pulse rounded-md bg-sunk"
              aria-label="Loading featured well"
            />
          )}
        </section>

        {/* ── Network ── */}
        <Section
          id="network"
          title="The monitoring network"
          lede="Every point is a well. The warnings layer follows the settings in the next section."
        >
          {stations.data ? (
            <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_300px]">
              <div className="min-w-0">
                <NetworkMap
                  stations={stations.data}
                  layer={layer}
                  warning={warning}
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
                  <ToggleGroupItem value="warnings" className="flex-1 px-3 text-[0.875rem]">
                    Warnings
                  </ToggleGroupItem>
                  <ToggleGroupItem value="trend" className="flex-1 px-3 text-[0.875rem]">
                    Trend
                  </ToggleGroupItem>
                  <ToggleGroupItem value="network" className="flex-1 px-3 text-[0.875rem]">
                    Type
                  </ToggleGroupItem>
                </ToggleGroup>
                <MapLegend stations={stations.data} layer={layer} warning={warning} />
                <p className="text-[0.875rem] text-ink-2">
                  {layer === "warnings" &&
                    `${EVENT_SHORT[warning.event]}, ${HORIZON_LABEL[warning.h]} after each well's latest reading, warning at a ${pct(warning.trigger)} chance or more.`}
                  {layer === "trend" &&
                    "Sen's slope of May (pre-monsoon) depth for wells with at least eight years of May readings, tested with Mann–Kendall at the 5% level."}
                  {layer === "network" &&
                    "Manual wells are read in January, May, August and November. Telemetry wells report several times a day, mostly since 2023."}
                </p>
                {layer === "warnings" && summary.data && (
                  <p className="text-[0.8125rem] text-ink-3">
                    Latest readings in the data range from 2019 to{" "}
                    {campaignShort(summary.data.operational.latest_origin)}; most are from
                    2022–2023, when the published manual records end.
                  </p>
                )}
              </div>
            </div>
          ) : (
            <div className="h-[520px] animate-pulse rounded-md bg-sunk" />
          )}
        </Section>

        {/* ── Decide ── */}
        <Section
          id="decide"
          title="Decide when to warn"
          lede="A warning is worth acting on when the chance of the event is at least the cost of acting divided by the loss it avoids. Set that ratio and see how the warnings would have performed in 2019–2025."
        >
          {decision.data && stations.data ? (
            <DecisionPanel
              data={decision.data}
              stations={stations.data}
              warning={warning}
              onChange={setWarning}
            />
          ) : (
            <div className="h-[420px] animate-pulse rounded-md bg-sunk" />
          )}
        </Section>

        {/* ── Wells ── */}
        <Section
          id="wells"
          title="Look at one well"
          lede="Readings, the forecasts made three months ahead with and without rainfall, and the forecasts after the latest reading."
        >
          {stations.data ? (
            <WellExplorer
              stations={stations.data}
              selectedId={selectedId}
              onSelect={setSelectedId}
              warning={warning}
            />
          ) : (
            <div className="h-[420px] animate-pulse rounded-md bg-sunk" />
          )}
        </Section>

        {/* ── Findings ── */}
        <Section
          id="findings"
          title="What the research found"
          lede="All results are on 2019–2025 readings the models never saw. Models were trained on data up to 2015 and calibrated on 2016–2018."
        >
          <div className="mb-10">
            <HorizonPicker value={horizon} onChange={setHorizon} id="findings-horizon" />
          </div>
          <h3 className="type-heading mb-6 text-[1.45rem] text-ink">
            Does monsoon rainfall improve the forecasts?
          </h3>
          {skill.data ? (
            <RainfallFindings data={skill.data} h={horizon} />
          ) : (
            <div className="h-[300px] animate-pulse rounded-md bg-sunk" />
          )}
          <h3 className="type-heading mb-6 mt-16 text-[1.45rem] text-ink">
            Can the ranges be trusted for every kind of well?
          </h3>
          {calibration.data ? (
            <CoverageFindings data={calibration.data} h={horizon} />
          ) : (
            <div className="h-[300px] animate-pulse rounded-md bg-sunk" />
          )}
        </Section>

        {/* ── Paper ── */}
        <Section
          id="paper"
          title="The paper"
          lede={`${PAPER_TITLE}. Questions 1–3 are answered above; 4–6 are follow-up work.`}
        >
          <ul className="grid gap-x-12 gap-y-8 md:grid-cols-2">
            {gaps.map((g, i) => (
              <li key={g.id} className="flex flex-col gap-2 border-t border-rule pt-4">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h3 className="type-heading text-[1.15rem] text-ink">
                    <span className="tnum mr-2 text-ink-3">{i + 1}</span>
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
            (manual network 1994–2025, DWLR telemetry mostly 2023–2025); IMD gridded rainfall and
            temperature; NOAA Niño 3.4 and DMI; state boundaries from geoBoundaries (ODbL).
            Processing and every figure are reproducible with scripts/reproduce.sh.
          </p>
          {summary.data && (
            <>
              <p className="max-w-[80ch]">
                {summary.data.wris.wris_used
                  ? `India-WRIS refresh: ${int(summary.data.wris.wells_extended ?? 0)} wells extended by ${int(summary.data.wris.campaigns_added ?? 0)} campaigns.`
                  : "India-WRIS refresh: not applied to this build."}
              </p>
              <details className="max-w-[80ch] [overflow-wrap:anywhere]">
                <summary className="cursor-pointer text-ink">Where each number comes from</summary>
                <ul className="mt-2 flex flex-col gap-1">
                  {Object.entries(summary.data.sources).map(([k, v]) => (
                    <li key={k}>
                      <span className="text-ink">{k}:</span> {v}
                    </li>
                  ))}
                </ul>
              </details>
              <p>Data generated {summary.data.generated}.</p>
            </>
          )}
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

function MapLegend({
  stations,
  layer,
  warning,
}: {
  stations: Station[];
  layer: MapLayer;
  warning: WarningSettings;
}) {
  const counts = layerCounts(stations, layer, warning);
  return (
    <table className="w-full text-[0.9375rem]">
      <caption className="sr-only">Wells per class</caption>
      <tbody>
        {layerClasses(layer, warning).map((c) => (
          <tr key={c.key} className="border-b border-rule last:border-0">
            <td className="py-1.5 pr-2">
              <span className="flex items-center gap-2 text-ink">
                <span
                  className="inline-block h-3 w-3 shrink-0 rounded-full"
                  style={{ background: `var(--${c.color})`, opacity: c.faint ? 0.45 : 1 }}
                  aria-hidden
                />
                {c.label}
              </span>
            </td>
            <td className="tnum py-1.5 text-right text-ink-2">{int(counts[c.key] ?? 0)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
