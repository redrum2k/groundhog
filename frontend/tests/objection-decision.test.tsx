import {cleanup, fireEvent, render, screen, waitFor, within} from "@testing-library/react";
import {afterEach, beforeEach, expect, it, vi} from "vitest";
import LiveRun from "../components/run/live-run";
import {currentAssessment} from "../lib/run/assessment";
import type {RunPage} from "../lib/runs.generated";
import fixture from "./fixtures/objection-page.json";

let page:RunPage;
let fetcher:ReturnType<typeof vi.fn>;
beforeEach(()=>{
  page={...structuredClone(fixture),poll_after_ms:20} as unknown as RunPage;
  localStorage.clear();localStorage.setItem("datumco.live-run.v1",JSON.stringify({id:"preview"}));
  vi.stubGlobal("ResizeObserver",class {observe(){} disconnect(){}});
  fetcher=vi.fn(async(url:string,options?:RequestInit)=>{
    if(options?.method==="POST")return Response.json({...page.quote,request_id:"new-offer"});
    const after=Number(new URL(url,"http://fixture").searchParams.get("after"));
    return Response.json({...page,events:page.events.filter(event=>event.seq>after)});
  });
  vi.stubGlobal("fetch",fetcher);
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();localStorage.clear();});

it("focuses the decision, explains scope and keeps actual funds held",async()=>{
  render(<LiveRun/>);
  await screen.findByRole("heading",{name:"Oakland wasn’t included in this order"});
  fireEvent.click(screen.getByRole("button",{name:"Run"}));
  const panel=await screen.findByRole("complementary",{name:"Finding"});
  expect(document.activeElement).toBe(panel);
  for(const step of ["investigate","verdict"]) {
    const node=document.querySelector(`[data-step="${step}"]`)!;
    expect(node.classList.contains("outcome-not-upheld")).toBe(true);
    expect(node.classList.contains("n-done")).toBe(true);
    expect(node.classList.contains("n-fail")).toBe(false);
    expect(node.textContent).toContain("Objection not upheld");
  }
  expect(within(panel).getByText("Oakland should be included in the delivery.")).toBeTruthy();
  expect(within(panel).getAllByText("San Francisco city ZIPs only")).toHaveLength(2);
  expect(within(panel).getByText("Held in escrow")).toBeTruthy();
  expect(within(panel).getByText("Demo: no funds move")).toBeTruthy();
  fireEvent.click(within(panel).getByText("Read full assessment"));
  expect(within(panel).getByText(/The complaint asserts Oakland should be included/)).toBeTruthy();
  fireEvent.click(within(panel).getByText("View agreement and supporting evidence"));
  expect(within(panel).getByText("Frozen coverage registry")).toBeTruthy();
  fireEvent.click(within(panel).getByRole("button",{name:"Review delivery"}));
  expect(screen.getByRole("complementary",{name:"Customer review"})).toBeTruthy();
  expect(fetcher.mock.calls.every(([,options])=>options?.method!=="POST")).toBe(true);
});

it("requests a separate quote without accepting or funding it",async()=>{
  render(<LiveRun/>);
  fireEvent.click(await screen.findByRole("button",{name:"Request an Oakland quote"}));
  await within(screen.getByRole("region",{name:"Complaint assessment"})).findByRole("button",{name:"Review separate offer"});
  const posts=fetcher.mock.calls.filter(([,options])=>options?.method==="POST");
  expect(posts).toHaveLength(1);
  expect(posts[0][0]).toBe("/api/live/runs/preview/offers");
  expect(JSON.parse(posts[0][1].body)).toMatchObject({scope:"oakland",binding:page.binding});
});

it("does not reopen a dismissed result on each poll or paint a new dispute red",async()=>{
  render(<LiveRun/>);
  await screen.findByRole("heading",{name:"Oakland wasn’t included in this order"});
  fireEvent.click(screen.getByRole("button",{name:"Run"}));
  await screen.findByRole("complementary",{name:"Finding"});
  fireEvent.click(screen.getByRole("button",{name:"Close panel"}));
  const polls=fetcher.mock.calls.length;
  await waitFor(()=>expect(fetcher.mock.calls.length).toBeGreaterThan(polls));
  expect(screen.queryByRole("complementary",{name:"Finding"})).toBeNull();
  const seq=page.next_after+1;
  page={...page,events:[...page.events,{seq,at:page.server_time,type:"dispute_opened",step:"investigate",dispute:{id:"new-dispute",claim:"Check the source",raisedBy:"buyer"}}],next_after:seq,high_watermark:seq};
  await waitFor(()=>expect(document.querySelector(".nd.outcome-not-upheld")).toBeNull());
});

