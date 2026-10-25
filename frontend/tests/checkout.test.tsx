import {act, cleanup, fireEvent, render, renderHook, screen, waitFor, within} from "@testing-library/react";
import {afterEach, beforeEach, expect, it, vi} from "vitest";
import LiveRun from "../components/run/live-run";
import {checkout} from "../lib/run/checkout";
import {useCheckout} from "../lib/run/use-checkout";
import type {CanvasBinding, FundingPreparation, Quote, RunPage} from "../lib/runs.generated";

const buyer = "0x" + "4".repeat(40);
const signature = "0x" + "a".repeat(130);
const binding = {runId:"run-1", orderId:"order-1", revision:1, snapshotId:"snapshot-1", deliveryVersion:0, evidenceVersion:1} as CanvasBinding;
const expected = {snapshot_id:"snapshot-1", delivery_version:0, evidence_revision:1};
const quote = {
  quote_id:"quote-1", amount:{amount_minor:100}, specification:{terms:{}},
  payment_terms:{mode:"base_sepolia", amount_atomic:"1000000", payment_hash:"hash-1", payment_info:{payer:buyer, pre_approval_expiry:"1792872600", authorization_expiry:"1792876200"}},
} as Quote;
const preparation = {order_id:"order-1", funding_attempt_id:"attempt-1", terms:quote.payment_terms, typed_data:{message:{value:"1000000"}}} as FundingPreparation;
const accepted = {order:{snapshot:{order_id:"order-1"}, revision:1, binding:expected}, available_actions:["prepare_funding"]};
const current = {
  events:[], next_after:0, high_watermark:0, caught_up:true, poll_after_ms:20,
  binding, quote, request:{status:"accepted", revision:3},
  available_actions:[{action:"prepare_funding",enabled:true}],
  payment:{payment:{state:"awaiting_signature",terms:quote.payment_terms},operations:[]},
} as unknown as RunPage;
const response = (body:unknown, status=200) => new Response(JSON.stringify(body), {status, headers:{"Content-Type":"application/json"}});

function setup(options: {mock?:boolean; initialQuote?:boolean} = {}) {
  const selectedQuote = options.mock ? {...quote, payment_terms:{...quote.payment_terms!,mode:"mock" as const}} : quote;
  const state: {page:RunPage} = {page:options.initialQuote ? {...current,binding:null,payment:null,available_actions:[{action:"accept_quote",enabled:true,reason:"Quote ready"}],quote:selectedQuote} : {...current,quote:selectedQuote}};
  const wallet = {request:vi.fn(async ({method}:{method:string}) => {
    if (method === "eth_accounts") return [buyer];
    if (method === "eth_chainId") return "0x14a34";
    if (method === "eth_signTypedData_v4") return signature;
    throw new Error(`Unexpected wallet method: ${method}`);
  })};
  const fetcher = vi.fn(async (url:string, options?:RequestInit) => {
    if (options?.method === "POST") {
      if (url.endsWith("quote-acceptance")) {
        state.page = {...current, quote:selectedQuote};
        return response(accepted);
      }
      if (url.endsWith("funding-preparation")) return response({...preparation,terms:selectedQuote.payment_terms});
      if (url.endsWith("funding-authorizations")) {
        state.page = {...state.page,available_actions:[],payment:{...current.payment!,payment:{...current.payment!.payment,state:"funding_pending"}}};
        return response(accepted);
      }
      if (url.endsWith("decisions")) return response({});
      throw new Error(`Unexpected POST: ${url}`);
    }
    const after=Number(new URL(url,"http://fixture").searchParams.get("after"));
    return response({...state.page,events:state.page.events.filter(event=>event.seq>after)});
  });
  vi.stubGlobal("fetch", fetcher);
  vi.stubGlobal("ethereum", wallet);
  const run = (overrides:Partial<Parameters<typeof checkout>[0]> = {}) => checkout({runId:"run-1",quote:selectedQuote,wallet,signal:new AbortController().signal,progress:vi.fn(),...overrides});
  return {fetcher,wallet,run,state};
}
const posts = (fetcher:ReturnType<typeof setup>["fetcher"]) => fetcher.mock.calls.filter(([,options])=>options?.method==="POST");

