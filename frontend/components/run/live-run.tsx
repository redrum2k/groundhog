"use client";
import { useEffect, useRef, useState } from "react";
import { useLiveOrder } from "../../lib/run/use-live-order";
import { S } from "../../lib/run/scenario";
import { useRunNavigation } from "../../lib/run/use-run-navigation";
import Canvas, { type CNode, type CanvasView } from "./canvas";
import { IcLogo, IcX } from "./icons";
import WalletSettings from "./wallet-settings";
import SourceLearning from "./source-learning";
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
  const recoveryAvailable=live.canRecover && !order.stage;
  const {tab,navigate,interaction}=useRunNavigation();
  const [panel,setPanel]=useState<string>();
  const previousReview=useRef({run:live.id,needed:false});
  useEffect(()=>{
    const previous=previousReview.current;
    if(previous.run===live.id && !previous.needed && order.needsHumanReview && (panel==="investigate" || panel==="verdict"))setPanel("decide");
    previousReview.current={run:live.id,needed:order.needsHumanReview};
  },[live.id,order.needsHumanReview,panel]);
  const [recenter,setRecenter]=useState(0);
  const rejection=order.assessment?.verdict.kind==="disagree" && !order.needsHumanReview && !page?.evidence_request?order.assessment:undefined;
  const openedDecision=useRef<string | undefined>(undefined);
  const panelRef=useRef<HTMLElement>(null);
  const decisionKey=rejection?`${live.id}:${rejection.seq}`:undefined;
  useEffect(()=>{
    if(tab!=="run" || !decisionKey || openedDecision.current===decisionKey)return;
    openedDecision.current=decisionKey;
    setPanel("verdict");
    setRecenter(n=>n+1);
  },[tab,decisionKey]);
  useEffect(()=>{
    if(tab==="run" && panel==="verdict" && decisionKey)panelRef.current?.focus({preventScroll:true});
  },[tab,panel,decisionKey]);
  useEffect(()=>{
    const id=requestAnimationFrame(()=>{document.documentElement.dataset.anim="";});
    return ()=>{cancelAnimationFrame(id);delete document.documentElement.dataset.anim;};
  },[]);
  const paymentState=page?.payment?.payment.state ?? (view.payments.length===1?view.paymentStates[view.payments[0].id]:undefined);
  const returned=paymentState==="voided";
  const settled=(paymentState==="captured" && !order.needsHumanReview) || returned;
  const reviewComplete=!order.needsHumanReview && !page?.payment?.payment.last_error
    && (paymentState==="capture_pending" || order.deliveryAccepted && paymentState==="funded");
  const simulated=!!page?.payment?.simulated;
  const paymentProcessing=simulated && paymentState==="funding_pending"?"paid":reviewComplete?"captured":undefined;
  const finished=settled;
  const nodes:CNode[]=view.order.map(key=>({id:key,row:MAIN.has(key)?0:1,col:view.order.filter(k=>MAIN.has(k)===MAIN.has(key)).indexOf(key),title:view.nodes[key].step.title,desc:key==="captured" && view.nodes[key].status==="running"?"Awaiting confirmation":DETAILS[key] ?? view.nodes[key].step.detail,keepChip:["verdict","grey"].includes(view.nodes[key].step.kind)}));
  const source=Object.values(view.nodes).find(n=>n.source && n.status!=="idle");
  const canvas:CanvasView={status:Object.fromEntries(Object.entries(view.nodes).map(([k,n])=>[k,reviewComplete && k==="review"?"done":n.status])),chip:Object.fromEntries(Object.entries(view.nodes).map(([k,n])=>[k,k==="captured" && n.status==="running"?"Confirming payment":CHIPS[n.status]])),orb:{node:finished?"captured":view.orb.step,mode:view.orb.mode},coin:view.coin,loops:view.loops,cards:view.cards,source:source?.source?{node:source.step.id,lines:source.source.map((l,i)=>({...l,checked:l.checked || i<order.read}))}:null};
  if(paymentProcessing) {
    const paymentNode=nodes.find(node=>node.id===paymentProcessing);
    if(paymentNode) {
      paymentNode.title="Processing payment";
      paymentNode.desc=simulated?"Simulated payment · no funds move":"Awaiting payment confirmation";
    }
    canvas.status[paymentProcessing]="running";
    canvas.chip[paymentProcessing]=simulated?"Simulating":"Confirming payment";
    canvas.orb={node:paymentProcessing,mode:"wait"};
  }
  if(rejection)for(const node of nodes) {
    if(node.id==="investigate" || node.id==="verdict") {
      node.outcome="not_upheld";
      node.desc=node.id==="investigate"?"Investigation complete":"Decision and evidence";
      canvas.chip[node.id]="Objection not upheld";
    }
  }
  const note=paymentProcessing==="paid"
    ? "Funding authorized for this demo. Simulating confirmation before production starts."
    : paymentProcessing==="captured"
      ? paymentState==="capture_pending"
        ? simulated?"Review complete. The server has queued the simulated payment release. Waiting for confirmation before marking it complete.":"Review complete. Waiting for payment confirmation."
        : simulated?"Delivery accepted. Preparing the simulated payment release.":"Delivery accepted. Preparing payment release."
      : returned?"The return is confirmed. Funds have been returned to the buyer.":settled?"Payment is confirmed and recorded.":rejection?"Objection not upheld. Open Finding to review the decision, agreement and supporting evidence.":order.needsHumanReview?"This dispute is escalated to a person. Nothing moves until they decide.":view.caption;
  const working=()=>{setPanel(undefined);navigate("run",true);setRecenter(n=>n+1);};
  const customer=()=>navigate("customer");
  const admin=()=>{navigate("run");setPanel("decide");};
  const pay=async()=>{if(!busy && await order.pay())working();};
  const turn=order.enabled("clarify")?"Your turn: answer the agent":order.enabled("accept_quote") || order.enabled("prepare_funding")?"Your turn: review & pay":order.enabled("accept")?"Your turn: review the dataset":order.enabled("quote")?"Your turn: review the request":undefined;
  const node=panel?view.nodes[panel]:undefined;
  const panelTitle=panel==="decide"?"Human review":node?.step.title ?? ({paid:"Funding",clarify:"Clarify the order",review:"Delivery & review"}[panel ?? ""] ?? "Live order");
  return <div className="shell live-shell" {...interaction}>
    <header className="top">
      <div className="brand"><IcLogo className="logo" size={22}/><div><div className="wordmark">{S.us}</div><div className="seat">Financial agent for {S.broker}</div></div></div>
      <nav className="tabs" aria-label="Demo views"><button type="button" aria-pressed={tab==="run"} className={tab==="run"?"on":""} onClick={()=>navigate("run")}>Run</button><button type="button" aria-pressed={tab==="customer"} className={tab==="customer"?"on":""} onClick={customer}>Customer view</button></nav>
      <div className="top-r">
        <WalletSettings/>
      </div>
    </header>
    <div className="tools">
      <SourceLearning openRun={live.resume}/>
      {live.id && <button type="button" className={`btn${tab==="run" && finished?" solid":""}`} disabled={busy && !recoveryAvailable} onClick={()=>{order.newRun();setPanel(undefined);customer();}}>New request</button>}
      <div className="spacer"/>
      {tab==="run" && <>
        {/* each step on the canvas opens its own panel, so there are no per-step buttons here */}
        {turn && <button type="button" className="btn turn" onClick={customer}><span className="turn-dot" aria-hidden/>{turn}</button>}
        {/* when a person has to decide, say so the same way the buyer's turn does */}
        {order.hasHumanReview && (order.needsHumanReview
          ? <button type="button" className="btn turn" onClick={admin}><span className="turn-dot" aria-hidden/>Escalated to a person: settle the dispute</button>
          : <button type="button" className="btn" onClick={admin}>Human review</button>)}
      </>}
    </div>
    {order.error && <div className="tools-err" role="alert">{order.error}<button type="button" className="btn" disabled={busy && !recoveryAvailable} onClick={live.retry}>Try again</button></div>}
    {tab==="customer"?<LiveCustomer order={order} pay={()=>void pay()} working={working} customer={customer} admin={admin}/>:<main className="stage" aria-label="Run view" tabIndex={-1}>
      {nodes.length>0?<Canvas nodes={nodes} view={canvas} focus={panel==="verdict" && rejection?{kind:"node",node:"verdict"}:finished?{kind:"node",node:"captured"}:{kind:"follow"}} hideAgent={finished} panelOpen={!!panel} onNode={setPanel} recenter={recenter} overlay={panel==="verdict" && rejection?undefined:<AgentNote text={note} settled={settled} shifted={!!panel}/>}/>:<div className="live-empty"><h2>{live.id?"Loading the order…":"The agent’s work will appear here"}</h2><p>Start the conversation and agree on a dataset to follow its progress.</p><button type="button" className="btn solid" onClick={customer}>Open customer view</button>{recorded && <button type="button" className="btn" onClick={recorded}>Open rehearsal</button>}</div>}
      {panel && <aside ref={panelRef} tabIndex={-1} className="panel" aria-label={panelTitle}><div className="panel-h"><div><div className="panel-t">{panelTitle}</div><div className="faint">{node?.step.detail ?? "Current order and evidence"}</div></div><button type="button" className="sq" aria-label="Close panel" onClick={()=>setPanel(undefined)}><IcX/></button></div><div className="panel-b live-content"><LiveStep order={order} step={panel} pay={()=>void pay()} working={working} customer={customer} review={()=>setPanel("review")}/></div></aside>}
    </main>}
  </div>;
}
