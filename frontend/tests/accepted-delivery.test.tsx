import {act, cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {afterEach, beforeEach, expect, it, vi} from "vitest";
import LiveRun from "../components/run/live-run";
import type {PaymentStateChanged, RunPage} from "../lib/runs.generated";

const at="2026-10-24T12:00:00Z";
const binding={runId:"run-1",orderId:"order-1",snapshotId:"snapshot-1",deliveryVersion:1,evidenceVersion:1,revision:1};
const accepted={snapshot_id:binding.snapshotId,delivery_version:1,evidence_revision:1};
const response=(data:unknown,status=200)=>new Response(JSON.stringify(data),{status});

function setup(reject=false, simulated=true) {
  const payment={id:"payment-1",amount:1,mock:simulated};
  let page={
    events:[
      {seq:1,at,type:"steps_planned",steps:[
        {id:"paid",kind:"paid",title:"Funding",detail:"Funding"},
        {id:"review",kind:"review",title:"Customer review",detail:"Review"},
        {id:"captured",kind:"captured",title:"Captured",detail:"Settlement"},
      ]},
      {seq:2,at,type:"delivery_ready",step:"review",delivery:{artifactId:"csv-1",file:"counts.csv",version:1,rows:[]}},
      {seq:3,at,type:"payment_state_changed",payment,state:"funded"},
    ],
    next_after:3,high_watermark:3,caught_up:true,poll_after_ms:100000,
    binding,request:{status:"accepted",revision:1},server_time:at,
    available_actions:[{action:"accept",enabled:true}],
    payment:{payment:{state:"funded",terms:{mode:simulated?"mock":"base_sepolia"}},operations:[],simulated},
  } as unknown as RunPage;
  let release:()=>void=()=>{};
  let hold:Promise<void> | undefined;
  const fetcher=vi.fn(async(url:string,options?:RequestInit)=>{
    if(options?.method==="POST") {
      if(!url.endsWith("/acceptance"))throw new Error("Unexpected command");
      if(reject)return response({detail:"The delivery changed"},409);
      hold=new Promise(resolve=>{release=resolve;});
      return response({order:{customer_acceptance:accepted,revision:2}});
    }
    await hold;
    const after=Number(new URL(url,"http://fixture").searchParams.get("after"));
    return response({...page,events:page.events.filter(event=>event.seq>after)});
  });
  vi.stubGlobal("fetch",fetcher);
  return {
    fetcher,
    publish(state:PaymentStateChanged["state"],evidenceVersion=1) {
      const seq=page.next_after+1;
      page={...page,binding:{...binding,revision:seq,evidenceVersion},available_actions:[],
        events:[...page.events,{seq,at,type:"payment_state_changed",payment,state}],next_after:seq,high_watermark:seq,
        payment:{...page.payment!,payment:{...page.payment!.payment,state}},
      };
      hold=undefined;release();
    },
  };
}

beforeEach(()=>{
  localStorage.clear();localStorage.setItem("datumco.live-run.v1",JSON.stringify({id:"run-1"}));
  vi.stubGlobal("ResizeObserver",class {observe(){} disconnect(){}});
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});

it("keeps the mock release visibly processing until settlement is confirmed",async()=>{
  const fixture=setup();
  render(<LiveRun/>);
  fireEvent.click(await screen.findByRole("button",{name:"Accept verified delivery"}));
  const complete=await screen.findByRole("button",{name:"Processing payment, running"});
  expect(complete.classList.contains("n-running")).toBe(true);
  expect(screen.getByText("Delivery accepted. Preparing the simulated payment release.")).toBeTruthy();
  expect(document.querySelector(".canvas-agent.departed")).toBeNull();
  expect(document.querySelector(".coin")).toBeTruthy();
  expect(screen.queryByRole("button",{name:"Captured, done"})).toBeNull();
  await act(async()=>fixture.publish("capture_pending"));
  await waitFor(()=>expect((screen.getByRole("button",{name:"Refresh"}) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole("button",{name:"Processing payment, running"}));
  expect(await screen.findByText("Review complete. Payment release is pending confirmation.")).toBeTruthy();
  fireEvent.click(screen.getByRole("button",{name:"Close panel"}));
  fixture.publish("captured");
  fireEvent.click(screen.getByRole("button",{name:"Refresh"}));
  expect(await screen.findByRole("button",{name:"Captured, done"})).toBeTruthy();
  expect(screen.getByText("Confirmed settlement")).toBeTruthy();
  expect(document.querySelector(".coin.done")).toBeTruthy();
});

it.each([true,false].flatMap(simulated=>(["uncertain","failed","reorg_hold","funded"] as const).map(state=>({simulated,state}))))("removes processing when payment becomes $state or acceptance is invalidated (mock=$simulated)",async({simulated,state})=>{
  const fixture=setup(false,simulated);
  render(<LiveRun/>);
  fireEvent.click(await screen.findByRole("button",{name:"Accept verified delivery"}));
  await screen.findByRole("button",{name:"Processing payment, running"});
  await act(async()=>fixture.publish("capture_pending"));
  await waitFor(()=>expect((screen.getByRole("button",{name:"Refresh"}) as HTMLButtonElement).disabled).toBe(false));
  fixture.publish(state,state==="funded"?2:1);
  fireEvent.click(screen.getByRole("button",{name:"Refresh"}));
  await waitFor(()=>expect(screen.queryByRole("button",{name:"Processing payment, running"})).toBeNull());
  expect(document.querySelector('[data-step="captured"].n-done')).toBeNull();
  expect(document.querySelector(".canvas-agent.departed")).toBeNull();
});

it("does not celebrate an acceptance rejected as stale",async()=>{
  setup(true);
  render(<LiveRun/>);
  fireEvent.click(await screen.findByRole("button",{name:"Accept verified delivery"}));
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button",{name:"Run"}));
  expect(screen.queryByRole("button",{name:"Processing payment, running"})).toBeNull();
  expect(document.querySelector('[data-step="captured"].n-done')).toBeNull();
});

it("shows a working agent during mock funding confirmation",async()=>{
  const fixture=setup();
  fixture.publish("funding_pending");
  render(<LiveRun/>);
  fireEvent.click(screen.getByRole("button",{name:"Run"}));
  expect(await screen.findByRole("button",{name:"Processing payment, running"})).toBeTruthy();
  expect(screen.getByText("Funding authorized for this demo. Simulating confirmation before production starts.")).toBeTruthy();
  expect(document.querySelector(".canvas-agent.departed")).toBeNull();
  fixture.publish("funded");
  fireEvent.click(screen.getByRole("button",{name:"Refresh"}));
  await waitFor(()=>expect(screen.queryByRole("button",{name:"Processing payment, running"})).toBeNull());
});

it("waits for confirmed wallet capture before completing the canvas and hiding the agent",async()=>{
  const fixture=setup(false,false);
  render(<LiveRun/>);
  fireEvent.click(await screen.findByRole("button",{name:"Accept verified delivery"}));
  expect(await screen.findByRole("button",{name:"Processing payment, running"})).toBeTruthy();
  expect(screen.getByText("Delivery accepted. Preparing payment release.")).toBeTruthy();
  expect(document.querySelector(".canvas-agent.departed")).toBeNull();
  expect(document.querySelector(".coin.done")).toBeNull();
  expect(document.querySelector('[data-step="captured"].n-done')).toBeNull();
  expect(screen.queryByText("Simulated payment · no funds move")).toBeNull();
  await act(async()=>fixture.publish("capture_pending"));
  await waitFor(()=>expect((screen.getByRole("button",{name:"Refresh"}) as HTMLButtonElement).disabled).toBe(false));
  expect(screen.getByRole("button",{name:"Processing payment, running"})).toBeTruthy();
  expect(screen.getByText("Review complete. Waiting for payment confirmation.")).toBeTruthy();
  expect(document.querySelector(".canvas-agent.departed")).toBeNull();
  expect(document.querySelector('[data-step="captured"].n-done')).toBeNull();
  expect(document.querySelector(".coin.done")).toBeNull();
  fixture.publish("captured");
  fireEvent.click(screen.getByRole("button",{name:"Refresh"}));
  expect(await screen.findByRole("button",{name:"Captured, done"})).toBeTruthy();
  expect(screen.getByText("Payment is confirmed and recorded.")).toBeTruthy();
  expect(document.querySelector(".canvas-agent.departed")).toBeTruthy();
  expect(document.querySelector(".coin.done")).toBeTruthy();
});
