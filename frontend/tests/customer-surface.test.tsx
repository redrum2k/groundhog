import {cleanup, fireEvent, render, screen, within} from "@testing-library/react";
import {afterEach, beforeEach, expect, it, vi} from "vitest";
import LiveRun from "../components/run/live-run";
import {LiveEvidence} from "../components/run/live-order";
import type {LiveOrder} from "../lib/run/use-live-order";
import type {RunPage} from "../lib/runs.generated";

const at="2026-10-25T04:00:00Z";
const audit="Buyer complaint: source authenticity. Finding: UNKNOWN. Provenance: model. Assessor: claude (assessment-v1). INTERNAL_SCHEMA_MARKER";
const explanation="I need more evidence to resolve your concern.";
const page={
  next_after:5,high_watermark:5,caught_up:true,poll_after_ms:100000,server_time:at,
  binding:null,available_actions:[],request:{status:"accepted",revision:1},quote:null,payment:null,
  events:[
    {seq:1,at,type:"steps_planned",steps:[{id:"clarify",kind:"clarify",title:"Clarify",detail:"Agreement"},{id:"verdict",kind:"verdict",title:"Finding",detail:"Assessment"}]},
    {seq:2,at,type:"message",step:"clarify",message:{id:"intro",from:"agent",text:"What dataset do you need?"}},
    {seq:3,at,type:"message",step:"clarify",message:{id:"buyer",from:"buyer",text:"Please check the source."}},
    {seq:4,at,type:"verdict",step:"verdict",allowedBy:"verified evidence",verdict:{kind:"grey",reason:explanation,decidedBy:"unresolved",evidenceIds:[]}},
    {seq:5,at,type:"message",step:"verdict",message:{id:"case:finding-message:2",from:"agent",text:audit}},
  ],
} as unknown as RunPage;

beforeEach(()=>{
  localStorage.clear();
  localStorage.setItem("datumco.live-run.v1",JSON.stringify({id:"run"}));
  vi.stubGlobal("ResizeObserver",class {observe(){} disconnect(){}});
  vi.stubGlobal("fetch",vi.fn(async()=>Response.json(page)));
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();localStorage.clear();});

it("keeps resolved diagnostic JSON out of the customer evidence surface",()=>{
  const order={binding:null,view:{evidence:{}},resolved:'{"input_schema":"private diagnostic payload"}'} as unknown as LiveOrder;
  const {container}=render(<LiveEvidence order={order}/>);
  expect(container.textContent).toBe("");
});

it("shows the customer conversation and result without internal assessment narration",async()=>{
  render(<LiveRun/>);
  expect(await screen.findByText(explanation)).toBeTruthy();
  expect(screen.getByText("Please check the source.")).toBeTruthy();
  expect(screen.queryByText(audit)).toBeNull();
  expect(screen.queryByText("Inspect persisted evidence")).toBeNull();
  expect(screen.queryByText("Selected evidence")).toBeNull();
  fireEvent.click(screen.getByRole("button",{name:"Run"}));
  fireEvent.click(screen.getByRole("button",{name:"Finding, grey"}));
  expect(within(screen.getByRole("complementary",{name:"Finding"})).getByText(explanation)).toBeTruthy();
  expect(document.body.textContent).not.toContain("INTERNAL_SCHEMA_MARKER");
  expect(document.body.textContent).not.toContain("Assessor:");
});

it("puts Summit Fitness in the header as the only customer identity and opens its wallet",async()=>{
  render(<LiveRun/>);
  await screen.findByText(explanation);
  const header=screen.getByRole("banner");
  expect(within(header).getByText("Financial agent for Bayline Data")).toBeTruthy();
  const account=within(header).getByRole("button",{name:/^Summit Fitness.*wallet settings/});
  expect(screen.getAllByText("Summit Fitness")).toHaveLength(1);
  expect(within(screen.getByRole("main",{name:"Customer view"})).queryByText("Summit Fitness")).toBeNull();
  expect(screen.queryByRole("button",{name:/Source learning/})).toBeNull();
  expect(document.body.textContent).not.toContain("The order · synthetic data");
  expect(document.body.textContent).not.toContain("Live backend");
  expect(account.textContent).not.toContain("Buyer ·");
  fireEvent.click(account.querySelector("svg")!);
  expect(await screen.findByRole("dialog",{name:"Buyer wallet"})).toBeTruthy();
  expect(screen.getByRole("button",{name:"Connect MetaMask"})).toBeTruthy();
});
