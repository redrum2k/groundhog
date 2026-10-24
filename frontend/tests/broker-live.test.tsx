import {act, cleanup, renderHook, render, screen} from "@testing-library/react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {useLiveRun, mergeEvents} from "../lib/run/live";
import {bridge} from "../lib/live-bridge";
import {signFunding} from "../lib/run/wallet";
import type {FundingPreparation} from "../lib/runs.generated";
import RunApp from "../components/run/run-app";

const plan = {seq:1,at:"2026-10-24T12:00:00Z",type:"steps_planned" as const,steps:[]};
const page = {events:[plan],next_after:1,high_watermark:1,caught_up:true,poll_after_ms:1000,server_time:"now",binding:null,available_actions:[],request:{status:"compiling"},quote:null,payment:null};
const response=(body:unknown,status=200)=>new Response(JSON.stringify(body),{status,headers:{"Content-Type":"application/json"}});
beforeEach(()=>{localStorage.clear();});
afterEach(()=>{cleanup();vi.useRealTimers();vi.unstubAllGlobals();vi.unstubAllEnvs();});

it("opens live intake without a recorded prefix",()=>{
 render(<RunApp/>);
 expect(screen.getByRole("button",{name:"Create request"})).toBeTruthy();
 expect(screen.queryByRole("button",{name:"Play"})).toBeNull();
});
it("merges duplicates by exclusive cursor",()=>{expect(mergeEvents([plan],[plan])).toEqual([plan]);});
it("reloads a persisted run from cursor zero and never creates another",async()=>{
 vi.useFakeTimers(); localStorage.setItem("datumco.live-run.v1",JSON.stringify({id:"saved"}));
 const fetcher=vi.fn().mockResolvedValue(response(page));vi.stubGlobal("fetch",fetcher);
 const {result,unmount}=renderHook(()=>useLiveRun());
 await act(async()=>{await vi.advanceTimersByTimeAsync(10);});
 expect(fetcher.mock.calls[0][0]).toBe("/api/live/runs/saved/events?after=0");
 expect(result.current.events).toEqual([plan]);unmount();
});
it("ignores a delayed old run and shows backend failure without a stub",async()=>{
 vi.useFakeTimers();localStorage.setItem("datumco.live-run.v1",JSON.stringify({id:"old"}));
 let resolve!:(r:Response)=>void;
 vi.stubGlobal("fetch",vi.fn().mockImplementationOnce(()=>new Promise(r=>{resolve=r;})).mockResolvedValue(response({detail:"offline"},502)));
 const {result}=renderHook(()=>useLiveRun());
 await act(async()=>{result.current.resume("new");});
 await act(async()=>{resolve(response(page));await vi.advanceTimersByTimeAsync(10);});
 expect(result.current.events).toEqual([]); expect(result.current.error).toBe("offline");
});
it("409 refreshes without retrying a reviewer decision",async()=>{
 vi.useFakeTimers();localStorage.setItem("datumco.live-run.v1",JSON.stringify({id:"saved"}));
 const fetcher=vi.fn().mockImplementation((_url,opts)=>Promise.resolve(opts.method==="POST"?response({detail:"stale"},409):response(page)));vi.stubGlobal("fetch",fetcher);
 const {result}=renderHook(()=>useLiveRun());
 await act(async()=>{await vi.advanceTimersByTimeAsync(10);});
 await act(async()=>{await result.current.command("/runs/saved/decisions",{action:"approve",binding:{revision:1}});});
 expect(result.current.error).toMatch(/click again/);
 expect(fetcher.mock.calls.filter(([,opts])=>opts.method==="POST")).toHaveLength(1);
});

it("resumes unfinished creation with its original key",async()=>{
 localStorage.setItem("datumco.live-run.v1",JSON.stringify({key:"original",prompt:"Synthetic request"}));
 const fetcher=vi.fn().mockResolvedValueOnce(response({id:"resumed"})).mockResolvedValue(response(page));
 vi.stubGlobal("fetch",fetcher);
 const {result}=renderHook(()=>useLiveRun());
 await act(async()=>{});
 expect(fetcher.mock.calls[0][1].headers["Idempotency-Key"]).toBe("original");
 expect(result.current.id).toBe("resumed");
});

it("ignores unfinished creation after a deliberate new request",async()=>{
 localStorage.setItem("datumco.live-run.v1",JSON.stringify({key:"original",prompt:"Synthetic request"}));
 let resolve!:(r:Response)=>void;
 vi.stubGlobal("fetch",vi.fn().mockImplementation(()=>new Promise(r=>{resolve=r;})));
 const {result}=renderHook(()=>useLiveRun());
 act(()=>result.current.newRun());
 await act(async()=>{resolve(response({id:"obsolete"}));});
 expect(result.current.id).toBeUndefined();
 expect(localStorage.getItem("datumco.live-run.v1")).toBeNull();
});

describe("local bridge",()=>{
 beforeEach(()=>{vi.stubEnv("BROKER_LOCAL_DEMO","1");vi.stubEnv("INTERNAL_API_TOKEN","worker");vi.stubEnv("REVIEWER_API_TOKEN","reviewer");vi.stubEnv("BACKEND_URL","http://127.0.0.1:8000");});
 it("fails closed for public hosts, cross-origin commands and arbitrary paths",async()=>{
  expect((await bridge(new Request("https://public.example/api/live/runs"),["runs"])).status).toBe(403);
  expect((await bridge(new Request("http://localhost:3000/api/live/runs",{method:"POST",headers:{origin:"https://evil.example"}}),["runs"])).status).toBe(403);
  expect((await bridge(new Request("http://localhost:3000/api/live/internal/payments/work"),["internal","payments","work"])).status).toBe(404);
 });
 it("uses the actual Host when Next normalizes the internal request URL",async()=>{
  vi.stubGlobal("fetch",vi.fn().mockResolvedValue(response({id:"new"})));
  const req=new Request("http://localhost:3016/api/live/runs",{method:"POST",headers:{host:"127.0.0.1:3016",origin:"http://127.0.0.1:3016"},body:"{}"});
  expect((await bridge(req,["runs"])).status).toBe(200);
 });
 it("forwards only the matching server credential",async()=>{
  const fetcher=vi.fn().mockResolvedValue(response({ok:true}));vi.stubGlobal("fetch",fetcher);
  await bridge(new Request("http://localhost:3000/api/live/runs/a/decisions",{method:"POST",headers:{origin:"http://localhost:3000","X-Internal-Token":"attacker"},body:"{}"}),["runs","a","decisions"]);
  const headers=fetcher.mock.calls[0][1].headers as Headers;
  expect(headers.get("X-Reviewer-Token")).toBe("reviewer");expect(headers.has("X-Internal-Token")).toBe(false);
 });
});
const payer="0x"+"1".repeat(40);
const prep={terms:{payment_info:{payer}},typed_data:{}} as FundingPreparation;
it.each(["missing","account","chain","rejected","malformed","changed-account","changed-chain"])("handles wallet %s without pretending funds are held",async kind=>{
 let accounts=0,chains=0;
 const wallet=kind==="missing"?undefined:{request:async({method}:{method:string})=>{
  if(method==="eth_requestAccounts" || method==="eth_accounts") return [kind==="account" || kind==="changed-account" && accounts++>0?"0xother":payer];
  if(method==="eth_chainId")return kind==="chain" || kind==="changed-chain" && chains++>0?"0x1":"0x14a34";
  if(kind==="rejected")throw new Error("User rejected");
  return kind==="malformed"?"invalid":"0x"+"a".repeat(130);
 }};
 await expect(signFunding(wallet,prep)).rejects.toThrow();
});
