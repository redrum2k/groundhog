import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import LiveRun from "../components/run/live-run";
import { saveBuyerAddress } from "../lib/run/buyer-settings";
import { signFunding } from "../lib/run/wallet";
import type { FundingPreparation } from "../lib/runs.generated";

const buyer = "0x" + "1".repeat(40);
const other = "0x" + "2".repeat(40);
const STORAGE = "datumco.buyer-wallet.v1";
const page = {
  events: [], next_after: 0, high_watermark: 0, caught_up: true, poll_after_ms: 100000,
  server_time: "now", binding: null, available_actions: [{action: "quote", enabled: true}],
  request: {status: "ready", revision: 2}, quote: null, payment: null,
};
const response = () => new Response(JSON.stringify(page), {headers: {"Content-Type": "application/json"}});

beforeEach(() => { localStorage.clear(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function wallet(address = buyer, chain = "0x14a34") {
  return {request: vi.fn(async ({method}: {method: string}) => {
    if (method === "eth_chainId") return chain;
    return [address];
  })};
}

it("saves the connected buyer once and uses it for quotes after reload", async () => {
  const provider = wallet();
  vi.stubGlobal("ethereum", provider);
  const first = render(<LiveRun recorded={() => {}}/>);
  fireEvent.click(screen.getByRole("button", {name: /^Summit Fitness/}));
  fireEvent.click(screen.getByRole("button", {name: "Connect MetaMask"}));
  await screen.findByText(buyer);
  expect(localStorage.getItem(STORAGE)).toBe(buyer);
  expect(provider.request.mock.calls.some(([call]) => call.method.includes("sign"))).toBe(false);
  first.unmount();

  localStorage.setItem("datumco.live-run.v1", JSON.stringify({id: "saved"}));
  const fetcher = vi.fn().mockImplementation(async () => response());
  vi.stubGlobal("fetch", fetcher);
  render(<LiveRun recorded={() => {}}/>);
  fireEvent.click(await screen.findByRole("button", {name: "Prepare quote"}));
  await waitFor(() => expect(fetcher.mock.calls.some(([url]) => url.endsWith("/quotes"))).toBe(true));
  const [, options] = fetcher.mock.calls.find(([url]) => url.endsWith("/quotes"))!;
  expect(JSON.parse(options.body).payer).toBe(buyer);
  expect(screen.queryByLabelText(/Buyer wallet address/)).toBeNull();
  fireEvent.click(await screen.findByRole("button", {name: "New request"}));
  expect(localStorage.getItem(STORAGE)).toBe(buyer);
});

it.each(["missing", "rejected", "network", "account-change"])("does not replace a saved buyer on %s connection failure", async kind => {
  saveBuyerAddress(buyer);
  const provider = wallet(other, kind === "network" ? "0x1" : "0x14a34");
  if (kind === "rejected") provider.request.mockRejectedValue(new Error("Connection rejected"));
  if (kind === "account-change") provider.request.mockImplementation(async ({method}) => {
    if (method === "eth_chainId") return "0x14a34";
    return [method === "eth_accounts" ? buyer : other];
  });
  vi.stubGlobal("ethereum", kind === "missing" ? undefined : provider);
  render(<LiveRun recorded={() => {}}/>);
  fireEvent.click(screen.getByRole("button", {name: /^Summit Fitness/}));
  fireEvent.click(screen.getByRole("button", {name: "Change buyer wallet"}));
  await screen.findByRole("alert");
  expect(localStorage.getItem(STORAGE)).toBe(buyer);
});

it("changing settings cannot change the signer on a prepared payment", async () => {
  saveBuyerAddress(other);
  const provider = wallet(other);
  const preparation = {terms: {payment_info: {payer: buyer}}, typed_data: {}} as FundingPreparation;
  await expect(signFunding(provider, preparation)).rejects.toThrow(/accepted payer/);
  expect(provider.request.mock.calls.some(([call]) => call.method.includes("sign"))).toBe(false);
});

it("forgets the saved address and updates an open page when another tab changes it", async () => {
  render(<LiveRun recorded={() => {}}/>);
  act(() => {
    localStorage.setItem(STORAGE, buyer);
    window.dispatchEvent(new StorageEvent("storage", {key: STORAGE}));
  });
  fireEvent.click(screen.getByRole("button", {name: /^Summit Fitness/}));
  expect(screen.getByText(buyer)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", {name: "Forget wallet"}));
  expect(localStorage.getItem(STORAGE)).toBeNull();
  expect(screen.getByText("No buyer wallet saved yet.")).toBeTruthy();
});

it("ignores invalid stored addresses and preserves wallet-free mock quoting", async () => {
  localStorage.setItem(STORAGE, "not-an-address");
  localStorage.setItem("datumco.live-run.v1", JSON.stringify({id: "saved"}));
  const fetcher = vi.fn().mockImplementation(async () => response());
  vi.stubGlobal("fetch", fetcher);
  render(<LiveRun recorded={() => {}}/>);
  fireEvent.click(await screen.findByRole("button", {name: "Prepare quote"}));
  await waitFor(() => expect(fetcher.mock.calls.some(([url]) => url.endsWith("/quotes"))).toBe(true));
  const [, options] = fetcher.mock.calls.find(([url]) => url.endsWith("/quotes"))!;
  expect(JSON.parse(options.body)).not.toHaveProperty("payer");
});
