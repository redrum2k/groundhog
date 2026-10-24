import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import RunApp from "../components/run/run-app";

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
  it("opens on No dispute, paused, with a Play button", () => {
    render(<RunApp />);
    expect(caption()).toBe("Press play to run this case.");
    expect(document.querySelector(".cap-step")?.textContent).toBe("0/5");
    expect(disabled("Play")).toBe(false);
    expect(panel()).toBeUndefined();
    expect(screen.getAllByRole("button", { name: /Clarify the order/ })).toHaveLength(1);
  });
});

describe("Our fault", () => {
  it("investigates with the panel open, carries the job back to Produce, and captures with the books posted", async () => {
    render(<RunApp />);
    await act(async () => { button("Our fault").click(); });
    await until(() => panel() === "Investigate");
    expect(caption()).toMatch(/checks the contract against the delivered sheet/);
    expect(disabled("Pause")).toBe(false);

    await until(() => !!document.querySelector(".loop"));
    expect(caption()).toMatch(/carries the job back to Produce/);
    expect(screen.getByText("Our miss")).toBeTruthy();

    await until(() => panel() === "Captured");
    await until(() => !!document.querySelector(".books .margin")); // the books post a beat after the step opens
    expect(document.querySelector(".books .margin")?.textContent).toMatch(/Margin \$108\.00/);
    await until(finished);
    expect(caption()).toMatch(/\$6 rerun is booked as our cost/);
  }, 30_000);
});

describe("Grey area", () => {
  it("pauses on Maya, resumes on her decision, and offers the replay with the new rule", async () => {
    render(<RunApp />);
    await act(async () => { button("Grey area").click(); });
    await until(() => !!screen.queryByRole("button", { name: "Waiting on Maya" }));
    expect(disabled("Waiting on Maya")).toBe(true);
    expect(panel()).toBe("Maya decides");
    expect(screen.getByText(/Should yoga studio members count as fitness/)).toBeTruthy();
    for (const name of ["Yoga counts, rerun free", "No, offer $30", "Ask Acme for more", "Send to CFO"]) expect(disabled(name)).toBe(false);

    await act(async () => { button("Yoga counts, rerun free").click(); });
    await until(() => !!screen.queryByRole("button", { name: "Replay yoga with the new rule" }));
    expect(caption()).toMatch(/\$120 captured/);
    expect(document.querySelector(".ev-rule")?.textContent).toMatch(/Learned yoga counts/);

    await act(async () => { button("Replay yoga with the new rule").click(); });
    await until(() => !!screen.queryByText("Covered"));
    await until(finished);
    expect(screen.queryByRole("button", { name: "Waiting on Maya" })).toBeNull();
    expect(document.querySelector(".cap-step")?.textContent).toBe("10/10"); // 5 steps, 3 detour steps, 2 revisits
  }, 60_000);
});

describe("All cases", () => {
  it("is a quiet map: every lane's verdict, no orb, no evidence cards", async () => {
    render(<RunApp />);
    await act(async () => { button("All cases").click(); });
    expect(document.querySelector(".orb-wrap")).toBeNull();
    expect(document.querySelector(".ev-stack")).toBeNull();
    for (const chip of ["Our miss", "We're right", "Grey area"]) expect(screen.getAllByText(chip).length).toBeGreaterThan(0);
    expect(document.querySelectorAll(".chip")).toHaveLength(3);
    expect(caption()).toMatch(/Existing platforms handle transactions/);
    expect(disabled("Run the order")).toBe(false);
  });
});
