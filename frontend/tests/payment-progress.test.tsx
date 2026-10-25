import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, expect, it, vi} from "vitest";
import {LiveDelivery, PaymentStatus} from "../components/run/live-order";
import type {PaymentStateChanged} from "../lib/runs.generated";
import type {RunEvent, Verdict} from "../lib/run/contract";
import {project, type FoldContext} from "../lib/run/fold";
import type {LiveOrder} from "../lib/run/use-live-order";

const at="2026-10-24T12:00:05Z";
const ctx:FoldContext={lane:"shared",ending:"human",learned:false,live:true,contract:{version:1,buyer:"Buyer",title:"SF dataset",price:1,lines:[]}};
const payment={id:"payment-1",amount:1,mock:true};
const initial:RunEvent[]=[
  {seq:1,at,type:"steps_planned",steps:[
    {id:"review",kind:"review",title:"Customer review",detail:"Review"},
    {id:"captured",kind:"captured",title:"Captured",detail:"Settlement"},
    {id:"investigate",kind:"investigate",title:"Investigate",detail:"Evidence"},
    {id:"verdict",kind:"verdict",title:"Finding",detail:"Assessment"},
  ]},
  {seq:2,at,type:"step_started",step:"review"},
  {seq:3,at,type:"step_started",step:"investigate"},
];
const finding=(kind:Verdict["kind"]):RunEvent=>({seq:4,at,type:"verdict",step:"verdict",allowedBy:"finding",verdict:{kind,decidedBy:"rules",reason:"Frozen scope evidence",evidenceIds:[]}});
const state=(value:PaymentStateChanged["state"],seq=5):RunEvent=>({seq,at,type:"payment_state_changed",payment,state:value});

afterEach(cleanup);

it("finishes the assessment and review while capture is pending, without showing paid",()=>{
  const view=project([...initial,finding("disagree"),state("capture_pending")],ctx);
  expect(view.nodes.investigate.status).toBe("done");
  expect(view.nodes.verdict.status).toBe("done");
  expect(view.nodes.review.status).toBe("done");
  expect(view.nodes.captured.status).toBe("running");
  expect(view.nodes.captured.step.title).toBe("Release pending");
  expect(view.orb).toEqual({step:"captured",mode:"wait"});
  expect(view.coin?.done).toBe(false);
  expect(view.captured).toEqual({});
});

it("keeps an unresolved finding waiting and does not complete review",()=>{
  const view=project([...initial,finding("grey"),state("funded")],ctx);
  expect(view.nodes.investigate.status).toBe("waiting");
  expect(view.nodes.verdict.status).toBe("grey");
  expect(view.nodes.review.status).toBe("running");
  expect(view.nodes.captured.status).toBe("idle");
  expect(view.coin?.done).toBe(false);
});

it("only confirms settlement on a confirmed state and retains later uncertainty",()=>{
  const events=[...initial,finding("disagree"),state("capture_pending"),state("captured",6)];
  const view=project(events,ctx);
  expect(view.nodes.captured.status).toBe("done");
  expect(view.nodes.captured.step.title).toBe("Captured");
  expect(view.coin?.done).toBe(true);
  const uncertain=project([...events,state("reorg_hold",7)],ctx);
  expect(uncertain.nodes.captured.status).toBe("waiting");
  expect(uncertain.coin?.done).toBe(false);
});

it("resets pending settlement when a pre-submission capture is invalidated",()=>{
  const view=project([...initial,finding("disagree"),state("capture_pending"),state("funded",6)],ctx);
  expect(view.nodes.captured.status).toBe("idle");
  expect(view.nodes.review.status).toBe("running");
});

it("also projects historical state events and leaves recorded demo behavior intact",()=>{
  const events:RunEvent[]=[...initial,state("funded"),{seq:6,at,type:"state_changed",step:"review",state:"delivered",reason:"Earlier complaint explanation",paymentState:"capture_pending",binding:{runId:"run",orderId:"order",snapshotId:"snapshot",revision:2,deliveryVersion:1,evidenceVersion:1}}];
  const view=project(events,ctx);
  expect(view.nodes.captured.status).toBe("running");
  expect(view.nodes.review.waitingOn).toBeUndefined();
  expect(view.caption).toBe("Review complete. Waiting for payment confirmation.");
  expect(project(events,{...ctx,live:false}).nodes.captured.status).toBe("idle");
});

it("replaces the remaining review countdown with truthful pending confirmation",()=>{
  const order={
    page:{server_time:at,reviewClosesAt:"2026-10-24T12:01:00Z",payment:{payment:{state:"capture_pending"},simulated:true}},
    view:project([],ctx),lines:[],binding:{orderId:"order-1"},
    delivery:{artifactId:"csv-1",file:"counts.csv",version:1,rows:[]},enabled:()=>false,
  } as unknown as LiveOrder;
  const shown=render(<><PaymentStatus order={order}/><LiveDelivery order={order} working={vi.fn()}/></>);
  expect(shown.container.querySelector(".wallet")?.textContent).toBe("Release pending, Mock");
  expect(screen.getByText("Review complete. Payment release is pending confirmation.")).toBeTruthy();
  expect(screen.queryByText(/Review window:/)).toBeNull();
  expect(screen.queryByText(/Paid to provider/)).toBeNull();
  order.page!.payment!.payment.state="captured";
  shown.rerender(<><PaymentStatus order={order}/><LiveDelivery order={order} working={vi.fn()}/></>);
  expect(shown.container.querySelector(".wallet")?.textContent).toBe("Paid to provider, Mock");
  expect(screen.getByText("Review complete. Payment confirmed.")).toBeTruthy();
});
