import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { bridge } from "../lib/live-bridge";
import { authorizeHostedDemo } from "../lib/hosted-demo";
import { proxy } from "../proxy";

const origin = "https://datumco.example";
const password = "synthetic-test-password-long-enough";
const authorization = `Basic ${Buffer.from(`demo:${password}`).toString("base64")}`;
const request = (path = "/api/live/runs", method = "POST", extra: Record<string, string> = {}) =>
  new Request(`http://localhost:3000${path}`, {
    method,
    headers: { host: "datumco.example", "x-forwarded-proto": "https", origin, authorization, ...extra },
    ...(method === "POST" ? { body: "{}" } : {}),
  });

beforeEach(() => {
  vi.stubEnv("BROKER_HOSTED_DEMO", "1");
  vi.stubEnv("BROKER_PUBLIC_DEMO", "0");
  vi.stubEnv("APP_ORIGIN", origin);
  vi.stubEnv("DEMO_USERNAME", "demo");
  vi.stubEnv("DEMO_PASSWORD", password);
  vi.stubEnv("BACKEND_URL", "http://backend.railway.internal:8000");
  vi.stubEnv("INTERNAL_API_TOKEN", "worker");
  vi.stubEnv("REVIEWER_API_TOKEN", "reviewer");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ ok: true })));
});
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

it("challenges unauthenticated page and direct live bridge access", async () => {
  const page = proxy(new NextRequest(request("/", "GET", { authorization: "" })));
  expect(page.status).toBe(401);
  expect(page.headers.get("www-authenticate")).toContain("Basic");
  expect((await bridge(request(undefined, "POST", { authorization: "" }), ["runs"])).status).toBe(401);
  expect(fetch).not.toHaveBeenCalled();
});

it("authenticates before legacy API rewrites and exposes only a minimal health route", () => {
  expect(proxy(new NextRequest(request("/api/jobflow/orders", "GET", { authorization: "" }))).status).toBe(401);
  expect(proxy(new NextRequest("http://localhost:3000/api/health")).status).toBe(200);
  expect(proxy(new NextRequest(request("/", "GET"))).headers.get("cache-control")).toBe("private, no-store");
});

it.each<Record<string, string>>([
  { authorization: "Basic incorrect" },
  { origin: "https://evil.example" },
  { origin: "" },
  { host: "evil.example", "x-forwarded-host": "datumco.example" },
  { "x-forwarded-proto": "http" },
])("rejects forged credentials, host, protocol or cross-origin writes: %j", async headers => {
  const response = await bridge(request(undefined, "POST", headers), ["runs"]);
  expect([401, 403]).toContain(response.status);
  expect(fetch).not.toHaveBeenCalled();
});

it.each([
  ["APP_ORIGIN", ""], ["APP_ORIGIN", "http://datumco.example"],
  ["APP_ORIGIN", `${origin}/`], ["DEMO_PASSWORD", "short"],
  ["INTERNAL_API_TOKEN", password], ["BACKEND_URL", "http://public.example"],
  ["BACKEND_URL", "https://user:secret@backend.example"],
  ["REVIEWER_API_TOKEN", "worker"],
])("fails closed for invalid %s configuration", async (key, value) => {
  vi.stubEnv(key, value);
  expect((await bridge(request(), ["runs"])).status).toBe(503);
  expect(fetch).not.toHaveBeenCalled();
});

it("forwards only the server reviewer credential, preserving status and idempotency", async () => {
  vi.mocked(fetch).mockResolvedValueOnce(Response.json({ detail: "stale" }, { status: 409 }));
  const response = await bridge(request("/api/live/runs/a/decisions", "POST", {
    "idempotency-key": "same-key", "x-internal-token": "attacker", "x-reviewer-token": "attacker",
  }), ["runs", "a", "decisions"]);
  expect(response.status).toBe(409);
  const [target, options] = vi.mocked(fetch).mock.calls[0];
  expect(String(target)).toBe("http://backend.railway.internal:8000/runs/a/decisions");
  const headers = new Headers(options?.headers);
  expect(headers.get("x-reviewer-token")).toBe("reviewer");
  expect(headers.get("idempotency-key")).toBe("same-key");
  expect(headers.has("authorization")).toBe(false);
  expect(headers.has("x-internal-token")).toBe(false);
});

