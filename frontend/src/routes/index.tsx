import { createFileRoute } from "@tanstack/react-router";
import type { ComponentPropsWithoutRef } from "react";
import { useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import {
  Activity,
  Building2,
  Calendar,
  ArrowRight,
  BarChart3,
  BrainCircuit,
  Droplets,
  Layers3,
  Map,
  Satellite,
  ShieldCheck,
  Sprout,
  Waves,
  Check,
  LoaderCircle,
  ArrowUpRight,
  Zap,
  Search,
  AlertTriangle,
} from "lucide-react";

import heroImage from "@/assets/aquasense-groundwater-hero.jpg";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AnimatedStat } from "@/components/animated-stat";
import { LiveGISMap } from "@/components/live-gis-map";
import { LiveForecastChart } from "@/components/live-forecast-chart";
import { LivePolicySimulator } from "@/components/live-policy-simulator";
import { XAIPanel } from "@/components/xai-panel";
import { demoRequestSchema } from "@/lib/policy-simulation";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "AquaSense AI | Groundwater Decision Support System" },
      {
        name: "description",
        content:
          "AquaSense AI forecasts groundwater depletion, detects anomalies, and guides sustainable irrigation and extraction decisions.",
      },
    ],
  }),
  component: Index,
});

// ── Static data ─────────────────────────────────────────────────────────────

type AudienceKey = "boards" | "agriculture" | "research";

const audienceContent: Record<
  AudienceKey,
  { title: string; description: string; priorities: string[]; focus: string; metrics: string[]; perspective: string }
> = {
  boards: {
    title: "For water boards & government",
    description:
      "Coordinate basin-wide planning with a clearer view of where groundwater pressure is building.",
    priorities: [
      "Compare risk across aquifers",
      "Plan restrictions earlier",
      "Explain decisions with local signals",
    ],
    focus: "Regional allocation & early warning",
    metrics: ["Basin-wide risk distribution", "12-month allocation outlook"],
    perspective:
      "Balance regional demand with aquifer health and make restrictions easier to explain.",
  },
  agriculture: {
    title: "For agricultural authorities",
    description:
      "Help irrigation districts and grower networks plan around seasonal water availability.",
    priorities: [
      "Anticipate seasonal drawdown",
      "Prioritize efficient irrigation",
      "Coordinate across local wells",
    ],
    focus: "Seasonal irrigation planning",
    metrics: ["Seasonal water availability", "Pumping and recharge scenarios"],
    perspective:
      "Align irrigation schedules with seasonal pressure and compare conservation choices across grower networks.",
  },
  research: {
    title: "For environmental researchers",
    description:
      "Bring remote sensing, weather, well observations, and geological context into one analytical view.",
    priorities: [
      "Explore multi-source signals",
      "Review uncertainty bands",
      "Compare station-level trends",
    ],
    focus: "Transparent monitoring & analysis",
    metrics: ["q₁₀–q₉₀ uncertainty interval", "Station-level trend comparisons"],
    perspective:
      "Investigate the drivers of aquifer change with traceable inputs and uncertainty-aware comparisons.",
  },
};

const steps = [
  {
    title: "Data acquisition",
    description:
      "GRACE satellite signals, rainfall, temperature, soil, wells, and geology are harmonized by region.",
    icon: Satellite,
  },
  {
    title: "Temporal fusion",
    description:
      "A Temporal Fusion Transformer combines changing conditions and lagged signals across forecast horizons.",
    icon: BrainCircuit,
  },
  {
    title: "Dashboard",
    description:
      "Decision teams see trends, confidence bands, and risk zones without reading raw data.",
    icon: BarChart3,
  },
  {
    title: "Policy decisions",
    description:
      "Scenario comparisons frame pumping and recharge choices in clear, locally relevant terms.",
    icon: Sprout,
  },
];

