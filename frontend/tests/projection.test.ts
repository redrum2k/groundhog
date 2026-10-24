import { describe, expect, it } from "vitest";
import {
  acceptableJobs,
  can,
  courierEvent,
  historical,
  jobTone,
  mergeEvents,
  mergeSnapshot,
  nextInTraversal,
  originalProgress,
  recoverableJobs,
  unresolvedIds,
} from "../lib/projection";
import { actor, event, job, order, provider } from "./fixtures";

describe("authoritative projections", () => {
  it("preserves disputed failures and never colors pending work green", () => {
    expect(jobTone(job({ dispute: "OPEN", processing: "FAILED" }))).toBe(
      "orange",
    );
    expect(jobTone(job())).toBe("red");
    expect(jobTone(job({ processing: "QUEUED" }))).toBe("blue");
    expect(jobTone(job({ processing: "VALIDATED", dispute: "RESOLVED" }))).toBe(
      "green",
    );
  });
  it("keeps the original denominator and separates validated from accepted", () => {
    const snapshot = order({
      jobs: [
        job({ processing: "VALIDATED" }),
        job({ id: "child", kind: "CORRECTION", processing: "VALIDATED" }),
        job({ id: "extra", kind: "CHANGE_ORDER", processing: "VALIDATED" }),
      ],
    });
    expect(originalProgress(snapshot)).toMatchObject({
      total: 100,
      accepted: 0,
      validated: 1,
    });
    expect(acceptableJobs(snapshot).map((j) => j.id)).toEqual(["job-1"]);
  });
  it("does not reprocess valid, exhausted or permanent failures", () => {
    const snapshot = order({
      jobs: [
        job(),
        job({ id: "valid", processing: "VALIDATED" }),
        job({ id: "permanent", recoverable: false }),
        job({
          id: "exhausted",
          attempts: [
            {
              id: "a",
              operation_id: "op",
              number: 1,
              status: "FAILED",
              input_artifact_id: "artifact",
            },
          ],
        }),
      ],
    });
    expect(recoverableJobs(snapshot).map((j) => j.id)).toEqual(["job-1"]);
  });
  it("never accepts disputed or already accepted artifacts", () => {
    expect(
      acceptableJobs(
        order({
          jobs: [
            job({ processing: "VALIDATED", dispute: "OPEN" }),
            job({
              processing: "VALIDATED",
              accepted_artifact_id: "artifact-1",
            }),
          ],
        }),
      ),
    ).toEqual([]);
  });
  it("ignores late snapshots and de-duplicates scoped event IDs", () => {
    const current = order();
    expect(mergeSnapshot(current, order({ revision: 2 }))).toBe(current);
    expect(mergeSnapshot(current, order({ revision: 4 })).revision).toBe(4);
    expect(
      mergeEvents(
        [event()],
        [
          event(),
          event({ id: "other", order_id: "other" }),
          event({ id: "event-2", sequence: 2 }),
        ],
        "order-1",
      ).map((e) => e.id),
    ).toEqual(["event-1", "event-2"]);
  });
  it("walks a fixed set once, including waiting states, then stops", () => {
    const snapshot = order({
      jobs: [job({ dispute: "WAITING_CUSTOMER" }), job({ id: "job-2" })],
    });
    const ids = unresolvedIds(snapshot);
    expect(nextInTraversal(ids, [], snapshot)).toBe("job-1");
    expect(nextInTraversal(ids, ["job-1"], snapshot)).toBe("job-2");
    expect(nextInTraversal(ids, ids, snapshot)).toBeUndefined();
  });
  it("only recorded correction/validation events drive the courier", () => {
    expect(courierEvent(event())).toBe(true);
    expect(courierEvent(event({ type: "payment.confirmed" }))).toBe(false);
    expect(
      courierEvent(event({ type: "check.passed", attempt_id: null })),
    ).toBe(false);
  });
  it("keeps role affordances separate", () => {
    expect(can(provider, "correct")).toBe(true);
    expect(can(actor, "correct")).toBe(false);
    expect(can(actor, "accept_delivery")).toBe(true);
    expect(can(provider, "execute_action")).toBe(false);
  });
  it("marks expired and superseded agreement proposals historical", () => {
    const proposal = {
      id: "action",
      kind: "CONCESSION" as const,
      basis: "Evidence",
      revision: 3,
      agreement_version: 1,
      evidence_digest: "digest",
      scope_digest: "scope",
      expires_at: "2026-10-24T00:00:00Z",
      owner: "controller",
    };
    expect(historical(proposal, order(), Date.parse("2026-10-25"))).toBe(true);
    expect(
      historical(
        { ...proposal, agreement_version: 2 },
        order(),
        Date.parse("2026-10-23"),
      ),
    ).toBe(true);
  });
});
