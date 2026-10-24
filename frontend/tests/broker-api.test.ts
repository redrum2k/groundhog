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

afterEach(() => vi.unstubAllGlobals());

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
