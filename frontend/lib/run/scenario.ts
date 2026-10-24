// The demo scenario: Datum Co. builds a custom audience dataset for Acme Fitness's buying agent.
// Every name, amount and line of text on the canvas comes from this file. Synthetic data;
// prices are sample values for the team to confirm.
import type {
  Amendment, ContractLine, ControllerAction, DataContract, Delivery, JournalEntry, LaneId, Message, Payment, RunEvent, Step,
  StepKind, Track, VerdictKind, ZipCount,
} from "./contract";

/** An event as written here, before seq and time are stamped on. */
export type Draft<E = RunEvent> = E extends RunEvent ? Omit<E, "seq" | "at" | "track"> & { track?: Track } : never;

// How long each event holds the screen during playback, long enough to read what changed
export function holdFor(e: { type: RunEvent["type"] }): number {
  switch (e.type) {
    case "evidence_found": return 1800;
    case "message": case "verdict": case "rule_updated": case "rule_applied": case "controller_decided": return 1500;
    case "check_passed": case "check_failed": case "check_fixed": case "contract_line_drafted": return 450;
    case "step_started": return 900;
    default: return 600;
  }
}

const T0 = Date.parse("2026-10-24T17:00:00Z");
export function stamp(track: Track, drafts: Draft[], from = 0): RunEvent[] {
  return drafts.map((d, i) => ({ track, ...d, seq: from + i + 1, at: new Date(T0 + (from + i + 1) * 60_000).toISOString() }) as RunEvent);
}

export const CO = {
  us: "Datum Co.",
  buyer: "Acme Fitness",
  buyerAgent: "Acme's buying agent",
  controller: "Maya",
  agent: "Datum agent",
  title: "SF fitness audience by ZIP",
  price: 120,
  runCost: 6, // vendor license + compute for one production run
  oakland: 60,
  yoga: 30,
  reviewHours: 48,
};

const buyer = (id: string, text: string, attach?: Message["attach"]): Message => ({ id, from: "buyer", name: CO.buyerAgent, text, attach });
const agent = (id: string, text: string, attach?: Message["attach"]): Message => ({ id, from: "agent", name: CO.agent, text, attach });
const maya = (id: string, text: string, attach?: Message["attach"]): Message => ({ id, from: "controller", name: CO.controller, text, attach });

const step = (id: string, kind: StepKind, title: string, detail: string): Step => ({ id, kind, title, detail });
const start = (s: string): Draft => ({ type: "step_started", step: s });
const done = (s: string): Draft => ({ type: "step_completed", step: s });
const wait = (s: string, on: string): Draft => ({ type: "step_waiting", step: s, waitingOn: on });
const say = (s: string, message: Message): Draft => ({ type: "message", step: s, message });
const passAll = (s: string, lines: ContractLine[]): Draft[] => lines.map((l) => ({ type: "check_passed", step: s, lineId: l.id }));
const pay = (id: string, amount: number): Payment => ({ id, amount, rail: "x402", network: "base-sepolia", mock: true });
let j = 0;
const entry = (memo: string, debit: string, credit: string, amount: number): JournalEntry => ({ id: `j${++j}`, memo, debit, credit, amount });
const closes = (hoursFromDelivery: number) => new Date(T0 + hoursFromDelivery * 3_600_000).toISOString();

export const POLICY = {
  contract: "Acme approved the contract and its price",
  amendment: "Acme approved the amendment and its price",
  freeRerun: "Our-fault policy: one free rerun per order",
  accepted: "Delivery accepted, no open dispute",
  ruling: "Controller ruling on an escalated dispute",
  savedRule: "Decided by a rule a controller saved",
};

export const V1: ContractLine[] = [
  { id: "fitness", text: "Fitness means gym members or fitness-app users", check: "code" },
  { id: "city", text: "San Francisco city only", check: "schema" },
  { id: "ages", text: "Ages 25–34", check: "schema" },
  { id: "privacy", text: "Every ZIP count is 50 or more, for privacy", check: "code" },
  { id: "coverage", text: "Every SF ZIP is present", check: "code" },
];
const reword = (lines: ContractLine[], words: Record<string, string>) => lines.map((l) => ({ ...l, text: words[l.id] ?? l.text }));
export const WITH_YOGA = reword(V1, { fitness: "Fitness means gym members, fitness-app users or yoga studios" });
export const CONTRACT_V1: DataContract = { version: 1, buyer: CO.buyer, title: CO.title, price: CO.price, lines: V1 };

