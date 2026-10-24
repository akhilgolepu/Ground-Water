/**
 * Research agenda shown on the dashboard. Source of truth: docs/03-research-gaps.md.
 * Keep the two in sync when the plan changes.
 */

export type GapStatus = "Pilot result in hand" | "Next" | "Planned" | "Needs new data";

export interface Gap {
  id: string;
  title: string;
  question: string;
  why: string;
  status: GapStatus;
}

export const PAPER_TITLE =
  "Monsoon forcing, depth-aware calibration and decision value in national-scale groundwater forecasting for India";

export const gaps: Gap[] = [
  {
    id: "G1",
    title: "Does the monsoon add skill, and how far ahead?",
    question:
      "Add gridded IMD rainfall accumulated between campaigns, drought indices and ENSO/IOD indices, then measure the extra skill at 3, 6 and 12 months against groundwater memory alone.",
    why: "The weather columns in the public CGWB file are single-day readings (about 3 mm per well-year), so earlier conclusions that climate adds nothing were never really tested.",
    status: "Next",
  },
  {
    id: "G2",
    title: "Intervals that hold for shallow and deep wells alike",
    question:
      "Calibrate uncertainty separately by aquifer depth and season, and adapt it as conditions shift.",
    why: "One interval width covers 88% of shallow-well readings but only 44% of readings in wells deeper than 40 m.",
    status: "Pilot result in hand",
  },
  {
    id: "G3",
    title: "When is a warning worth acting on?",
    question:
      "Score exceedance warnings by their economic value across cost–loss ratios, and find the trigger probabilities that serve village water-security plans.",
    why: "No groundwater study has measured the decision value of its forecasts.",
    status: "Planned",
  },
  {
    id: "G4",
    title: "Telemetry and manual wells together",
    question:
      "Use the 922 daily DWLR wells to sharpen forecasts at neighbouring wells read four times a year.",
    why: "No published model uses CGWB telemetry data.",
    status: "Planned",
  },
  {
    id: "G5",
    title: "Forecasting where there is no history",
    question:
      "Describe each site with AlphaEarth satellite embeddings and test on wells the model has never seen.",
    why: "Accuracy drops sharply for unseen regions, and the embeddings have only been used for one-year maps.",
    status: "Needs new data",
  },
  {
    id: "G6",
    title: "Quantity and quality together",
    question:
      "Link water-level forecasts with fluoride and salinity in Andhra Pradesh using the CGWB quality records.",
    why: "Quality and level are modelled separately everywhere we looked.",
    status: "Planned",
  },
];

export const beyond = [
  {
    title: "Electricity use as a measure of pumping",
    body: "Feeder-level electricity data (about 5 m³ of water per kWh) would give the first measured pumping signal for Indian aquifers and make extraction planning possible.",
  },
  {
    title: "Forecasting the official extraction category",
    body: "Predict a block's safe, semi-critical, critical or over-exploited status a year before the national assessment is published.",
  },
  {
    title: "Physics-guided models for hard-rock aquifers",
    body: "Use the water-table fluctuation equation and specific-yield maps as a constraint for peninsular India's hard-rock aquifers.",
  },
];
