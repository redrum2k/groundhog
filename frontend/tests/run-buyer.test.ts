import { describe, expect, it } from "vitest";
import { buyerMove, type Run } from "../lib/run/broker/driver";

// The presenter's moves as Acme, against the gates the driver opens.

const run = (awaiting: Run["awaiting"]): Run => ({ id: "x", case: "green", tokens: { customer: "", provider: "", investigator: "", controller: "" }, finished: false, awaiting, move: null, ready: Promise.resolve(), markReady: () => {} });

describe("buyer gate", () => {
  it("refuses a move when the order is not waiting on Acme", () => {
    expect(buyerMove(run(null), { action: "accept" })).toMatchObject({ status: 409, detail: /not waiting on Acme/ });
  });

  it("refuses the wrong kind of move for the gate", () => {
    const r = run("approve");
    let got: unknown = null;
    r.move = (m) => { got = m; };
    expect(buyerMove(r, { action: "accept" })).toMatchObject({ status: 409, detail: /approve the contract/ });
    expect(buyerMove(run("review"), { action: "approve" })).toMatchObject({ status: 409, detail: /accept or object/ });
    expect(got).toBeNull();
  });

  it("hands the move to the waiting driver and closes the gate", () => {
    const r = run("review");
    let got: unknown = null;
    r.move = (m) => { got = m; r.awaiting = null; r.move = null; };
    expect(buyerMove(r, { action: "object", text: "Counts look low." })).toEqual({ status: 200 });
    expect(got).toEqual({ action: "object", text: "Counts look low." });
    expect(buyerMove(r, { action: "accept" })).toMatchObject({ status: 409 });
  });
});
