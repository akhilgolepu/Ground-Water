# AquaSense AI Platform

Project: Marketing/landing website for "AquaSense AI" — an ML-based groundwater level prediction platform for sustainable water resource management.

Use Case: This site introduces an ML system that ingests satellite (GRACE), meteorological, and geological data to forecast groundwater depletion, detect anomalies, and guide irrigation/extraction decisions for farmers, local authorities, and water boards.

Design Direction (Minimalist, Premium):

Primary color: Deep/electric blue (#0B4F8A or similar) — dominant across hero, CTAs, accents

Secondary: White/off-white with subtle gray for breathing room

Typography: Large serif or elegant display font for headlines (like editorial sites), clean sans-serif for body

Style references: (1) full-bleed atmospheric photography/imagery behind bold minimal text (like a landscape/vineyard hero), (2) confident oversized headline + short subtext + single CTA button (like a statement-led hero), (3) card-based booking/search UI with rounded corners and soft shadows floating over hero imagery

Generous whitespace, subtle scroll animations, no clutter — every section should feel deliberate

Site Structure:

Hero — bold headline (e.g., "Predicting Water, Preserving Tomorrow"), one-line value prop, single CTA ("Request Demo" / "Explore Platform")

Problem statement — groundwater depletion crisis, 2-3 stat callouts

How it works — 3-4 step visual flow: Data Acquisition → ML Forecasting (LSTM/XGBoost) → Dashboard → Actionable Insights

Live dashboard preview — mockup of prediction charts/maps (water table trends, risk zones)

Tech/methodology section — brief, credibility-focused

CTA/footer — contact/demo request form

PRD (condensed):

Goal: Convert visitors (govt bodies, agri-stakeholders, researchers) into demo requests

Users: Non-technical decision-makers — copy must stay simple, visuals do the heavy lifting

Key metric: Demo request conversion rate

Must-have: responsive design, fast load, one clear CTA repeated at top and bottom

Tech Stack:

Frontend: React + Tailwind CSS

Animations: Framer Motion (subtle fade/slide on scroll)

Charts: Recharts or Chart.js for dashboard preview mockups

Hosting: Vercel/Netlify-ready static build

Forms: Simple contact form (no backend required for MVP)

Tone: Scientific credibility + calm confidence — not flashy, not corporate-boring. Think "climate-tech meets editorial design."

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
