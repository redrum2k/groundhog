import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {afterEach,expect,it,vi} from "vitest";
import type {DecisionBinding,RunEvidenceRequest} from "../lib/runs.generated";
import EvidenceAnswer from "../components/run/evidence-answer";
import ComplaintForm from "../components/run/complaint-form";
afterEach(cleanup);
const binding:DecisionBinding={runId:"run",orderId:"order",snapshotId:"snapshot",revision:4,deliveryVersion:1,evidenceVersion:2};
const request:RunEvidenceRequest={request_id:"case:question:1",case_id:"case",prompt:"Which taxonomy cell?",deadline:"2026-10-24T12:01:00Z",references_required:true,allowed_references:[{kind:"dataset",artifact_id:"authority",sha256:"a".repeat(64),source_id:"sf-aggregate-v1:authority",version:1,row:"$",column:"yoga_category",value:"Wellness"}]};
it("submits the request identity, current binding and selected resolving evidence",()=>{
 const submit=vi.fn();render(<EvidenceAnswer request={request} binding={binding} busy={false} submit={submit}/>);
 fireEvent.change(screen.getByLabelText("Evidence answer"),{target:{value:"See the cited taxonomy cell."}});
 expect((screen.getByRole("button") as HTMLButtonElement).disabled).toBe(true);
 fireEvent.click(screen.getByRole("checkbox"));
 fireEvent.click(screen.getByRole("button"));
 expect(submit).toHaveBeenCalledWith({request_id:request.request_id,binding,text:"See the cited taxonomy cell.",references:request.allowed_references});
});
it("submits a complaint using only a prompt field, without target selectors",()=>{
 const submit=vi.fn();render(<ComplaintForm disabled={false} submit={submit}/>);
 expect(screen.queryAllByRole("combobox")).toHaveLength(0);
 expect(screen.getAllByRole("textbox")).toHaveLength(1);
 const button=screen.getByRole("button",{name:"Send complaint"}) as HTMLButtonElement;
 expect(button.disabled).toBe(true);
 fireEvent.change(screen.getByLabelText("Your complaint"),{target:{value:"ZIP 94110 is missing from the delivery"}});
 fireEvent.click(button);
 expect(submit).toHaveBeenCalledWith("ZIP 94110 is missing from the delivery");
});
it("keeps the draft while permissions change and blocks disabled or blank submissions",()=>{
 const submit=vi.fn();const {rerender}=render(<ComplaintForm disabled={false} submit={submit}/>);
 fireEvent.change(screen.getByRole("textbox"),{target:{value:"   "}});
 fireEvent.submit(screen.getByRole("textbox").closest("form")!);
 expect(submit).not.toHaveBeenCalled();
 fireEvent.change(screen.getByRole("textbox"),{target:{value:"Yoga should be included."}});
 rerender(<ComplaintForm disabled submit={submit}/>);
 expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("Yoga should be included.");
 fireEvent.submit(screen.getByRole("textbox").closest("form")!);
 expect(submit).not.toHaveBeenCalled();
});
