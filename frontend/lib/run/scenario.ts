// The demo scenario: DataPact builds a custom audience dataset for Acme Fitness's buying agent.
// Every name, amount and line of text on the canvas comes from this file. Synthetic data;
// prices are sample values for the team to confirm.
import type {
  Amendment, ContractLine, ControllerAction, DataContract, Delivery, Evidence, JournalEntry, LaneId, Message, Payment, RunEvent, Step,
  Track, ZipCount,
} from "./contract";

/** An event as written here, before seq and time are stamped on. */
export type Draft<E = RunEvent> = E extends RunEvent ? Omit<E, "seq" | "at" | "track"> & { track?: Track } : never;

const T0 = Date.parse("2026-10-24T17:00:00Z");
export function stamp(track: Track, drafts: Draft[], from = 0): RunEvent[] {
  return drafts.map((d, i) => ({ track, ...d, seq: from + i + 1, at: new Date(T0 + (from + i + 1) * 60_000).toISOString() }) as RunEvent);
}

// How long each event holds the screen during playback, long enough to read what changed
export function holdFor(e: { type: RunEvent["type"] }): number {
  switch (e.type) {
    case "evidence_found": return 1100;
    case "source_checked": return 900;
    case "aside": return 1300;
    case "message": return 1250; // long enough to read a one- or two-line bubble
    case "verdict": case "rule_updated": case "controller_decided": case "amendment_signed": case "books_posted": return 1400;
    case "check_passed": case "check_failed": case "check_fixed": return 600;
    case "contract_line_asked": case "contract_line_drafted": case "contract_approved": case "delivery_ready": return 300;
    case "step_started": return 1200;
    case "step_completed": return 700;
    case "dispute_opened": return 1800;
    case "caption": return 100;
    default: return 500;
  }
}

export const S = {
  us: "DataPact",
  agent: "Order agent",
  buyer: "Acme Fitness",
  buyerAgent: "Acme's buying agent",
  controller: "Human",
  controllerRole: "Controller",
  order: "SF adults 25–34 interested in fitness, counts by ZIP",
  price: 120,
  rerunCost: 6, // vendor license + compute for one production run
  oakland: 60,
  yoga: 30,
  seat: "Order-to-cash agent for a data broker",
  positioning: "Existing platforms handle transactions and delivery. We connect a custom order's requirements to fulfillment checks, evidence gathering, correction and authorized settlement.",
  reviewHours: 48,
};

export const POLICY = {
  contract: "Acme approved the contract and its price",
  amendment: "Acme approved and signed the amendment",
  freeRerun: "Our-fault policy: one free rerun per order",
  accepted: "Delivery accepted, no open dispute",
  ruling: "Controller ruling on an escalated dispute",
  contractV2: "Contract v2 settles it: no person needed",
  unclearSpec: "Our rule: an unclear spec is on us",
  vendorCategory: "Our rule: when the interview is silent, the vendor's category decides",
  escalate: "Rules can't decide: escalate to the controller",
};

export const CONTRACT: ContractLine[] = [
  { id: "fitness", text: "Fitness = gym members or fitness-app users", check: "code" },
  { id: "city", text: "San Francisco city ZIPs only", check: "schema" },
  { id: "ages", text: "Ages 25–34", check: "schema" },
  { id: "privacy", text: "At least 50 people per ZIP (privacy)", check: "code" },
  { id: "coverage", text: "Every SF ZIP present", check: "code" },
];
export const CONTRACT_V2: ContractLine = { id: "yoga", text: "Yoga studio members count as fitness", check: "code" };
export const CONTRACT_V1: DataContract = { version: 1, buyer: S.buyer, title: S.order, price: S.price, lines: CONTRACT };
const V2: DataContract = { ...CONTRACT_V1, version: 2, lines: [...CONTRACT, CONTRACT_V2] };

const buyer = (id: string, text: string, attach?: Message["attach"]): Message => ({ id, from: "buyer", text, attach });
const agent = (id: string, text: string, attach?: Message["attach"], asks?: string): Message => ({ id, from: "agent", text, attach, asks });
const human = (id: string, text: string): Message => ({ id, from: "controller", text });

