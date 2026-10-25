import { describe, expect, it } from "vitest";
import type { RunEvent, Step } from "../lib/run/contract";
import { apply, emptyView, project, type FoldContext } from "../lib/run/fold";

const context: FoldContext = {
  live: true, lane: "shared", ending: "human", learned: false,
  contract: { version: 0, buyer: "", title: "", price: 0, lines: [] },
};
const at = "2026-10-24T19:00:00Z";
const payment = { id: "synthetic-payment", amount: 1, mock: true };
const binding = { deliveryVersion: 1, evidenceVersion: 2 };
const steps = (ids: Step["kind"][]): Step[] => ids.map(id => ({ id, kind: id, title: id, detail: id }));

// Synthetic fixture preserving the old server's event ordering and missing step
// completions. It must work without rewriting history or requiring newer events.
const assessed: RunEvent[] = [
  { seq: 1, at, type: "steps_planned", steps: steps(["clarify", "paid", "produce", "review", "captured"]) },
  { seq: 17, at, type: "step_completed", step: "clarify" },
  { seq: 26, at, type: "payment_authorized", payment, allowedBy: "Synthetic confirmed funding" },
  { seq: 27, at, type: "step_completed", step: "paid" },
  { seq: 57, at, type: "step_completed", step: "produce" },
  { seq: 58, at, type: "step_started", step: "review" },
  { seq: 59, at, type: "steps_planned", steps: steps(["investigate", "verdict", "decide"]) },
  { seq: 60, at, type: "dispute_opened", step: "investigate", dispute: { id: "synthetic-case", claim: "A different city was owed", raisedBy: "buyer" } },
  { seq: 65, at, type: "step_started", step: "investigate" },
  { seq: 68, at, type: "verdict", step: "verdict", allowedBy: "Synthetic evidence assessment; no payment authority",
    verdict: { kind: "disagree", decidedBy: "model", evidenceIds: [], reason: "The accepted scope excludes that city." } },
  { seq: 70, at, type: "state_changed", step: "review", state: "delivered", paymentState: "funded", binding, reason: "The accepted scope excludes that city." },
];
const pending: RunEvent[] = [
  { seq: 92, at, type: "payment_state_changed", payment, state: "capture_pending" },
  { seq: 93, at, type: "state_changed", step: "review", state: "delivered", paymentState: "capture_pending", binding, reason: "The accepted scope excludes that city." },
  { seq: 94, at, type: "payment_state_changed", payment, state: "capture_pending" },
  { seq: 95, at, type: "state_changed", step: "review", state: "delivered", paymentState: "capture_pending", binding, reason: "The accepted scope excludes that city." },
];
const confirmed: RunEvent[] = [
  { seq: 96, at, type: "step_completed", step: "review" },
  { seq: 97, at, type: "payment_captured", paymentId: payment.id, captureTx: null, allowedBy: "Confirmed synthetic capture" },
  { seq: 98, at, type: "books_posted", step: "captured", entries: [], operationIds: ["synthetic-capture"] },
  { seq: 99, at, type: "step_completed", step: "captured" },
  { seq: 100, at, type: "payment_state_changed", payment, state: "captured" },
  { seq: 101, at, type: "state_changed", step: "review", state: "closed", paymentState: "captured", binding, reason: "The accepted scope excludes that city." },
];

describe("historical aggregate capture replay", () => {
  it("finishes a resolved assessment without interpreting its finding as payment authority", () => {
    const view = project(assessed, context);
    expect(view.nodes.investigate.status).toBe("done");
    expect(view.nodes.verdict.status).toBe("done");
    expect(view.nodes.review.status).not.toBe("done");
    expect(view.nodes.captured.status).toBe("idle");
    expect(view.captured).toEqual({});
    expect(view.coin?.done).toBe(false);
  });

  it.each(["explicit", "legacy"] as const)("shows settlement pending on reload using %s payment events", mode => {
    const events = [...assessed, ...pending.filter(event => mode === "explicit" || event.type !== "payment_state_changed")];
    const original = JSON.stringify(events);
    const view = project(events, context);
    expect(view.nodes.review.status).toBe("done");
    expect(view.nodes.investigate.status).toBe("done");
    expect(view.nodes.verdict.status).toBe("done");
    expect(["waiting", "running"]).toContain(view.nodes.captured.status);
    expect(view.orb.step).toBe("captured");
    expect(view.coin).toMatchObject({ text: "$1 capture pending", done: false, locked: true, alert: false });
    expect(view.captured).toEqual({});
    expect(view.nodes.captured.entries).toBeUndefined();
    expect(JSON.stringify(events)).toBe(original);
  });

  it("gives identical results for page-by-page polling, duplicate pages and full reload", () => {
    const view = emptyView(context.contract);
    for (const page of [assessed, pending, pending, confirmed, confirmed]) {
      for (const event of page) apply(view, event, context);
    }
    expect(view).toEqual(project([...assessed, ...pending, ...confirmed], context));
    expect(view.nodes.investigate.status).toBe("done");
    expect(view.nodes.verdict.status).toBe("done");
    expect(view.nodes.captured.status).toBe("done");
    expect(view.coin).toMatchObject({ text: "$1 captured", done: true });
    expect(view.captured).toEqual({ [payment.id]: null });
  });

  it("keeps an unanswered evidence request waiting when its grey finding arrives", () => {
    const events: RunEvent[] = [
      ...assessed.filter(event => event.seq < 68),
      { seq: 66, at, type: "step_waiting", step: "investigate", waitingOn: "Actual buyer evidence answer" },
      { seq: 68, at, type: "verdict", step: "verdict", allowedBy: "Unresolved synthetic evidence",
        verdict: { kind: "grey", decidedBy: "unresolved", evidenceIds: [], reason: "A source cell is needed." } },
      { seq: 70, at, type: "state_changed", step: "review", state: "delivered", paymentState: "funded", binding },
    ];
    const view = project(events, context);
    expect(view.nodes.investigate.status).toBe("waiting");
    expect(view.nodes.investigate.waitingOn).toBe("Actual buyer evidence answer");
    expect(view.nodes.review.status).not.toBe("done");
    expect(view.nodes.captured.status).toBe("idle");
    expect(view.coin?.done).toBe(false);
  });
});
