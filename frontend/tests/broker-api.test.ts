import { afterEach, expect, it, vi } from "vitest";
import {
  brokerOrder,
  mergeProfileSnapshot,
  prepareImprovementMutation,
  profileEvents,
  sendProfileMutation,
} from "../lib/broker-api";
import { mergeEvents } from "../lib/projection";
import { event } from "./fixtures";
import nextConfig from "../next.config";

afterEach(() => vi.unstubAllGlobals());

it("keeps the improvement root request same-origin without a backend auth-losing redirect", async () => {
  const rewrites = await nextConfig.rewrites?.();
  expect(Array.isArray(rewrites)).toBe(true);
  if (!Array.isArray(rewrites)) throw new Error("Expected ordered rewrite rules");
  const root = rewrites.findIndex((rule) => rule.source === "/api/improvements");
  const children = rewrites.findIndex(
    (rule) => rule.source === "/api/improvements/:path*",
  );
  expect(root).toBeGreaterThanOrEqual(0);
  expect(root).toBeLessThan(children);
  expect(rewrites[root].destination).toMatch(/\/api\/improvements\/$/);
});

it("reads broker state and versioned events without mutation side effects", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue(
      new Response(JSON.stringify({ id: "broker-1", revision: 3 })),
    );
  vi.stubGlobal("fetch", fetcher);
  await brokerOrder("broker-1", "local-session");
  fetcher.mockResolvedValue(new Response("[]"));
  await profileEvents("/api/broker", "broker-1", "local-session", 10);
  expect(
    fetcher.mock.calls.every(([, options]) => options.method !== "POST"),
  ).toBe(true);
  expect(fetcher.mock.calls[0][0]).toBe("/api/broker/orders/broker-1");
  expect(fetcher.mock.calls[0][1].headers.Authorization).toBe(
    "Bearer local-session",
  );
});

it("prepares immutable explicit improvement commands without granting a role", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue(new Response(JSON.stringify({ status: "APPROVED" })));
  vi.stubGlobal("fetch", fetcher);
  const mutation = prepareImprovementMutation({
    verb: "approve",
    customer_id: "northwind",
    patch_id: "patch-1",
  });
  expect(fetcher).not.toHaveBeenCalled();
  await sendProfileMutation(mutation, "local-session");
  fetcher.mockResolvedValue(
    new Response(JSON.stringify({ status: "APPROVED" })),
  );
  await sendProfileMutation(mutation, "local-session");
  expect(fetcher.mock.calls[0][1].body).toBe(fetcher.mock.calls[1][1].body);
  expect(JSON.parse(mutation.body)).not.toHaveProperty("role");
});

it("reuses event de-duplication for broker and improvement events without replaying commands", () => {
  const fetcher = vi.fn();
  vi.stubGlobal("fetch", fetcher);
  const items = [
    event({
      id: "spec",
      order_id: "broker-1",
      sequence: 1,
      type: "spec.accepted",
    }),
    event({
      id: "verify",
      order_id: "broker-1",
      sequence: 2,
      type: "verification.completed",
    }),
    event({
      id: "review",
      order_id: "broker-1",
      sequence: 3,
      type: "review.opened",
    }),
  ];
  expect(mergeEvents(items, [items[1], items[0]], "broker-1")).toEqual(items);
  const current = { id: "broker-1", revision: 4, colour: "orange" };
  expect(
    mergeProfileSnapshot(current, { ...current, revision: 2, colour: "green" }),
  ).toBe(current);
  expect(fetcher).not.toHaveBeenCalled();
});
