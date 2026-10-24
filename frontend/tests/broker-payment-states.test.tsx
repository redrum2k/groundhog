import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {afterEach,expect,it,vi} from "vitest";
import type {PaymentView} from "../lib/runs.generated";
import LiveRun from "../components/run/live-run";
const mock=vi.hoisted(()=>({payment:undefined as PaymentView | undefined}));
vi.mock("../lib/run/live",()=>({LIVE_API:"/api/live",jsonRequest:vi.fn(),useLiveRun:()=>({
 id:"fixture-run",events:[],page:{payment:mock.payment,request:{status:"accepted"},available_actions:[]},busy:false,start:vi.fn(),resume:vi.fn(),command:vi.fn(),retry:vi.fn(),newRun:vi.fn()
})}));
const fixtures=import.meta.glob<PaymentView>("../fixtures/payments/*.json",{eager:true,import:"default"});
afterEach(cleanup);
it.each(Object.entries(fixtures))("displays %s without invented completion or explorer links",(_path,payment)=>{
 mock.payment=payment;
 render(<LiveRun recorded={()=>{}}/>);
 fireEvent.click(screen.getByRole("button",{name:"Funding"}));
 expect(screen.getByRole("heading",{name:`Funding · ${payment.payment.state}`})).toBeTruthy();
 expect(screen.queryByRole("link",{name:/basescan/i})).toBeNull();
 expect(screen.queryByRole("button",{name:"Accept verified delivery"})).toBeNull();
});
