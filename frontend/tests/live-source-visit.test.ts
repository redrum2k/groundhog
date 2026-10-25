import {expect,it} from "vitest";
import {project} from "../lib/run/fold";
import {CONTRACT_V1} from "../lib/run/scenario";
import type {RunEvent} from "../lib/run/contract";

// The live backend never says "the agent went to the database"; it reports cited cells. The canvas derives the
// groundhog's visit to the source from those, so /live shows the same beat the recorded demo narrates itself.

const at="2026-10-25T12:00:00Z";
const live={lane:"amber" as const,ending:"human" as const,learned:false,contract:CONTRACT_V1,live:true};
const planned:RunEvent={seq:1,at,type:"steps_planned",steps:[{id:"investigate",kind:"investigate",title:"Investigate",detail:"Evidence-backed resolution"}]};
const started:RunEvent={seq:2,at,type:"step_started",step:"investigate"};
const cited=(seq:number,id:string):RunEvent=>({seq,at,type:"evidence_found",step:"investigate",evidence:{id,kind:"sheet_cell",label:"sf-aggregate-v1 · 12 · adults",note:"The source row carries the delivered count.",file:"delivery-1",row:"12",column:"adults",value:"418",source:{kind:"cell",row:"12",column:"adults",version:3}}});
const completed=(seq:number):RunEvent=>({seq,at,type:"step_completed",step:"investigate"});

it("a live investigation opens the source with three unchecked lines, one per thing the agent reads",()=>{
  const source=project([planned,started],live).nodes.investigate.source;
  expect(source?.map(l=>l.checked)).toEqual([false,false,false]);
  expect(source?.[1].text).toBe(`${CONTRACT_V1.lines.length} contract lines · against the source`);
});

it("each cited cell ticks the next line and names the contract line it answers; the last line waits for the step",()=>{
  const one=project([planned,started,cited(3,"job-1:dataset:geography:0")],live).nodes.investigate.source;
  expect(one?.map(l=>l.checked)).toEqual([true,false,false]);
  const two=project([planned,started,cited(3,"job-1:dataset:geography:0"),cited(4,"job-1:dataset:geography:1")],live).nodes.investigate.source;
  expect(two?.map(l=>l.checked)).toEqual([true,true,false]);
  expect(two?.[1].text).toBe("Geography line · against the source");
  const more=project([planned,started,cited(3,"job-1:dataset:geography:0"),cited(4,"job-1:dataset:geography:1"),cited(5,"job-1:dataset:coverage:0")],live).nodes.investigate.source;
  expect(more?.map(l=>l.checked)).toEqual([true,true,false]); // the delivered rows line is the step's to tick
  const done=project([planned,started,cited(3,"job-1:dataset:geography:0"),completed(4)],live).nodes.investigate.source;
  expect(done?.every(l=>l.checked)).toBe(true);
});

it("the finding closes the visit: the backend ends an investigation with a verdict, not a step completion",()=>{
  const steps:RunEvent={seq:1,at,type:"steps_planned",steps:[{id:"investigate",kind:"investigate",title:"Investigate",detail:"Evidence-backed resolution"},{id:"verdict",kind:"verdict",title:"Finding",detail:"Evidence assessment"}]};
  const finding:RunEvent={seq:4,at,type:"verdict",step:"verdict",allowedBy:"Frozen terms",verdict:{kind:"disagree",reason:"Oakland is not in San Francisco.",decidedBy:"rules",evidenceIds:[]}};
  const view=project([steps,started,cited(3,"job-1:dataset:geography:0"),finding],live);
  expect(view.nodes.investigate.status).toBe("done");
  expect(view.nodes.investigate.source?.every(l=>l.checked)).toBe(true);
});

it("the recorded demo keeps narrating the visit itself",()=>{
  const recorded={...live,live:false};
  expect(project([planned,started,cited(3,"e-city")],recorded).nodes.investigate.source).toBeUndefined();
  const lines=[{id:"src-pin",text:"Vendor panel v3 · as pinned at acceptance",checked:true}];
  const narrated:RunEvent={seq:3,at,track:"amber",type:"source_checked",step:"investigate",lines};
  expect(project([planned,started,narrated],recorded).nodes.investigate.source).toEqual(lines);
});
