import { cleanup, render, screen, waitFor, fireEvent } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import CatalogRun from "../components/run/catalog-run";
import { catalogCanvas, mergeCatalogEvents, orderBinding } from "../lib/run/catalog";
import type { CatalogEvent, OrderView } from "../lib/run.generated";

class RO { observe() {} disconnect() {} unobserve() {} }
afterEach(() => { cleanup(); vi.unstubAllGlobals(); localStorage.clear(); });
const event = (state = "funded", seq = 1) => ({
  seq, event_id: `event-${seq}`, run_id: "order-1", aggregate_revision: 9,
  binding: { snapshot_id: "s1", evidence_revision: 17, delivery_version: 2 },
  order: {
    snapshot: { order_id: "order-1", quote: { amount: { amount_minor: 1500, currency: "USD", decimals: 2 }, policy: { version: "catalog-v0.3" } } },
    order_state: "human_review", authorization: { status: "mock_authorized", receipt: {} },
    sources: [], deliveries: [], ledger: [],
  }, payment: { simulated: true, payment: { state } },
} as unknown as CatalogEvent);

describe("catalog projection", () => {
  it("does not collapse uncertain, expired, pending or failed money into returned/captured", () => {
    for (const state of ["uncertain", "expired_not_returned", "capture_pending", "void_pending", "failed"]) {
      const view = catalogCanvas(event(state));
      expect(view.chip.captured).toBe(state);
      expect(view.status.captured).not.toBe("done");
      expect(view.coin?.done).toBe(false);
      expect(view.coin?.text).toContain("USD 15.00");
      expect(JSON.stringify(view)).not.toMatch(/x402|120|48-hour|yoga/);
    }
    expect(catalogCanvas(event("voided")).chip.captured).toBe("voided");
  });
  it("deduplicates reconnects and uses actual aggregate and evidence revisions", () => {
    expect(mergeCatalogEvents([event()], [event(), event("funded", 2)])).toHaveLength(2);
    expect(() => mergeCatalogEvents([event()], [{ ...event(), run_id: "other" }])).toThrow();
    const view = { order: { revision: 9, binding: event().binding } } as OrderView;
    expect(orderBinding(view, "one")).toEqual({ expected_revision: 9, expected_binding: event().binding, idempotency_key: "one" });
  });
});

describe("catalog UI mutation boundary", () => {
  it("mount, overview, reopen and replay only read; explicit create uses actual input", async () => {
    vi.stubGlobal("ResizeObserver", RO);
    const calls: { url: string; method: string; body?: string }[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, method: init?.method ?? "GET", body: init?.body as string });
      let body: unknown = url.endsWith("corpora") ? { "storage-demo": [] } : [];
      if (url.includes("/events")) body = { events: [], next_cursor: 0, server_time: "2026-10-24T09:00:00Z", poll_after_ms: 2000 };
      if (url.endsWith("requests")) body = { request_id: "request-new", prompt: "selected prompt", corpus_id: "storage-demo", status: "compiling", revision: 1 };
      return new Response(JSON.stringify(body), { status: 200 });
    }));
    localStorage.setItem("objection.catalog.run", "order-existing");
    render(<CatalogRun onRecorded={() => {}} />);
    await waitFor(() => expect(calls.some(c => c.url.includes("/events"))).toBe(true));
    fireEvent.click(screen.getByRole("button", { name: "Overview" }));
    fireEvent.click(screen.getByRole("button", { name: "Read-only replay" }));
    await waitFor(() => expect(screen.getByText("Read-only saved events")).toBeTruthy());
    expect(calls.every(c => c.method === "GET")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Return to live" }));
    fireEvent.click(screen.getByRole("button", { name: "New order" }));
    fireEvent.change(screen.getByLabelText("Requested work"), { target: { value: "selected prompt" } });
    fireEvent.click(screen.getByRole("button", { name: "Create new draft" }));
    await waitFor(() => expect(calls.filter(c => c.method === "POST")).toHaveLength(1));
    expect(JSON.parse(calls.find(c => c.method === "POST")!.body!)).toMatchObject({ prompt: "selected prompt", corpus_id: "storage-demo" });
    expect(calls.find(c => c.method === "POST")!.body).not.toContain("ending");
  });
});