/** The intake interview. Each answer settles one contract line. */
export const INTERVIEW: Message[] = [
  buyer("m1", "We need SF adults 25–34 interested in fitness, counts by ZIP, for an ad campaign."),
  agent("m2", "How should we define \"interested in fitness\"?", undefined, "fitness"),
  buyer("m3", "Gym members or people who use fitness apps."),
  agent("m4", "San Francisco city only, or the wider Bay Area?", undefined, "city"),
  buyer("m5", "SF city only."),
  agent("m6", "Ages 25 to 34, inclusive?", undefined, "ages"),
  buyer("m7", "Yes."),
  agent("m8", "Any ZIP with fewer than 50 people is withheld for privacy. OK?", undefined, "privacy"),
  buyer("m9", "Fine."),
  agent("m10", `Every SF ZIP will be covered. Price: $${S.price}. Approve?`, undefined, "coverage"),
  buyer("m11", "Approved."),
];
const SETTLES: Record<string, string> = { m3: "fitness", m5: "city", m7: "ages", m9: "privacy", m11: "coverage" };

const row = (zip: string, area: string, count: number | null, flag?: ZipCount["flag"]): ZipCount => ({ zip, area, count, flag });
// Every San Francisco ZIP in the backend's registry (datasets.py SF_KEYS); the counts are synthetic
export const ROWS: ZipCount[] = [
  row("94102", "Tenderloin", 1820), row("94103", "SoMa", 2140), row("94104", "Financial District", 140), row("94105", "Rincon Hill", 2310),
  row("94107", "Potrero Hill", 2960), row("94108", "Chinatown", 860), row("94109", "Nob Hill", 3310), row("94110", "Mission", 4120),
  row("94111", "Embarcadero", 610), row("94112", "Excelsior", 2840), row("94114", "Castro", 2450), row("94115", "Western Addition", 3120),
  row("94116", "Parkside", 1760), row("94117", "Haight", 2780), row("94118", "Inner Richmond", 2530), row("94121", "Outer Richmond", 2080),
  row("94122", "Sunset", 3050), row("94123", "Marina", 3480), row("94124", "Bayview", 1540), row("94127", "West Portal", 980),
  row("94129", "Presidio", null, "withheld"), row("94130", "Treasure Island", 160), row("94131", "Glen Park", 2270), row("94132", "Lake Merced", 1690),
  row("94133", "North Beach", 1990), row("94134", "Visitacion Valley", 1130), row("94158", "Mission Bay", 1870),
];
export const AREA_BY_ZIP: Record<string, string> = Object.fromEntries(ROWS.map((r) => [r.zip, r.area]));
export const OAKLAND: ZipCount[] = [row("94607", "West Oakland", 1640, "added"), row("94610", "Lakeshore", 2210, "added"), row("94612", "Downtown Oakland", 1880, "added")];
const PRIVACY_FLOOR = 50;
const withheld = (rows: ZipCount[]) => rows.map((r) => (r.count === null || r.count < PRIVACY_FLOOR ? { ...r, flag: "withheld" as const } : r));
// The vendor's ZIP list leaves out 94110, and our check compared against it until the red lane's fix
const VENDOR = ROWS.filter((r) => r.zip !== "94110");
const yoga = (rows: ZipCount[]) => rows.map((r) => (r.flag === "withheld" ? r : { ...r, count: Math.round((r.count ?? 0) * 1.09), flag: "yoga" as const }));
const closes = (hours: number) => new Date(T0 + hours * 3_600_000).toISOString();
const SHEET_V1: Delivery = { version: 1, file: "acme-sf-fitness-v1.csv", rows: withheld(VENDOR), reviewClosesAt: closes(48) };
const sheet = (version: number, file: string, rows: ZipCount[]): Delivery => ({ version, file, rows, reviewClosesAt: closes(96) });

export const MAIN: Step[] = [
  { id: "clarify", kind: "clarify", title: "Clarify the order", detail: `Interview to a $${S.price} contract`, panel: true },
  { id: "paid", kind: "paid", title: "Paid upfront", detail: `$${S.price} authorized` },
  { id: "produce", kind: "produce", title: "Produce & check", detail: "Build and check the dataset", panel: true },
  { id: "review", kind: "review", title: "Customer review", detail: `${S.reviewHours}h to accept or dispute` },
  { id: "captured", kind: "captured", title: "Captured", detail: "Paid and booked", panel: true },
];

