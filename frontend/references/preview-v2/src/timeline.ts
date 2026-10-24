// Scripted event timeline. In the real build these frames come from polling
// GET /runs/{id}/events?after=<seq>; the canvas only ever reads View.
import { S } from "./scenario";

export type NS = "idle" | "running" | "done" | "waiting" | "fail" | "grey";
export type Lane = "red" | "green" | "amber";
export type Ending = "rules_no" | "rules_yes" | "maya";
export type OrbMode = "float" | "carry" | "look" | "wait" | "happy";

export type Node = { id: string; row: number; col: number; title: string; desc: string };
export const COL_X = (c: number) => 40 + c * 240;
export const ROW_Y = [40, 220, 390, 560];
export const W = 190, H = 54;
export const laneOf = (id: string): Lane | null => (id[0] === "r" ? "red" : id[0] === "g" ? "green" : id[0] === "a" ? "amber" : null);

/** only: one lane (shown on row 1), "none" (normal path only), or undefined (all lanes stacked). */
export function nodes(ending: Ending, learned: boolean, only?: Lane | "none"): Node[] {
  const aX = learned
    ? { title: "Contract v2 decides", desc: "Yoga counts · free rerun" }
    : ending === "rules_no" ? { title: "Rules: we're right", desc: `Yoga amendment · $${S.yoga}` }
    : ending === "rules_yes" ? { title: "Rules: they're right", desc: "Unclear spec · free rerun" }
    : { title: `${S.controller} decides`, desc: "Controller review" };
  const main: Node[] = [
    { id: "s0", row: 0, col: 0, title: "Clarify the order", desc: `Interview → contract · $${S.price}` },
    { id: "s2", row: 0, col: 1, title: "Paid upfront", desc: `$${S.price} authorized via x402` },
    { id: "s3", row: 0, col: 2, title: "Produce & check", desc: "Rented data → counts" },
    { id: "s5", row: 0, col: 3, title: "Customer review", desc: "48h to accept or dispute" },
    { id: "s6", row: 0, col: 4, title: "Captured", desc: "Payment taken · books posted" },
  ];
  const lanes: Record<Lane, Omit<Node, "row">[]> = {
    red: [
      { id: "rI", col: 0, title: "Investigate", desc: "“ZIP 94110 is missing”" },
      { id: "rV", col: 1, title: "They're right", desc: "Our check missed 94110" },
    ],
    green: [
      { id: "gI", col: 0, title: "Investigate", desc: "“Add Oakland”" },
      { id: "gV", col: 1, title: "We're right", desc: "Contract: SF city only" },
      { id: "gA", col: 2, title: "Amendment", desc: `+ Oakland · $${S.oakland}` },
    ],
    amber: [
      { id: "aI", col: 0, title: "Investigate", desc: "“Yoga should count”" },
      { id: "aG", col: 1, title: learned ? "Covered" : "Grey area", desc: learned ? "Contract v2 says yoga counts" : "Nothing says yes or no" },
      { id: "aX", col: 2, ...aX },
    ],
  };
  if (only === "none") return main;
  if (only) return [...main, ...lanes[only].map((n) => ({ ...n, row: 1 }))];
  return [...main, ...lanes.red.map((n) => ({ ...n, row: 1 })), ...lanes.green.map((n) => ({ ...n, row: 2 })), ...lanes.amber.map((n) => ({ ...n, row: 3 }))];
}

export type Card = { id: string; node: string; text: string; tone?: "ev" | "rule" | "claim" };
export type View = {
  status: Record<string, NS>;
  chip: Record<string, string>;
  orb: { node: string; mode: OrbMode };
  coin: { text: string; locked?: boolean; done?: boolean } | null;
  loops: string[]; // lane node ids whose work was carried back to Produce
  cards: Card[];
  contract: 1 | 2;
  caption: string;
};
type Frame = { patch: (v: View) => View; hold: number; wait?: "maya"; panel?: string | null };

const base = (): View => ({ status: {}, chip: {}, orb: { node: "s0", mode: "float" }, coin: null, loops: [], cards: [], contract: 1, caption: "" });
const set = (v: View, s: Record<string, NS>, chip: Record<string, string> = {}): View => ({ ...v, status: { ...v.status, ...s }, chip: { ...v.chip, ...chip } });

const authorized = { text: `$${S.price} authorized` };