beforeEach(()=>localStorage.clear());
afterEach(()=>{cleanup();vi.unstubAllGlobals();});

it("accepts, prepares, signs once and submits the exact $1 authorization", async()=>{
  const {run,fetcher,wallet}=setup();
  await run();
  expect(posts(fetcher).map(([url])=>url)).toEqual([
    "/api/live/quote-acceptance", "/api/live/orders/order-1/funding-preparation", "/api/live/orders/order-1/funding-authorizations",
  ]);
  expect(wallet.request.mock.calls.filter(([call])=>call.method==="eth_signTypedData_v4")).toHaveLength(1);
  expect(wallet.request.mock.calls.some(([call])=>call.method==="eth_requestAccounts")).toBe(false);
  const signatureCall=wallet.request.mock.calls.find(([call])=>call.method==="eth_signTypedData_v4")![0];
  expect(signatureCall).toEqual({method:"eth_signTypedData_v4",params:[buyer,JSON.stringify(preparation.typed_data)]});
  expect(JSON.parse(posts(fetcher)[2][1]!.body as string)).toEqual({
    expected_revision:1,expected_binding:expected,idempotency_key:"checkout:fund:attempt-1",
    funding_attempt_id:"attempt-1",payment_hash:"hash-1",simulate:false,signature,
  });
  expect(localStorage.length).toBe(0);
});

it("keeps explicit mock checkout wallet-free", async()=>{
  const {run,fetcher,wallet}=setup({mock:true});
  await run({wallet:undefined});
  expect(wallet.request).not.toHaveBeenCalled();
  const body=JSON.parse(posts(fetcher).at(-1)![1]!.body as string);
  expect(body.simulate).toBe(true);
  expect(body).not.toHaveProperty("signature");
});

it("leaves a rejected signature unpaid and retries without accepting the order twice", async()=>{
  const {run,fetcher,wallet}=setup();
  const request=wallet.request.getMockImplementation()!;
  wallet.request.mockImplementation(async call=>{
    if(call.method==="eth_signTypedData_v4")throw new Error("User rejected signature");
    return request(call);
  });
  await expect(run()).rejects.toThrow("User rejected signature");
  expect(posts(fetcher)).toHaveLength(2);
  wallet.request.mockImplementation(request);
  await run({binding});
  expect(posts(fetcher).filter(([url])=>url.endsWith("quote-acceptance"))).toHaveLength(1);
  const preparations=posts(fetcher).filter(([url])=>url.endsWith("funding-preparation"));
  expect(preparations[0][1]!.body).toBe(preparations[1][1]!.body);
});

it("reconciles a lost submission response before requesting another signature", async()=>{
  const {run,fetcher,wallet,state}=setup();
  const fetch=fetcher.getMockImplementation()!;
  fetcher.mockImplementation(async(url,options)=>{
    const result=await fetch(url,options);
    if(url.endsWith("funding-authorizations"))throw new Error("Response lost");
    return result;
  });
  await expect(run()).rejects.toThrow("Response lost");
  expect(state.page.payment?.payment.state).toBe("funding_pending");
  await run({binding});
  expect(wallet.request.mock.calls.filter(([call])=>call.method==="eth_signTypedData_v4")).toHaveLength(1);
  expect(posts(fetcher).filter(([url])=>url.endsWith("funding-authorizations"))).toHaveLength(1);
});

it("does not submit a signature after the checkout is abandoned", async()=>{
  const {run,fetcher,wallet}=setup();
  const controller=new AbortController();
  const request=wallet.request.getMockImplementation()!;
  wallet.request.mockImplementation(async call=>{
    if(call.method==="eth_signTypedData_v4")controller.abort();
    return request(call);
  });
  await expect(run({signal:controller.signal})).rejects.toThrow();
  expect(posts(fetcher).some(([url])=>url.endsWith("funding-authorizations"))).toBe(false);
});

it.each(["stale", "amount", "hash"])("does not sign when preparation is %s", async kind=>{
  const {run,fetcher,wallet}=setup();
  const fetch=fetcher.getMockImplementation()!;
  fetcher.mockImplementation(async(url,options)=>url.endsWith("funding-preparation")
    ? kind==="stale" ? response({detail:"Order changed"},409)
      : response({...preparation,terms:{...preparation.terms,...(kind==="amount"?{amount_atomic:"15000000"}:{payment_hash:"different"})}})
    : fetch(url,options));
  await expect(run()).rejects.toThrow();
  expect(wallet.request).not.toHaveBeenCalled();
  expect(posts(fetcher)).toHaveLength(2);
});

