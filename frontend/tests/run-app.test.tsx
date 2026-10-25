import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import RunApp from "../components/run/run-app";
import { S } from "../lib/run/scenario";

// The run screen through its buttons and captions only. Fake timers stand in for the recorded
// scenario's pacing; nothing here reaches into the fold or the canvas internals.

class RO { observe() {} disconnect() {} unobserve() {} }
beforeEach(() => { vi.useFakeTimers(); vi.stubGlobal("ResizeObserver", RO); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers(); });

/** Advances the recorded playback until the screen shows what we expect. */
async function until(pred: () => boolean, maxMs = 180_000) {
  for (let t = 0; t < maxMs && !pred(); t += 500) await act(async () => { await vi.advanceTimersByTimeAsync(500); });
  if (!pred()) throw new Error("gave up waiting");
}
const caption = () => document.querySelector(".cap-text")?.textContent ?? "";
const exact = (name: string) => new RegExp(`^${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`);
const button = (name: string | RegExp) => screen.getByRole("button", { name: typeof name === "string" ? exact(name) : name });
const panel = () => document.querySelector(".panel .panel-t")?.textContent;
const disabled = (name: string) => (button(name) as HTMLButtonElement).disabled;
/** Done: Play/Pause is gone and Replay is the only way on. */
const finished = () => !screen.queryByRole("button", { name: /^(Play|Pause)$/ }) && !!screen.queryByRole("button", { name: exact("Replay") });

describe("run screen", () => {
  it("opens paused on the order, with a Play button", () => {
    render(<RunApp />);
    expect(caption()).toBe("Press play to run the recorded order.");
    expect(document.querySelector(".cap-step")?.textContent).toMatch(/^0\//);
    expect(disabled("Play")).toBe(false);
    expect(panel()).toBeUndefined();
    expect(screen.getAllByRole("button", { name: /Clarify the order/ })).toHaveLength(1);
  });
});

describe("The order", () => {
  it("investigates on the canvas with the panel closed, carries the job back to Produce, and captures with the books posted", async () => {
    render(<RunApp />);
    await act(async () => { button("The order").click(); });
    await until(() => !!document.querySelector(".src")); // the orb reads the source on the canvas; no panel slides over it
    expect(panel()).toBeUndefined();
    expect(caption()).toMatch(/pulls what Summit agreed to/);
    expect(disabled("Pause")).toBe(false);

    await until(() => !!document.querySelector(".loop"));
    expect(caption()).toMatch(/Back to Produce with the amended contract/);
    expect(screen.getAllByText("We're right").length).toBeGreaterThan(0);

    await until(() => panel() === "Captured");
    await until(() => !!document.querySelector(".books .margin")); // the books post a beat after the step opens
    expect(document.querySelector(".books .margin")?.textContent).toMatch(/Margin \$168\.00/);
    await until(finished);
    expect(caption()).toMatch(/\$180 captured in total/);
  }, 30_000);
});

describe("Escalation", () => {
  it("pauses on Human, resumes on their decision, and offers the replay with the new rule", async () => {
    render(<RunApp />);
    await act(async () => { button("Escalation").click(); });
    await until(() => !!screen.queryByRole("button", { name: "Waiting on Human" }));
    expect(disabled("Waiting on Human")).toBe(true);
    expect(panel()).toBe("Human decides");
    expect(screen.getByText(/Should yoga studio members count as fitness/)).toBeTruthy();
    for (const name of ["Yoga counts, rerun free", "No, offer $30", "Ask Summit for more", "Send to CFO"]) expect(disabled(name)).toBe(false);

    await act(async () => { button("Yoga counts, rerun free").click(); });
    await until(() => !!screen.queryByRole("button", { name: "Replay yoga with the new rule" }));
    expect(caption()).toMatch(/\$120 captured/);
    expect(document.querySelector(".ev-rule")?.textContent).toMatch(/Learned yoga counts/);

    await act(async () => { button("Replay yoga with the new rule").click(); });
    await until(() => !!screen.queryByText("Covered"));
    await until(finished);
    expect(screen.queryByRole("button", { name: "Waiting on Human" })).toBeNull();
    expect(document.querySelector(".cap-step")?.textContent).toBe("10/10"); // 5 steps, 3 detour steps, 2 revisits
  }, 60_000);
});

describe("Customer view", () => {
  it("shows Summit's decisions as taken on a recorded run", async () => {
    render(<RunApp />);
    await act(async () => { button("The order").click(); });
    await until(() => /captured in total/.test(caption()));
    await act(async () => { screen.getByRole("tab", { name: "Customer view" }).click(); });
    expect(screen.getByText(/Approved and \$120 authorized/)).toBeTruthy();
    expect(screen.getByText(/Objected, answered, then accepted/)).toBeTruthy();
    expect(screen.getAllByText(new RegExp(`paid to ${S.us}`)).length).toBeGreaterThan(0); // the wallet pill and the Paid line
    expect(screen.queryByRole("button", { name: /Approve and authorize/ })).toBeNull(); // nothing to click on a recorded run
  }, 60_000);
});
