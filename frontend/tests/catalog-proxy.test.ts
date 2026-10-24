import { afterEach, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST } from "../app/api/catalog/[...path]/route";

afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });
function request(origin = "http://127.0.0.1:3106", host = "127.0.0.1:3106") {
  return new NextRequest("http://localhost:3106/api/catalog/requests", {
    method: "POST", headers: { origin, host, "Content-Type": "application/json" },
    body: JSON.stringify({ prompt: "customer input" }),
  });
}
const context = (path: string[]) => ({ params: Promise.resolve({ path }) });
it("accepts the real same-origin Host even when Next normalizes the URL", async () => {
  const fetch = vi.fn(async () => new Response("{}", { status: 201 })); vi.stubGlobal("fetch", fetch);
  expect((await POST(request(), context(["requests"]))).status).toBe(201);
  expect(fetch).toHaveBeenCalledTimes(1);
});
it("rejects cross-origin, non-local and unsupported requests before reaching backend", async () => {
  const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
  expect((await POST(request("https://attacker.example"), context(["requests"]))).status).toBe(403);
  expect((await POST(request("http://public.example", "public.example"), context(["requests"]))).status).toBe(403);
  expect((await POST(request(), context(["internal", "secrets"]))).status).toBe(404);
  expect(fetch).not.toHaveBeenCalled();
});
it("keeps staff capabilities server-side and disabled without explicit demo enablement", async () => {
  const fetch = vi.fn(async () => new Response("{}")); vi.stubGlobal("fetch", fetch);
  const route = context(["worker", "orders", "order-one", "work"]);
  vi.stubEnv("ENABLE_CATALOG_DEMO_CONTROLS", "false");
  expect((await POST(request(), route)).status).toBe(403);
  expect(fetch).not.toHaveBeenCalled();
  vi.stubEnv("ENABLE_CATALOG_DEMO_CONTROLS", "true");
  vi.stubEnv("INTERNAL_API_TOKEN", "synthetic-worker-test-capability");
  const response = await POST(request(), route);
  expect(response.status).toBe(200);
  expect(await response.text()).not.toContain("synthetic-worker-test-capability");
  expect(fetch).toHaveBeenCalledTimes(1);
});

it("routes improvement proposals and reviews through distinct server-held roles", async () => {
  const fetch = vi.fn(async () => new Response("{}")); vi.stubGlobal("fetch", fetch);
  vi.stubEnv("ENABLE_CATALOG_DEMO_CONTROLS", "true");
  vi.stubEnv("INTERNAL_API_TOKEN", "worker-test-only");
  vi.stubEnv("REVIEWER_API_TOKEN", "reviewer-test-only");
  await POST(request(), context(["worker", "improvements", "commands"]));
  await POST(request(), context(["reviewer", "improvements", "review"]));
  const calls = fetch.mock.calls as unknown as [string, RequestInit][];
  expect(calls[0][0]).toContain("/api/catalog-improvements/commands");
  expect((calls[0][1].headers as Headers).get("X-Internal-Token")).toBe("worker-test-only");
  expect((calls[0][1].headers as Headers).get("X-Reviewer-Token")).toBeNull();
  expect(calls[1][0]).toContain("/api/catalog-improvements/review");
  expect((calls[1][1].headers as Headers).get("X-Reviewer-Token")).toBe("reviewer-test-only");
  expect((calls[1][1].headers as Headers).get("X-Internal-Token")).toBeNull();
});