const zips = (rows: [string, number][]): ZipCount[] => rows.map(([zip, count]) => ({ zip, count }));
const SF_ALL = zips([
  ["94102", 1840], ["94103", 2210], ["94104", 120], ["94105", 1630], ["94107", 2480], ["94108", 960], ["94109", 3120],
  ["94110", 3940], ["94111", 410], ["94112", 2650], ["94114", 2870], ["94115", 2290], ["94116", 1720], ["94117", 2960],
  ["94118", 2130], ["94121", 1580], ["94122", 2410], ["94123", 2740], ["94124", 1190], ["94127", 860], ["94129", 42],
  ["94130", 90], ["94131", 1930], ["94132", 1460], ["94133", 1520], ["94134", 980], ["94158", 1110],
]);
const PRIVACY_FLOOR = 50;
const withheld = (rows: ZipCount[]) => rows.map((r) => (r.count !== null && r.count < PRIVACY_FLOOR ? { ...r, count: null, note: `${r.count} people, under ${PRIVACY_FLOOR}: withheld` } : r));
// The vendor's ZIP list leaves out 94110, and our checks compared against it until the red lane's fix
const VENDOR_SF = SF_ALL.filter((r) => r.zip !== "94110");
const SF_FINAL = withheld(SF_ALL);
const VENDOR_FINAL = withheld(VENDOR_SF);
const OAKLAND = zips([
  ["94601", 1310], ["94602", 1150], ["94603", 640], ["94605", 1020], ["94606", 1480], ["94607", 1270], ["94608", 1390],
  ["94609", 1210], ["94610", 1660], ["94611", 1830], ["94612", 1740], ["94618", 980], ["94619", 890], ["94621", 520],
]);
const yogaBoost = (rows: ZipCount[]) => rows.map((r) => (r.count === null ? r : { ...r, count: Math.round(r.count * 1.09) }));
const YOGA_DELIVERY: Delivery = { version: 2, file: "acme-sf-fitness-v2.csv", rows: yogaBoost(VENDOR_FINAL), changed: VENDOR_FINAL.map((r) => r.zip), reviewClosesAt: closes(96) };

const INTERVIEW: Draft[] = [
  say("interview", agent("m-q1", "Does fitness mean gym members, fitness-app users, or something broader?")),
  say("interview", buyer("m-a1", "Gym members and fitness-app users.")),
  { type: "contract_line_drafted", step: "interview", line: V1[0] },
  say("interview", agent("m-q2", "San Francisco city only, or the wider Bay Area?")),
  say("interview", buyer("m-a2", "SF city only.")),
  { type: "contract_line_drafted", step: "interview", line: V1[1] },
  say("interview", agent("m-q3", "Ages 25 to 34, as counts by ZIP?")),
  say("interview", buyer("m-a3", "Yes, 25 to 34.")),
  { type: "contract_line_drafted", step: "interview", line: V1[2] },
  say("interview", agent("m-q4", `Counts only, and any ZIP under ${PRIVACY_FLOOR} people is held back for privacy. OK?`)),
  say("interview", buyer("m-a4", "Yes, that works.")),
  { type: "contract_line_drafted", step: "interview", line: V1[3] },
  { type: "contract_line_drafted", step: "interview", line: V1[4] },
  say("interview", agent("m-sum", `Here is the contract as I understand it, $${CO.price} for the dataset:`, [{ kind: "checklist" }])),
  say("interview", buyer("m-ok", "Looks right.")),
];

