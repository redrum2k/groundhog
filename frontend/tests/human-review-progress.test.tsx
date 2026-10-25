import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, expect, it} from "vitest";
import {LiveReview} from "../components/run/live-order";
import {project, type FoldContext} from "../lib/run/fold";
import type {RunEvent} from "../lib/run/contract";
import type {LiveOrder} from "../lib/run/use-live-order";

afterEach(cleanup);
const at="2026-10-25T03:51:59Z";
const binding={runId:"run",orderId:"order",snapshotId:"snapshot",revision:10,deliveryVersion:1,evidenceVersion:3};
const ctx:FoldContext={lane:"shared",ending:"human",learned:false,live:true,contract:{version:1,buyer:"Buyer",title:"Dataset",price:1,lines:[]}};
const events:RunEvent[]=[
  {seq:1,at,type:"steps_planned",steps:[
    {id:"review",kind:"review",title:"Customer review",detail:"Review"},
    {id:"captured",kind:"captured",title:"Captured",detail:"Settlement"},
    {id:"investigate",kind:"investigate",title:"Investigate",detail:"Evidence"},
    {id:"verdict",kind:"verdict",title:"Finding",detail:"Evidence assessment"},
    {id:"decide",kind:"decide",title:"Human reviews",detail:"Review"},
  ]},
  {seq:2,at,type:"step_started",step:"investigate"},
  {seq:3,at,type:"verdict",step:"verdict",allowedBy:"Current evidence",verdict:{kind:"grey",reason:"Evidence remains inconclusive",evidenceIds:[],decidedBy:"unresolved"}},
  {seq:4,at,type:"state_changed",step:"review",state:"human_review",reason:"Evidence unresolved",binding,paymentState:"funded"},
  {seq:5,at,type:"step_waiting",step:"decide",waitingOn:"Human review"},
];
const returned=(state:"void_pending"|"voided"):RunEvent[]=>[
  ...events,
  {seq:6,at,type:"controller_decided",step:"decide",action:"approve",by:"reviewer:local-trusted",note:"Return the uncaptured funds",binding},
  {seq:7,at,type:"payment_state_changed",payment:{id:"payment",amount:1,mock:true},state},
  {seq:8,at,type:"state_changed",step:"review",state:state==="voided"?"closed":"human_review",reason:"Evidence unresolved",binding,paymentState:state},
  ...(state==="void_pending"?[{seq:9,at,type:"step_waiting",step:"decide",waitingOn:"Evidence unresolved"} as RunEvent]:[]),
];

it("stops the investigation spinner when the case reaches human review",()=>{
  const view=project(events,ctx);
  expect(view.nodes.investigate.status).toBe("waiting");
  expect(view.nodes.review.status).toBe("waiting");
  expect(view.nodes.verdict.status).toBe("grey");
  expect(view.orb.step).toBe("decide");
});

it.each(["void_pending","voided"] as const)("preserves the human decision and shows %s instead of another approval form",state=>{
  const view=project(returned(state),ctx);
  expect(view.nodes.decide.status).toBe("done");
  expect(view.nodes.verdict.status).toBe("done");
  expect(view.nodes.verdict.chip).toBe("Reviewed");
  expect(view.nodes.verdict.verdict).toMatchObject({kind:"grey",reason:"Evidence remains inconclusive"});
  expect(view.nodes.captured.status).toBe(state==="voided"?"done":"running");
  expect(view.nodes.captured.step.title).toBe(state==="voided"?"Funds returned":"Return pending");
  expect(view.caption).not.toBe("Evidence unresolved");
  const order={view,page:{payment:{payment:{state},simulated:true}},needsHumanReview:state!=="voided",enabled:()=>false} as unknown as LiveOrder;
  render(<LiveReview order={order}/>);
  expect(screen.getByText("Return approved")).toBeTruthy();
  expect(screen.getByText("Return the uncaptured funds")).toBeTruthy();
  expect(screen.getByRole("status").textContent).toContain(state==="voided"?"Funds returned":"Waiting for confirmation");
  expect(screen.queryByRole("textbox")).toBeNull();
});

it("shows a failed return explicitly even if an older funding audit reports held funds",()=>{
  const view=project(returned("void_pending"),ctx);
  const order={view,page:{available_actions:[],payment:{payment:{state:"funded"},operations:[{intent:{action:"void"},state:"failed",error:"eth_getCode unavailable"}]}},needsHumanReview:true,enabled:()=>false,reason:""} as unknown as LiveOrder;
  render(<LiveReview order={order}/>);
  expect(screen.getByRole("status").textContent).toContain("Return could not be submitted");
  expect(screen.getByRole("status").textContent).toContain("eth_getCode unavailable");
  expect(screen.queryByText("Waiting for confirmation")).toBeNull();
});

it("restores the review indicator when a failed return genuinely requires human attention",()=>{
  const view=project([
    ...returned("void_pending"),
    {seq:10,at,type:"payment_state_changed",payment:{id:"payment",amount:1,mock:true},state:"funded"},
    {seq:11,at,type:"state_changed",step:"review",state:"human_review",reason:"Return submission failed",binding,paymentState:"funded"},
  ],ctx);
  expect(view.nodes.verdict.status).toBe("grey");
  expect(view.nodes.verdict.chip).toBe("Needs review");
  expect(view.nodes.decide.status).toBe("waiting");
});