export function sharedFrames(): Frame[] {
  return [
    { hold: 9500, panel: "s0", patch: (v) => ({ ...set(v, { s0: "running" }), orb: { node: "s0", mode: "look" }, caption: "Our agent interviews Acme's buying agent. Each answer becomes a line in the contract." }) },
    { hold: 2200, panel: null, patch: (v) => ({ ...set(v, { s0: "done", s2: "done" }, { s0: "Contract v1 approved" }), orb: { node: "s2", mode: "float" }, coin: authorized, caption: `Acme approves the contract and authorizes $${S.price}. We only take it once the data is accepted.` }) },
    { hold: 6000, panel: "s3", patch: (v) => ({ ...set(v, { s3: "running" }), orb: { node: "s3", mode: "carry" }, caption: "We build the counts from rented vendor data and check every contract line." }) },
    { hold: 2200, panel: null, patch: (v) => ({ ...set(v, { s3: "done", s5: "running" }, { s3: "5 of 5 passed", s5: "48h window" }), orb: { node: "s5", mode: "float" }, caption: "Delivered. One ZIP was held back for privacy. Acme has 48 hours to accept or dispute." }) },
    { hold: 0, panel: "s6", patch: (v) => ({ ...set(v, { s5: "done", s6: "done" }, { s5: "Accepted" }), orb: { node: "s6", mode: "happy" }, coin: { text: `$${S.price} captured · mock`, done: true }, caption: "Accepted. Payment captured and the books are posted." }) },
  ];
}

const dispute = (claim: string): Frame => ({
  hold: 1800, panel: null,
  patch: (v) => ({ ...set(v, { s5: "waiting" }, { s5: "Disputed" }), orb: { node: "s5", mode: "float" }, coin: { ...authorized, locked: true }, caption: `Acme disputes: ${claim}. The payment is on hold until it's resolved.` }),
});
const backToProduce = (from: string, chip: string, caption: string): Frame => ({
  hold: 2800, panel: null,
  patch: (v) => ({ ...set(v, { s3: "running", s5: "idle" }, { s3: chip }), loops: [from], orb: { node: "s3", mode: "carry" }, caption }),
});
const recheck = (chip: string, caption: string, card?: Card): Frame => ({
  hold: 2600,
  patch: (v) => ({ ...set(v, { s3: "done", s5: "running" }, { s3: chip, s5: "New 48h window" }), orb: { node: "s5", mode: "float" }, cards: card ? [...v.cards, card] : v.cards, caption }),
});
const capture = (amount: number, caption: string): Frame => ({
  hold: 0, panel: "s6",
  patch: (v) => ({ ...set(v, { s5: "done", s6: "done" }, { s5: "Accepted" }), orb: { node: "s6", mode: "happy" }, coin: { text: `$${amount} captured · mock`, done: true }, caption }),
});

