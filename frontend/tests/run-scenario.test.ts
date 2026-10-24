import { describe, expect, it } from "vitest";
import type { DataContract } from "../lib/run/contract";
import { bindingFor, project, type FoldContext } from "../lib/run/fold";
import { CONTRACT_V1, controllerContinuation, ENDINGS, LANES, S, stamp, timeline, type Case, type Ending } from "../lib/run/scenario";

const ctx = (lane: Case, ending: Ending = "human", learned = false): FoldContext => ({ lane, ending, learned, contract: CONTRACT_V1 as DataContract });
const CASES: Case[] = ["shared", ...LANES];

/** The whole recorded run, with Human's approval appended when the ending waits on them. */
function full(c: Case, ending: Ending, learned = false) {
  const { events } = timeline(c, ending, learned);
  if (c !== "amber" || ending !== "human" || learned) return events;
  const v = project(events, ctx(c, ending, learned));
  return [...events, ...stamp("amber", controllerContinuation("approve", bindingFor(v)), events.length)];
}

describe("scenario integrity", () => {
  for (const c of CASES) for (const [ending] of ENDINGS) {
    it(`every event lands on a planned step (${c}, ${ending})`, () => {
      const events = full(c, ending);
      const planned = new Set<string>();
      for (const e of events) {
        if (e.type === "steps_planned") { for (const s of e.steps) planned.add(s.id); continue; }
        if ("step" in e) expect(planned.has(e.step), `${e.type} on ${e.step}`).toBe(true);
      }
      expect(events.map((e) => e.seq)).toEqual(events.map((_, i) => i + 1));
    });
  }

  it("every citation points at a message or a sheet row that is on screen", () => {
    for (const c of LANES) {
      const v = project(full(c, "human"), ctx(c));
      const messages = new Set(Object.values(v.nodes).flatMap((n) => n.messages.map((m) => m.id)));
      for (const e of Object.values(v.evidence)) {
        const src = e.source;
        if (src.kind === "message") expect(messages.has(src.messageId), `${c}: ${e.id}`).toBe(true);
        if (src.kind === "cell") expect(v.deliveries.some((d) => d.version === src.version), `${c}: ${e.id}`).toBe(true);
      }
    }
  });

  it("every case ends captured with books and a margin", () => {
    const expected: Record<Case, number> = { shared: S.price, red: S.price, green: S.price + S.oakland, amber: S.price };
    for (const c of CASES) {
      const v = project(full(c, "human"), ctx(c));
      expect(v.nodes.captured.status, c).toBe("done");
      expect(v.nodes.captured.margin?.revenue, c).toBe(expected[c]);
      expect(v.coin, c).toMatchObject({ done: true, text: `$${expected[c]} captured · mock` });
    }
    expect(project(full("amber", "rules_no"), ctx("amber", "rules_no")).coin?.text).toBe(`$${S.price + S.yoga} captured · mock`);
  });

  it("a dispute re-enters Produce as attempt 2 and draws the return loop", () => {
    const v = project(full("red", "human"), ctx("red"));
    expect(v.nodes.produce.attempt).toBe(2);
    expect(v.loops).toEqual(["verdict"]);
    expect(v.nodes.verdict.status).toBe("fail");
    expect(v.nodes.verdict.chip).toBe("Our miss");
    expect(v.cards.some((c) => c.tone === "rule" && c.node === "produce")).toBe(true);
  });

  it("the shared check fixes the privacy line and the delivery withholds the ZIP", () => {
    const v = project(full("shared", "human"), ctx("shared"));
    expect(v.nodes.produce.checks.privacy).toMatchObject({ passed: true, fix: expect.stringContaining("94129") });
    expect(v.deliveries.at(-1)?.rows.find((r) => r.zip === "94129")?.flag).toBe("withheld");
    expect(v.nodes.produce.chip).toBe("5 of 5 passed");
  });

  it("the grey area waits on the controller, then learns contract v2", () => {
    const { events } = timeline("amber", "human");
    const v = project(events, ctx("amber"));
    expect(v.nodes.decide.status).toBe("waiting");
    expect(v.orb).toEqual({ step: "decide", mode: "wait" });
    const after = project(full("amber", "human"), ctx("amber"));
    expect(after.contract.version).toBe(2);
    expect(after.nodes.decide.chip).toBe("Rule learned");
    const learned = project(full("amber", "human", true), ctx("amber", "human", true));
    expect(learned.nodes.grey.chip).toBe("Covered");
    expect(learned.nodes.captured.status).toBe("done");
  });
});
