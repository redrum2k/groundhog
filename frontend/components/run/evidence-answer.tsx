"use client";
import {useState} from "react";
import type {DatasetReference, DecisionBinding, RunEvidenceAnswer, RunEvidenceRequest} from "../../lib/runs.generated";
import {IcLogo} from "./icons";

const referenceKey=(ref:DatasetReference)=>JSON.stringify([ref.sha256,ref.source_id,ref.version,ref.row,ref.column]);
const replyDeadline=new Intl.DateTimeFormat("en-US",{month:"short",day:"numeric",hour:"numeric",minute:"2-digit",second:"2-digit",timeZone:"America/Los_Angeles",timeZoneName:"short"});

export default function EvidenceAnswer({request,binding,busy,submit}:{
  request:RunEvidenceRequest; binding:DecisionBinding; busy:boolean;
  submit:(answer:RunEvidenceAnswer)=>void;
}) {
  const [text,setText]=useState("");
  const [selected,setSelected]=useState<Set<string>>(()=>new Set());
  // Selection is capped at eight, matching the generated bounded tuple union.
  const references=(request.references_required ? (request.allowed_references ?? []).filter(ref=>selected.has(referenceKey(ref))) : []) as NonNullable<RunEvidenceAnswer["references"]>;
  const disabled=busy || !text.trim() || request.references_required && !references.length;
  const deadline=replyDeadline.format(new Date(request.deadline));
  return <form className="live-form evidence-answer" onSubmit={e=>{e.preventDefault();if(!disabled)submit({binding,request_id:request.request_id,text,references});}}>
    <div className="live-agent-message">
      <div className="live-agent-message-header"><IcLogo size={16}/><span>Groundhog</span><span className="faint">Evidence request</span></div>
      <p className="live-agent-message-text">Could you help me verify this concern? Here’s the evidence I need:</p>
      <blockquote className="live-request-detail">{request.prompt}</blockquote>
      {!request.references_required && <p className="live-agent-message-text">If you don’t have this evidence, let me know and I’ll pass the case to a human reviewer.</p>}
      <div className="live-agent-message-meta">Reply by <time dateTime={request.deadline}>{deadline}</time></div>
    </div>
    <label htmlFor="evidence-answer">Evidence answer</label>
    <textarea id="evidence-answer" value={text} onChange={e=>setText(e.target.value)} required maxLength={2000}/>
    {request.references_required && <fieldset className="required-evidence"><legend>Supporting evidence (required)</legend>
      {(request.allowed_references ?? []).map(ref=><label key={referenceKey(ref)}>
        <input type="checkbox" checked={selected.has(referenceKey(ref))} disabled={busy || !selected.has(referenceKey(ref)) && selected.size>=8}
          onChange={e=>{const checked=e.target.checked;setSelected(prev=>{const next=new Set(prev);if(checked)next.add(referenceKey(ref));else next.delete(referenceKey(ref));return next;});}}/>
        <span>{ref.source_id} · {ref.row} · {ref.column}: {ref.value ?? "Unknown"}</span>
      </label>)}
    </fieldset>}
    <div className="decision-actions">
      <button type="submit" className="btn" disabled={disabled}>Send reply</button>
      {!request.references_required && <button type="button" className="btn" disabled={busy} onClick={()=>submit({binding,request_id:request.request_id,text:"I cannot provide this evidence.",references:[]})}>I don’t have this evidence</button>}
    </div>
  </form>;
}