export const SHARED: Draft[] = [
  { type: "steps_planned", steps: [
    step("request", "request", `Request from ${CO.buyer}`, "Their buying agent describes the job"),
    step("interview", "interview", "Interview", "Pin down every requirement"),
    step("contract", "contract", "Data contract v1", `${V1.length} lines · $${CO.price}`),
    step("produce", "produce", "Produce the data", "Rented vendor data, counts by ZIP"),
    step("check", "check", "Check against the contract", "Every line is a check"),
    step("deliver", "deliver", "Deliver", "acme-sf-fitness-v1.csv"),
    step("review", "review", "Customer review", `${CO.reviewHours}-hour window`),
  ] },
  start("request"),
  say("request", buyer("m-req", "We need San Francisco adults 25–34 who are into fitness, as counts by ZIP.")),
  done("request"),
  start("interview"),
  ...INTERVIEW,
  done("interview"),
  start("contract"),
  { type: "contract_approved", step: "contract", contract: CONTRACT_V1, allowedBy: POLICY.contract },
  say("contract", buyer("m-approve", `Approved. Authorizing $${CO.price}.`)),
  { type: "payment_authorized", payment: pay("order", CO.price), allowedBy: POLICY.contract },
  done("contract"),
  start("produce"),
  { type: "delivery_ready", step: "produce", delivery: { version: 1, file: "acme-sf-fitness-v1.csv", rows: VENDOR_SF } },
  done("produce"),
  start("check"),
  ...passAll("check", V1.slice(0, 3)),
  { type: "check_failed", step: "check", lineId: "privacy", reason: `ZIP 94129 has 42 people, under ${PRIVACY_FLOOR}` },
  { type: "check_fixed", step: "check", lineId: "privacy", fix: "Withheld ZIP 94129 and rechecked" },
  { type: "check_passed", step: "check", lineId: "coverage" },
  done("check"),
  start("deliver"),
  { type: "delivery_ready", step: "deliver", delivery: { version: 1, file: "acme-sf-fitness-v1.csv", rows: VENDOR_FINAL, reviewClosesAt: closes(48) } },
  say("deliver", agent("m-deliver", `Delivered. ZIP 94129 had 42 people, under the ${PRIVACY_FLOOR} floor, so it is withheld. You have ${CO.reviewHours} hours to review.`, [{ kind: "sheet", version: 1, rows: ["94127", "94129", "94130"] }])),
  done("deliver"),
  start("review"),
  wait("review", CO.buyer),
  say("review", buyer("m-accept", "Reviewed and accepted.")),
  done("review"),
  { type: "payment_captured", paymentId: "order", captureTx: null, allowedBy: POLICY.accepted },
];

/** Every lane opens the same way: Acme disputes instead of accepting. */
const disputeStep = (claim: string) => step("dispute", "dispute", "Dispute", `“${claim}”`);
const openDispute = (claim: string): Draft[] => [
  start("dispute"),
  say("dispute", buyer("m-claim", claim)),
  { type: "dispute_opened", step: "dispute", dispute: { id: "dispute", claim, raisedBy: CO.buyerAgent } },
  done("dispute"),
];

const booksFor = (revenue: number, cost: number, extra: JournalEntry[] = []): Draft => ({
  type: "books_posted", step: "books", entries: [
    entry("Order payment captured", "Cash (USDC)", "Deferred revenue", CO.price),
    ...extra,
    entry("Delivery accepted", "Deferred revenue", "Revenue", revenue),
    entry("Production runs: vendor license and compute", "Data cost", "Accounts payable", cost),
  ], margin: { revenue, cost },
});

// Our fault: rerun free, recheck, redeliver, capture
const fixFree = (delivery: Delivery, lines: ContractLine[], whileChecking: Draft[] = []): Draft[] => [
  { type: "steps_planned", steps: [
    step("produce", "produce", "Back to production", `Rerun free · $${CO.runCost} our cost`),
    step("check", "check", "Recheck", "Every line again"),
    step("deliver", "deliver", "Redeliver", delivery.file),
    step("books", "books", "Books", "Capture and post entries"),
  ] },
  start("produce"),
  { type: "delivery_ready", step: "produce", delivery: { ...delivery, reviewClosesAt: undefined } },
  done("produce"),
  start("check"),
  ...passAll("check", lines),
  ...whileChecking,
  done("check"),
  start("deliver"),
  { type: "delivery_ready", step: "deliver", delivery },
  say("deliver", buyer("m-accept2", "Looks right. Accepted.")),
  done("deliver"),
  start("books"),
  { type: "payment_captured", paymentId: "order", captureTx: null, allowedBy: POLICY.accepted },
  booksFor(CO.price, CO.runCost * 2),
  done("books"),
];