it("does not expose arbitrary operations or controlled local source learning", async () => {
  expect((await bridge(request(), ["internal", "payments", "work"])).status).toBe(404);
  expect((await bridge(request(), ["source-learning", "resolve"])).status).toBe(403);
  expect(fetch).not.toHaveBeenCalled();
});

it("allows authenticated polling and checks writes against the configured external origin", () => {
  expect(authorizeHostedDemo(request("/api/live/runs/a/events", "GET", { origin: "" }))).toBeNull();
  expect(authorizeHostedDemo(request())).toBeNull();
});

describe("public mock-payment demo", () => {
  const mockHealth = { payment_mode: "mock", live_adapter: "disabled", live_settlement_enabled: false };
  beforeEach(() => {
    vi.stubEnv("BROKER_PUBLIC_DEMO", "1");
    vi.stubEnv("BROKER_HOSTED_DEMO", "0");
    vi.stubEnv("DEMO_USERNAME", "");
    vi.stubEnv("DEMO_PASSWORD", "");
  });

  it("opens the UI without a password and forwards a command only after checking mock capabilities", async () => {
    expect(proxy(new NextRequest(request("/", "GET", { authorization: "" }))).status).toBe(200);
    vi.mocked(fetch).mockResolvedValueOnce(Response.json(mockHealth))
      .mockResolvedValueOnce(Response.json({ id: "new" }, { status: 201 }));
    expect((await bridge(request(undefined, "POST", { authorization: "" }), ["runs"])).status).toBe(201);
    expect(String(vi.mocked(fetch).mock.calls[0][0])).toBe("http://backend.railway.internal:8000/health");
    expect(String(vi.mocked(fetch).mock.calls[1][0])).toBe("http://backend.railway.internal:8000/runs");
    expect(new Headers(vi.mocked(fetch).mock.calls[1][1]?.headers).has("authorization")).toBe(false);
  });

  it.each([
    { payment_mode: "base_sepolia", live_adapter: "ready", live_settlement_enabled: true },
    { payment_mode: "base_sepolia", live_adapter: "unavailable", live_settlement_enabled: false },
    { ...mockHealth, live_settlement_enabled: true }, {}, null,
  ])("never forwards commands to a live or unverified backend: %j", async capabilities => {
    vi.mocked(fetch).mockResolvedValueOnce(Response.json(capabilities));
    expect((await bridge(request(undefined, "POST", { authorization: "" }), ["runs"])).status).toBe(503);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("rechecks capabilities on every request, including polling", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(Response.json(mockHealth))
      .mockResolvedValueOnce(Response.json({ events: [] }))
      .mockResolvedValueOnce(Response.json({ ...mockHealth, payment_mode: "base_sepolia" }));
    const req = request("/api/live/runs/a/events", "GET", { authorization: "" });
    expect((await bridge(req, ["runs", "a", "events"])).status).toBe(200);
    expect((await bridge(req, ["runs", "a", "events"])).status).toBe(503);
    expect(fetch).toHaveBeenCalledTimes(3);
  });

  it("does not forward when the capability probe fails", async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error("offline"));
    expect((await bridge(request(), ["runs"])).status).toBe(502);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it.each(["/api/jobflow/orders", "/api/broker/orders", "/api/improvements", "/api/broker-run/runs"])("blocks legacy bypass %s", path => {
    expect(proxy(new NextRequest(request(path, "GET", { authorization: "" }))).status).toBe(403);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("still rejects cross-origin writes, wrong hosts and controlled learning", async () => {
    expect((await bridge(request(undefined, "POST", { authorization: "", origin: "https://evil.example" }), ["runs"])).status).toBe(403);
    expect((await bridge(request(undefined, "POST", { authorization: "", host: "evil.example" }), ["runs"])).status).toBe(403);
    expect((await bridge(request(undefined, "POST", { authorization: "" }), ["source-learning", "resolve"])).status).toBe(403);
    expect(fetch).not.toHaveBeenCalled();
  });
});
