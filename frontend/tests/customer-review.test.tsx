import { act, cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import Customer from "../components/run/customer";
import { project } from "../lib/run/fold";
import { CONTRACT, CONTRACT_V1, MAIN, timeline } from "../lib/run/scenario";

// Acme's review turn on a live run: the delivered rows sit beside the contract checks, the orb waits
// at the decision, and the review window reads as time left until it accepts and pays on its own.

beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(new Date("2026-10-24T20:00:00Z")); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

function reviewTurn(closesIn: number, skew = 0) {
  const { events } = timeline("shared", "rules_no");
  const reviewing = events.slice(0, events.findIndex((e) => "step" in e && e.step === "captured")); // delivered, not yet paid
  const projected = project(reviewing, { lane: "shared", ending: "rules_no", learned: false, contract: CONTRACT_V1, live: true });
  const delivery = { ...projected.deliveries.at(-1)!, reviewClosesAt: new Date(Date.now() + closesIn).toISOString() };
  const view = { ...projected, deliveries: [delivery] };
  const bodyProps = { view, lane: "shared" as const, ending: "rules_no" as const, learned: false, done: false, live: true, decide: async () => null, onReplayLearned: () => {} };
  render(<Customer run="shared" steps={MAIN} view={view} bodyProps={bodyProps} awaiting="review" skew={skew} buyer={async () => null} />);
}

it("lists every contract line as checked beside the delivered sheet", () => {
  reviewTurn(42_000);
  const checks = screen.getByRole("region", { name: "Contract checks" });
  for (const line of CONTRACT) expect(within(checks).getByText(line.text)).toBeTruthy();
  expect(within(checks).getAllByText(/Completed:/)).toHaveLength(CONTRACT.length);
  expect(document.querySelector('[data-orb-slot="decision"] .cust-orb')).not.toBeNull();
});

it("counts the review window down on the server's clock, then says it closed", () => {
  reviewTurn(42_000);
  expect(screen.getByRole("timer").textContent).toBe("Auto-accepts and pays $120 in 0:42");
  act(() => { vi.advanceTimersByTime(2_000); });
  expect(screen.getByRole("timer").textContent).toBe("Auto-accepts and pays $120 in 0:40");
  act(() => { vi.advanceTimersByTime(41_000); });
  expect(screen.getByRole("timer").textContent).toBe("Review window closed");
});

it("reads a browser clock that runs behind the server as less time left", () => {
  reviewTurn(42_000, 30_000); // the server is 30s ahead of this browser
  expect(screen.getByRole("timer").textContent).toBe("Auto-accepts and pays $120 in 0:12");
});
