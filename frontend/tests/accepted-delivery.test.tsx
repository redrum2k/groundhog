import {act, cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {afterEach, beforeEach, expect, it, vi} from "vitest";
import LiveRun from "../components/run/live-run";
import type {PaymentStateChanged, RunPage} from "../lib/runs.generated";

const at="2026-10-24T12:00:00Z";
const binding={runId:"run-1",orderId:"order-1",snapshotId:"snapshot-1",deliveryVersion:1,evidenceVersion:1,revision:1};
const accepted={snapshot_id:binding.snapshotId,delivery_version:1,evidence_revision:1};
const payment={id:"payment-1",amount:1,mock:true};
const response=(data:unknown,status=200)=>new Response(JSON.stringify(data),{status});

function setup(reject=false) {
  let page={
    events:[
      {seq:1,at,type:"steps_planned",steps:[
        {id:"review",kind:"review",title:"Customer review",detail:"Review"},
        {id:"captured",kind:"captured",title:"Captured",detail:"Settlement"},
      ]},
      {seq:2,at,type:"delivery_ready",step:"review",delivery:{artifactId:"csv-1",file:"counts.csv",version:1,rows:[]}},
      {seq:3,at,type:"payment_state_changed",payment,state:"funded"},
    ],
    next_after:3,high_watermark:3,caught_up:true,poll_after_ms:20,
    binding,request:{status:"accepted",revision:1},server_time:at,
    available_actions:[{action:"accept",enabled:true}],
    payment:{payment:{state:"funded",terms:{mode:"mock"}},operations:[],simulated:true},
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

it("celebrates acknowledged delivery acceptance before the refresh, then shows actual settlement",async()=>{
  const fixture=setup();
  render(<LiveRun/>);
  fireEvent.click(await screen.findByRole("button",{name:"Accept verified delivery"}));
  const complete=await screen.findByRole("button",{name:"Dataset accepted, done"});
  expect(complete.classList.contains("n-done")).toBe(true);
  expect(screen.getByText("Dataset accepted. Payment is processing in the background.")).toBeTruthy();
  expect(document.querySelector(".canvas-agent.departed")).toBeTruthy();
  expect(document.querySelector(".coin")).toBeNull();
  expect(screen.queryByRole("button",{name:"Captured, done"})).toBeNull();
  await act(async()=>fixture.publish("capture_pending"));
  fireEvent.click(screen.getByRole("button",{name:"Dataset accepted, done"}));
  expect(await screen.findByText("Review complete. Payment release is pending confirmation.")).toBeTruthy();
  fireEvent.click(screen.getByRole("button",{name:"Close panel"}));
  fixture.publish("captured");
  expect(await screen.findByRole("button",{name:"Captured, done"})).toBeTruthy();
  expect(screen.getByText("Confirmed settlement")).toBeTruthy();
  expect(document.querySelector(".coin.done")).toBeTruthy();
});

it.each(["uncertain","failed","reorg_hold","funded"] as const)("removes the success presentation when payment becomes %s or acceptance is invalidated",async state=>{
  const fixture=setup();
  render(<LiveRun/>);
  fireEvent.click(await screen.findByRole("button",{name:"Accept verified delivery"}));
  await screen.findByRole("button",{name:"Dataset accepted, done"});
  await act(async()=>fixture.publish("capture_pending"));
  fixture.publish(state,state==="funded"?2:1);
  await waitFor(()=>expect(screen.queryByRole("button",{name:"Dataset accepted, done"})).toBeNull());
  expect(document.querySelector('[data-step="captured"].n-done')).toBeNull();
  expect(document.querySelector(".canvas-agent.departed")).toBeNull();
});

it("does not celebrate an acceptance rejected as stale",async()=>{
  setup(true);
  render(<LiveRun/>);
  fireEvent.click(await screen.findByRole("button",{name:"Accept verified delivery"}));
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button",{name:"Run"}));
  expect(screen.queryByRole("button",{name:"Dataset accepted, done"})).toBeNull();
  expect(document.querySelector('[data-step="captured"].n-done')).toBeNull();
});
