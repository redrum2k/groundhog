import {act, cleanup, fireEvent, render, renderHook, screen, waitFor} from "@testing-library/react";
import {afterEach, beforeEach, expect, it, vi} from "vitest";
import {useLiveRun} from "../lib/run/live";
import type {RunPage} from "../lib/runs.generated";
import LiveRun from "../components/run/live-run";

const page={
  events:[{seq:1,at:"2026-10-24T12:00:00Z",type:"payment_state_changed",payment:{id:"payment-1",amount:1,mock:true},state:"funded"}],
  next_after:1,high_watermark:1,caught_up:true,poll_after_ms:100000,
  available_actions:[{action:"accept",enabled:true}],
  payment:{payment:{state:"funded"}},
} as unknown as RunPage;
const response=(body:unknown,status=200)=>new Response(JSON.stringify(body),{status,headers:{"Content-Type":"application/json"}});

beforeEach(()=>localStorage.setItem("datumco.live-run.v1",JSON.stringify({id:"run-1"})));
afterEach(()=>{cleanup();vi.useRealTimers();vi.unstubAllGlobals();localStorage.clear();});

it("stops polling a missing order without clearing its identity or sending mutations",async()=>{
  vi.useFakeTimers();
  const fetcher=vi.fn(async()=>response({detail:"Run not found"},404));
  vi.stubGlobal("fetch",fetcher);
  const {result}=renderHook(useLiveRun);
  await act(async()=>{});
  expect(result.current.canRecover).toBe(true);
  expect(result.current.busy).toBe(true);
  expect(result.current.id).toBe("run-1");
  expect(JSON.parse(localStorage.getItem("datumco.live-run.v1")!).id).toBe("run-1");
  await act(async()=>{
    await vi.advanceTimersByTimeAsync(5000);
    await result.current.command("/orders/order-1/acceptance",{});
  });
  expect(fetcher).toHaveBeenCalledTimes(1);
  fetcher.mockImplementation(async()=>response(page));
  await act(async()=>result.current.retry());
  expect(result.current.page).toEqual(page);
  expect(result.current.canRecover).toBe(false);
  expect(result.current.busy).toBe(false);
});

it("lets the user leave a missing order and start a new request",async()=>{
  vi.stubGlobal("fetch",vi.fn(async()=>response({detail:"Run not found"},404)));
  render(<LiveRun/>);
  await screen.findByText(/This order was not found on the connected backend/);
  expect((screen.getByRole("button",{name:"Refresh"}) as HTMLButtonElement).disabled).toBe(false);
  const reset=screen.getByRole("button",{name:"New request"}) as HTMLButtonElement;
  expect(reset.disabled).toBe(false);
  fireEvent.click(reset);
  expect(localStorage.getItem("datumco.live-run.v1")).toBeNull();
  expect(screen.getByRole("button",{name:"Create request"})).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull();
});

it.each([200,409])("retains the display but blocks actions while refreshing after HTTP %s",async status=>{
  let complete!:(value:Response)=>void;
  const refresh=new Promise<Response>(resolve=>{complete=resolve;});
  let gets=0;
  const fetcher=vi.fn(async (_url:string,options?:RequestInit)=>{
    if(options?.method==="POST")return response(status===200?{accepted:true}:{detail:"Stale revision"},status);
    return ++gets===1?response(page):refresh;
  });
  vi.stubGlobal("fetch",fetcher);
  const {result}=renderHook(useLiveRun);
  await waitFor(()=>expect(result.current.page?.payment?.payment.state).toBe("funded"));
  await act(async()=>{await result.current.command("/orders/order-1/acceptance",{});});
  expect(result.current.events).toEqual(page.events);
  expect(result.current.page).toEqual(page);
  expect(result.current.busy).toBe(true);
  await act(async()=>{await result.current.command("/orders/order-1/acceptance",{});});
  expect(fetcher.mock.calls.filter(([,options])=>options?.method==="POST")).toHaveLength(1);
  const fresh={...page,available_actions:[],payment:{payment:{state:"capture_pending"}}};
  await act(async()=>complete(response(fresh)));
  await waitFor(()=>expect(result.current.busy).toBe(false));
  expect(result.current.page?.payment?.payment.state).toBe("capture_pending");
  expect(result.current.events).toEqual(page.events);
});

it("clears the old order when switching runs, including while its new page is loading",async()=>{
  const fetcher=vi.fn(async (url:string)=>url.includes("run-1")?response(page):new Promise<Response>(()=>{}));
  vi.stubGlobal("fetch",fetcher);
  const {result}=renderHook(useLiveRun);
  await waitFor(()=>expect(result.current.page).toEqual(page));
  act(()=>result.current.resume("run-2"));
  expect(result.current.id).toBe("run-2");
  expect(result.current.events).toEqual([]);
  expect(result.current.page).toBeUndefined();
  expect(result.current.busy).toBe(true);
});

it("keeps human review visible during a failed poll and resumes with fresh permissions",async()=>{
  const review={...page,available_actions:[{action:"approve",enabled:true},{action:"reject",enabled:true}]};
  let gets=0;
  const fetcher=vi.fn(async()=>{
    gets++;
    if(gets===2)throw new Error("Connection interrupted");
    return response(gets===1?review:{...review,available_actions:[],payment:{payment:{state:"void_pending"}}});
  });
  vi.stubGlobal("fetch",fetcher);
  const {result}=renderHook(useLiveRun);
  await waitFor(()=>expect(result.current.page).toEqual(review));
  act(()=>result.current.retry());
  await waitFor(()=>expect(result.current.error).toBe("Connection interrupted"));
  expect(result.current.page).toEqual(review);
  expect(result.current.busy).toBe(true);
  await act(async()=>{await result.current.command("/runs/run-1/decisions",{action:"approve"});});
  expect(gets).toBe(2);
  await waitFor(()=>expect(result.current.page?.payment?.payment.state).toBe("void_pending"),{timeout:2000});
  expect(result.current.error).toBeUndefined();
  expect(result.current.busy).toBe(false);
});