const step = (id: string, kind: Step["kind"], title: string, detail: string, panel?: boolean): Step => ({ id, kind, title, detail, panel });
const start = (s: string, attempt = 1): Draft => ({ type: "step_started", step: s, attempt });
const done = (s: string, attempt = 1): Draft => ({ type: "step_completed", step: s, attempt });
const wait = (s: string, on: string, attempt = 1): Draft => ({ type: "step_waiting", step: s, waitingOn: on, attempt });
const say = (s: string, message: Message, attempt = 1): Draft => ({ type: "message", step: s, message, attempt });
const found = (s: string, evidence: Evidence): Draft => ({ type: "evidence_found", step: s, evidence });
const pay = (id: string, amount: number): Payment => ({ id, amount, rail: "commerce-payments", network: "base-sepolia", mock: true });
let j = 0;
const entry = (memo: string, debit: string, credit: string, amount: number): JournalEntry => ({ id: `j${++j}`, memo, debit, credit, amount });

const passAll = (attempt: number, detailFor: (id: string) => string | undefined): Draft[] =>
  CONTRACT.map((l) => ({ type: "check_passed", step: "produce", attempt, lineId: l.id, detail: detailFor(l.id) }));
const firstRunChecks: Draft[] = [
  ...CONTRACT.slice(0, 3).map((l): Draft => ({ type: "check_passed", step: "produce", lineId: l.id })),
  { type: "check_failed", step: "produce", lineId: "privacy", reason: `ZIP 94129 is suppressed, below ${PRIVACY_FLOOR}` },
  { type: "check_fixed", step: "produce", lineId: "privacy", fix: "94129 withheld" },
  { type: "delivery_ready", step: "produce", delivery: SHEET_V1 },
  { type: "check_passed", step: "produce", lineId: "coverage", detail: "vs vendor list" },
];
const books = (attempt: number, revenue: number, extra: JournalEntry[]): Draft => ({
  type: "books_posted", step: "captured", attempt, entries: [
    entry("Payment captured", "Cash", "Revenue", S.price),
    entry("Data + compute, first run", "Data cost", "Cash", S.rerunCost),
    ...extra,
  ], margin: { revenue, cost: S.rerunCost + extra.filter((e) => e.debit === "Data cost").reduce((a, e) => a + e.amount, 0) },
});

/** The normal path up to the review window; every case starts here. */
export const SHARED_PREFIX: Draft[] = [
  { type: "steps_planned", steps: MAIN },
  start("clarify"),
  ...INTERVIEW.flatMap((m): Draft[] => {
    const settles = SETTLES[m.id];
    const line = CONTRACT.find((l) => l.id === settles);
    return [say("clarify", m), ...(line ? [{ type: "contract_line_drafted", step: "clarify", line } as Draft] : [])];
  }),
  { type: "contract_approved", step: "clarify", contract: CONTRACT_V1, allowedBy: POLICY.contract },
  done("clarify"),
  start("paid"),
  { type: "payment_authorized", payment: pay("order", S.price), allowedBy: POLICY.contract },
  done("paid"),
  start("produce"),
  { type: "delivery_ready", step: "produce", delivery: { ...SHEET_V1, rows: VENDOR } },
  ...firstRunChecks,
  done("produce"),
  start("review"),
];
const accept = (attempt: number): Draft[] => [say("review", buyer("m-accept", "Reviewed and accepted."), attempt), done("review", attempt)];
export const SHARED: Draft[] = [
  ...SHARED_PREFIX,
  ...accept(1),
  start("captured"),
  { type: "payment_captured", paymentId: "order", captureTx: null, allowedBy: POLICY.accepted },
  books(1, S.price, []),
  done("captured"),
];

const CLAIM = { red: "ZIP 94110 is missing", green: "Counts look low, add Oakland", amber: "Yoga studio members should count" };
const openDispute = (lane: LaneId, steps: Step[], claim: Message): Draft[] => [
  { type: "dispute_opened", step: "review", dispute: { id: "dispute", claim: CLAIM[lane], raisedBy: S.buyerAgent } },
  wait("review", S.buyer),
  { type: "steps_planned", steps },
  start("investigate"),
  say("investigate", claim),
];
/** Back to Produce with attempt 2, then review and capture again. */
const rewalk = (delivery: Delivery, checkDetail: (id: string, delivery: Delivery) => string | undefined, captured: number, extra: JournalEntry[], rule?: Draft): Draft[] => [
  start("produce", 2),
  { type: "delivery_ready", step: "produce", attempt: 2, delivery },
  ...passAll(2, (id) => checkDetail(id, delivery)),
  ...(rule ? [rule] : []),
  done("produce", 2),
  start("review", 2),
  ...accept(2),
  start("captured"),
  { type: "payment_captured", paymentId: "order", captureTx: null, allowedBy: POLICY.accepted },
  ...(captured > S.price ? [{ type: "payment_captured", paymentId: "extra", captureTx: null, allowedBy: POLICY.accepted } as Draft] : []),
  books(1, captured, extra),
  done("captured"),
];
const coverageDetails = (id: string, delivery: Delivery) => (id === "coverage" ? `${delivery.rows.length} ZIP rows checked` : id === "privacy" ? "94129 withheld" : undefined);