const methods = [
  "Temporal Fusion Transformers model multiple forecast horizons and shifting environmental signals.",
  "TreeSHAP and variable selection networks help show which inputs shape a forecast.",
  "GIS mapping and kriging interpolation bring station readings into a spatial view.",
  "Plain-language policy briefs translate model outputs into decision context.",
];

// ── Helpers ──────────────────────────────────────────────────────────────────

function AnimatedSection({
  children,
  className,
  ...props
}: ComponentPropsWithoutRef<typeof motion.section>) {
  const reduceMotion = useReducedMotion();
  if (reduceMotion) {
    return (
      <motion.section className={className} {...props}>
        {children}
      </motion.section>
    );
  }
  return (
    <motion.section
      initial={{ opacity: 0, y: 28 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.7, ease: "easeOut" }}
      className={className}
      {...props}
    >
      {children}
    </motion.section>
  );
}

// ── Dashboard section ────────────────────────────────────────────────────────

function DashboardSection() {
  const [selectedWell, setSelectedWell] = useState<string | null>(null);
  const [horizon, setHorizon] = useState<3 | 6 | 12>(12);
  const [activeTab, setActiveTab] = useState("gis");
  const [wellSearch, setWellSearch] = useState("");

  return (
    <AnimatedSection id="dashboard" className="mx-auto max-w-7xl px-5 py-24 sm:px-8 lg:px-10">
      {/* header */}
      <div className="mb-10 grid gap-6 lg:grid-cols-[1fr_auto] lg:items-end">
        <div>
          <p className="mb-3 text-sm font-semibold uppercase text-primary">
            Phase 6 · Decision Support Dashboard
          </p>
          <h2 className="font-display text-4xl font-semibold leading-tight md:text-5xl">
            Live operational view
          </h2>
          <p className="mt-4 max-w-2xl text-muted-foreground leading-7">
            Real data from <code className="text-xs">/api/wells</code>,{" "}
            <code className="text-xs">/api/forecast</code>,{" "}
            <code className="text-xs">/api/xai</code>, and{" "}
            <code className="text-xs">/api/simulate</code>. Select any well to load its TFT
            forecast, XAI explanation, and run policy scenarios.
          </p>
        </div>
        {/* well search */}
        <div className="flex gap-2 min-w-0">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Well ID…"
              className="pl-9 w-52"
              value={wellSearch}
              onChange={(e) => setWellSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && wellSearch.trim()) {
                  setSelectedWell(wellSearch.trim());
                  setActiveTab("forecast");
                }
              }}
            />
          </div>
          <Button
            size="sm"
            onClick={() => {
              if (wellSearch.trim()) {
                setSelectedWell(wellSearch.trim());
                setActiveTab("forecast");
              }
            }}
          >
            Load
          </Button>
        </div>
      </div>

      {/* selected well pill */}
      {selectedWell && (
        <div className="mb-6 flex flex-wrap items-center gap-3">
          <span className="rounded-full bg-primary/10 px-4 py-1.5 text-sm font-semibold text-primary">
            Active well: {selectedWell}
          </span>
          <div className="flex gap-1.5">
            {([3, 6, 12] as const).map((h) => (
              <button
                key={h}
                onClick={() => setHorizon(h)}
                className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${
                  horizon === h
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary text-secondary-foreground hover:bg-accent"
                }`}
              >
                {h}mo
              </button>
            ))}
          </div>
          <button
            className="text-xs text-muted-foreground underline"
            onClick={() => setSelectedWell(null)}
          >
            Clear selection
          </button>
        </div>
      )}

      {/* main dashboard tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="min-w-0">
        <TabsList className="h-auto w-full max-w-full justify-start gap-1 overflow-x-auto rounded-none bg-transparent p-0 border-b pb-0 mb-6">
          <TabsTrigger value="gis" className="shrink-0 rounded-t-lg rounded-b-none px-4 py-3 gap-2 data-[state=active]:border-b-2 data-[state=active]:border-primary">
            <Map className="size-4" /> GIS Map
          </TabsTrigger>
          <TabsTrigger value="forecast" className="shrink-0 rounded-t-lg rounded-b-none px-4 py-3 gap-2 data-[state=active]:border-b-2 data-[state=active]:border-primary">
            <Activity className="size-4" /> Forecast
          </TabsTrigger>
          <TabsTrigger value="xai" className="shrink-0 rounded-t-lg rounded-b-none px-4 py-3 gap-2 data-[state=active]:border-b-2 data-[state=active]:border-primary">
            <BrainCircuit className="size-4" /> XAI
          </TabsTrigger>
          <TabsTrigger value="simulator" className="shrink-0 rounded-t-lg rounded-b-none px-4 py-3 gap-2 data-[state=active]:border-b-2 data-[state=active]:border-primary">
            <Zap className="size-4" /> Policy Simulator
          </TabsTrigger>
        </TabsList>

        <TabsContent value="gis" className="mt-0">
          <LiveGISMap
            selectedWellId={selectedWell}
            onSelectWell={(id) => {
              setSelectedWell(id);
            }}
          />
        </TabsContent>

        <TabsContent value="forecast" className="mt-0">
          <LiveForecastChart wellId={selectedWell} horizon={horizon} />
        </TabsContent>

        <TabsContent value="xai" className="mt-0">
          <XAIPanel wellId={selectedWell} />
        </TabsContent>

        <TabsContent value="simulator" className="mt-0">
          <LivePolicySimulator wellId={selectedWell} />
        </TabsContent>
      </Tabs>
    </AnimatedSection>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────

function Index() {
  const reduceMotion = useReducedMotion();
  const [demoOpen, setDemoOpen] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [audience, setAudience] = useState<AudienceKey>("boards");
  const [formError, setFormError] = useState("");

  return (
    <Dialog
      open={demoOpen}
      onOpenChange={(open) => {
        setDemoOpen(open);
        if (!open) {
          setFormError("");
          setIsSubmitted(false);
          setIsSubmitting(false);
        }
      }}
    >
      <div className="min-h-screen overflow-x-hidden bg-background text-foreground">
        {/* ── HERO ── */}
        <section className="relative bg-primary text-primary-foreground">
          <img
            src={heroImage}
            alt="Irrigated farmland, river basin, dry terrain, and aquifer layers seen from above"
            width={1920}
            height={1200}
            className="absolute inset-0 h-full w-full object-cover"
          />
          <div className="absolute inset-0 bg-[image:var(--gradient-hero-scrim)]" />
          <div className="relative z-10 mx-auto flex min-h-[760px] w-full max-w-7xl flex-col px-5 pb-36 pt-6 sm:px-8 lg:min-h-[820px] lg:px-10">
            <header className="flex items-center justify-between gap-6">
              <a href="#top" className="flex items-center gap-3" aria-label="AquaSense AI home">
                <span className="flex size-11 items-center justify-center rounded-full border border-primary-foreground/30 bg-primary-foreground/10 backdrop-blur-md">
                  <Droplets className="size-5" aria-hidden="true" />
                </span>
                <span className="font-semibold">AquaSense AI</span>
              </a>
              <nav className="hidden items-center gap-8 text-sm text-primary-foreground/78 md:flex">
                <a href="#dashboard" className="transition-colors hover:text-primary-foreground">Dashboard</a>
                <a href="#process" className="transition-colors hover:text-primary-foreground">How it works</a>
                <a href="#method" className="transition-colors hover:text-primary-foreground">Technology</a>
                <a href="#impact" className="transition-colors hover:text-primary-foreground">Impact</a>
              </nav>
              <Button variant="glass" size="sm" onClick={() => setDemoOpen(true)}>
                Request Demo
              </Button>
            </header>

            {reduceMotion ? (
              <div id="top" className="mt-auto max-w-5xl pb-12">
                <HeroContent setDemoOpen={setDemoOpen} />
              </div>
            ) : (
              <motion.div
                id="top"
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.8, ease: "easeOut" }}
                className="mt-auto max-w-5xl pb-12"
              >
                <HeroContent setDemoOpen={setDemoOpen} />
              </motion.div>
            )}
          </div>

          {/* hero info bar */}
          <div className="relative mx-auto -mt-24 z-20 md:absolute md:bottom-0 md:left-1/2 w-[min(1120px,calc(100%-2rem))] md:-translate-x-1/2 md:translate-y-1/2 rounded-3xl bg-card p-4 text-card-foreground shadow-panel sm:p-5">
            <div className="grid gap-3 md:grid-cols-[1.2fr_1fr_1fr_auto] md:items-center">
              <div className="rounded-2xl bg-secondary px-5 py-4">
                <p className="text-xs font-semibold uppercase text-muted-foreground">Wells monitored</p>
                <p className="mt-2 text-base font-semibold">~6,108 CGWB stations</p>
              </div>
              <div className="rounded-2xl bg-secondary px-5 py-4">
                <p className="text-xs font-semibold uppercase text-muted-foreground">Forecast horizon</p>
                <p className="mt-2 text-base font-semibold">3 / 6 / 12 months</p>
              </div>
              <div className="rounded-2xl bg-secondary px-5 py-4">
                <p className="text-xs font-semibold uppercase text-muted-foreground">Model</p>
                <p className="mt-2 text-base font-semibold">TFT q₁₀–q₅₀–q₉₀ bands</p>
              </div>
              <Button variant="hero" size="xl" className="w-full md:w-auto" onClick={() => setDemoOpen(true)}>
                Request Demo
              </Button>
            </div>
          </div>
        </section>

        <main>
          {/* ── IMPACT STATS ── */}
          <AnimatedSection
            id="impact"
            className="mx-auto max-w-7xl px-5 pb-20 pt-20 md:pt-44 sm:px-8 lg:px-10"
          >
            <div className="grid gap-10 lg:grid-cols-[0.95fr_1.05fr] lg:items-end">
              <div>
                <p className="mb-4 text-sm font-semibold uppercase text-primary">
                  The invisible crisis below our feet
                </p>
                <h2 className="font-display text-5xl font-semibold leading-tight tracking-normal text-foreground md:text-6xl">
                  Groundwater decisions are still made too late.
                </h2>
              </div>
              <p className="text-lg leading-8 text-muted-foreground">
                Groundwater depletion is difficult to see until wells decline and crops suffer.
                Earlier, clearer signals can help water boards and agricultural authorities plan
                before emergency restrictions become the only option.
              </p>
            </div>
            <div className="mt-12 grid gap-4 md:grid-cols-3">
              {[
                {
                  value: 6108,
                  suffix: " wells",
                  icon: Waves,
                  label: "CGWB monitoring stations across India wired to live TFT forecasts",
                },
                {
                  value: 80,
                  suffix: "% band",
                  icon: Activity,
                  label: "q₁₀–q₉₀ forecast interval for communicating uncertainty to decision-makers",
                },
                {
                  value: 12,
                  suffix: " months",
                  icon: Calendar,
                  label: "planning horizon for seasonal groundwater outlooks from the backend API",
                },
              ].map((stat) => (
                <div key={stat.value} className="rounded-3xl border bg-card p-7 shadow-soft">
                  <stat.icon className="mb-5 size-6 text-primary/70" aria-hidden="true" />
                  <p className="font-display text-5xl font-semibold text-primary">
                    <AnimatedStat value={stat.value} suffix={stat.suffix} />
                  </p>
                  <p className="mt-4 leading-7 text-muted-foreground">{stat.label}</p>
                </div>
              ))}
            </div>
          </AnimatedSection>

          {/* ── AUDIENCE TABS ── */}
          <AnimatedSection id="audiences" className="border-y bg-card py-20">
            <div className="mx-auto max-w-7xl px-5 sm:px-8 lg:px-10">
              <div className="grid gap-8 lg:grid-cols-[0.75fr_1.25fr] [&>*]:min-w-0 lg:items-end">
                <div>
                  <p className="mb-4 text-sm font-semibold uppercase text-primary">
                    Built around your decisions
                  </p>
                  <h2 className="font-display text-5xl font-semibold leading-tight md:text-6xl">
                    One water picture. Different priorities.
                  </h2>
                </div>
                <Tabs value={audience} onValueChange={(v) => setAudience(v as AudienceKey)}>
                  <TabsList className="flex h-auto w-full max-w-full justify-start gap-1 overflow-x-auto rounded-none bg-transparent p-0 pb-2">
                    <TabsTrigger value="boards" className="h-auto shrink-0 rounded-full px-3 py-3">
                      Water boards & government
                    </TabsTrigger>
                    <TabsTrigger value="agriculture" className="h-auto shrink-0 rounded-full px-3 py-3">
                      Agricultural authorities
                    </TabsTrigger>
                    <TabsTrigger value="research" className="h-auto shrink-0 rounded-full px-3 py-3">
                      Environmental researchers
                    </TabsTrigger>
                  </TabsList>
                  {Object.entries(audienceContent).map(([key, content]) => (
                    <TabsContent key={key} value={key} className="mt-7 border-t pt-6">
                      <div className="grid gap-8 md:grid-cols-[1fr_0.8fr]">
                        <div>
                          <h3 className="text-xl font-semibold">{content.title}</h3>
                          <p className="mt-3 max-w-xl leading-7 text-muted-foreground">
                            {content.description}
                          </p>
                          <ul className="mt-5 grid gap-3 sm:grid-cols-2">
                            {content.priorities.map((p) => (
                              <li key={p} className="flex items-start gap-2 text-sm">
                                <Check className="mt-0.5 size-4 shrink-0 text-primary" />
                                {p}
                              </li>
                            ))}
                          </ul>
                        </div>
                        <div className="border-l-2 border-primary pl-5">
                          <p className="text-xs font-semibold uppercase text-muted-foreground">
                            Decision focus
                          </p>
                          <p className="mt-2 font-display text-2xl font-semibold">
                            {content.focus}
                          </p>
                          <ul className="mt-4 space-y-2 text-sm font-semibold text-primary">
                            {content.metrics.map((m) => (
                              <li key={m}>{m}</li>
                            ))}
                          </ul>
                          <p className="mt-4 text-sm leading-6 text-muted-foreground">
                            {content.perspective}
                          </p>
                        </div>
                      </div>
                    </TabsContent>
                  ))}
                </Tabs>
              </div>
            </div>
          </AnimatedSection>

          {/* ── HOW IT WORKS ── */}
          <AnimatedSection
            id="process"
            className="bg-[image:var(--gradient-section)] py-20"
          >
            <div className="mx-auto max-w-7xl px-5 sm:px-8 lg:px-10">
              <div className="max-w-3xl">
                <p className="mb-4 text-sm font-semibold uppercase text-primary">How it works</p>
                <h2 className="font-display text-5xl font-semibold leading-tight tracking-normal md:text-6xl">
                  From earth observation to field-level decisions.
                </h2>
              </div>
              <div className="mt-12 grid gap-5 lg:grid-cols-4">
                {steps.map((step, index) => {
                  const Icon = step.icon;
                  return (
                    <div
                      key={step.title}
                      className="rounded-3xl border bg-card p-7 shadow-soft transition-all duration-300 hover:-translate-y-1 hover:shadow-panel motion-reduce:transform-none"
                    >
                      <div className="mb-8 flex items-center justify-between">
                        <span className="flex size-12 items-center justify-center rounded-2xl bg-secondary text-primary">
                          <Icon className="size-5" />
                        </span>
                        <span className="font-display text-3xl text-muted-foreground">
                          0{index + 1}
                        </span>
                      </div>
                      <h3 className="text-xl font-semibold">{step.title}</h3>
                      <p className="mt-4 leading-7 text-muted-foreground">{step.description}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          </AnimatedSection>

          {/* ── LIVE DASHBOARD ── */}
          <DashboardSection />

          {/* ── METHODOLOGY ── */}
          <AnimatedSection id="method" className="bg-primary py-24 text-primary-foreground">
            <div className="mx-auto grid max-w-7xl gap-12 px-5 sm:px-8 lg:grid-cols-[1fr_1fr] lg:px-10">
              <div>
                <p className="mb-4 text-sm font-semibold uppercase text-primary-foreground/70">
                  Methodology
                </p>
                <h2 className="font-display text-5xl font-semibold leading-tight tracking-normal md:text-6xl">
                  Scientifically grounded. Simple to act on.
                </h2>
              </div>
              <div className="space-y-4">
                {methods.map((m) => (
                  <div
                    key={m}
                    className="flex gap-4 rounded-3xl border border-primary-foreground/15 bg-primary-foreground/10 p-6 backdrop-blur-md"
                  >
                    <ShieldCheck className="mt-1 size-5 shrink-0 text-aqua" />
                    <p className="leading-7 text-primary-foreground/82">{m}</p>
                  </div>
                ))}
                <div className="flex gap-4 rounded-3xl border border-primary-foreground/15 bg-primary-foreground/10 p-6 backdrop-blur-md">
                  <Layers3 className="mt-1 size-5 shrink-0 text-aqua" />
                  <p className="leading-7 text-primary-foreground/82">
                    LSTM and XGBoost models are presented as confidence-led guidance, not opaque
                    black-box recommendations.
                  </p>
                </div>
              </div>
            </div>
          </AnimatedSection>

          {/* ── CTA ── */}
          <AnimatedSection id="demo" className="bg-primary py-20 text-primary-foreground sm:py-24">
            <div className="mx-auto flex max-w-7xl flex-col gap-8 px-5 sm:px-8 md:flex-row md:items-end md:justify-between lg:px-10">
              <div className="max-w-3xl">
                <p className="mb-4 text-sm font-semibold uppercase text-primary-foreground/70">
                  Request a demonstration
                </p>
                <h2 className="font-display text-5xl font-semibold leading-tight md:text-6xl">
                  Transform environmental data into actionable policy.
                </h2>
                <p className="mt-5 max-w-2xl text-lg leading-8 text-primary-foreground/80">
                  Share your organization and region to start a conversation about groundwater
                  planning.
                </p>
              </div>
              <Button
                variant="hero"
                size="xl"
                className="shrink-0 bg-background text-foreground hover:bg-background/90"
                onClick={() => setDemoOpen(true)}
              >
                Request Demo <ArrowRight className="size-4" />
              </Button>
            </div>
          </AnimatedSection>
        </main>

        <footer className="border-t py-8">
          <div className="mx-auto flex max-w-7xl flex-col gap-4 px-5 text-sm text-muted-foreground sm:px-8 md:flex-row md:items-center md:justify-between lg:px-10">
            <p className="font-semibold text-foreground">AquaSense AI</p>
            <p>
              Groundwater prediction for sustainable water resource management · 6,108 CGWB stations
            </p>
          </div>
        </footer>
      </div>

      {/* ── DEMO DIALOG ── */}
      <DialogContent className="demo-glass max-h-[90dvh] w-[calc(100%-2rem)] overflow-y-auto rounded-lg border-hero-foreground/20 bg-dialog-glass text-hero-foreground backdrop-blur-xl sm:max-w-xl">
        {isSubmitted ? (
          <motion.div
            initial={{ opacity: 0, y: reduceMotion ? 0 : 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="py-8 text-center"
          >
            <span className="mx-auto flex size-14 items-center justify-center rounded-full bg-primary/10 text-primary">
              <Check className="size-7" />
            </span>
            <DialogHeader className="mt-5">
              <DialogTitle className="font-display text-3xl">Demo Request Received.</DialogTitle>
              <DialogDescription className="mt-3 text-base leading-6">
                An AquaSense hydro-AI specialist will reach out within 24 hours.
              </DialogDescription>
            </DialogHeader>
            <Button
              className="mt-6"
              onClick={() => {
                setDemoOpen(false);
                setIsSubmitted(false);
              }}
            >
              Close
            </Button>
          </motion.div>
        ) : (
          <>
            <DialogHeader className="pr-8">
              <p className="text-xs font-semibold uppercase text-primary">AquaSense AI</p>
              <DialogTitle className="font-display text-3xl">Request a demonstration</DialogTitle>
              <DialogDescription className="leading-6">
                Tell us where you work and which groundwater decisions you're planning for.
              </DialogDescription>
            </DialogHeader>
            <form
              className="mt-2 grid gap-4"
              onSubmit={(e) => {
                e.preventDefault();
                if (isSubmitting) return;
                const parsed = demoRequestSchema.safeParse(
                  Object.fromEntries(new FormData(e.currentTarget)),
                );
                if (!parsed.success) {
                  setFormError(parsed.error.issues[0]?.message ?? "Check your details.");
                  return;
                }
                setFormError("");
                setIsSubmitting(true);
                setTimeout(() => {
                  setIsSubmitting(false);
                  setIsSubmitted(true);
                }, 1000);
              }}
            >
              <fieldset disabled={isSubmitting} className="grid gap-4">
                <div className="grid gap-2">
                  <Label htmlFor="demo-name">Full Name</Label>
                  <Input id="demo-name" name="name" placeholder="Your name" maxLength={100} required />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="organization-type">Organization Type</Label>
                  <Select name="organizationType" required>
                    <SelectTrigger id="organization-type" className="w-full">
                      <SelectValue placeholder="Choose an organization type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="government">Government / Water Board</SelectItem>
                      <SelectItem value="agriculture">Agricultural Co-op</SelectItem>
                      <SelectItem value="research">Environmental Research</SelectItem>
                      <SelectItem value="enterprise">Private Enterprise</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="demo-region">Region / Aquifer Area of Interest</Label>
                  <Input id="demo-region" name="region" placeholder="Region, basin, or aquifer" maxLength={200} required />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="demo-email">Work Email</Label>
                  <Input id="demo-email" name="email" type="email" placeholder="name@organization.org" maxLength={255} required />
                </div>
              </fieldset>
              {formError && <p role="alert" className="text-sm text-risk-medium">{formError}</p>}
              <Button type="submit" variant="hero" size="xl" disabled={isSubmitting}>
                {isSubmitting ? (
                  <>
                    <LoaderCircle className="size-4 animate-spin" /> Submitting…
                  </>
                ) : (
                  <>
                    Submit Request <ArrowRight className="size-4" />
                  </>
                )}
              </Button>
            </form>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function HeroContent({ setDemoOpen }: { setDemoOpen: (v: boolean) => void }) {
  return (
    <>
      <p className="mb-6 flex items-center gap-3 text-sm font-semibold uppercase text-primary-foreground/75">
        <span className="h-px w-10 bg-primary-foreground/45" />
        Groundwater intelligence for climate-stressed regions
      </p>
      <h1 className="font-display text-6xl font-semibold leading-none tracking-normal sm:text-7xl lg:text-8xl">
        Predicting Water, Preserving Tomorrow
      </h1>
      <div className="mt-8 flex max-w-3xl flex-col gap-7 md:flex-row md:items-end md:justify-between">
        <p className="text-lg leading-8 text-primary-foreground/82 md:text-xl">
          AquaSense AI forecasts groundwater depletion across 6,108 CGWB wells, flags anomalies,
          and turns complex environmental data into calm, practical decisions.
        </p>
        <div className="flex flex-wrap items-center gap-4">
          <Button variant="hero" size="xl" className="shrink-0" onClick={() => setDemoOpen(true)}>
            Request Demo <ArrowRight className="size-4" />
          </Button>
          <a
            href="#dashboard"
            className="inline-flex items-center gap-2 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-80"
          >
            Open live dashboard <ArrowUpRight className="size-4" />
          </a>
        </div>
      </div>
    </>
  );
}
