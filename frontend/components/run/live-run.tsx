"use client";
import { useEffect, useState } from "react";
import { useLiveOrder } from "../../lib/run/use-live-order";
import { S } from "../../lib/run/scenario";
import Canvas, { type CNode, type CanvasView } from "./canvas";
import { IcLogo, IcX } from "./icons";
import WalletSettings from "./wallet-settings";
import SourceLearning from "./source-learning";
import LiveCustomer from "./live-customer";
import { LiveStep } from "./live-order";

const MAIN = new Set(["clarify","paid","produce","review","captured"]);

export default function LiveRun({recorded}:{recorded?:()=>void}={}) {
  const order=useLiveOrder();
  const {live,view,page,busy}=order;
  const [tab,setTab]=useState<"customer"|"run">("customer");
  const [panel,setPanel]=useState<string>();
  const [recenter,setRecenter]=useState(0);
  useEffect(()=>{
    const id=requestAnimationFrame(()=>{document.documentElement.dataset.anim="";});
    return ()=>{cancelAnimationFrame(id);delete document.documentElement.dataset.anim;};
  },[]);
  const nodes:CNode[]=view.order.map(key=>({id:key,row:MAIN.has(key)?0:1,col:view.order.filter(k=>MAIN.has(k)===MAIN.has(key)).indexOf(key),title:view.nodes[key].step.title,desc:view.nodes[key].step.detail,keepChip:["verdict","grey"].includes(view.nodes[key].step.kind)}));
  const source=Object.values(view.nodes).find(n=>n.source && n.status!=="idle");
  const canvas:CanvasView={status:Object.fromEntries(Object.entries(view.nodes).map(([k,n])=>[k,n.status])),chip:Object.fromEntries(Object.entries(view.nodes).map(([k,n])=>[k,n.chip])),orb:{node:view.orb.step,mode:view.orb.mode},coin:view.coin,loops:view.loops,cards:view.cards,source:source?.source?{node:source.step.id,lines:source.source}:null};
  const working=()=>{setPanel(undefined);setTab("run");setRecenter(n=>n+1);};
  const customer=()=>setTab("customer");
  const admin=()=>{setTab("run");setPanel("decide");};
  const pay=async()=>{if(!busy && await order.pay())working();};
  const turn=order.enabled("clarify")?"Your turn: answer the agent":order.enabled("accept_quote") || order.enabled("prepare_funding")?"Your turn: review & pay":order.enabled("accept")?"Your turn: review the dataset":order.enabled("quote")?"Your turn: review the request":undefined;
  const paymentMode=(page?.payment?.payment.terms ?? page?.quote?.payment_terms)?.mode;
  const node=panel?view.nodes[panel]:undefined;
  const panelTitle=panel==="decide"?"Admin review":node?.step.title ?? ({paid:"Funding",clarify:"Clarify the order",review:"Delivery & review"}[panel ?? ""] ?? "Live order");
  return <div className="shell live-shell">
    <SourceLearning openRun={live.resume}/>
    <header className="top">
      <div className="brand"><IcLogo className="logo" size={22}/><div><div className="wordmark">{S.us}</div><div className="seat">{S.seat}</div></div></div>
      <nav className="tabs" aria-label="Demo views"><button type="button" aria-pressed={tab==="run"} className={tab==="run"?"on":""} onClick={()=>setTab("run")}>Run</button><button type="button" aria-pressed={tab==="customer"} className={tab==="customer"?"on":""} onClick={customer}>Customer view</button></nav>
      <div className="top-r"><span className="live-mode">Live backend{paymentMode==="base_sepolia"?" · Base Sepolia":paymentMode==="mock"?" · mock payments":""}</span><WalletSettings/></div>
    </header>
    <div className="tools">
      {live.id && <button type="button" className="btn" disabled={busy} onClick={()=>{order.newRun();setPanel(undefined);customer();}}>New request</button>}
      <span className="faint">{live.id?"The order":"New order"} · synthetic data</span><div className="spacer"/>
      {tab==="run" && <>
        {turn && <button type="button" className="btn solid" onClick={customer}>{turn}</button>}
        <button type="button" className="btn" onClick={working}>Follow agent</button>
        <button type="button" className="btn" onClick={()=>setPanel("clarify")}>Agreement</button>
        <button type="button" className="btn" onClick={()=>setPanel("paid")}>Funding</button>
        <button type="button" className="btn" onClick={()=>setPanel("review")}>Delivery & review</button>
        <button type="button" className="btn" onClick={admin}>Admin review</button>
      </>}
      <button type="button" className="btn" disabled={busy} onClick={live.retry}>Refresh</button>
    </div>
    {order.error && <div className="tools-err" role="alert">{order.error}</div>}
    {tab==="customer"?<LiveCustomer order={order} pay={()=>void pay()} working={working} customer={customer} admin={admin}/>:<main className="stage" aria-label="Run view">
      {nodes.length>0?<Canvas nodes={nodes} view={canvas} focus={{kind:"follow"}} panelOpen={!!panel} onNode={setPanel} recenter={recenter} overlay={<div className={`caption${panel?" shifted":""}`} aria-live="polite"><span key={view.caption} className="cap-text">{view.caption || "Waiting for the next backend event."}</span></div>}/>:<div className="live-empty"><h2>{live.id?"Loading the order…":"The agent’s work will appear here"}</h2><p>Start the conversation and agree on a dataset to follow its progress.</p><button type="button" className="btn solid" onClick={customer}>Open customer view</button>{recorded && <button type="button" className="btn" onClick={recorded}>Open rehearsal</button>}</div>}
      {panel && <aside className="panel"><div className="panel-h"><div><div className="panel-t">{panelTitle}</div><div className="faint">{node?.step.detail ?? "Current order and evidence"}</div></div><button type="button" className="sq" aria-label="Close panel" onClick={()=>setPanel(undefined)}><IcX/></button></div><div className="panel-b live-content"><LiveStep order={order} step={panel} pay={()=>void pay()} working={working} customer={customer}/></div></aside>}
    </main>}
  </div>;
}