it("ignores a second click while checkout is in progress", async()=>{
  const {fetcher}=setup();
  const refresh=vi.fn();
  const {result}=renderHook(()=>useCheckout("run-1",refresh));
  await act(async()=>{await Promise.all([result.current.pay(quote),result.current.pay(quote)]);});
  expect(posts(fetcher).filter(([url])=>url.endsWith("quote-acceptance"))).toHaveLength(1);
  expect(refresh).toHaveBeenCalledTimes(1);
});

it("offers one payment button and reports pending funds without claiming fulfillment", async()=>{
  const {fetcher,wallet}=setup({initialQuote:true});
  localStorage.setItem("datumco.live-run.v1",JSON.stringify({id:"run-1"}));
  render(<LiveRun recorded={()=>{}}/>);
  fireEvent.click(await screen.findByRole("button",{name:"Accept & pay $1.00"}));
  await screen.findByRole("main",{name:"Run view"});
  fireEvent.click(screen.getByRole("button",{name:"Customer view"}));
  await screen.findByText("Payment submitted. Waiting for confirmed funds before starting work.");
  expect(screen.queryByRole("button",{name:"Prepare funding"})).toBeNull();
  expect(screen.queryByRole("link",{name:"Download CSV"})).toBeNull();
  expect(wallet.request.mock.calls.filter(([call])=>call.method==="eth_signTypedData_v4")).toHaveLength(1);
  expect(posts(fetcher)).toHaveLength(3);
});

it("switches customer/admin views on the same run and honors current reviewer permissions", async()=>{
  const {fetcher,state}=setup();
  state.page={...current,available_actions:[{action:"reject",enabled:true,reason:"Retain review"},{action:"approve",enabled:false,reason:"No eligible release"}]};
  localStorage.setItem("datumco.live-run.v1",JSON.stringify({id:"run-1"}));
  render(<LiveRun recorded={()=>{}}/>);
  await screen.findByText("Awaiting payment");
  expect(screen.queryByRole("button",{name:/^(Escalated to a person|Human review)/})).toBeNull();
  fireEvent.click(screen.getByRole("button",{name:"Run"}));
  fireEvent.click(screen.getByRole("button",{name:/^Escalated to a person/}));
  await waitFor(()=>expect((screen.getByRole("button",{name:"Reject"}) as HTMLButtonElement).disabled).toBe(false));
  expect((screen.getByRole("button",{name:"Approve"}) as HTMLButtonElement).disabled).toBe(true);
  expect(posts(fetcher)).toHaveLength(0);
  fireEvent.change(screen.getByLabelText("Reason or evidence answer"),{target:{value:"Need more evidence"}});
  fireEvent.click(screen.getByRole("button",{name:"Reject"}));
  await waitFor(()=>expect(posts(fetcher)).toHaveLength(1));
  expect(posts(fetcher)[0][0]).toBe("/api/live/runs/run-1/decisions");
  expect(JSON.parse(posts(fetcher)[0][1]!.body as string)).toMatchObject({binding,action:"reject",reason:"Need more evidence"});
  fireEvent.click(screen.getByRole("button",{name:"Customer view"}));
  expect(screen.queryByRole("button",{name:"Reject"})).toBeNull();
  expect(JSON.parse(localStorage.getItem("datumco.live-run.v1")!).id).toBe("run-1");
});

it("keeps a rejected payment in the conversation and hands off to Run only after a successful retry", async()=>{
  const {fetcher,wallet}=setup({initialQuote:true});
  const request=wallet.request.getMockImplementation()!;
  wallet.request.mockImplementation(async call=>{
    if(call.method==="eth_signTypedData_v4")throw new Error("User rejected signature");
    return request(call);
  });
  localStorage.setItem("datumco.live-run.v1",JSON.stringify({id:"run-1"}));
  render(<LiveRun/>);
  fireEvent.click(await screen.findByRole("button",{name:"Accept & pay $1.00"}));
  await screen.findByText("User rejected signature");
  expect(screen.getByRole("main",{name:"Customer view"})).toBeTruthy();
  expect(posts(fetcher).some(([url])=>url.endsWith("funding-authorizations"))).toBe(false);
  wallet.request.mockImplementation(request);
  fireEvent.click(await screen.findByRole("button",{name:"Pay $1.00"}));
  await screen.findByRole("main",{name:"Run view"});
  expect(posts(fetcher).filter(([url])=>url.endsWith("quote-acceptance"))).toHaveLength(1);
});

