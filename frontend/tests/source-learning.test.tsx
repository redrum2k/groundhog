import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import SourceLearning from "../components/run/source-learning";
import { bridge } from "../lib/live-bridge";

afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

const state = {
  enabled: true, mode: "controlled_local_mock", disclosure: "Simulated identities; mock funding only.",
  reviews: [{ encounter_id: "e1", request_id: "r1", source_family: "partition-a", source_sha256: "a".repeat(64), authority_sha256: "b".repeat(64), reason: "ambiguous_source_definition", columns: ["v_count", "v_devices"], resolved: false, actionable: true, review_status: "open" }],
  candidates: [], versions: [], events: [], active_version: null,
};

it("requires an explicit owner column and evidence explanation, then submits the real command", async () => {
  const fetch = vi.fn(async (_url: unknown, init?: RequestInit) => Response.json(init?.method === "POST" ? { status: "RESOLVED", record_id: "p1" } : state));
  vi.stubGlobal("fetch", fetch);
  render(<SourceLearning openRun={vi.fn()} />);
  fireEvent.click(await screen.findByRole("button", { name: /Source learning/ }));
  const resolve = await screen.findByRole("button", { name: "Answer as source owner" });
  expect((resolve as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Count column for partition-a"), { target: { value: "v_count" } });
  fireEvent.change(screen.getByLabelText("Owner explanation for partition-a"), { target: { value: "Owner confirms unique adults for this schema." } });
  fireEvent.click(resolve);
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => String(url).endsWith("/resolve"))).toBe(true));
  const call = fetch.mock.calls.find(([url]) => String(url).endsWith("/resolve"))!;
  const body = JSON.parse(String(call[1]?.body));
  expect(body).toMatchObject({ encounter_id: "e1", column: "v_count", applicability: "source_edition" });
  expect(body).not.toHaveProperty("actor");
  expect(body.idempotency_key).toBeTruthy();
});

it("stops polling a disabled backend and permits an explicit availability retry", async () => {
  vi.useFakeTimers();
  const fetch = vi.fn(async () => Response.json({detail: "controlled local source learning is not enabled"}, {status: 503}));
  vi.stubGlobal("fetch", fetch);
  render(<SourceLearning openRun={vi.fn()} />);
  await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
  expect(fetch).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", {name: /Source learning/}));
  fireEvent.click(screen.getByRole("button", {name: "Check again"}));
  await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
  expect(fetch).toHaveBeenCalledTimes(2);
});

it("retains stale reviews as history without a resolve control or actionable count", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({...state, reviews: [
    {...state.reviews[0], actionable: false, review_status: "stale"},
  ]})));
  render(<SourceLearning openRun={vi.fn()} />);
  fireEvent.click(await screen.findByRole("button", {name: "Source learning"}));
  expect(await screen.findByText("Answered questions")).toBeTruthy();
  expect(screen.getByText(/Status: stale/)).toBeTruthy();
  expect(screen.queryByRole("button", {name: "Answer as source owner"})).toBeNull();
});

it("shows persisted active versions and measured qualification instead of playback events", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({ ...state, reviews: [], active_version: "version-42", active_current: true,
    qualification: { id: "q1", candidate_id: "c1", passed: true, cases: 6, correct_both: 6, baseline_reviews: 10, candidate_reviews: 6, baseline_operations: 100, candidate_operations: 120, capsule_sha256: "c".repeat(64), violations: [] },
    events: [{ id: "event1", kind: "knowledge_reused", text: "New bytes handled using approved evidence.", actor: "employee", created_at: "2026-10-24T00:00:00Z", evidence_ids: ["proof-1"] }],
  })));
  render(<SourceLearning openRun={vi.fn()} />);
  fireEvent.click(await screen.findByRole("button", { name: "Learning active" }));
  expect(await screen.findByText("A learned procedure is on")).toBeTruthy();
  expect(screen.getByText(/10 → 6/)).toBeTruthy();
  expect(screen.getByText("New bytes handled using approved evidence.")).toBeTruthy();
});

it("keeps owner and controller credentials server-side and enforces same-origin commands", async () => {
  vi.stubEnv("BROKER_LOCAL_DEMO", "1"); vi.stubEnv("BACKEND_URL", "http://127.0.0.1:8026");
  vi.stubEnv("INTERNAL_API_TOKEN", "worker-test"); vi.stubEnv("REVIEWER_API_TOKEN", "controller-test"); vi.stubEnv("SOURCE_OWNER_API_TOKEN", "owner-test");
  const fetch = vi.fn(async () => Response.json({ status: "RESOLVED", record_id: "proof" }));
  vi.stubGlobal("fetch", fetch);
  const make = (origin: string) => new Request("http://localhost:3026/api/live/source-learning/resolve", { method: "POST", headers: { origin }, body: "{}" });
  expect((await bridge(make("https://evil.example"), ["source-learning", "resolve"])).status).toBe(403);
  const response = await bridge(make("http://localhost:3026"), ["source-learning", "resolve"]);
  expect(response.status).toBe(200);
  const headers = new Headers((fetch.mock.calls[0] as unknown as [URL, RequestInit])[1].headers);
  expect(headers.get("X-Source-Owner-Token")).toBe("owner-test");
  expect(headers.has("X-Reviewer-Token")).toBe(false);
  expect(await response.text()).not.toContain("owner-test");
});
