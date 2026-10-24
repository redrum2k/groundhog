import { describe, expect, it } from "vitest";
import { bindingFor, coinFor, locate, nodeKey, project } from "../lib/run/fold";
import { CO, controllerContinuation, ENDINGS, LANES, stamp, timeline } from "../lib/run/scenario";
import { createRun, decide, eventsAfter } from "../lib/run/stub-store";

describe("scenario integrity", () => {
  for (const [ending] of ENDINGS) {
    it(`every event lands on a planned step (${ending})`, () => {
      const { events } = timeline("all", ending);
      const planned = new Set<string>();
      for (const e of events) {
        if (e.type === "steps_planned") { for (const s of e.steps) planned.add(nodeKey(e.track, s.id)); continue; }
        if ("step" in e) expect(planned.has(nodeKey(e.track, e.step)), `${e.type} on ${e.track}/${e.step}`).toBe(true);
      }
      expect(events.map((e) => e.seq)).toEqual(events.map((_, i) => i + 1));
    });
  }

  it("every citation points at a message or cell that exists", () => {
    const run = project([...timeline("all", "controller").events, ...stamp("amber", controllerContinuation("approve", { deliveryVersion: 1, evidenceVersion: 3 }), 10_000)]);
    for (const e of Object.values(run.evidence)) {
      const src = e.source;
      if (src.kind === "none") continue;
      const node = run.nodes[locate(run, src)!.key];
      if (src.kind === "message") expect(node.messages.some((m) => m.id === src.messageId), e.id).toBe(true);
      else expect(node.delivery?.version, e.id).toBe(src.version);
    }
  });

  it("the shared path ends captured and each lane ends in its books", () => {
    const run = project(timeline("all", "agree").events);
    expect(coinFor(run, "shared")).toMatchObject({ amount: CO.price, state: "captured", mock: true });
    for (const lane of LANES) {
      expect(run.nodes[nodeKey(lane, "books")].status).toBe("done");
      expect(run.nodes[nodeKey(lane, "books")].margin).toBeDefined();
      expect(coinFor(run, lane)?.state).toBe("captured");
    }
    expect(coinFor(run, "green")?.amount).toBe(CO.price + CO.oakland);
  });

  it("the shared check fixes the privacy line and the delivery withholds the ZIP", () => {
    const run = project(timeline("all", "agree").events);
    expect(run.nodes["shared/check"].checks.privacy).toMatchObject({ passed: true, fix: expect.stringContaining("94129") });
    const row = run.nodes["shared/deliver"].delivery?.rows.find((r) => r.zip === "94129");
    expect(row?.count).toBeNull();
  });

  it("a controller approval leads to contract v2 and a rule-decided rerun", () => {
    const { events } = timeline("amber", "controller");
    const run = project(events);
    expect(run.nodes["amber/controller"].status).toBe("waiting");
    const after = project([...events, ...stamp("amber", controllerContinuation("approve", bindingFor(run, "amber")), events.length)]);
    expect(after.tracks.amber.contract?.version).toBe(2);
    expect(after.nodes["amber/learned"].ruleApplied).toEqual({ ruleId: "rule-yoga", outcome: "agree" });
    expect(after.nodes["amber/learned"].status).toBe("done");
  });
});

describe("stub run", () => {
  it("releases events on a clock and holds for the controller", () => {
    const run = createRun("controller");
    expect(eventsAfter(run.id, 0)?.length).toBe(1);
    expect(eventsAfter("nope", 0)).toBeNull();
    expect(decide(run.id, "approve", { deliveryVersion: 1, evidenceVersion: 3 })).toMatchObject({ ok: false, status: 409 });
  });

  it("refuses a decision bound to stale evidence", () => {
    const run = createRun("controller");
    const releaseAll = Date.now() + 120_000;
    const spy = Date.now;
    Date.now = () => releaseAll;
    try {
      expect(decide(run.id, "approve", { deliveryVersion: 1, evidenceVersion: 2 })).toMatchObject({ ok: false, status: 409 });
      expect(decide(run.id, "approve", { deliveryVersion: 1, evidenceVersion: 3 })).toEqual({ ok: true });
      expect(eventsAfter(run.id, 0)?.some((e) => e.type === "controller_decided")).toBe(true);
    } finally {
      Date.now = spy;
    }
  });
});