export function laneFrames(lane: Lane, ending: Ending, learned: boolean): Frame[] {
  if (lane === "red") return [
    dispute("“ZIP 94110 is missing”"),
    { hold: 7000, panel: "rI", patch: (v) => ({ ...set(v, { rI: "running" }, { rI: "Checking" }), orb: { node: "rI", mode: "look" }, cards: [{ id: "c1", node: "rI", text: "Contract line 5 · every SF ZIP", tone: "ev" }, { id: "c2", node: "rI", text: "Delivered sheet · no 94110 row", tone: "ev" }], caption: "The agent checks the contract against the delivered sheet." }) },
    { hold: 2000, panel: null, patch: (v) => ({ ...set(v, { rI: "done", rV: "fail" }, { rI: "2 sources", rV: "Our miss" }), orb: { node: "rV", mode: "float" }, caption: "They're right. Our check used the vendor's ZIP list, which didn't have 94110." }) },
    backToProduce("rV", `Rerun · our cost $${S.rerunCost}`, `The orb carries the job back to Produce. The rerun is on us: $${S.rerunCost}.`),
    recheck("Rechecked", "94110 added and rechecked against the official SF ZIP list. That check is now permanent.", { id: "c3", node: "s3", text: "Rule updated · use the official SF ZIP list", tone: "rule" }),
    capture(S.price, `Accepted. $${S.price} captured; the $${S.rerunCost} rerun is booked as our cost.`),
  ];
  if (lane === "green") return [
    dispute("“Counts look low, add Oakland”"),
    { hold: 7000, panel: "gI", patch: (v) => ({ ...set(v, { gI: "running" }, { gI: "Checking" }), orb: { node: "gI", mode: "look" }, cards: [{ id: "c1", node: "gI", text: "Interview · “SF city only.”", tone: "ev" }, { id: "c2", node: "gI", text: "Contract line 2 · SF ZIPs only", tone: "ev" }], caption: "The agent pulls what Acme agreed to in the interview." }) },
    { hold: 2000, panel: null, patch: (v) => ({ ...set(v, { gI: "done", gV: "done" }, { gI: "2 sources", gV: "We're right" }), orb: { node: "gV", mode: "float" }, caption: "We're right: we delivered what was agreed. No charge for asking." }) },
    { hold: 5500, panel: "gA", patch: (v) => ({ ...set(v, { gA: "done" }, { gA: `+$${S.oakland} signed` }), orb: { node: "gA", mode: "float" }, coin: { text: `$${S.price} + $${S.oakland} authorized`, locked: true }, caption: `Acme still wants Oakland, so it becomes an amendment: $${S.oakland}, approved and signed by Acme.` }) },
    backToProduce("gA", "Adding Oakland", "Back to Produce with the amended contract."),
    recheck("Checks passed", "Oakland rows added and checked. New review window."),
    capture(S.price + S.oakland, `Accepted. $${S.price + S.oakland} captured in total.`),
  ];
  // amber
  const yes = learned || ending === "rules_yes";
  const f: Frame[] = [
    dispute("“Yoga studio members should count”"),
    { hold: 7000, panel: "aI", patch: (v) => ({ ...set(v, { aI: "running" }, { aI: "Checking" }), orb: { node: "aI", mode: "look" }, cards: learned
        ? [{ id: "c1", node: "aI", text: "Contract v2 · yoga counts as fitness", tone: "rule" }]
        : [{ id: "c1", node: "aI", text: "Interview · “gym members or fitness-app users”", tone: "ev" }, { id: "c2", node: "aI", text: "Vendor · yoga filed under “Wellness”", tone: "ev" }, { id: "c3", node: "aI", text: "Acme · “yoga is fitness”", tone: "claim" }],
      caption: learned ? "Same complaint as before. This time the contract already answers it." : "The agent gathers evidence. The interview never mentioned yoga." }) },
    { hold: 2000, panel: null, patch: (v) => ({ ...set(v, { aI: "done", aG: learned ? "done" : "grey" }, { aI: learned ? "1 source" : "3 sources", aG: learned ? "Covered" : "Grey area" }), orb: { node: "aG", mode: "float" }, caption: learned ? "Covered by contract v2. No person needed." : "Grey area: no contract line or rule says yes or no." }) },
  ];
  if (ending === "maya" && !learned) {
    f.push({ hold: 0, wait: "maya", panel: "aX", patch: (v) => ({ ...set(v, { aX: "waiting" }, { aX: `Waiting on ${S.controller}` }), orb: { node: "aX", mode: "wait" }, caption: `The rules can't decide, so it goes to ${S.controller}, our controller, with the evidence.` }) });
    f.push({ hold: 4200, panel: "aX", patch: (v) => ({ ...set(v, { aX: "done" }, { aX: "Rule learned" }), orb: { node: "aX", mode: "float" }, contract: 2, cards: [...v.cards, { id: "c4", node: "aX", text: "Learned · yoga counts as fitness (contract v2)", tone: "rule" }], caption: `${S.controller}: yoga counts. Saved as contract v2, so next time no person is needed.` }) });
  } else {
    f.push({ hold: 2000, panel: null, patch: (v) => ({ ...set(v, { aX: yes ? "fail" : "done" }, { aX: yes ? "They're right" : "We're right" }), orb: { node: "aX", mode: "float" }, caption: learned ? "Contract v2 decides: yoga counts. Free rerun." : yes ? "Our rule: an unclear spec is on us. So they're right, and the rerun is free." : "Our rule: the vendor's category decides. So we're right, and yoga is extra." }) });
    if (!yes) f.push({ hold: 4500, panel: "aX", patch: (v) => ({ ...set(v, {}, { aX: `+$${S.yoga} signed` }), coin: { text: `$${S.price} + $${S.yoga} authorized`, locked: true }, caption: `Acme accepts a yoga amendment at $${S.yoga}.` }) });
  }
  const paid = ending === "rules_no" && !learned ? S.price + S.yoga : S.price;
  f.push(
    backToProduce("aX", yes || ending === "maya" ? `Rerun · our cost $${S.rerunCost}` : "Adding yoga", "Back to Produce to add yoga studio members."),
    recheck("Checks passed", "Yoga members added and checked. New review window."),
    capture(paid, `Accepted. $${paid} captured.`),
  );
  return f;
}

/** Normal path done up to review; Acme is about to dispute instead of accepting. */
export function laneBase(): View {
  return {
    ...base(),
    status: { s0: "done", s2: "done", s3: "done", s5: "running" },
    chip: { s0: "Contract v1 approved", s3: "5 of 5 passed", s5: "48h window" },
    orb: { node: "s5", mode: "float" }, coin: { text: `$${S.price} authorized` }, caption: "",
  };
}
export const emptyView = base;
export type { Frame };