// We were right but the buyer still wants it: amendment, new authorization, then produce
const amendWith = (a: Amendment, delivery: Delivery, yes: string): Draft[] => [
  { type: "steps_planned", steps: [
    step("amend", "amend", "Amendment", `${a.summary} · $${a.price}`),
    step("produce", "produce", "Back to production", a.summary),
    step("check", "check", "Check against the amendment", "Every line, amended"),
    step("deliver", "deliver", "Deliver", delivery.file),
    step("books", "books", "Books", "Capture and post entries"),
  ] },
  start("amend"),
  say("amend", agent("m-offer", `We can add it as an amendment for $${a.price}. Approve to go ahead.`)),
  wait("amend", CO.buyer),
  say("amend", buyer("m-yes", yes)),
  { type: "amendment_approved", step: "amend", amendment: a, allowedBy: POLICY.amendment },
  { type: "payment_authorized", payment: pay(a.id, a.price), allowedBy: POLICY.amendment },
  done("amend"),
  start("produce"),
  { type: "delivery_ready", step: "produce", delivery: { ...delivery, reviewClosesAt: undefined } },
  done("produce"),
  start("check"),
  ...passAll("check", a.lines),
  done("check"),
  start("deliver"),
  { type: "delivery_ready", step: "deliver", delivery },
  say("deliver", buyer("m-accept2", "Accepted.")),
  done("deliver"),
  start("books"),
  { type: "payment_captured", paymentId: "order", captureTx: null, allowedBy: POLICY.accepted },
  { type: "payment_captured", paymentId: a.id, captureTx: null, allowedBy: POLICY.accepted },
  booksFor(CO.price + a.price, CO.runCost * 2, [entry("Amendment payment captured", "Cash (USDC)", "Deferred revenue", a.price)]),
  done("books"),
];

const CLAIM = { red: "ZIP 94110 is missing.", green: "Add Oakland.", amber: "Yoga studios should count as fitness." };

export const RED: Draft[] = [
  { type: "steps_planned", steps: [disputeStep(CLAIM.red), step("verdict", "verdict", "Check the claim", "Is the complaint justified?")] },
  ...openDispute(CLAIM.red),
  start("verdict"),
  { type: "check_failed", step: "verdict", lineId: "coverage", reason: "94110 is on the official SF ZIP list but not in the delivery" },
  { type: "evidence_found", step: "verdict", evidence: {
    id: "e-94110", kind: "sheet_cell", file: "acme-sf-fitness-v1.csv", row: "94110", column: "Count", value: null,
    note: "Missing from the delivery. Our check used the vendor's ZIP list, which leaves 94110 out.",
    source: { kind: "cell", track: "shared", step: "deliver", version: 1, row: "94110", column: "Count" },
  } },
  { type: "verdict", step: "verdict", verdict: {
    kind: "agree", decidedBy: "rules", evidenceIds: ["e-94110"],
    reason: "The contract promises every SF ZIP. We checked against the vendor's list instead of the official one, so this one is on us.",
  }, allowedBy: `Contract line: ${V1[4].text}` },
  say("verdict", agent("m-sorry", "You're right, 94110 is missing. Rerunning now at no charge.", [{ kind: "evidence", evidenceId: "e-94110" }])),
  done("verdict"),
  ...fixFree({ version: 2, file: "acme-sf-fitness-v2.csv", rows: SF_FINAL, changed: ["94110"], reviewClosesAt: closes(96) }, V1, [
    { type: "rule_updated", step: "check", rule: { id: "rule-zips", decidedBy: CO.agent, text: "Check ZIP coverage against the official SF list, not the vendor's." } },
  ]),
];

const ADD_OAKLAND: Amendment = {
  id: "oakland", summary: "Add Oakland ZIPs", price: CO.oakland,
  lines: reword(V1, { city: "San Francisco and Oakland", coverage: "Every SF and Oakland ZIP is present" }),
};
export const GREEN: Draft[] = [
  { type: "steps_planned", steps: [disputeStep(CLAIM.green), step("verdict", "verdict", "Check the claim", "Is the complaint justified?")] },
  ...openDispute(CLAIM.green),
  start("verdict"),
  { type: "evidence_found", step: "verdict", evidence: {
    id: "e-city", kind: "interview_quote", speaker: CO.buyerAgent, quote: "SF city only.",
    note: "Agreed in the interview. It became line 2 of the contract.",
    source: { kind: "message", track: "shared", step: "interview", messageId: "m-a2" },
  } },
  { type: "verdict", step: "verdict", verdict: {
    kind: "disagree", decidedBy: "rules", evidenceIds: ["e-city"],
    reason: "The contract says San Francisco city only, which Acme agreed to in the interview.",
  }, allowedBy: `Contract line: ${V1[1].text}` },
  say("verdict", agent("m-no", "Oakland isn't in the contract: you said SF city only.", [{ kind: "evidence", evidenceId: "e-city" }])),
  done("verdict"),
  ...amendWith(ADD_OAKLAND, {
    version: 2, file: "acme-sf-oakland-fitness-v2.csv", rows: [...VENDOR_FINAL, ...OAKLAND], changed: OAKLAND.map((r) => r.zip), reviewClosesAt: closes(96),
  }, `OK, add Oakland for $${CO.oakland}.`),
];

