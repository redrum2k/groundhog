import {act, cleanup, renderHook} from "@testing-library/react";
import {afterEach, expect, it, vi} from "vitest";
import {useRunNavigation} from "../lib/run/use-run-navigation";

afterEach(() => {cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();delete document.documentElement.dataset.runTransition;});

it("falls back to direct navigation when view transitions are unavailable", () => {
  const {result}=renderHook(useRunNavigation);
  act(()=>result.current.navigate("run",true));
  expect(result.current.tab).toBe("run");
  expect(document.documentElement.dataset.runTransition).toBeUndefined();
});

it("ignores a stale transition callback after a rapid return to the chat", async () => {
  const moves: {commit: () => void; finish: () => void; skipTransition: ReturnType<typeof vi.fn>}[]=[];
  const original=Object.getOwnPropertyDescriptor(document,"startViewTransition");
  Object.defineProperty(document,"startViewTransition",{configurable:true,value:(commit:()=>void)=>{
    let finish!:()=>void;
    const finished=new Promise<void>(resolve=>{finish=resolve;});
    const skipTransition=vi.fn();
    moves.push({commit,finish,skipTransition});
    return {ready:Promise.resolve(),finished,skipTransition};
  }});
  try {
    const {result}=renderHook(useRunNavigation);
    act(()=>result.current.navigate("run",true));
    act(()=>result.current.navigate("customer"));
    expect(moves[0].skipTransition).toHaveBeenCalledOnce();
    act(()=>moves[1].commit());
    act(()=>moves[0].commit());
    expect(result.current.tab).toBe("customer");
    await act(async()=>moves[0].finish());
    expect(document.documentElement.dataset.runTransition).toBe("customer");
    await act(async()=>moves[1].finish());
    expect(document.documentElement.dataset.runTransition).toBeUndefined();
  } finally {
    if(original)Object.defineProperty(document,"startViewTransition",original);
    else Reflect.deleteProperty(document,"startViewTransition");
  }
});

it.each(["keyboard","reduced motion"])("uses immediate navigation for %s", mode => {
  const start=vi.fn();
  const original=Object.getOwnPropertyDescriptor(document,"startViewTransition");
  Object.defineProperty(document,"startViewTransition",{configurable:true,value:start});
  vi.stubGlobal("matchMedia",()=>({matches:mode==="reduced motion"}));
  try {
    const {result}=renderHook(useRunNavigation);
    if(mode==="keyboard")act(()=>result.current.interaction.onKeyDownCapture());
    act(()=>result.current.navigate("run",true));
    expect(result.current.tab).toBe("run");
    expect(start).not.toHaveBeenCalled();
  } finally {
    if(original)Object.defineProperty(document,"startViewTransition",original);
    else Reflect.deleteProperty(document,"startViewTransition");
  }
});
