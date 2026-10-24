"use client";
import {useState} from "react";
import type {DatasetReference, DecisionBinding, RunEvidenceAnswer, RunEvidenceRequest} from "../../lib/runs.generated";

const referenceKey=(ref:DatasetReference)=>JSON.stringify([ref.sha256,ref.source_id,ref.version,ref.row,ref.column]);

export default function EvidenceAnswer({request,binding,busy,submit}:{
  request:RunEvidenceRequest; binding:DecisionBinding; busy:boolean;
  submit:(answer:RunEvidenceAnswer)=>void;
}) {
  const [text,setText]=useState("");
  const [selected,setSelected]=useState<Set<string>>(()=>new Set());
  // Selection is capped at eight, matching the generated bounded tuple union.
  const references=(request.allowed_references ?? []).filter(ref=>selected.has(referenceKey(ref))) as RunEvidenceAnswer["references"];
  return <form onSubmit={e=>{e.preventDefault();submit({binding,request_id:request.request_id,text,references});}}>
    <p>{request.prompt}</p><p>Answer by {request.deadline}. Customer testimony does not change accepted source authority or purchase scope.</p>
    <label htmlFor="evidence-answer">Evidence answer</label>
    <textarea id="evidence-answer" value={text} onChange={e=>setText(e.target.value)} required maxLength={2000}/>
    <fieldset><legend>Frozen evidence references{request.references_required ? " (required)" : " (optional)"}</legend>
      {(request.allowed_references ?? []).map(ref=><label key={referenceKey(ref)}>
        <input type="checkbox" checked={selected.has(referenceKey(ref))} disabled={busy || !selected.has(referenceKey(ref)) && selected.size>=8}
          onChange={e=>{const checked=e.target.checked;setSelected(prev=>{const next=new Set(prev);if(checked)next.add(referenceKey(ref));else next.delete(referenceKey(ref));return next;});}}/>
        {ref.source_id} · {ref.row} · {ref.column}: {ref.value ?? "Unknown"}
      </label>)}
    </fieldset>
    <button type="submit" className="btn" disabled={busy || !text.trim() || request.references_required && !references?.length}>Submit actual evidence answer</button>
  </form>;
}
