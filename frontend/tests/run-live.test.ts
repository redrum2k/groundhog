import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { RunEvent } from "../lib/run/contract";
import type { FoldContext } from "../lib/run/fold";
import { amberEnding, amberOpen, CONTRACT_V1, stamp, timeline } from "../lib/run/scenario";
import { usePlayback, type Feed } from "../lib/run/source";

// The live seam from the canvas's side: a fake server that answers the three endpoints the stub
// and, later, Nikita's backend expose. Nothing here knows how the hook polls.

const ctx: FoldContext = { lane: "amber", ending: "maya", learned: false, contract: CONTRACT_V1 };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function fakeServer(released: RunEvent[]) {
  const calls: { method: string; url: string; body?: unknown }[] = [];
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method: init?.method ?? "GET", url, body });
    if (url.endsWith("/runs")) return json({ id: "run-1", poll_after_ms: 5 });
    if (url.includes("/events")) {
      const after = Number(new URL(url, "http://x").searchParams.get("after"));
      return json({ events: released.filter((e) => e.seq > after), poll_after_ms: 5 });
    }
    return json({ detail: "not found" }, 404);
  });
  return { fetch, calls, released };
}

const liveFeed = (): Feed => {
  const { events, start } = timeline("amber", "maya");
  return { kind: "live", api: "/api/live", body: { case: "amber" }, before: events.slice(0, start), ctx };
};

beforeEach(() => vi.useFakeTimers());
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers(); });

describe("live feed", () => {
  it("starts a run, then folds the events it polls after the last seq it saw", async () => {
    const amber = stamp("amber", [...amberOpen("maya", false), ...amberEnding("maya", false)]);
    const server = fakeServer(amber.slice(0, 6)); // up to the dispute and the start of Investigate
    vi.stubGlobal("fetch", server.fetch);
    const feed = liveFeed(); // one object: a new feed each render would restart the poll
    const { result } = renderHook(() => usePlayback(feed));

    // waitFor polls with the (faked) timers, so advance them and assert directly
    await act(async () => { await vi.advanceTimersByTimeAsync(20); });
    expect(result.current.view.nodes.investigate?.status).toBe("running");
    expect(result.current.view.nodes.review.status).toBe("waiting");
    expect(result.current.view.coin).toMatchObject({ locked: true });
    expect(server.calls[0]).toMatchObject({ method: "POST", url: "/api/live/runs", body: { case: "amber" } });
    expect(server.calls[1].url).toBe("/api/live/runs/run-1/events?after=0");

    // the next poll asks only for what is new
    await act(async () => { await vi.advanceTimersByTimeAsync(10); });
    expect(server.calls.at(-1)?.url).toBe("/api/live/runs/run-1/events?after=6");
  });
});

describe("live feed at the controller gate", () => {
  it("waits on the controller, surfaces a 409 on a stale decision, then resumes to done", async () => {
    const open = stamp("amber", amberOpen("maya", false));
    const gate = stamp("amber", amberEnding("maya", false), open.length); // ends with step_waiting on Maya
    const server = fakeServer([...open, ...gate]);
    let decisions = 0;
    const fetch = vi.fn(async (url: string, init?: RequestInit) => {
      if (!url.endsWith("/decisions")) return server.fetch(url, init);
      decisions += 1;
      if (decisions === 1) return json({ detail: "Evidence or delivery changed since this was shown; review again" }, 409);
      // the server appends the approval's continuation; the next poll picks it up
      const { controllerContinuation } = await import("../lib/run/scenario");
      server.released.push(...stamp("amber", controllerContinuation("approve", JSON.parse(String(init?.body)).binding), server.released.length));
      return json({ ok: true });
    });
    vi.stubGlobal("fetch", fetch);
    const feed = liveFeed();
    const { result } = renderHook(() => usePlayback(feed));

    await act(async () => { await vi.advanceTimersByTimeAsync(30); });
    expect(result.current.status).toBe("waiting");
    expect(result.current.view.nodes.decide.status).toBe("waiting");
    expect(result.current.view.orb).toEqual({ step: "decide", mode: "wait" });

    const binding = { deliveryVersion: 1, evidenceVersion: 3 };
    let detail: string | null = null;
    await act(async () => { detail = await result.current.decide("approve", binding); });
    expect(detail).toMatch(/review again/);
    expect(result.current.status).toBe("waiting");

    await act(async () => { detail = await result.current.decide("approve", binding); });
    expect(detail).toBeNull();
    await act(async () => { await vi.advanceTimersByTimeAsync(30); });
    expect(result.current.status).toBe("done");
    expect(result.current.view.contract.version).toBe(2);
    expect(result.current.view.coin).toMatchObject({ done: true });
    expect(fetch.mock.calls.filter(([u]) => String(u).endsWith("/decisions")).map(([, i]) => JSON.parse(String((i as RequestInit).body)))).toEqual([{ action: "approve", binding }, { action: "approve", binding }]);
  });
});

describe("live feed failure", () => {
  it("reports an error instead of guessing when the server stops answering", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ detail: "boom" }, 503)));
    const feed = liveFeed();
    const { result } = renderHook(() => usePlayback(feed));
    await act(async () => { await vi.advanceTimersByTimeAsync(20); });
    expect(result.current.status).toBe("error");
    expect(result.current.error).toMatch(/503/);
    // the recorded prefix is still on screen, nothing invented past it
    expect(result.current.view.nodes.review.status).toBe("running");
    expect(result.current.view.nodes.investigate).toBeUndefined();
  });
});
