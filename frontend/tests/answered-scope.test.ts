import {expect,it} from "vitest";
import {project} from "../lib/run/fold";
import {CONTRACT_V1} from "../lib/run/scenario";
import type {RunEvent} from "../lib/run/contract";

it("a completed cited scope answer is not a failed delivery or invented correction",()=>{
  const at="2026-10-24T12:00:00Z";
  const events:RunEvent[]=[
    {seq:1,at,type:"steps_planned",steps:[{id:"verdict",kind:"verdict",title:"Finding",detail:"Evidence, not payment authority"}]},
    {seq:2,at,type:"verdict",step:"verdict",allowedBy:"Frozen terms",verdict:{kind:"agree",reason:"Answer: Yes, included in the accepted scope.",decidedBy:"rules",evidenceIds:[]}},
    {seq:3,at,type:"step_completed",step:"verdict"},
  ];
  const view=project(events,{lane:"amber",ending:"human",learned:false,contract:CONTRACT_V1,live:true});
  expect(view.nodes.verdict.status).toBe("done");
  expect(view.payments).toHaveLength(0);
  expect(view.loops).toHaveLength(0);
});