it("shows drafted terms as agreed without marking the delivery checks as passed", async()=>{
  const {state}=setup({initialQuote:true});
  vi.stubGlobal("ResizeObserver",class {observe(){} disconnect(){}});
  const at="2026-10-24T12:00:00Z";
  state.page={...state.page,events:[
    {seq:1,at,type:"steps_planned",steps:[{id:"clarify",kind:"clarify",title:"Clarify",detail:"Agree on terms"},{id:"produce",kind:"produce",title:"Produce",detail:"Verify output"}]},
    {seq:2,at,type:"contract_line_drafted",step:"clarify",line:{id:"dataset:coverage",text:"Every agreed ZIP appears once",check:"code"}},
    {seq:3,at,type:"message",step:"clarify",message:{id:"question-1",from:"agent",text:"Which area should the dataset cover?"}},
  ],next_after:3,high_watermark:3};
  localStorage.setItem("datumco.live-run.v1",JSON.stringify({id:"run-1"}));
  render(<LiveRun/>);
  await screen.findByText("Which area should the dataset cover?");
  expect(within(screen.getByRole("region",{name:"Data contract"})).getByText("Completed:")).toBeTruthy();
  fireEvent.click(screen.getByRole("button",{name:"Run"}));
  fireEvent.click(screen.getByRole("button",{name:/^Produce,/}));
  expect(within(screen.getByRole("region",{name:"Delivery checks"})).getByText("Pending:")).toBeTruthy();
  expect(screen.queryByRole("link",{name:"Download CSV"})).toBeNull();
  fireEvent.click(screen.getByRole("button",{name:"Customer view"}));
  expect(screen.getByText("Which area should the dataset cover?")).toBeTruthy();
});

it("shows a pending evidence question without presenting human approval controls", async()=>{
  const {state}=setup();
  vi.stubGlobal("ResizeObserver",class {observe(){} disconnect(){}});
  const at="2026-10-24T12:00:00Z";
  state.page={...state.page,available_actions:[{action:"approve",enabled:false,reason:"Not in human review"}],evidence_request:{request_id:"question-1",case_id:"case-1",deadline:at,prompt:"Which frozen source supports this complaint?",references_required:false},events:[
    {seq:1,at,type:"steps_planned",steps:[{id:"investigate",kind:"investigate",title:"Investigate",detail:"Read the evidence"}]},
    {seq:2,at,type:"step_started",step:"investigate"},
    {seq:3,at,type:"step_waiting",step:"investigate",waitingOn:"Waiting for the requested evidence"},
  ],next_after:3,high_watermark:3};
  localStorage.setItem("datumco.live-run.v1",JSON.stringify({id:"run-1"}));
  render(<LiveRun/>);
  await screen.findByLabelText("Evidence answer");
  fireEvent.click(screen.getByRole("button",{name:"Run"}));
  fireEvent.click(screen.getByRole("button",{name:"Investigate, waiting"}));
  expect(screen.getByLabelText("Evidence answer")).toBeTruthy();
  expect(within(screen.getByRole("complementary",{name:"Investigate"})).getAllByText("Which frozen source supports this complaint?")).toHaveLength(1);
  expect(screen.queryByText("Needs a person's decision")).toBeNull();
  expect(screen.queryByLabelText("Reason or evidence answer")).toBeNull();
  expect(screen.queryByRole("button",{name:/^(Escalated to a person|Human review)/})).toBeNull();
  state.page={...state.page,evidence_request:null,available_actions:[{action:"reject",enabled:true,reason:"Human review required"}],events:[...state.page.events,
    {seq:4,at,type:"steps_planned",steps:[{id:"decide",kind:"decide",title:"Human reviews",detail:"Review the case"}]},
    {seq:5,at,type:"state_changed",step:"investigate",state:"human_review",reason:"No further evidence",binding:state.page.binding!},
  ],next_after:5,high_watermark:5};
  expect(await screen.findByRole("complementary",{name:"Human review"})).toBeTruthy();
  expect(screen.queryByLabelText("Evidence answer")).toBeNull();
  fireEvent.click(screen.getByRole("button",{name:"Investigate, waiting"}));
  expect(screen.getByRole("complementary",{name:"Investigate"})).toBeTruthy();
});

