import {act,cleanup,renderHook} from "@testing-library/react";
import {afterEach,beforeEach,expect,it,vi} from "vitest";
import {useRevealed,VISIT} from "../lib/run/reveal";
import type {RunEvent} from "../lib/run/contract";

// The deterministic backend finishes an investigation within one poll. The live route still shows the groundhog
// walking to the database and reading its lines before the finding lands, by holding the verdict on screen.

beforeEach(()=>vi.useFakeTimers());
afterEach(()=>{cleanup();vi.useRealTimers();});

const burst=(at:string):RunEvent[]=>[
  {seq:64,at,type:"step_started",step:"investigate"},
  {seq:65,at,type:"step_completed",step:"produce"},
  {seq:66,at,type:"verdict",step:"verdict",allowedBy:"Frozen terms",verdict:{kind:"disagree",reason:"Oakland is not in San Francisco.",decidedBy:"rules",evidenceIds:[]}},
  {seq:67,at,type:"step_completed",step:"verdict"},
];
const seqs=(r:{events:RunEvent[]})=>r.events.map(e=>e.seq);

it("holds the finding of a fresh investigation until the three lines are read, then shows the rest",()=>{
  const events=burst(new Date().toISOString()); // one stream, as the poll keeps it; rebuilding it would be a new run
  const {result}=renderHook(()=>useRevealed(events));
  expect(seqs(result.current)).toEqual([64,65]);
  expect(result.current.read).toBe(0);
  act(()=>{vi.advanceTimersByTime(VISIT.walk);});
  expect(result.current.read).toBe(1);
  act(()=>{vi.advanceTimersByTime(VISIT.line);});
  expect(result.current.read).toBe(2);
  act(()=>{vi.advanceTimersByTime(VISIT.line);});
  expect(result.current.read).toBe(3);
  expect(seqs(result.current)).toEqual([64,65]); // still reading
  act(()=>{vi.advanceTimersByTime(VISIT.finding);});
  expect(seqs(result.current)).toEqual([64,65,66,67]);
});

it("an investigation from a while ago shows its history at once",()=>{
  const events=burst("2026-10-25T12:00:00Z");
  const {result}=renderHook(()=>useRevealed(events));
  expect(seqs(result.current)).toEqual([64,65,66,67]);
  expect(result.current.read).toBe(0);
});

it("a new run starts over",()=>{
  const old=burst("2026-10-25T12:00:00Z");
  const {result,rerender}=renderHook(({events})=>useRevealed(events),{initialProps:{events:old}});
  expect(seqs(result.current)).toEqual([64,65,66,67]);
  const fresh:RunEvent[]=[{seq:1,at:"2026-10-25T12:01:00Z",type:"step_started",step:"clarify"}];
  rerender({events:fresh});
  expect(seqs(result.current)).toEqual([1]);
});