const E = {
  line5: { id: "e-line5", kind: "interview_quote", label: "Contract line 5 · every SF ZIP", speaker: S.buyerAgent, quote: "Approved.", note: "Line 5 of the contract: every SF ZIP present.", source: { kind: "message", messageId: "m11" } },
  no94110: { id: "e-94110", kind: "sheet_cell", label: "Delivered sheet · no 94110 row", file: SHEET_V1.file, row: "94110", column: "People", value: null, note: "Missing from the delivery. Our check used the vendor's ZIP list, which lacked it.", source: { kind: "cell", version: 1, row: "94110", column: "People" } },
  sfOnly: { id: "e-city", kind: "interview_quote", label: "Interview · “SF city only.”", speaker: S.buyerAgent, quote: "SF city only.", note: "Agreed in the interview. It became line 2 of the contract.", source: { kind: "message", messageId: "m5" } },
  line2: { id: "e-line2", kind: "interview_quote", label: "Contract line 2 · SF ZIPs only", speaker: S.buyerAgent, quote: "SF city only.", note: "Line 2 of the contract.", source: { kind: "none", reason: "The contract is on the Clarify step" } },
  gyms: { id: "e-fitness", kind: "interview_quote", label: "Interview · “gym members or fitness-app users”", speaker: S.buyerAgent, quote: "Gym members or people who use fitness apps.", note: "What Acme said fitness means. Yoga wasn't named.", source: { kind: "message", messageId: "m3" } },
  wellness: { id: "e-wellness", kind: "vendor_category", label: "Vendor · yoga filed under “Wellness”", vendor: "Data vendor", item: "Yoga studios", category: "Wellness", note: "The vendor files yoga under Wellness, not Fitness.", source: { kind: "none", reason: "The vendor's category list lives outside this run" } },
  claim: { id: "e-claim", kind: "claim", label: "Acme · “yoga is fitness”", speaker: S.buyerAgent, quote: "Yoga studio members should count as fitness.", note: "Acme's claim during the dispute. A claim, not something the contract says.", source: { kind: "message", messageId: "m-claim" } },
  v2: { id: "e-v2", kind: "interview_quote", label: "Contract v2 · yoga counts as fitness", speaker: S.controller, quote: CONTRACT_V2.text, note: "Added to the contract by the controller's ruling.", source: { kind: "none", reason: "Contract v2 is on the Clarify step" } },
} satisfies Record<string, Evidence>;
const cite = (...ids: string[]): Message["attach"] => ids.map((evidenceId) => ({ kind: "evidence", evidenceId }));

/** The three things the agent reads at the source during any dispute. */
const SRC = (checked: boolean): Draft => ({ type: "source_checked", step: "investigate", lines: [
  { id: "src-pin", text: "Vendor panel v1, pinned at acceptance", checked },
  { id: "src-lines", text: "Every contract line re-checked against it", checked },
  { id: "src-counts", text: "Delivered counts compared with the source", checked },
] });
export const RED: Draft[] = [
  ...openDispute("red", [
    step("investigate", "investigate", "Investigate", `“${CLAIM.red}”`, true),
    step("verdict", "verdict", "They're right", "Our check missed 94110"),
  ], buyer("m-claim", "ZIP 94110 is missing from the delivery.")),
  SRC(false),
  SRC(true),
  found("investigate", E.line5),
  found("investigate", E.no94110),
  say("investigate", agent("m-reply", "Checking against your contract. You're right: there's no 94110 row. Our check used the vendor's ZIP list, which lacked it. Rerunning now at our cost.", cite("e-line5", "e-94110"))),
  done("investigate"),
  start("verdict"),
  { type: "verdict", step: "verdict", verdict: { kind: "agree", decidedBy: "rules", evidenceIds: ["e-line5", "e-94110"], reason: "The contract promises every SF ZIP and 94110 is missing. Our check used the vendor's list instead of the official one." }, allowedBy: `Contract line: ${CONTRACT[4].text}` },
  { type: "aside", step: "verdict", text: "Our miss, caught by the checks. Corrected at our cost, no human needed." },
  done("verdict"),
  ...rewalk(sheet(2, "acme-sf-fitness-v2.csv", withheld(ROWS).map((r) => (r.zip === "94110" ? { ...r, flag: "added" as const } : r))), coverageDetails, S.price,
    [entry("Rerun 94110, our cost", "Data cost", "Cash", S.rerunCost)],
    { type: "rule_updated", step: "produce", attempt: 2, rule: { id: "rule-zips", label: "Rule updated · use the official SF ZIP list", text: "Check ZIP coverage against the official SF list, not the vendor's.", decidedBy: S.agent } }),
];