/** How the grey-area lane ends; on stage the live agent decides, the switch is the rehearsal. */
export type Ending = "disagree" | "agree" | "controller";
export const ENDINGS: [Ending, string][] = [["disagree", "Rules: disagree"], ["agree", "Rules: agree"], ["controller", "Maya decides"]];
export const MAYA_QUESTION = "Should yoga studios count as fitness under contract v1?";
const AMBER_EVIDENCE = ["e-fitness", "e-wellness", "e-assumed"];

export const AMBER_OPEN: Draft[] = [
  { type: "steps_planned", steps: [
    disputeStep(CLAIM.amber),
    step("investigate", "investigate", "Investigate", "The interview and the vendor's categories"),
    step("verdict", "verdict", "Decide", "Rules first, Maya if they can't"),
  ] },
  ...openDispute(CLAIM.amber),
  start("investigate"),
  say("investigate", agent("m-look", "Checking what you told us and how our vendor files yoga.")),
  { type: "evidence_found", step: "investigate", evidence: {
    id: "e-fitness", kind: "interview_quote", speaker: CO.buyerAgent, quote: "Gym members and fitness-app users.",
    note: "What Acme said fitness means. Yoga wasn't named.",
    source: { kind: "message", track: "shared", step: "interview", messageId: "m-a1" },
  } },
  { type: "evidence_found", step: "investigate", evidence: {
    id: "e-wellness", kind: "vendor_category", vendor: "Data vendor", item: "Yoga studios", category: "Wellness",
    note: "The vendor files yoga under Wellness, not Fitness.",
    source: { kind: "none", reason: "The vendor's category list lives outside this run" },
  } },
  say("investigate", agent("m-ask", "When you said gym members, did you mean to include yoga studios?")),
  wait("investigate", CO.buyer),
  say("investigate", buyer("m-assumed", "We assumed so. Our members treat them the same.")),
  { type: "evidence_found", step: "investigate", evidence: {
    id: "e-assumed", kind: "interview_quote", speaker: CO.buyerAgent, quote: "We assumed so. Our members treat them the same.",
    note: "Acme's answer during the dispute. An assumption, not something the contract says.",
    source: { kind: "message", track: "amber", step: "investigate", messageId: "m-assumed" },
  } },
  done("investigate"),
  start("verdict"),
];

const YOGA: Amendment = { id: "yoga", summary: "Add yoga studios", price: CO.yoga, lines: WITH_YOGA };
export const AMBER_ENDINGS: Record<Ending, Draft[]> = {
  disagree: [
    { type: "verdict", step: "verdict", verdict: {
      kind: "disagree", decidedBy: "rules", evidenceIds: AMBER_EVIDENCE,
      reason: "The vendor files yoga under Wellness, and the interview named gyms and fitness apps only.",
    }, allowedBy: `Contract line: ${V1[0].text}` },
    say("verdict", agent("m-no", "Yoga wasn't in the contract.", [{ kind: "evidence", evidenceId: "e-fitness" }, { kind: "evidence", evidenceId: "e-wellness" }])),
    done("verdict"),
    ...amendWith(YOGA, YOGA_DELIVERY, `OK, add yoga studios for $${CO.yoga}.`),
  ],
  agree: [
    { type: "verdict", step: "verdict", verdict: {
      kind: "agree", decidedBy: "rules", evidenceIds: AMBER_EVIDENCE,
      reason: "Our rules count studio memberships as gym memberships, so yoga was in scope.",
    }, allowedBy: `Contract line: ${V1[0].text}` },
    say("verdict", agent("m-sorry", "You're right, yoga studios count. Rerunning now at no charge.", [{ kind: "evidence", evidenceId: "e-fitness" }])),
    done("verdict"),
    ...fixFree(YOGA_DELIVERY, V1),
  ],
  controller: [
    { type: "verdict", step: "verdict", verdict: {
      kind: "grey", decidedBy: "rules", evidenceIds: AMBER_EVIDENCE,
      reason: "The interview and the vendor's categories point different ways, so a person decides.",
    }, allowedBy: "Rules can't decide: escalate to the controller" },
    done("verdict"),
    { type: "steps_planned", steps: [step("controller", "controller", `${CO.controller} reviews`, "Controller decision")] },
    start("controller"),
    say("controller", agent("m-escalate", MAYA_QUESTION, [{ kind: "evidence", evidenceId: "e-fitness" }, { kind: "evidence", evidenceId: "e-wellness" }, { kind: "evidence", evidenceId: "e-assumed" }])),
    wait("controller", CO.controller),
  ],
};

