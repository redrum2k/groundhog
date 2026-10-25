import {expect,it} from "vitest";
import {project} from "../lib/run/fold";
import {CONTRACT_V1} from "../lib/run/scenario";
import type {RunEvent} from "../lib/run/contract";

// The live backend never says "the agent went to the database"; it reports a finding. The canvas opens the visit
// when Investigate starts and closes it with the finding, so /live shows the beat the recorded demo narrates itself.

const at="2026-10-25T12:00:00Z";
const live={lane:"amber" as const,ending:"human" as const,learned:false,contract:CONTRACT_V1,live:true};
const planned:RunEvent={seq:1,at,type:"steps_planned",steps:[{id:"investigate",kind:"investigate",title:"Investigate",detail:"Evidence-backed resolution"},{id:"verdict",kind:"verdict",title:"Finding",detail:"Evidence assessment"}]};
const started:RunEvent={seq:2,at,type:"step_started",step:"investigate"};
const finding:RunEvent={seq:3,at,type:"verdict",step:"verdict",allowedBy:"Frozen terms",verdict:{kind:"disagree",reason:"Oakland is not in San Francisco.",decidedBy:"rules",evidenceIds:[]}};
const cited:RunEvent={seq:4,at,type:"evidence_found",step:"investigate",evidence:{id:"job-1:dataset:geography:0",kind:"sheet_cell",label:"sf-aggregate-v1 · 12 · adults",note:"The source row carries the delivered count.",file:"delivery-1",row:"12",column:"adults",value:"418",source:{kind:"cell",row:"12",column:"adults",version:3}}};

it("a live investigation opens the source with three unchecked lines, one per thing the agent reads",()=>{
  const source=project([planned,started],live).nodes.investigate.source;
  expect(source?.map(l=>l.checked)).toEqual([false,false,false]);
  expect(source?.[1].text).toBe(`${CONTRACT_V1.lines.length} contract lines · against the source`);
});

it("the finding closes the visit: the backend ends an investigation with a verdict, and its cited cells come after",()=>{
  const view=project([planned,started,finding,cited],live);
  expect(view.nodes.investigate.status).toBe("done");
  expect(view.nodes.investigate.source?.every(l=>l.checked)).toBe(true);
  expect(view.nodes.investigate.evidence).toHaveLength(1);
  expect(project([planned,started,{seq:3,at,type:"step_completed",step:"investigate"}],live).nodes.investigate.source?.every(l=>l.checked)).toBe(true);
});

it("the recorded demo keeps narrating the visit itself",()=>{
  const recorded={...live,live:false};
  expect(project([planned,started],recorded).nodes.investigate.source).toBeUndefined();
  const lines=[{id:"src-pin",text:"Vendor panel v3 · as pinned at acceptance",checked:true}];
  const narrated:RunEvent={seq:3,at,track:"amber",type:"source_checked",step:"investigate",lines};
  expect(project([planned,started,narrated],recorded).nodes.investigate.source).toEqual(lines);
});
