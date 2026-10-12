import { useState } from "react";
import { MapPin } from "lucide-react";
import mapImage from "@/assets/aquasense-region-map.jpg";
import { Button } from "@/components/ui/button";

const wells = [
  { id: "2804", risk: "Critical", depth: 48.2, position: "left-[22%] top-[28%]", color: "text-risk-high" },
  { id: "0623", risk: "Moderate", depth: 32.5, position: "left-[52%] top-[32%]", color: "text-risk-medium" },
  { id: "1417", risk: "Stable", depth: 18.7, position: "left-[73%] top-[57%]", color: "text-risk-low" },
  { id: "3012", risk: "Critical", depth: 51.4, position: "left-[38%] top-[67%]", color: "text-risk-high" },
  { id: "1906", risk: "Moderate", depth: 36.1, position: "left-[76%] top-[23%]", color: "text-risk-medium" },
  { id: "2208", risk: "Stable", depth: 21.3, position: "left-[19%] top-[72%]", color: "text-risk-low" },
];

export function RegionalWells() {
  const [selected, setSelected] = useState(wells[0]);
  return <div>
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
      <h3 className="text-xl font-semibold">Regional monitoring wells</h3>
      <div className="flex gap-4 text-xs">{["Critical", "Moderate", "Stable"].map((risk, i) => <span key={risk} className="flex items-center gap-1.5"><span className={`size-2 rounded-full ${["bg-risk-high", "bg-risk-medium", "bg-risk-low"][i]}`} />{risk}</span>)}</div>
    </div>
    <div className="relative isolate aspect-[4/3] overflow-hidden rounded-lg border">
      <img src={mapImage} alt="Illustrative aquifer region with farmland, river, and monitoring well locations" loading="lazy" width={1024} height={768} className="absolute inset-0 h-full w-full object-cover" />
      {wells.map((well) => <div key={well.id} className={`group absolute ${well.position} -translate-x-1/2 -translate-y-1/2`}>
        <Button variant="ghost" size="icon" className={`size-10 rounded-full border border-background bg-card/95 shadow-soft hover:bg-card ${well.color}`} aria-label={`Well ${well.id}, ${well.risk}, depth ${well.depth} meters`} onMouseEnter={() => setSelected(well)} onFocus={() => setSelected(well)} onClick={() => setSelected(well)}><MapPin className="size-6" /></Button>
        <div role="tooltip" className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 hidden w-36 -translate-x-1/2 rounded-md border bg-popover p-2 text-xs text-popover-foreground shadow-soft group-hover:block group-focus-within:block"><p className="font-semibold">Well #{well.id} · {well.risk}</p><p className="mt-1">Depth: {well.depth} m</p></div>
      </div>)}
    </div>
    <div className="mt-4 flex flex-wrap justify-between gap-2 text-sm" aria-live="polite"><span className="font-semibold">Well #{selected?.id} · {selected?.risk}</span><span className="text-muted-foreground">Depth below ground: {selected?.depth} m</span></div>
    <p className="mt-3 text-xs leading-5 text-muted-foreground">Conceptual GIS mockup. Locations, risk levels, and depths are illustrative, not live measurements.</p>
  </div>;
}