import { afterEach, expect, it, vi } from "vitest";
import { GET } from "../app/api/broker-run/health/route";

afterEach(() => vi.unstubAllGlobals());

it("does not advertise a live broker when generic health is up but demo identities are disabled", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url.endsWith("/health")
    ? Response.json({payment_mode: "mock"}) : Response.json({detail: "Local demo is disabled"}, {status: 404})));
  expect((await GET()).status).toBe(503);
});

it("checks broker demo capability read-only, without minting sessions", async () => {
  const fetcher = vi.fn(async (_url: string) => Response.json([
    {id: "customer", role: "customer"}, {id: "provider", role: "provider"},
    {id: "investigator", role: "investigator"}, {id: "controller", role: "controller"},
  ]));
  vi.stubGlobal("fetch", fetcher);
  expect((await GET()).status).toBe(200);
  expect(fetcher.mock.calls[0][0]).toContain("/api/jobflow/actors");
});