const ADD_OAKLAND: Amendment = { id: "extra", summary: "Add Oakland ZIPs", price: S.oakland, line: { id: "oakland", text: `Amendment: add Oakland ZIPs · +$${S.oakland}`, check: "schema" } };
export const GREEN: Draft[] = [
  ...openDispute("green", [
    step("investigate", "investigate", "Investigate", `“Add Oakland”`, true),
    step("verdict", "verdict", "We're right", "Contract: SF city only"),
    step("amend", "amend", "Amendment", `Add Oakland for $${S.oakland}`, true),
  ], buyer("m-claim", "Counts look low. Oakland should be in there.")),
  SRC(false),
  SRC(true),
  found("investigate", E.sfOnly),
  found("investigate", E.line2),
  say("investigate", agent("m-reply", `Your order covers San Francisco city only. Nothing's missing from what was agreed, and there's no charge for asking. Want Oakland added as an amendment for $${S.oakland}?`, cite("e-city", "e-line2"))),
  done("investigate"),
  start("verdict"),
  { type: "verdict", step: "verdict", verdict: { kind: "disagree", decidedBy: "rules", evidenceIds: ["e-city", "e-line2"], reason: "We delivered what was agreed: San Francisco city only, which Acme said in the interview." }, allowedBy: `Contract line: ${CONTRACT[1].text}` },
  { type: "aside", step: "verdict", text: "Settled by the contract and the source. No human needed." },
  done("verdict"),
  start("amend"),
  say("amend", buyer("m-yes", "Yes, add Oakland.")),
  say("amend", agent("m-offer", `Amendment: + Oakland (3 ZIPs), $${S.oakland}. Same rules otherwise. Approve and sign?`)),
  say("amend", buyer("m-signed", `Approved. Signed $${S.oakland}.`)),
  { type: "amendment_signed", step: "amend", amendment: ADD_OAKLAND, allowedBy: POLICY.amendment },
  { type: "payment_authorized", payment: pay("extra", S.oakland), allowedBy: POLICY.amendment },
  done("amend"),
  ...rewalk(sheet(2, "acme-sf-oakland-fitness-v2.csv", [...withheld(VENDOR), ...OAKLAND]), coverageDetails, S.price + S.oakland,
    [entry("Amendment: Oakland", "Cash", "Revenue", S.oakland), entry("Oakland run", "Data cost", "Cash", S.rerunCost)]),
];

/** How the grey-area lane ends; on stage the live agent decides, the switch is the rehearsal. */
export type Ending = "rules_no" | "rules_yes" | "human";
export const ENDINGS: [Ending, string][] = [["rules_no", "Rules: we're right"], ["rules_yes", "Rules: they're right"], ["human", `${S.controller} decides`]];
export const HUMAN_QUESTION = "Should yoga studio members count as fitness for Acme's order?";
const AMBER_EVIDENCE = ["e-fitness", "e-wellness", "e-claim"];
const YOGA: Amendment = { id: "extra", summary: "Add yoga studio members", price: S.yoga, line: { id: "yoga-amend", text: `Amendment: add yoga studio members · +$${S.yoga}`, check: "code" } };
const YOGA_SHEET = sheet(2, "acme-sf-fitness-v2.csv", yoga(withheld(VENDOR)));

/** The decide step's title depends on the ending; learned = the replay after Human's ruling. */
export function amberSteps(ending: Ending, learned: boolean): Step[] {
  const decide = learned ? step("decide", "decide", "Contract v2 decides", "Yoga counts, free rerun", true)
    : ending === "rules_no" ? step("decide", "decide", "Rules: we're right", `Yoga amendment for $${S.yoga}`, true)
    : ending === "rules_yes" ? step("decide", "decide", "Rules: they're right", "Unclear spec, free rerun", true)
    : step("decide", "decide", `${S.controller} decides`, "Controller review", true);
  return [
    step("investigate", "investigate", "Investigate", `“Yoga should count”`, true),
    learned ? step("grey", "grey", "Covered", "Contract v2 says yoga counts") : step("grey", "grey", "Grey area", "Nothing says yes or no"),
    decide,
  ];
}

