/**
 * LiveGISMap – Leaflet map wired to /api/wells.
 * Shows all wells color-coded by risk level. Click a well to focus.
 */
import { useEffect, useRef } from "react";
import { Loader2, AlertCircle } from "lucide-react";
import { useWells, type WellOverview } from "@/hooks/use-api";

const RISK_COLOR: Record<WellOverview["risk_level"], string> = {
  Critical: "#e45c3a",
  Moderate: "#d4a017",
  Stable:   "#2ea88a",
};

const RISK_FILL: Record<WellOverview["risk_level"], string> = {
  Critical: "#ff6b4a",
  Moderate: "#f0be30",
  Stable:   "#3ecaa8",
};

interface Props {
  selectedWellId: string | null;
  onSelectWell: (id: string) => void;
}

export function LiveGISMap({ selectedWellId, onSelectWell }: Props) {
  const { data: wells, isLoading, error } = useWells();
  const mapRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const leafletRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const markersRef = useRef<Map<string, any>>(new Map());

  // initialise map once
  useEffect(() => {
    if (!mapRef.current || leafletRef.current) return;
    // @ts-expect-error leaflet loaded via CDN on index.html
    const L = window.L;
    if (!L) return;

    const map = L.map(mapRef.current, { zoomControl: true }).setView([22.5, 79.0], 5);
    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
      {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com">CARTO</a>',
        maxZoom: 18,
        subdomains: "abcd",
      },
    ).addTo(map);

    leafletRef.current = map;
    return () => {
      map.remove();
      leafletRef.current = null;
      markersRef.current.clear();
    };
  }, []);

  // add / update markers whenever wells data arrives
  useEffect(() => {
    // @ts-expect-error leaflet loaded via CDN
    const L = window.L;
    const map = leafletRef.current;
    if (!L || !map || !wells) return;

    // remove old markers
    markersRef.current.forEach((m) => m.remove());
    markersRef.current.clear();

    const bounds: [number, number][] = [];

    wells.forEach((w) => {
      const color = RISK_COLOR[w.risk_level];
      const fill  = RISK_FILL[w.risk_level];
      const isSelected = w.well_id === selectedWellId;

      const marker = L.circleMarker([w.latitude, w.longitude], {
        radius: isSelected ? 9 : 6,
        color,
        fillColor: fill,
        fillOpacity: 0.85,
        weight: isSelected ? 2.5 : 1.5,
      })
        .addTo(map)
        .bindTooltip(
          `<strong>Well ${w.well_id}</strong><br/>
           Risk: ${w.risk_level}<br/>
           Depth now: ${w.current_depth_m} m<br/>
           Predicted: ${w.predicted_depth_m} m`,
          { direction: "top", offset: [0, -6] },
        )
        .on("click", () => onSelectWell(w.well_id));

      markersRef.current.set(w.well_id, marker);
      bounds.push([w.latitude, w.longitude]);
    });

    if (bounds.length > 0) {
      map.fitBounds(bounds, { padding: [30, 30], maxZoom: 9 });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wells]);

  // highlight selected marker
  useEffect(() => {
    // @ts-expect-error leaflet loaded via CDN
    const L = window.L;
    const map = leafletRef.current;
    if (!L || !map || !wells) return;

    markersRef.current.forEach((marker, id) => {
      const w = wells.find((x) => x.well_id === id);
      if (!w) return;
      const isSelected = id === selectedWellId;
      marker.setStyle({
        radius: isSelected ? 10 : 6,
        weight: isSelected ? 3 : 1.5,
      });
      if (isSelected) {
        marker.openTooltip();
        map.panTo([w.latitude, w.longitude]);
      }
    });
  }, [selectedWellId, wells]);

  if (isLoading) {
    return (
      <div className="flex h-[420px] items-center justify-center rounded-2xl border bg-card">
        <Loader2 className="size-6 animate-spin text-primary" />
        <span className="ml-3 text-sm text-muted-foreground">Loading wells from API…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-[420px] items-center justify-center rounded-2xl border bg-card">
        <AlertCircle className="size-5 text-destructive" />
        <span className="ml-3 text-sm text-destructive">
          Could not reach /api/wells — start the backend server.
        </span>
      </div>
    );
  }

  const counts = {
    Critical: wells?.filter((w) => w.risk_level === "Critical").length ?? 0,
    Moderate: wells?.filter((w) => w.risk_level === "Moderate").length ?? 0,
    Stable:   wells?.filter((w) => w.risk_level === "Stable").length   ?? 0,
  };

  return (
    <div className="space-y-3">
      {/* legend + stats */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-lg font-semibold">
          {wells?.length.toLocaleString()} CGWB monitoring wells
        </h3>
        <div className="flex gap-4 text-xs font-medium">
          {(["Critical", "Moderate", "Stable"] as const).map((risk) => (
            <span key={risk} className="flex items-center gap-1.5">
              <span
                className="size-2.5 rounded-full"
                style={{ background: RISK_FILL[risk] }}
              />
              {risk} ({counts[risk]})
            </span>
          ))}
        </div>
      </div>

      {/* map container */}
      <div
        ref={mapRef}
        className="h-[420px] w-full overflow-hidden rounded-2xl border"
        aria-label="Interactive GIS map of CGWB groundwater monitoring wells"
      />

      {/* selected well info */}
      {selectedWellId && wells && (() => {
          const w = wells.find((x) => x.well_id === selectedWellId);
          if (!w) return null;
          return (
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border bg-secondary px-4 py-3 text-sm">
              <span className="font-semibold">Well {w.well_id}</span>
              <span style={{ color: RISK_COLOR[w.risk_level] }} className="font-semibold">
                {w.risk_level}
              </span>
              <span className="text-muted-foreground">
                Current: {w.current_depth_m} m · Predicted: {w.predicted_depth_m} m
              </span>
              <span className="text-muted-foreground text-xs">Updated {w.last_updated}</span>
            </div>
          );
        })()
      }

      <p className="text-xs text-muted-foreground">
        Live data from <code className="text-xs">/api/wells</code> · Click any well to load its
        forecast and XAI brief.
      </p>
    </div>
  );
}