/** What follows the controller's click. The stub serves this; a recorded replay appends it. */
export function controllerContinuation(action: ControllerAction, binding: { deliveryVersion: number; evidenceVersion: number }): Draft[] {
  const decided = (note: string): Draft => ({ type: "controller_decided", step: "controller", action, by: CO.controller, note, binding });
  switch (action) {
    case "approve": return [
      decided("Yoga counts. Studio members are gym members in all but name."),
      say("controller", maya("m-maya", "Yoga counts. Studio members are gym members in all but name.")),
      { type: "verdict", step: "controller", verdict: { kind: "agree", decidedBy: "controller", evidenceIds: AMBER_EVIDENCE, reason: `${CO.controller} ruled that yoga studios count as fitness.` }, allowedBy: POLICY.ruling },
      done("controller"),
      { type: "steps_planned", steps: [step("contract", "contract", "Data contract v2", "Yoga counts")] },
      start("contract"),
      { type: "contract_approved", step: "contract", contract: { ...CONTRACT_V1, version: 2, lines: WITH_YOGA }, allowedBy: POLICY.ruling },
      { type: "rule_updated", step: "contract", rule: { id: "rule-yoga", decidedBy: CO.controller, text: "Count yoga studios as fitness, even when the vendor files them under Wellness." } },
      done("contract"),
      ...fixFree(YOGA_DELIVERY, WITH_YOGA),
      { type: "steps_planned", steps: [step("learned", "learned", "Next time", "Same claim, no person")] },
      start("learned"),
      say("learned", buyer("m-again", CLAIM.amber)),
      { type: "rule_applied", step: "learned", ruleId: "rule-yoga", outcome: "agree", allowedBy: POLICY.savedRule },
      say("learned", agent("m-auto", `Yoga studios count: decided by the rule ${CO.controller} saved. No person needed.`)),
      done("learned"),
    ];
    case "reject": return [
      decided("Yoga wasn't agreed. Offer it as an amendment."),
      say("controller", maya("m-maya", "Yoga wasn't agreed. Offer it as an amendment.")),
      { type: "verdict", step: "controller", verdict: { kind: "disagree", decidedBy: "controller", evidenceIds: AMBER_EVIDENCE, reason: `${CO.controller} ruled that yoga studios were not in scope.` }, allowedBy: POLICY.ruling },
      done("controller"),
      ...amendWith(YOGA, YOGA_DELIVERY, `OK, add yoga studios for $${CO.yoga}.`),
    ];
    case "ask": return [
      decided("Asked Acme for their member categories."),
      say("controller", maya("m-maya", "Can you share how your own members are categorized?")),
      say("controller", buyer("m-cats", "We tag yoga, pilates and gyms all as fitness.")),
      wait("controller", CO.controller),
    ];
    case "escalate": return [
      decided("Sent up to the CFO."),
      say("controller", maya("m-maya", "Sending this up to the CFO.")),
      wait("controller", "the CFO"),
    ];
  }
}

export const LANES: LaneId[] = ["red", "green", "amber"];
export const LANE_NAME: Record<LaneId, string> = { red: "Agree · our fault", green: "Disagree · we were right", amber: "Grey area" };
export const LANE_IF: Record<LaneId, string> = { red: CLAIM.red, green: CLAIM.green, amber: CLAIM.amber };
export const VERDICT_LANE: Record<VerdictKind, LaneId> = { agree: "red", disagree: "green", grey: "amber" };

export function laneDrafts(lane: LaneId, ending: Ending): Draft[] {
  return lane === "red" ? RED : lane === "green" ? GREEN : [...AMBER_OPEN, ...AMBER_ENDINGS[ending]];
}

/** The whole run in demo order; a focused lane goes last so it can be replayed on top of the rest. */
export function timeline(focus: "all" | LaneId, ending: Ending): { events: RunEvent[]; start: number } {
  const order = focus === "all" ? LANES : [...LANES.filter((l) => l !== focus), focus];
  const events: RunEvent[] = stamp("shared", SHARED);
  for (const lane of order) events.push(...stamp(lane, laneDrafts(lane, ending), events.length));
  const start = focus === "all" ? 0 : events.length - laneDrafts(focus, ending).length;
  return { events, start };
}
