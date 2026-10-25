import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import PaymentJustification from "../components/run/payment-justification";
import {LiveReview} from "../components/run/live-order";
import type {LiveOrder} from "../lib/run/use-live-order";

afterEach(()=>vi.unstubAllGlobals());
it("shows the persisted complaint, exact amount and blocked state without inventing settlement", async()=>{
  const fetch = vi.fn().mockResolvedValue({ok:true,json:async()=>({agreement:{quote:{specification:{summary:"Frozen SF dataset"}}},exact_price:"0.25",amount_atomic:"250000",delivery_hashes:{csv:"abc",json:"def"},bytes_revalidated:true,cases:[{complaint:{text:"Are those memberships current?"}}],state:"funded",payment:{simulated:true},capture_eligible_now:false,blockers:["An unresolved dispute prevents capture."],bookings:[],decisions:[],revision:12,observed_at:"2026-10-24T12:00:00Z"})});
  vi.stubGlobal("fetch",fetch);
  render(<PaymentJustification orderId="order-test"/>);
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("Inspect financial evidence"));
  expect(await screen.findByText(/Frozen SF dataset.*0.25/)).toBeTruthy();
  expect(screen.getByText(/Are those memberships current/)).toBeTruthy();
  expect(screen.getByText("An unresolved dispute prevents capture.")).toBeTruthy();
  expect(screen.getByText(/0 persisted terminal booking/)).toBeTruthy();
  expect(fetch.mock.calls[0][0]).toContain("/orders/order-test/payment-justification");
});

it("does not present settled funds as an active human-review task", ()=>{
  const order={page:{payment:{payment:{state:"voided"},simulated:true}}} as LiveOrder;
  render(<LiveReview order={order}/>);
  expect(screen.getByText(/This does not resolve any factual uncertainty/)).toBeTruthy();
  expect(screen.queryByRole("button",{name:"approve"})).toBeNull();
});
