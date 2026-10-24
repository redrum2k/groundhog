import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {afterEach,expect,it,vi} from "vitest";
import type {PaymentView} from "../lib/runs.generated";
import type {RunEvent} from "../lib/run/contract";
import LiveRun from "../components/run/live-run";
import transitions from "../fixtures/run-payment-transitions.json";
import {project} from "../lib/run/fold";
vi.stubGlobal("ResizeObserver",class {observe(){} disconnect(){}});
const mock=vi.hoisted(()=>({payment:undefined as PaymentView | undefined, events:[] as RunEvent[]}));
vi.mock("../lib/run/live",()=>({LIVE_API:"/api/live",jsonRequest:vi.fn(),useLiveRun:()=>({
 id:"fixture-run",events:mock.events,page:{payment:mock.payment,request:{status:"accepted"},available_actions:[]},busy:false,start:vi.fn(),resume:vi.fn(),command:vi.fn(),retry:vi.fn(),newRun:vi.fn()
})}));
const fixtures=import.meta.glob<PaymentView>("../fixtures/payments/*.json",{eager:true,import:"default"});
afterEach(()=>{cleanup();mock.events=[];});
it.each(Object.entries(fixtures))("displays %s without invented completion or explorer links",(_path,payment)=>{
 mock.payment=payment;
 render(<LiveRun recorded={()=>{}}/>);
 fireEvent.click(screen.getByRole("button",{name:"Funding"}));
 expect(screen.getByRole("heading",{name:`Funding · ${payment.payment.state}`})).toBeTruthy();
 expect(screen.queryByRole("link",{name:/basescan/i})).toBeNull();
 expect(screen.queryByRole("button",{name:"Accept verified delivery"})).toBeNull();
});

const labels:Record<string,string>={funded:"held",void_pending:"return pending",voided:"returned",uncertain:"outcome uncertain",expired_not_returned:"expired · not returned",captured:"captured",reorg_hold:"reorg hold"};
it.each(transitions.frames)("projects persisted $state events consistently across canvas, panel and reload",frame=>{
 mock.payment=Object.values(fixtures).find(p=>p.payment.state===frame.state)!;
 mock.events=frame.events as RunEvent[];
 const {unmount}=render(<LiveRun recorded={()=>{}}/>);
 fireEvent.click(screen.getByRole("button",{name:"Funding"}));
 expect(screen.getByRole("heading",{name:`Funding · ${frame.state}`})).toBeTruthy();
 expect(screen.getByText(`$120 ${labels[frame.state]} · mock`)).toBeTruthy();
 expect(screen.queryByRole("link",{name:/basescan/i})).toBeNull();
 if(frame.state==="reorg_hold") {
   const view=project(mock.events,{lane:"shared",ending:"maya",learned:false,live:true,contract:{version:0,buyer:"",title:"",price:0,lines:[]}});
   expect(Object.keys(view.captured)).toHaveLength(1);
   expect(view.coin?.done).toBe(false);
   expect(mock.events.filter(e=>e.type==="books_posted")).toHaveLength(1);
 }
 unmount();
 render(<LiveRun recorded={()=>{}}/>);
 expect(screen.getByText(`$120 ${labels[frame.state]} · mock`)).toBeTruthy();
});

it("replays held to returned through the whole canvas and funding panel",()=>{
 const payment=Object.values(fixtures).find(p=>p.payment.state==="voided")!;
 mock.payment=payment;
 const at="2026-10-24T12:00:00Z";
 mock.events=[
  {seq:1,at,type:"steps_planned",steps:[{id:"paid",kind:"paid",title:"Funding",detail:"Funding"}]},
  {seq:2,at,type:"payment_authorized",payment:{id:payment.payment.payment_id,amount:120,mock:true},allowedBy:"Explicit mock funding"},
  {seq:3,at,type:"state_changed",step:"paid",state:"closed",paymentState:"voided",binding:{deliveryVersion:1,evidenceVersion:1}},
 ];
 render(<LiveRun recorded={()=>{}}/>);
 fireEvent.click(screen.getAllByRole("button",{name:"Funding"})[0]);
 expect(screen.getByRole("heading",{name:"Funding · voided"})).toBeTruthy();
 expect(screen.getByText("$120 returned · mock")).toBeTruthy();
 expect(screen.queryByText("$120 held · mock")).toBeNull();
});
