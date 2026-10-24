import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import Customer from "../components/run/customer";
import { project } from "../lib/run/fold";
import { CONTRACT, CONTRACT_V1, MAIN, timeline } from "../lib/run/scenario";

// Acme's review turn on a live run: the delivered rows sit beside the contract checks, and the orb waits at the decision.

afterEach(cleanup);

it("lists every contract line as checked beside the delivered sheet, with the orb at the decision", () => {
  const { events } = timeline("shared", "rules_no");
  const reviewing = events.slice(0, events.findIndex((e) => "step" in e && e.step === "captured")); // delivered, not yet paid
  const view = project(reviewing, { lane: "shared", ending: "rules_no", learned: false, contract: CONTRACT_V1, live: true });
  const bodyProps = { view, lane: "shared" as const, ending: "rules_no" as const, learned: false, done: false, live: true, decide: async () => null, onReplayLearned: () => {} };
  render(<Customer run="shared" steps={MAIN} view={view} bodyProps={bodyProps} awaiting="review" buyer={async () => null} />);

  const checks = screen.getByRole("region", { name: "Contract checks" });
  for (const line of CONTRACT) expect(within(checks).getByText(line.text)).toBeTruthy();
  expect(within(checks).getAllByText(/Completed:/)).toHaveLength(CONTRACT.length);
  expect(document.querySelector('[data-orb-slot="decision"] .cust-orb')).not.toBeNull();
});