export function amberOpen(ending: Ending, learned: boolean): Draft[] {
  const claim = buyer("m-claim", "Yoga studio members should count as fitness.");
  return [
    ...openDispute("amber", amberSteps(ending, learned), claim),
    ...(learned ? [
      found("investigate", E.v2),
      say("investigate", agent("m-reply", "Contract v2 already says yoga counts. Adding yoga members now at no cost. No review needed.", cite("e-v2"))),
      done("investigate"),
      start("grey"),
      { type: "verdict", step: "grey", verdict: { kind: "agree", decidedBy: "contract", evidenceIds: ["e-v2"], reason: "Contract v2 says yoga counts. No person needed." }, allowedBy: POLICY.contractV2 } as Draft,
      done("grey"),
    ] : [
      found("investigate", E.gyms),
      found("investigate", E.wellness),
      found("investigate", E.claim),
      say("investigate", agent("m-reply", "Your definition was gym members or fitness-app users. Our data vendor files yoga under “Wellness”. The contract doesn't settle it either way.", cite("e-fitness", "e-wellness"))),
      done("investigate"),
      start("grey"),
      { type: "verdict", step: "grey", verdict: { kind: "grey", decidedBy: "rules", evidenceIds: AMBER_EVIDENCE, reason: "No contract line or rule says yes or no." }, allowedBy: POLICY.escalate } as Draft,
      done("grey"),
    ]),
    start("decide"),
  ];
}

const yogaRerun = (extra: JournalEntry[] = []) => rewalk(YOGA_SHEET, coverageDetails, S.price, [entry("Rerun with yoga, our cost", "Data cost", "Cash", S.rerunCost), ...extra]);
const yogaAmendment: Draft[] = [
  say("decide", buyer("m-signed", `Yes. Signed $${S.yoga}.`)),
  { type: "amendment_signed", step: "decide", amendment: YOGA, allowedBy: POLICY.amendment },
  { type: "payment_authorized", payment: pay("extra", S.yoga), allowedBy: POLICY.amendment },
  done("decide"),
  ...rewalk(YOGA_SHEET, coverageDetails, S.price + S.yoga, [entry("Amendment: yoga", "Cash", "Revenue", S.yoga), entry("Yoga run", "Data cost", "Cash", S.rerunCost)]),
];

export function amberEnding(ending: Ending, learned: boolean): Draft[] {
  if (learned) return [
    say("decide", agent("m-auto", "Contract v2 decides: yoga counts. Free rerun.", cite("e-v2"))),
    { type: "verdict", step: "decide", verdict: { kind: "agree", decidedBy: "contract", evidenceIds: ["e-v2"], reason: "Contract v2 decides: yoga counts." }, allowedBy: POLICY.contractV2 },
    done("decide"),
    ...yogaRerun(),
  ];
  if (ending === "rules_yes") return [
    say("decide", agent("m-rule", "Our rule: an unclear spec is on us. Adding yoga members now at no cost.")),
    { type: "verdict", step: "decide", verdict: { kind: "agree", decidedBy: "rules", evidenceIds: AMBER_EVIDENCE, reason: "An unclear spec is on us, so they're right and the rerun is free." }, allowedBy: POLICY.unclearSpec },
    done("decide"),
    ...yogaRerun(),
  ];
  if (ending === "rules_no") return [
    say("decide", agent("m-rule", `Our rule: when the interview is silent, the vendor's category decides. Yoga isn't in your order. Want it added for $${S.yoga}?`)),
    { type: "verdict", step: "decide", verdict: { kind: "disagree", decidedBy: "rules", evidenceIds: AMBER_EVIDENCE, reason: "The vendor's category decides, so we're right and yoga is extra." }, allowedBy: POLICY.vendorCategory },
    ...yogaAmendment,
  ];
  // human: hold here until the controller clicks; controllerContinuation supplies the rest
  return [
    say("decide", agent("m-escalate", HUMAN_QUESTION, cite("e-fitness", "e-wellness", "e-claim"))),
    wait("decide", S.controller),
  ];
}