it("invalidates the current decision on evidence changes without confusing payment revisions",()=>{
  expect(currentAssessment(page.events,page.binding)).toBeTruthy();
  expect(currentAssessment(page.events,{...page.binding!,revision:100})).toBeTruthy();
  expect(currentAssessment(page.events,{...page.binding!,evidenceVersion:2})).toBeUndefined();
  expect(currentAssessment(page.events,{...page.binding!,deliveryVersion:2})).toBeUndefined();
});

it("keeps an unresolved assessment out of the red rejection styling",async()=>{
  page.events=page.events.map(event=>event.type==="verdict"?{...event,verdict:{...event.verdict,kind:"grey",finding:null,reason:"More evidence is needed."}}:event);
  render(<LiveRun/>);
  await screen.findByText("More evidence is needed.");
  fireEvent.click(screen.getByRole("button",{name:"Run"}));
  expect(document.querySelector(".nd.outcome-not-upheld")).toBeNull();
  expect(screen.queryByText("Objection not upheld")).toBeNull();
});


it("keeps the objection control visible and enables another submission after resolution",async()=>{
  page.available_actions=[{action:"accept",enabled:true,reason:"Resolved"},{action:"dispute",enabled:true,reason:"Previous case resolved"}];
  render(<LiveRun/>);
  const button=await screen.findByRole("button",{name:"Object again"}) as HTMLButtonElement;
  expect(button.disabled).toBe(false);
  fireEvent.click(button);
  fireEvent.change(screen.getByLabelText("Your complaint"),{target:{value:"ZIP 94112 is missing"}});
  fireEvent.click(screen.getByRole("button",{name:"Send complaint"}));
  await waitFor(()=>expect(fetcher.mock.calls.some(([url,options])=>url.endsWith("/complaints") && options?.method==="POST")).toBe(true));
  const call=fetcher.mock.calls.find(([url,options])=>url.endsWith("/complaints") && options?.method==="POST")!;
  expect(JSON.parse(call[1].body)).toMatchObject({text:"ZIP 94112 is missing",expected_revision:page.binding!.revision});
});

it("keeps the repeat objection button visible but disabled while a case needs review",async()=>{
  page.available_actions=[{action:"approve",enabled:true,reason:"Human review required"}];
  render(<LiveRun/>);
  const button=await screen.findByRole("button",{name:"Object again"}) as HTMLButtonElement;
  expect(button.disabled).toBe(true);
  fireEvent.click(button);
  expect(screen.queryByLabelText("Your complaint")).toBeNull();
});

it.each(["void_pending","voided"] as const)("clears the stale review prompt after approval with payment %s",async(state)=>{
  page.events=page.events.map(event=>event.type==="verdict"?{...event,verdict:{...event.verdict,kind:"grey",finding:null,reason:"Evidence remains inconclusive."}}:event);
  const seq=page.next_after;
  page.events.push(
    {seq:seq+1,at:page.server_time,type:"controller_decided",step:"decide",action:"approve",by:"Human",note:"Return the uncaptured funds",binding:page.binding!},
    {seq:seq+2,at:page.server_time,type:"payment_state_changed",payment:{id:"payment-preview",amount:1,mock:true},state},
    {seq:seq+3,at:page.server_time,type:"state_changed",step:"review",state:state==="voided"?"closed":"human_review",reason:"Evidence unresolved",binding:page.binding!,paymentState:state},
  );
  page.next_after=page.high_watermark=seq+3;
  page.payment!.payment.state=state;
  // The backend can retain these actions while an approved return is reconciling.
  page.available_actions=[{action:"reject",enabled:true,reason:"Human review retained"}];
  render(<LiveRun/>);
  await screen.findByText("Evidence remains inconclusive.");
  fireEvent.click(screen.getByRole("button",{name:"Run"}));
  await waitFor(()=>expect(document.querySelector('[data-step="verdict"]')?.textContent).toContain("Reviewed"));
  expect(document.querySelector('[data-step="verdict"]')?.classList.contains("n-done")).toBe(true);
  expect(screen.queryByText("Needs review")).toBeNull();
  expect(screen.queryByRole("button",{name:"Escalated to a person: settle the dispute"})).toBeNull();
  fireEvent.click(screen.getByRole("button",{name:"Human review"}));
  expect(screen.getByText("Return approved")).toBeTruthy();
  expect(screen.queryByLabelText("Reason or evidence answer")).toBeNull();
});
