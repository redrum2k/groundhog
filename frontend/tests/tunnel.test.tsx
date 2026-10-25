import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TUNNEL, useTunnel } from "../components/run/canvas";

// The groundhog's travel between steps: it sinks where it is, slides underground to the step, then climbs out.
// Steps that start while it is underground share the tunnel.

const hook = () => renderHook(({ x }) => useTunnel(x, 0), { initialProps: { x: 0 } });
const tick = (ms: number) => act(() => { vi.advanceTimersByTime(ms); });

describe("useTunnel", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("sinks where it is, slides to the step underground, then climbs out", () => {
    const { result, rerender } = hook();
    rerender({ x: 300 });
    expect(result.current).toEqual({ x: 0, y: 0, phase: "down" });
    tick(TUNNEL.dive);
    expect(result.current).toEqual({ x: 300, y: 0, phase: "travel" });
    tick(TUNNEL.slide);
    expect(result.current).toEqual({ x: 300, y: 0, phase: "up" });
    tick(TUNNEL.rise);
    expect(result.current).toEqual({ x: 300, y: 0, phase: "" });
  });

  it("tunnels on to a step that starts while it is sliding", () => {
    const { result, rerender } = hook();
    rerender({ x: 300 });
    tick(TUNNEL.dive + 200);
    rerender({ x: 600 });
    expect(result.current).toEqual({ x: 600, y: 0, phase: "travel" });
    tick(TUNNEL.slide - 1);
    expect(result.current.phase).toBe("travel"); // a fresh slide for the new step
    tick(1);
    expect(result.current.phase).toBe("up");
  });

  it("slides to the newest step when one starts during the dive", () => {
    const { result, rerender } = hook();
    rerender({ x: 300 });
    tick(100);
    rerender({ x: 600 });
    expect(result.current).toEqual({ x: 0, y: 0, phase: "down" });
    tick(TUNNEL.dive);
    expect(result.current).toEqual({ x: 600, y: 0, phase: "travel" });
  });

  it("sinks again if a step starts while it is climbing out", () => {
    const { result, rerender } = hook();
    rerender({ x: 300 });
    tick(TUNNEL.dive + TUNNEL.slide);
    expect(result.current.phase).toBe("up");
    rerender({ x: 600 });
    expect(result.current).toEqual({ x: 300, y: 0, phase: "down" });
    tick(TUNNEL.dive);
    expect(result.current).toEqual({ x: 600, y: 0, phase: "travel" });
    tick(TUNNEL.slide + TUNNEL.rise);
    expect(result.current).toEqual({ x: 600, y: 0, phase: "" });
  });
});
