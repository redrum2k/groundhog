"use client";
import { useEffect, useRef, useState } from "react";
import { useLiveOrder } from "../../lib/run/use-live-order";
import { S } from "../../lib/run/scenario";
import { useRunNavigation } from "../../lib/run/use-run-navigation";
import Canvas, { type CNode, type CanvasView } from "./canvas";
import { IcLogo, IcX } from "./icons";
import WalletSettings from "./wallet-settings";
import LiveCustomer from "./live-customer";
import { LiveStep } from "./live-order";
import AgentNote from "./agent-note";

const MAIN = new Set(["clarify","paid","produce","review","captured"]);
const DETAILS:Record<string,string> = {
  clarify:"Agree on the contract", paid:"Buyer confirms funding", produce:"Validate against the contract",
  review:"Review the delivery", investigate:"Evidence-backed resolution", verdict:"Evidence assessment",
  decide:"Bounded reviewer actions", captured:"Confirmed settlement",
};
const CHIPS = {idle:undefined,running:"In progress",done:"Done",waiting:"Waiting",fail:"Needs attention",grey:"Needs review"};

export default function LiveRun({recorded}:{recorded?:()=>void}={}) {
  const order=useLiveOrder();
  const {live,view,page,busy}=order;
  const {tab,navigate,interaction}=useRunNavigation();
  const [panel,setPanel]=useState<string>();
  const previousReview=useRef({run:live.id,needed:false});
  useEffect(()=>{
    const previous=previousReview.current;
    if(previous.run===live.id && !previous.needed && order.needsHumanReview && (panel==="investigate" || panel==="verdict"))setPanel("decide");
    previousReview.current={run:live.id,needed:order.needsHumanReview};
  },[live.id,order.needsHumanReview,panel]);
  const [recenter,setRecenter]=useState(0);
  useEffect(()=>{
    const id=requestAnimationFrame(()=>{document.documentElement.dataset.anim="";});
    return ()=>{cancelAnimationFrame(id);delete document.documentElement.dataset.anim;};
  },[]);
  const paymentState=page?.payment?.payment.state ?? (view.payments.length===1?view.paymentStates[view.payments[0].id]:undefined);
  const returned=paymentState==="voided";
  const settled=(paymentState==="captured" && !order.needsHumanReview) || returned;
  const reviewComplete=!order.needsHumanReview && !page?.payment?.payment.last_error
    && (paymentState==="capture_pending" || order.deliveryAccepted && paymentState==="funded");
  const finished=settled || reviewComplete;
  const completionTitle=order.deliveryAccepted?"Dataset accepted":"Review complete";
  const nodes:CNode[]=view.order.map(key=>({id:key,row:MAIN.has(key)?0:1,col:view.order.filter(k=>MAIN.has(k)===MAIN.has(key)).indexOf(key),title:key==="captured" && reviewComplete?completionTitle:view.nodes[key].step.title,desc:key==="captured" && reviewComplete?"Payment processing":key==="captured" && view.nodes[key].status==="running"?"Awaiting confirmation":DETAILS[key] ?? view.nodes[key].step.detail,keepChip:["verdict","grey"].includes(view.nodes[key].step.kind)}));
  const source=Object.values(view.nodes).find(n=>n.source && n.status!=="idle");
  const canvas:CanvasView={status:Object.fromEntries(Object.entries(view.nodes).map(([k,n])=>[k,reviewComplete && ["review","captured"].includes(k)?"done":n.status])),chip:Object.fromEntries(Object.entries(view.nodes).map(([k,n])=>[k,k==="captured" && reviewComplete?order.deliveryAccepted?"Accepted":"Reviewed":k==="captured" && n.status==="running"?"Confirming payment":CHIPS[n.status]])),orb:{node:finished?"captured":view.orb.step,mode:view.orb.mode},coin:reviewComplete?null:view.coin,loops:view.loops,cards:view.cards,source:source?.source?{node:source.step.id,lines:source.source}:null};
  const note=returned?"The return is confirmed. Funds have been returned to the buyer.":settled?"Payment is confirmed and recorded.":reviewComplete?`${completionTitle}. Payment is processing in the background.`:view.caption;
  const working=()=>{setPanel(undefined);navigate("run",true);setRecenter(n=>n+1);};
  const customer=()=>navigate("customer");
  const admin=()=>{navigate("run");setPanel("decide");};
  const pay=async()=>{if(!busy && await order.pay())working();};
  const turn=order.enabled("clarify")?"Your turn: answer the agent":order.enabled("accept_quote") || order.enabled("prepare_funding")?"Your turn: review & pay":order.enabled("accept")?"Your turn: review the dataset":order.enabled("quote")?"Your turn: review the request":undefined;
  const node=panel?view.nodes[panel]:undefined;
  const panelTitle=panel==="decide"?"Admin review":node?.step.title ?? ({paid:"Funding",clarify:"Clarify the order",review:"Delivery & review"}[panel ?? ""] ?? "Live order");
  return <div className="shell live-shell" {...interaction}>
    <header className="top">
      <div className="brand"><IcLogo className="logo" size={22}/><div><div className="wordmark">{S.us}</div><div className="seat">Financial agent for {S.broker}</div></div></div>
      <nav className="tabs" aria-label="Demo views"><button type="button" aria-pressed={tab==="run"} className={tab==="run"?"on":""} onClick={()=>navigate("run")}>Run</button><button type="button" aria-pressed={tab==="customer"} className={tab==="customer"?"on":""} onClick={customer}>Customer view</button></nav>
      <div className="top-r"><WalletSettings/></div>
    </header>
    <div className="tools">
      {live.id && <button type="button" className={`btn${tab==="run" && finished?" new-request-ready":""}`} disabled={busy} onClick={()=>{order.newRun();setPanel(undefined);customer();}}>New request</button>}
      <div className="spacer"/>
      {tab==="run" && <>
        {turn && <button type="button" className="btn solid" onClick={customer}>{turn}</button>}
        <button type="button" className="btn" onClick={working}>Follow agent</button>
        <button type="button" className="btn" onClick={()=>setPanel("clarify")}>Agreement</button>
        <button type="button" className="btn" onClick={()=>setPanel("paid")}>Funding</button>
        <button type="button" className="btn" onClick={()=>setPanel("review")}>Delivery & review</button>
        {order.hasHumanReview && <button type="button" className="btn" onClick={admin}>Admin review</button>}
      </>}
      <button type="button" className="btn" disabled={busy} onClick={live.retry}>Refresh</button>
    </div>
    {order.error && <div className="tools-err" role="alert">{order.error}</div>}
    {tab==="customer"?<LiveCustomer order={order} pay={()=>void pay()} working={working} customer={customer} admin={admin}/>:<main className="stage" aria-label="Run view" tabIndex={-1}>
      {nodes.length>0?<Canvas nodes={nodes} view={canvas} focus={finished?{kind:"node",node:"captured"}:{kind:"follow"}} hideAgent={finished} panelOpen={!!panel} onNode={setPanel} recenter={recenter} overlay={<AgentNote text={note} settled={settled} shifted={!!panel}/>}/>:<div className="live-empty"><h2>{live.id?"Loading the order…":"The agent’s work will appear here"}</h2><p>Start the conversation and agree on a dataset to follow its progress.</p><button type="button" className="btn solid" onClick={customer}>Open customer view</button>{recorded && <button type="button" className="btn" onClick={recorded}>Open rehearsal</button>}</div>}
      {panel && <aside className="panel" aria-label={panelTitle}><div className="panel-h"><div><div className="panel-t">{panelTitle}</div><div className="faint">{node?.step.detail ?? "Current order and evidence"}</div></div><button type="button" className="sq" aria-label="Close panel" onClick={()=>setPanel(undefined)}><IcX/></button></div><div className="panel-b live-content"><LiveStep order={order} step={panel} pay={()=>void pay()} working={working} customer={customer}/></div></aside>}
    </main>}
  </div>;
}
