import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useTunnel } from "../components/run/canvas";
import { TUNNEL } from "../components/run/orb";

// The groundhog's travel between steps: it ducks into its burrow where it is, waits under for a beat, then climbs
// out of a burrow at the step. The burrow never moves. Steps that start while it is under share the tunnel.

const hook = () => renderHook(({ x, y }: { x: number; y: number }) => useTunnel(x, y), { initialProps: { x: 0, y: 0 } });
const tick = (ms: number) => act(() => { vi.advanceTimersByTime(ms); });

describe("useTunnel", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("ducks in where it is, moves while under, then climbs out at the step", () => {
    const { result, rerender } = hook();
    rerender({ x: 300, y: 0 });
    expect(result.current).toEqual({ x: 0, y: 0, phase: "down" });
    tick(TUNNEL.dive);
    expect(result.current).toEqual({ x: 300, y: 0, phase: "under" });
    tick(TUNNEL.under);
    expect(result.current).toEqual({ x: 300, y: 0, phase: "up" });
    tick(TUNNEL.rise);
    expect(result.current).toEqual({ x: 300, y: 0, phase: "" });
  });

  it("stays under and surfaces at the newest step when one starts while it is under", () => {
    const { result, rerender } = hook();
    rerender({ x: 300, y: 0 });
    tick(TUNNEL.dive + 100);
    rerender({ x: 600, y: 0 });
    expect(result.current).toEqual({ x: 600, y: 0, phase: "under" });
    tick(TUNNEL.under - 1);
    expect(result.current.phase).toBe("under"); // a fresh beat for the new step
    tick(1);
    expect(result.current).toEqual({ x: 600, y: 0, phase: "up" });
  });

  it("goes under with the newest step when one starts during the dive", () => {
    const { result, rerender } = hook();
    rerender({ x: 300, y: 0 });
    tick(100);
    rerender({ x: 600, y: 0 });
    expect(result.current).toEqual({ x: 0, y: 0, phase: "down" });
    tick(TUNNEL.dive - 100);
    expect(result.current).toEqual({ x: 600, y: 0, phase: "under" });
  });

  it("ducks back in if a step starts while it is climbing out", () => {
    const { result, rerender } = hook();
    rerender({ x: 300, y: 0 });
    tick(TUNNEL.dive + TUNNEL.under);
    expect(result.current.phase).toBe("up");
    rerender({ x: 600, y: 0 });
    expect(result.current).toEqual({ x: 300, y: 0, phase: "down" });
    tick(TUNNEL.dive);
    expect(result.current).toEqual({ x: 600, y: 0, phase: "under" });
    tick(TUNNEL.under + TUNNEL.rise);
    expect(result.current).toEqual({ x: 600, y: 0, phase: "" });
  });

  it("a step on another row is the same trip: the burrow never moves", () => {
    const { result, rerender } = hook();
    rerender({ x: 300, y: 200 });
    expect(result.current).toEqual({ x: 0, y: 0, phase: "down" });
    tick(TUNNEL.dive);
    expect(result.current).toEqual({ x: 300, y: 200, phase: "under" });
  });
});
