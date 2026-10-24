import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { translate } from "../lib/run/broker/translate";
import type { BrokerEvent, BrokerOrder, BrokerSnapshot } from "../lib/run/broker/types";
import { CONTRACT_V1, S, type Case } from "../lib/run/scenario";
import { project } from "../lib/run/fold";

// Recorded from Jeff's backend on Oct 24 2026 by driving our order through /api/broker.
const load = <T,>(name: string): T => JSON.parse(readFileSync(join(process.cwd(), "tests", "fixtures", "broker", `${name}.json`), "utf8")) as T;
const snapshot = (c: Case, upTo = Infinity): BrokerSnapshot => {
  const events = load<BrokerEvent[]>(`${c}-events`).filter((e) => e.sequence <= upTo), order = load<BrokerOrder>(`${c}-order`);
  const { checksBySeq, rowsByVersion } = load<Pick<BrokerSnapshot, "checksBySeq" | "rowsByVersion">>(`${c}-snapshots`);
  return { events, order, checksBySeq, rowsByVersion };
};
const view = (c: Case) => project(translate(snapshot(c), c), { lane: c, ending: "human", learned: false, contract: CONTRACT_V1 });

describe("broker stream → canvas", () => {
  it("walks the no-dispute order from interview to a mock capture", () => {
    const v = view("shared");
    expect(v.nodes.clarify.messages[0].text).toMatch(/SF adults 25-34/);
    // in the order the interview settled them; freshness was answered last in this recording
    expect(v.contract.lines.map((l) => l.id)).toEqual(["geography", "reference_period", "metric", "entity_unit", "coverage", "source_lineage", "output_schema", "freshness"]);
    expect(v.contract.lines.find((l) => l.id === "geography")?.text).toBe("San Francisco only, 10 ZIPs, boundary 2026-Q3");
    expect(v.payments[0]).toMatchObject({ amount: S.price, rail: "mock", mock: true });
    expect(v.nodes.produce.chip).toBe("8 of 8 passed");
    expect(v.deliveries.at(-1)?.rows.map((r) => r.zip)).toContain("94110");
    expect(v.deliveries.at(-1)?.rows.find((r) => r.zip === "94129")?.count).toBe(42);
    expect(v.reviewWindow).toBe("10 minutes");
    expect(v.nodes.review.step.detail).toBe("10-minute review window");
    expect(v.nodes.captured.status).toBe("done");
    expect(v.coin).toEqual({ text: `$${S.price} captured · mock`, done: true });
    expect(v.nodes.captured.entries?.[0]).toMatchObject({ amount: S.price });
  });

  it("asks each contract line as a question until Acme's answer settles its wording", () => {
    const events = translate(snapshot("green"), "green");
    const asked = events.flatMap((e) => (e.type === "contract_line_asked" ? [e.line.text] : []));
    expect(asked.length).toBeGreaterThan(0);
    expect(asked.some((t) => /undefined|NaN/.test(t))).toBe(false);
    expect(asked).toContain("Which area, boundary and ZIPs");
    // the approved contract lists its lines in the order the interview settled them
    const drafted = events.flatMap((e) => (e.type === "contract_line_drafted" ? [e.line.id] : []));
    const approved = events.flatMap((e) => (e.type === "contract_approved" ? [e.contract.lines.map((l) => l.id)] : []))[0];
    expect(approved).toEqual(drafted);
    expect(events.some((e) => e.type === "contract_line_drafted" && /adults 25-34 interested in fitness/.test(e.line.text))).toBe(true);
    // the intent, then each question with its answer, in turn
    const turns = events.flatMap((e) => (e.type === "message" && e.step === "clarify" ? [e.message.from] : []));
    expect(turns.slice(0, 5)).toEqual(["buyer", "agent", "buyer", "agent", "buyer"]);
  });

  it("maps a refuted dispute onto the We're-right detour and back to capture", () => {
    const v = view("green");
    expect(v.dispute?.claim).toMatch(/Oakland/);
    expect(v.nodes.investigate.messages[0].from).toBe("buyer");
    expect(v.nodes.verdict.verdict).toMatchObject({ kind: "disagree", decidedBy: "rules", evidenceIds: ["cite-geography", "cite-coverage"] });
    expect(v.nodes.investigate.evidence.map((e) => e.label)).toEqual(["Contract: San Francisco only", expect.stringMatching(/^\d+ of \d+ ZIPs delivered$/)]);
    expect(v.nodes.investigate.messages.at(-1)).toMatchObject({ from: "agent", attach: [{ kind: "evidence", evidenceId: "cite-geography" }, { kind: "evidence", evidenceId: "cite-coverage" }] });
    expect(v.nodes.verdict.chip).toBe("We're right");
    // what the agent read at the source, ticked once the re-verification landed, and the thought it had at the verdict
    expect(v.nodes.investigate.source?.map((l) => l.checked)).toEqual([true, true, true]);
    expect(v.nodes.investigate.source?.[0].text).toMatch(/^Vendor panel v1, pinned/);
    expect(v.aside).toEqual({ step: "verdict", text: "Settled by the contract and the source. No human needed." });
    expect(v.nodes.review.attempt).toBe(2);
    expect(v.nodes.captured.status).toBe("done");
  });

  // Jeff's dispute.assessed (PR #12, flag off by default), spliced into the recorded refuted dispute after case.opened
  const assessed = (payload: Record<string, unknown>) => {
    const s = snapshot("green");
    const opened = s.events.findIndex((e) => e.type === "case.opened");
    const event: BrokerEvent = { ...s.events[opened], id: "event_assessed", type: "dispute.assessed", payload };
    const events = translate({ ...s, events: [...s.events.slice(0, opened + 1), event, ...s.events.slice(opened + 1)] }, "green");
    return { events, v: project(events, { lane: "green", ending: "human", learned: false, contract: CONTRACT_V1 }) };
  };

  it("shows a model-decided dispute as decided by model, verified by code, with its quoted references as evidence", () => {
    const { v } = assessed({ kind: "not_justified", reason: "The contract names San Francisco only; Oakland was never in scope.", decided_by: "model", evidence_ids: [], references: [{ artifact_id: "spec-v1", version: 1, locator: "/requirements/geography", value: "San Francisco only, 10 ZIPs, boundary 2026-Q3" }] });
    expect(v.nodes.verdict.step.detail).toBe("Decided by model, verified by code");
    expect(v.nodes.verdict.verdict?.reason).toMatch(/^Decided by the model, verified by code: The contract names San Francisco only/);
    expect(v.nodes.verdict.verdict?.evidenceIds).toContain("assessed-43-0");
    expect(v.nodes.investigate.evidence.some((e) => e.kind === "claim" && "quote" in e && /San Francisco only, 10 ZIPs/.test(e.quote))).toBe(true);
    expect(v.nodes.investigate.messages.some((m) => m.from === "agent" && /The model read the objection/.test(m.text))).toBe(true);
    expect(v.nodes.verdict.chip).toBe("We're right");
  });

  it("never reads as model-decided on a fallback: an unresolved assessment opens the grey area", () => {
    const { events, v } = assessed({ kind: "unclear", reason: "The complaint may mean a cohort the contract does not define.", decided_by: "unresolved", evidence_ids: [], references: [] });
    expect(v.order).toContain("grey");
    expect(v.nodes.verdict?.step.detail ?? "").not.toMatch(/model/);
    const words = events.flatMap((e) => (e.type === "caption" ? [e.text] : e.type === "message" ? [e.message.text] : []));
    expect(words.some((t) => /decided by the model/i.test(t))).toBe(false);
  });

  it("maps an unknown verdict onto questions, a grey area, the controller's resume and a free correction", () => {
    const v = view("amber");
    expect(v.nodes.produce.checks.freshness).toBeDefined();
    expect(v.nodes.investigate.messages.filter((m) => m.from === "agent").length).toBeGreaterThanOrEqual(2); // two bounded questions
    expect(v.nodes.grey.verdict?.kind).toBe("grey");
    expect(v.nodes.decide.decision).toMatchObject({ action: "approve", by: S.controller });
    expect(v.nodes.decide.chip).toBe("Resumed · corrected");
    expect(v.contract.version).toBe(2);
    expect(v.nodes.produce.attempt).toBe(2);
    expect(v.loops).toEqual(["decide"]);
    expect(v.nodes.captured.status).toBe("done");
    expect(v.coin).toMatchObject({ done: true });
  });

  it("maps a failed check onto Our miss, a clarification and the free correction", () => {
    const v = view("red");
    expect(v.nodes.produce.checks.coverage).toBeDefined();
    expect(v.nodes.verdict.verdict).toMatchObject({ kind: "agree", decidedBy: "rules" });
    expect(v.nodes.verdict.chip).toBe("Our miss");
    expect(v.nodes.investigate.evidence[0].label).toMatch(/Failed · coverage/);
    expect(v.deliveries[0].rows.some((r) => r.zip === "94110")).toBe(false); // the first delivery lacked the Mission ZIP
    expect(v.deliveries.at(-1)?.rows.some((r) => r.zip === "94110")).toBe(true);
    expect(v.contract.version).toBe(2);
    expect(v.nodes.produce.attempt).toBe(2);
    expect(v.loops).toEqual(["verdict"]);
    expect(v.nodes.captured.status).toBe("done");
    expect(v.caption).toMatch(/captured/);
  });

  it("is append-only as the stream grows, so a seq cursor stays valid", () => {
    const whole = translate(snapshot("amber"), "amber");
    const half = translate(snapshot("amber", 45), "amber");
    expect(whole.slice(0, half.length).map((e) => [e.seq, e.type, "step" in e ? e.step : ""])).toEqual(half.map((e) => [e.seq, e.type, "step" in e ? e.step : ""]));
  });
});