it("shows the persisted scope explanation and buyer acceptance without stale human-review prompts", async()=>{
  const {state}=setup();
  vi.stubGlobal("ResizeObserver",class {observe(){} disconnect(){}});
  const at="2026-10-24T12:00:00Z";
  const reason="Oakland is outside the accepted San Francisco geography. The current delivery meets that agreed scope.";
  state.page={...state.page,available_actions:[{action:"accept",enabled:true,reason:"Verified delivery"}],events:[
    {seq:1,at,type:"steps_planned",steps:[{id:"review",kind:"review",title:"Customer review",detail:"Review delivery"},{id:"verdict",kind:"verdict",title:"Assessment",detail:"Read the finding"},{id:"decide",kind:"decide",title:"Human",detail:"Prior review"}]},
    {seq:2,at,type:"delivery_ready",step:"review",delivery:{artifactId:"artifact-1",file:"counts.csv",rows:[],version:1}},
    {seq:3,at,type:"step_waiting",step:"decide",waitingOn:"Prior historical review"},
    {seq:4,at,type:"verdict",step:"verdict",allowedBy:"finding-1",verdict:{kind:"disagree",decidedBy:"rules",reason,evidenceIds:[]}},
  ],next_after:4,high_watermark:4};
  localStorage.setItem("datumco.live-run.v1",JSON.stringify({id:"run-1"}));
  render(<LiveRun/>);
  expect(await screen.findByText(reason)).toBeTruthy();
  expect(screen.getByRole("button",{name:"Accept verified delivery"})).toBeTruthy();
  expect(screen.queryByRole("button",{name:"Open human review"})).toBeNull();
  fireEvent.click(screen.getByRole("button",{name:"Run"}));
  expect(screen.queryByRole("button",{name:/^(Escalated to a person|Human review)/})).toBeNull();
  fireEvent.click(screen.getByRole("button",{name:"Assessment, done"}));
  expect(screen.getByText(reason)).toBeTruthy();
  expect(screen.queryByText("Needs a person's decision")).toBeNull();
});

it("keeps every repeated-label source cell inspectable by its persisted evidence ID", async()=>{
  vi.stubGlobal("ResizeObserver",class {observe(){} disconnect(){}});
  const {state,fetcher}=setup();
  const at="2026-10-24T12:00:00Z";
  const events:RunPage["events"]=[{seq:1,at,type:"steps_planned",steps:[{id:"investigate",kind:"investigate",title:"Investigate",detail:"Read evidence"}]}];
  for(let i=0;i<60;i++)events.push({seq:i+2,at,type:"evidence_found",step:"investigate",evidence:{id:`ref-${i}`,kind:"sheet_cell",label:"coverage.csv",file:"coverage.csv",row:String(i),column:"city",value:"San Francisco",note:"Frozen geography",source:{kind:"cell",row:String(i),column:"city",version:1}}});
  state.page={...state.page,events,next_after:61,high_watermark:61};
  localStorage.setItem("datumco.live-run.v1",JSON.stringify({id:"run-1"}));
  render(<LiveRun/>);
  fireEvent.click(screen.getByRole("button",{name:"Run"}));
  fireEvent.click(await screen.findByRole("button",{name:/^Investigate,/}));
  fireEvent.click(await screen.findByText("Inspect persisted evidence"));
  fireEvent.click(screen.getByText("coverage.csv · 60 references"));
  expect(document.querySelectorAll(".live-evidence-list .cite")).toHaveLength(60);
  fireEvent.click(screen.getByRole("button",{name:"Row 59 · city · v1"}));
  await waitFor(()=>expect(fetcher.mock.calls.some(([url])=>url==="/api/live/runs/run-1/evidence/ref-59")).toBe(true));
  await screen.findByText("Selected evidence");
});