/** What follows the controller's click. The stub serves this; a recorded replay appends it. */
export function controllerContinuation(action: ControllerAction, binding: { deliveryVersion: number; evidenceVersion: number }): Draft[] {
  const decided = (note: string): Draft => ({ type: "controller_decided", step: "decide", action, by: S.controller, note, binding });
  switch (action) {
    case "approve": return [
      decided("Yoga counts. They're right that it's fitness."),
      say("decide", human("m-human", "Yoga counts. They're right that it's fitness.")),
      { type: "verdict", step: "decide", verdict: { kind: "agree", decidedBy: "controller", evidenceIds: AMBER_EVIDENCE, reason: `${S.controller} ruled that yoga studio members count as fitness.` }, allowedBy: POLICY.ruling },
      { type: "contract_approved", step: "decide", contract: V2, allowedBy: POLICY.ruling },
      { type: "rule_updated", step: "decide", rule: { id: "rule-yoga", label: "Learned · yoga counts as fitness (contract v2)", text: CONTRACT_V2.text, decidedBy: S.controller } },
      say("decide", agent("m-after", "Our controller reviewed it: yoga counts. Adding yoga members now at no cost.", cite("e-v2"))),
      done("decide"),
      ...yogaRerun(),
    ];
    case "reject": return [
      decided("Yoga wasn't agreed. Offer it as an amendment."),
      say("decide", human("m-human", "Yoga wasn't agreed. Offer it as an amendment.")),
      { type: "verdict", step: "decide", verdict: { kind: "disagree", decidedBy: "controller", evidenceIds: AMBER_EVIDENCE, reason: `${S.controller} ruled that yoga was not in scope.` }, allowedBy: POLICY.ruling },
      say("decide", agent("m-offer", `Our controller reviewed it: yoga isn't in your order. Want it added for $${S.yoga}?`)),
      ...yogaAmendment,
    ];
    case "ask": return [
      decided("Asked Acme for their member categories."),
      say("decide", human("m-human", "Can you share how your own members are categorized?")),
      say("decide", buyer("m-cats", "We tag yoga, pilates and gyms all as fitness.")),
      wait("decide", S.controller),
    ];
    case "escalate": return [
      decided("Sent up to the CFO."),
      say("decide", human("m-human", "Sending this up to the CFO.")),
      wait("decide", "the CFO"),
    ];
  }
}

export const LANES: LaneId[] = ["red", "green", "amber"];
export const LANE_NAME: Record<LaneId, string> = { red: "Our fault", green: "We were right", amber: "Grey area" };
export type Case = "shared" | LaneId;
export const CASE_NAME: Record<Case, string> = { shared: "No dispute", ...LANE_NAME };

export function laneDrafts(lane: LaneId, ending: Ending, learned: boolean): Draft[] {
  return lane === "red" ? RED : lane === "green" ? GREEN : [...amberOpen(ending, learned), ...amberEnding(ending, learned)];
}

/** One case's recorded run: the normal path, then the lane if any. */
export function timeline(c: Case, ending: Ending, learned = false): { events: RunEvent[]; start: number } {
  if (c === "shared") return { events: stamp("shared", SHARED), start: 0 };
  const before = stamp("shared", SHARED_PREFIX);
  return { events: [...before, ...stamp(c, laneDrafts(c, ending, learned), before.length)], start: before.length };
}

/** The canvas chip for a step, from what the step has been through. */
export function chipFor(step: Step, n: { status: string; attempt: number; checks: number; lines: number; sources: number; verdictKind?: string; verdictBy?: string; amendmentPrice?: number; waitingOn?: string; window?: string; learned: boolean; disputed: boolean; decided?: string; ruled: boolean }): string | undefined {
  const { status, attempt } = n;
  if (status === "idle") return undefined;
  switch (step.kind) {
    case "clarify": return status === "done" ? "Contract v1 approved" : "Interviewing";
    case "paid": return "Done";
    case "produce":
      if (status === "running") return attempt > 1 ? (n.verdictKind === "agree" ? `Rerun · our cost $${S.rerunCost}` : n.amendmentPrice === S.oakland ? "Adding Oakland" : "Adding yoga") : "Checking";
      return attempt > 1 ? (n.verdictKind === "agree" ? "Rechecked" : "Checks passed") : `${n.checks} of ${n.lines} passed`;
    case "review": return status === "waiting" ? "Disputed" : status === "done" ? "Accepted" : attempt > 1 ? "New review window" : `${n.window ?? `${S.reviewHours}h`} window`;
    case "captured": return "Done";
    case "investigate": return status === "done" ? `${n.sources} source${n.sources === 1 ? "" : "s"}` : "Checking";
    case "verdict": return n.verdictKind === "agree" ? "Our miss" : "We're right";
    case "grey": return n.learned ? "Covered" : "Grey area";
    case "amend": return status === "done" ? `+$${S.oakland} signed` : "Amendment";
    case "decide":
      if (status === "waiting") return `Waiting on ${n.waitingOn}`;
      if (n.learned) return "Covered";
      if (n.amendmentPrice) return `+$${n.amendmentPrice} signed`;
      if (n.verdictBy === "controller") return n.ruled ? "Rule learned" : "Resumed · corrected";
      if (n.decided === "approve") return "Resumed";
      return n.verdictKind === "agree" ? "They're right" : n.verdictKind === "disagree" ? "We're right" : "Deciding";
  }
}

