// Every demo name, amount and line of text lives here. Rename freely; nothing else hardcodes them.
export const S = {
  us: "Datum Co.",
  agent: "Order agent",
  buyer: "Acme Fitness",
  buyerAgent: "Acme's buying agent",
  controller: "Human",
  controllerRole: "Controller",
  order: "SF adults 25–34 interested in fitness, counts by ZIP",
  price: 120,
  rerunCost: 6,
  oakland: 60,
  yoga: 30,
  seat: "Order-to-cash agent for a data broker",
  positioning:
    "Existing platforms handle transactions and delivery. We connect a custom order's requirements to fulfillment checks, evidence gathering, correction and authorized settlement.",
};

export type Msg = { id: string; from: "buyer" | "agent" | "human"; text: string; tick?: number };

// The intake interview. `tick` = which contract line this answer settles.
export const INTERVIEW: Msg[] = [
  { id: "m1", from: "buyer", text: "We need SF adults 25–34 interested in fitness, counts by ZIP, for an ad campaign." },
  { id: "m2", from: "agent", text: "How should we define \"interested in fitness\"?" },
  { id: "m3", from: "buyer", text: "Gym members or people who use fitness apps.", tick: 0 },
  { id: "m4", from: "agent", text: "San Francisco city only, or the wider Bay Area?" },
  { id: "m5", from: "buyer", text: "SF city only.", tick: 1 },
  { id: "m6", from: "agent", text: "Ages 25 to 34, inclusive?" },
  { id: "m7", from: "buyer", text: "Yes.", tick: 2 },
  { id: "m8", from: "agent", text: "Any ZIP with fewer than 50 people is withheld for privacy. OK?" },
  { id: "m9", from: "buyer", text: "Fine.", tick: 3 },
  { id: "m10", from: "agent", text: "Every SF ZIP will be covered. Price: $120. Approve?" },
  { id: "m11", from: "buyer", text: "Approved.", tick: 4 },
];

export const CONTRACT = [
  "Fitness = gym members or fitness-app users",
  "San Francisco city ZIPs only",
  "Ages 25–34",
  "At least 50 people per ZIP (privacy)",
  "Every SF ZIP present",
];
export const CONTRACT_V2 = "Yoga studio members count as fitness";

export type Row = { zip: string; area: string; people: number; flag?: "withheld" | "missing" | "added" | "yoga" };
export const ROWS: Row[] = [
  { zip: "94102", area: "Tenderloin", people: 1820 },
  { zip: "94103", area: "SoMa", people: 2140 },
  { zip: "94107", area: "Potrero Hill", people: 2960 },
  { zip: "94109", area: "Nob Hill", people: 3310 },
  { zip: "94110", area: "Mission", people: 4120 },
  { zip: "94114", area: "Castro", people: 2450 },
  { zip: "94117", area: "Haight", people: 2780 },
  { zip: "94122", area: "Sunset", people: 3050 },
  { zip: "94129", area: "Presidio", people: 42 },
  { zip: "94133", area: "North Beach", people: 1990 },
];
export const OAKLAND: Row[] = [
  { zip: "94607", area: "West Oakland", people: 1640, flag: "added" },
  { zip: "94610", area: "Lakeshore", people: 2210, flag: "added" },
  { zip: "94612", area: "Downtown Oakland", people: 1880, flag: "added" },
];
