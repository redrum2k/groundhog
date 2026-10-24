import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import CatalogImprovement from "../components/run/catalog-improvement";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it("navigation and replay never generate, approve or activate; exact controls are explicit", async () => {
  const calls: { method: string; body?: string; url: string }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, method: init?.method ?? "GET", body: init?.body as string });
    return new Response(JSON.stringify(init?.method ? { status: "COMPLETE" } : {
      corpus_id: "demo", active_version: "catalog-static-v1", model_generation: "CONFIGURED", statuses: {},
      records: [{ id: "incident-a", kind: "catalog_incident", corpus_id: "demo", data: { reason: "source unreadable" } }],
    }));
  }));
  const ui = render(<CatalogImprovement corpus="demo" replay />);
  await waitFor(() => expect(screen.getByText("Observed incidents (1)")).toBeTruthy());
  fireEvent.click(screen.getByRole("button", { name: "Refresh saved improvement records" }));
  fireEvent.click(screen.getByRole("button", { name: "Generate genuine model proposal" }));
  expect(calls.every(c => c.method === "GET")).toBe(true);
  ui.rerender(<CatalogImprovement corpus="demo" replay={false} />);
  fireEvent.click(screen.getByRole("button", { name: "Generate genuine model proposal" }));
  await waitFor(() => expect(calls.filter(c => c.method === "POST")).toHaveLength(1));
  expect(JSON.parse(calls.find(c => c.method === "POST")!.body!)).toMatchObject({
    verb: "propose", expected_active_version: "catalog-static-v1", incident_ids: ["incident-a"], cycle: 1,
  });
});
