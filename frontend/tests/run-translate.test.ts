import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { translate } from "../lib/run/broker/translate";
import type { BrokerEvent, BrokerOrder, DataRow } from "../lib/run/broker/types";
import { CONTRACT_V1, S, type Case } from "../lib/run/scenario";
import { project } from "../lib/run/fold";

// Recorded from Jeff's backend on Oct 24 2026 by driving our order through /api/broker.
const load = <T,>(name: string): T => JSON.parse(readFileSync(join(process.cwd(), "tests", "fixtures", "broker", `${name}.json`), "utf8")) as T;
const rows = load<{ rows: DataRow[] }>("shared-rows").rows;
const view = (c: Case) => {
  const events = load<BrokerEvent[]>(`${c}-events`), order = load<BrokerOrder>(`${c}-order`);
  return project(translate({ events, order, rows }, c), { lane: c, ending: "maya", learned: false, contract: CONTRACT_V1 });
};

describe("broker stream → canvas", () => {
  it("walks the no-dispute order from interview to a mock capture", () => {
    const v = view("shared");
    expect(v.nodes.clarify.messages[0].text).toMatch(/SF adults 25-34/);
    expect(v.contract.lines.map((l) => l.id)).toEqual(["freshness", "geography", "reference_period", "metric", "entity_unit", "coverage", "source_lineage", "output_schema"]);
    expect(v.contract.lines[1].text).toBe("San Francisco only, 10 ZIPs, boundary 2026-Q3");
    expect(v.payments[0]).toMatchObject({ amount: S.price, rail: "mock", mock: true });
    expect(v.nodes.produce.chip).toBe("8 of 8 passed");
    expect(v.deliveries.at(-1)?.rows.map((r) => r.zip)).toContain("94110");
    expect(v.reviewWindow).toBe("10 minutes");
    expect(v.nodes.review.step.detail).toBe("10-minute window to accept or dispute");
    expect(v.nodes.captured.status).toBe("done");
    expect(v.coin).toEqual({ text: `$${S.price} captured · mock`, done: true });
    expect(v.nodes.captured.entries?.[0]).toMatchObject({ amount: S.price });
  });

  it("maps a refuted dispute onto the We're-right detour and back to capture", () => {
    const v = view("green");
    expect(v.dispute?.claim).toMatch(/Oakland/);
    expect(v.nodes.investigate.messages[0].from).toBe("buyer");
    expect(v.nodes.verdict.verdict).toMatchObject({ kind: "disagree", decidedBy: "rules" });
    expect(v.nodes.verdict.chip).toBe("We're right");
    expect(v.nodes.review.attempt).toBe(2);
    expect(v.nodes.captured.status).toBe("done");
  });

  it("maps an unknown verdict onto questions, a grey area and the controller's hold", () => {
    const v = view("amber");
    expect(v.nodes.produce.checks.freshness.passed).toBe(false);
    expect(v.nodes.investigate.messages.filter((m) => m.from === "agent").length).toBeGreaterThanOrEqual(2); // two bounded questions
    expect(v.nodes.grey.verdict?.kind).toBe("grey");
    expect(v.nodes.decide.decision).toMatchObject({ action: "approve", by: S.controller });
    expect(v.coin).toMatchObject({ text: `$${S.price} authorized` });
    expect(v.nodes.captured.status).toBe("idle");
  });

  it("is append-only as the stream grows, so a seq cursor stays valid", () => {
    const events = load<BrokerEvent[]>("green-events"), order = load<BrokerOrder>("green-order");
    const whole = translate({ events, order, rows }, "green");
    const half = translate({ events: events.slice(0, 30), order, rows }, "green");
    expect(whole.slice(0, half.length).map((e) => [e.seq, e.type, "step" in e ? e.step : ""])).toEqual(half.map((e) => [e.seq, e.type, "step" in e ? e.step : ""]));
  });
});
