import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import {afterEach, expect, it, vi} from "vitest";
import {LiveReview, LiveVerdict} from "../components/run/live-order";
import type {LiveOrder} from "../lib/run/use-live-order";
import type {Verdict} from "../lib/run/contract";

afterEach(cleanup);
const ref={kind:"dataset",artifact_id:"current-artifact",sha256:"a".repeat(64),source_id:"authority",version:1,row:"$",column:"yoga_is_gym",value:"false"};
const memory={memory_id:"memory",actor:"Human",originating_order:"previous-order",originating_case:"previous-case",explanation:"Read the authority cell.",guidance:"Wellness is not membership evidence.",applicability:{},current_citations:[ref]};
function order() {
  return {view:{nodes:{decide:{decision:{action:"escalate",by:"Human",note:"Needs review"}}},evidence:{}},page:{payment:{payment:{state:"funded"}},available_actions:[]},binding:{orderId:"current-order"},needsHumanReview:false,enabled:()=>true,inspect:vi.fn()} as unknown as LiveOrder;
}
it("shows the saved receipt only from the persisted decision",()=>{
  const current=order();
  const {rerender}=render(<LiveReview order={current}/>);
  expect(screen.queryByText("Guidance saved for similar cases")).toBeNull();
  current.view.nodes.decide.decision!.guidanceMemoryId="memory";
  rerender(<LiveReview order={current}/>);
  expect(screen.getByText("Guidance saved for similar cases")).toBeTruthy();
});
it("keeps consultation distinct from an established answer and links current evidence",()=>{
  const current=order();
  const verdict={kind:"grey",reason:"Still unknown",evidenceIds:[],finding:{reviewer_guidance:[memory]}} as unknown as Verdict;
  const {rerender}=render(<LiveVerdict order={current} verdict={verdict}/>);
  expect(screen.getByText("Prior reviewer guidance consulted")).toBeTruthy();
  expect(screen.getByText(/Consultation alone does not establish a successful answer/)).toBeTruthy();
  expect(screen.getByText(/previous-case/)).toBeTruthy();
  expect(screen.getByRole("link",{hidden:true}).getAttribute("href")).toBe("/api/live/orders/current-order/artifacts/current-artifact");
  rerender(<LiveVerdict order={current} verdict={{...verdict,finding:undefined}}/>);
  expect(screen.queryByText("Prior reviewer guidance consulted")).toBeNull();
});
it("collects optional guidance with existing evidence identifiers",()=>{
  const current=order();
  current.needsHumanReview=true;
  current.guidance="";current.reviewEvidence=[];
  current.setGuidance=vi.fn();current.setReviewEvidence=vi.fn();
  current.view.evidence={cell:{id:"cell",kind:"sheet_cell",label:"Authority",note:"Frozen",file:"source",row:"$",column:"yoga_is_gym",value:"false",source:{kind:"cell",row:"$",column:"yoga_is_gym",version:1,reference:ref}}} as LiveOrder["view"]["evidence"];
  render(<LiveReview order={current}/>);
  fireEvent.change(screen.getByLabelText("Guidance for similar cases (optional)"),{target:{value:"Read current authority"}});
  expect(current.setGuidance).toHaveBeenCalledWith("Read current authority");
  fireEvent.click(screen.getByRole("checkbox",{hidden:true}));
  expect(current.setReviewEvidence).toHaveBeenCalledWith(["cell"]);
});
