"use client";
import {useState} from "react";
import type {Complaint} from "../../lib/catalog.generated";
import type {DatasetComplaintTarget} from "../../lib/runs.generated";

export default function ComplaintForm({targets,artifactId,disabled,submit}:{
  targets:DatasetComplaintTarget[];artifactId:string;disabled:boolean;
  submit:(complaint:Complaint)=>void;
}) {
  const [requirement,setRequirement]=useState("");
  const [row,setRow]=useState("dataset");
  const [column,setColumn]=useState<NonNullable<Complaint["column"]> | "">("");
  const [intent,setIntent]=useState<Complaint["intent"]>("dispute_fact");
  const [text,setText]=useState("");
  const target=targets.find(t=>t.requirement_id===requirement);
  return <form onSubmit={e=>{e.preventDefault();if(target)submit({artifact_id:artifactId,requirement_id:target.requirement_id,field:target.field,product_id:row,column:column || null,intent,text});}}>
    <label htmlFor="complaint-requirement">Accepted requirement</label>
    <select id="complaint-requirement" value={requirement} required onChange={e=>{setRequirement(e.target.value);setRow("dataset");setColumn("");}}>
      <option value="">Select requirement</option>{targets.map(t=><option key={t.requirement_id} value={t.requirement_id}>{t.requirement_id} · {t.field}</option>)}
    </select>
    <label htmlFor="complaint-row">Dataset row</label>
    <select id="complaint-row" value={row} disabled={!target} onChange={e=>{setRow(e.target.value);setColumn("");}}>
      {(target?.row_ids ?? ["dataset"]).map(id=><option key={id} value={id}>{id==="dataset" ? "Whole dataset" : id}</option>)}
    </select>
    <label htmlFor="complaint-column">Dataset column (optional)</label>
    <select id="complaint-column" value={column} disabled={!target || row==="dataset"} onChange={e=>setColumn(e.target.value as typeof column)}>
      <option value="">Whole row</option>{target?.columns.map(c=><option key={c}>{c}</option>)}
    </select>
    <label htmlFor="complaint-intent">Request type</label>
    <select id="complaint-intent" value={intent} onChange={e=>setIntent(e.target.value as typeof intent)}>
      <option value="dispute_fact">Dispute delivered facts</option><option value="change_scope">Request changed scope</option>
    </select>
    <label htmlFor="complaint">Complaint or scope request</label><textarea id="complaint" value={text} required maxLength={2000} onChange={e=>setText(e.target.value)}/>
    <button type="submit" className="btn" disabled={disabled || !target || !text.trim()}>Record complaint</button>
  </form>;
}
