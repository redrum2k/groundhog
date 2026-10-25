"use client";
import { useMemo, useState } from "react";
import type { Quote, RunDecision } from "../runs.generated";
import type { Source } from "./contract";
import { project } from "./fold";
import { jsonRequest, useLiveRun } from "./live";
import { useBuyerAddress } from "./buyer-settings";
import { useCheckout } from "./use-checkout";

const EMPTY = {version:0,buyer:"",title:"",price:0,lines:[]};

export function useLiveOrder() {
  const live = useLiveRun();
  const checkout = useCheckout(live.id, live.retry);
  const payer = useBuyerAddress();
  const [prompt,setPrompt] = useState("SF adults 25–34 interested in fitness, counts by ZIP.");
  const [answer,setAnswer] = useState("");
  const [reason,setReason] = useState("");
  const [offer,setOffer] = useState<Quote>();
  const [resolved,setResolved] = useState<string>();
  const [error,setError] = useState<string>();
  const view = useMemo(()=>project(live.events,{lane:"shared",ending:"human",learned:false,contract:EMPTY,live:true}),[live.events]);
  const page = live.page;
  const binding = page?.binding;
  const busy = live.busy || !!checkout.stage;
  const enabled = (action:string) => !busy && !!page?.available_actions.some(a=>a.action===action && a.enabled);
  const command = binding ? {expected_revision:binding.revision,expected_binding:{snapshot_id:binding.snapshotId,delivery_version:binding.deliveryVersion,evidence_revision:binding.evidenceVersion}} : {};
  const current = (action:string,body:Record<string,unknown>={}) => live.command(`/orders/${binding?.orderId}/${action}`,{...command,...body},true);
  const request = (action:string,body:Record<string,unknown>={}) => live.command(`/requests/${live.id}/${action}`,{expected_revision:page?.request.revision,...body},true);
  const runAction = (action:string,body:Record<string,unknown>) => live.command(`/runs/${live.id}/${action}`,{binding,...body});
  const delivery = view.deliveries.at(-1);
  const lines = view.contract.lines.length ? view.contract.lines : view.nodes.clarify?.drafted ?? [];
  const messages = live.events.flatMap(event=>event.type==="message"?[event.message]:[]);

  async function inspect(evidenceId:string) {
    try { setResolved(JSON.stringify(await jsonRequest(`/runs/${live.id}/evidence/${encodeURIComponent(evidenceId)}`),null,2)); }
    catch(err) { setError(err instanceof Error?err.message:"Evidence unavailable"); }
  }
  function cite(source:Source) {
    const evidence=Object.values(view.evidence).find(e=>e.source===source);
    if(evidence)void inspect(evidence.id);
  }
  function clear() { checkout.clearError();setOffer(undefined);setResolved(undefined);setError(undefined);setAnswer("");setReason(""); }
  return {
    live, page, view, binding, busy, enabled, delivery, lines, messages,
    prompt, setPrompt, answer, setAnswer, reason, setReason, offer, resolved, inspect, cite,
    stage:checkout.stage, error:live.error ?? error ?? checkout.error,
    newRun:()=>{live.newRun();clear();},
    prepareQuote:()=>request("quotes",payer?{payer}:{}),
    answerQuestion:async()=>{const result=await request("answers",{question_id:page?.request.question?.question_id,text:answer});if(result)setAnswer("");},
    pay:async()=>{setError(undefined);return page?.quote ? checkout.pay(page.quote,binding) : false;},
    acceptDelivery:async()=>!!await current("acceptance"),
    complain:async(text:string)=>!!await current("complaints",{text}),
    decide:(action:RunDecision["action"])=>runAction("decisions",{action,reason:reason || "Review the current frozen evidence and proposed remedy."}),
    evidenceAnswer:(answer:Record<string,unknown>)=>runAction("answers",answer),
    requestOffer:async(scope:string)=>{const q=await live.command<Quote>(`/runs/${live.id}/offers`,{binding,scope});if(q)setOffer(q);},
    reviewOffer:()=>{if(offer){live.resume(offer.request_id);clear();}},
  };
}

export type LiveOrder = ReturnType<typeof useLiveOrder>;