/** The caption under the canvas, for the events that change what the viewer should understand. */
export function captionFor(e: RunEvent, ctx: { lane: Case; ending: Ending; learned: boolean; captured: number; reviewWindow?: string }): string | undefined {
  const window = ctx.reviewWindow ?? `${S.reviewHours} hours`;
  const s = "step" in e ? e.step : undefined;
  const attempt = "attempt" in e ? e.attempt ?? 1 : 1;
  if (e.type === "dispute_opened") return `Acme disputes: “${e.dispute.claim}”. The payment is on hold until it's resolved.`;
  if (e.type === "step_started") {
    if (s === "clarify") return "Our agent interviews Acme's buying agent. Each answer becomes a line in the contract.";
    if (s === "paid") return `Acme approves the contract and authorizes $${S.price}. We only take it once the data is accepted.`;
    if (s === "produce" && attempt === 1) return "We build the counts from rented vendor data and check every contract line.";
    if (s === "produce") return ctx.lane === "red" ? `The orb carries the job back to Produce. The rerun is on us: $${S.rerunCost}.`
      : ctx.lane === "green" ? "Back to Produce with the amended contract." : "Back to Produce to add yoga studio members.";
    if (s === "review" && attempt === 1) return ctx.reviewWindow ? `Delivered. Acme has ${window} to accept or dispute.` : `Delivered. One ZIP was held back for privacy. Acme has ${window} to accept or dispute.`;
    if (s === "review") return ctx.lane === "red" ? "94110 added and rechecked against the official SF ZIP list. That check is now permanent."
      : ctx.lane === "green" ? "Oakland rows added and checked. New review window." : "Yoga members added and checked. New review window.";
    if (s === "investigate") return ctx.lane === "red" ? "The agent checks the contract against the delivered sheet."
      : ctx.lane === "green" ? "The agent pulls what Acme agreed to in the interview."
      : ctx.learned ? "Same complaint as before. This time the contract already answers it." : "The agent gathers evidence. The interview never mentioned yoga.";
    if (s === "amend") return `Acme still wants Oakland, so it becomes an amendment: $${S.oakland}, approved and signed by Acme.`;
  }
  if (e.type === "step_completed" && s === "captured") {
    if (ctx.lane === "shared") return "Accepted. Payment captured and the books are posted.";
    if (ctx.lane === "red") return `Accepted. $${S.price} captured; the $${S.rerunCost} rerun is booked as our cost.`;
    if (ctx.lane === "green") return `Accepted. $${ctx.captured} captured in total.`;
    return `Accepted. $${ctx.captured} captured.`;
  }
  if (e.type === "verdict") {
    const v = e.verdict;
    if (s === "verdict") return v.kind === "agree" ? "They're right. Our check used the vendor's ZIP list, which didn't have 94110." : "We're right: we delivered what was agreed. No charge for asking.";
    if (s === "grey") return ctx.learned ? "Covered by contract v2. No person needed." : "Grey area: no contract line or rule says yes or no.";
    if (s === "decide") return v.decidedBy === "controller" ? `${S.controller}: yoga counts. Saved as contract v2, so next time no person is needed.`
      : v.decidedBy === "contract" ? "Contract v2 decides: yoga counts. Free rerun."
      : v.kind === "agree" ? "Our rule: an unclear spec is on us. So they're right, and the rerun is free." : "Our rule: the vendor's category decides. So we're right, and yoga is extra.";
  }
  if (e.type === "step_waiting" && s === "decide") return `The rules can't decide, so it goes to ${S.controller}, our controller, with the evidence.`;
  if (e.type === "amendment_signed" && s === "decide") return `Acme accepts a yoga amendment at $${S.yoga}.`;
  return undefined;
}
