"use client";
import { useMemo, useState } from "react";
import type { FundingPreparation, Quote, RunDecision } from "../../lib/runs.generated";
import { useLiveRun, jsonRequest, LIVE_API } from "../../lib/run/live";
import { signFunding, type BuyerWallet } from "../../lib/run/wallet";
import { project } from "../../lib/run/fold";
import Canvas, { type CNode } from "./canvas";
import { IcLogo, IcX } from "./icons";
import TodoList from "./checklist";
import EvidenceAnswer from "./evidence-answer";
import ComplaintForm from "./complaint-form";

const EMPTY = {version:0,buyer:"",title:"",price:0,lines:[]};
const MAIN = new Set(["clarify","paid","produce","review","captured"]);
export default function LiveRun({recorded}: {recorded:()=>void}) {
  const live = useLiveRun();
  const {page,id,busy} = live;
  const [prompt,setPrompt] = useState("SF adults 25–34 interested in fitness, counts by ZIP.");
  const [text,setText] = useState("");
  const [payer,setPayer] = useState("");
  const [panel,setPanel] = useState("clarify");
  const [localError,setLocalError] = useState<string>();
  const [resolved,setResolved] = useState<string>();
  const [preparation,setPreparation] = useState<FundingPreparation>();
  const [offer,setOffer] = useState<Quote>();
  const view = useMemo(()=>project(live.events,{lane:"shared",ending:"human",learned:false,contract:EMPTY,live:true}),[live.events]);
  const nodes: CNode[] = view.order.map((key)=>({id:key,row:MAIN.has(key)?0:1,col:view.order.filter(k=>MAIN.has(k)===MAIN.has(key)).indexOf(key),title:view.nodes[key].step.title,desc:view.nodes[key].step.detail}));
  const canvas = {status:Object.fromEntries(Object.entries(view.nodes).map(([k,n])=>[k,n.status])),chip:Object.fromEntries(Object.entries(view.nodes).map(([k,n])=>[k,n.chip])),orb:{node:view.orb.step,mode:view.orb.mode},coin:view.coin,loops:view.loops,cards:view.cards};
  const node = view.nodes[panel];
  const enabled = (action:string) => !busy && !!page?.available_actions.some(a=>a.action===action && a.enabled);
  const binding = page?.binding;
  const orderCommand = binding ? {expected_revision:binding.revision,expected_binding:{snapshot_id:binding.snapshotId,delivery_version:binding.deliveryVersion,evidence_revision:binding.evidenceVersion}} : {};
  const delivery = view.deliveries.at(-1);
  const payment = page?.payment;
  const quote = page?.quote;
  const current = (action: string, body: Record<string,unknown>={}) => live.command(`/orders/${binding?.orderId}/${action}`,{...orderCommand,...body},true);
  const request = (action:string, body:Record<string,unknown>={}) => live.command(`/requests/${id}/${action}`,{expected_revision:page?.request.revision,...body},true);
  const runAction = (action:string, body:Record<string,unknown>) => live.command(`/runs/${id}/${action}`,{binding,...body});
  const funding = async (simulate:boolean) => {
    if (!preparation || !binding || preparation.order_id !== binding.orderId) return;
    setLocalError(undefined);
    try {
      const signature = simulate ? undefined : await signFunding((window as Window & {ethereum?:BuyerWallet}).ethereum,preparation);
      await current("funding-authorizations",{funding_attempt_id:preparation.funding_attempt_id,payment_hash:preparation.terms.payment_hash,simulate,...(signature?{signature}:{})});
      setPreparation(undefined);
    } catch (err) { setLocalError(err instanceof Error ? err.message : "Wallet declined signing; funds are not held."); }
  };
  const decision = (action:RunDecision["action"]) => runAction("decisions",{action,reason:text || "Review the current frozen evidence and proposed remedy."});
  const inspect = async (evidenceId:string) => {
    try {setResolved(JSON.stringify(await jsonRequest(`/runs/${id}/evidence/${encodeURIComponent(evidenceId)}`),null,2));}
    catch(err){setLocalError(err instanceof Error?err.message:"Evidence unavailable");}
  };
  const checks = view.contract.lines.length ? view.contract.lines : view.nodes.clarify?.drafted ?? [];
  return <div className="shell">
    <header className="top"><div className="brand"><span className="logo" aria-hidden><IcLogo/></span><div><div className="title">DatumCo <span className="faint">· AcmeFitness</span></div><div className="seatline">Aggregate dataset brokerage</div></div></div><div className="top-r"><button type="button" className="btn" onClick={recorded}>Recorded rehearsal</button><span className="tag">Live backend · synthetic data · {payment?.simulated === false ? "Base Sepolia" : "mock payments"}</span></div></header>
    <div className="tools">{id && <button type="button" className="btn" disabled={busy} onClick={()=>{live.newRun();setPreparation(undefined);setOffer(undefined);setPanel("clarify");}}>New request</button>}<span className="faint">{id ?? "New request"}</span><div className="spacer"/><button type="button" className="btn" onClick={()=>setPanel("clarify")}>Agreement</button><button type="button" className="btn" onClick={()=>setPanel("paid")}>Funding</button><button type="button" className="btn" onClick={()=>setPanel("review")}>Delivery & review</button><button type="button" className="btn" onClick={live.retry}>Refresh</button></div>
    {(live.error || localError) && <div className="tools-err" role="alert">{live.error ?? localError}</div>}
    <main className="stage">{nodes.length > 0 && <Canvas nodes={nodes} view={canvas} focus={{kind:"follow"}} panelOpen={!!panel} onNode={setPanel} overlay={<div className="caption shifted" aria-live="polite">{view.caption || "Start a request. Every live transition is persisted by the backend."}</div>}/>}
      <aside className="panel" hidden={!panel}><div className="panel-h"><div><span className="faint">{node?.step.detail ?? "Live run"}</span><h2>{node?.step.title ?? "Request & agreement"}</h2></div><button type="button" className="sq" aria-label="Close panel" onClick={()=>setPanel("")}><IcX/></button></div><div className="panel-b">
      {!id && <form onSubmit={e=>{e.preventDefault();void live.start(prompt);}}><label htmlFor="broker-prompt">Dataset request</label><textarea id="broker-prompt" value={prompt} onChange={e=>setPrompt(e.target.value)} required maxLength={4000}/><button type="submit" className="btn solid" disabled={busy}>Create request</button></form>}
      {node?.messages.map(m=><div className={`bub b-${m.from}`} key={m.id}><span className="bub-who">{m.from}</span><div className="bub-text">{m.text}</div></div>)}
      {(panel==="clarify" || !node) && page && <>
        <p>{page.request.status} · {page.request.error}</p>
        {checks.length>0 && <TodoList title="Accepted requirements" items={checks.map(line=>({id:line.id,title:line.text,status:view.nodes.produce?.checks[line.id]?.passed?"completed":"pending"}))}/>}
        {page.request.question && <p>{page.request.question.prompt}</p>}
        <label htmlFor="broker-answer">Answer or review reason</label><textarea id="broker-answer" value={text} onChange={e=>setText(e.target.value)} maxLength={2000}/>
        {enabled("clarify") && <button type="button" className="btn solid" onClick={()=>request("answers",{question_id:page.request.question?.question_id,text})} disabled={!text}>Submit answer</button>}
        {page.request.status==="compiling" && <button type="button" className="btn" disabled={busy} onClick={()=>live.command(`/internal/requests/${id}/compile`,{expected_revision:page.request.revision},true)}>Compile request</button>}
        {!binding && <><label htmlFor="payer">Buyer wallet address (optional in mock mode)</label><input id="payer" value={payer} onChange={e=>setPayer(e.target.value)}/></>}
        {enabled("quote") && <button type="button" className="btn" onClick={()=>request("quotes",payer?{payer}:{})}>Prepare quote</button>}
        {quote && <><h3>Quote · ${(quote.amount.amount_minor/100).toFixed(2)}</h3><p>{quote.work_description}</p><p>Expires {quote.expires_at}. {quote.policy?.version}</p><pre className="live-data">{JSON.stringify(quote.specification.terms,null,2)}</pre><p>Exact token amount: {quote.payment_terms?.payment_info.max_amount} atomic units. Network: Base Sepolia.</p><p>Receiver: {quote.payment_terms?.payment_info.receiver}<br/>Operator: {quote.payment_terms?.payment_info.operator}<br/>Conversion: {quote.payment_terms?.pricing_rule}</p><p>The operator controls capture/void under this agreement. Acceptance, wallet signature, submission and confirmed held funds are separate.</p>{enabled("accept_quote") && <button type="button" className="btn solid" onClick={()=>live.command("/quote-acceptance",{quote_id:quote.quote_id,customer_actor:"AcmeFitness"},true)}>Accept ${(quote.amount.amount_minor/100).toFixed(2)} quote</button>}</>}
      </>}
      {panel==="paid" && <>
        <h3>Funding · {payment?.payment.state ?? "Accept a quote first"}</h3><p>{payment?.payment.last_error}</p><p>Direct Base Commerce Payments. Mock simulation has no transaction hash. Expiry does not establish a return.</p>
        {enabled("prepare_funding") && <button type="button" className="btn" onClick={async()=>{const p=await live.command<FundingPreparation>(`/orders/${binding?.orderId}/funding-preparation`,orderCommand,true);if(p)setPreparation(p);}}>Prepare funding</button>}
        {preparation && <><p>Authorize exactly {preparation.terms.payment_info.max_amount} atomic USDC for {preparation.terms.payment_info.receiver}. Funding signature expires {preparation.expires_at}.</p>{preparation.terms.mode==="mock" ? <button type="button" className="btn solid" disabled={busy} onClick={()=>funding(true)}>Simulate mock funding</button> : <button type="button" className="btn solid" disabled={busy} onClick={()=>funding(false)}>Sign & submit funding</button>}</>}
        {payment?.operations.map(op=><p key={op.operation_id}>{op.intent.action}: {op.state} · {op.reconciliation_status}{op.transaction_hash && !payment.simulated && <span> · {op.transaction_hash}</span>}</p>)}
      </>}
      {(panel==="produce" || panel==="review") && <>
        {checks.map(line=><p key={line.id}>{view.nodes.produce?.checks[line.id]?.passed ? "✓" : "○"} {line.text}<br/><span className="faint">{view.nodes.produce?.checks[line.id]?.reason}</span></p>)}
        {delivery && <><h3>{delivery.file}</h3><a className="btn" href={`${LIVE_API}/orders/${binding?.orderId}/artifacts/${delivery.artifactId}`} download={delivery.file}>Download CSV</a><p>SHA-256: {delivery.sha256}</p><div className="sheet"><table><thead><tr><th>ZIP</th><th>Area</th><th>Count</th><th>Status</th></tr></thead><tbody>{delivery.rows.map(row=><tr key={row.zip}><td>{row.zip}</td><td>{row.area}</td><td>{row.count ?? "—"}</td><td>{row.status}</td></tr>)}</tbody></table></div></>}
        <p>Server time: {page?.server_time}<br/>Review closes: {page?.reviewClosesAt ?? "Not started"}<br/>Dispute closes: {page?.disputeClosesAt ?? "Not opened"}<br/>Latest safe capture submission: {page?.latestSafeSubmissionAt ?? "Not accepted"}<br/>Authorization expires: {page?.captureClosesAt ?? "Not accepted"}</p>
        {enabled("accept") && <button type="button" className="btn solid" onClick={()=>current("acceptance")}>Accept verified delivery</button>}
        {delivery?.artifactId && <ComplaintForm key={`${binding?.orderId}:${binding?.revision}`} targets={page?.complaint_targets ?? []} artifactId={delivery.artifactId} disabled={!enabled("dispute")} submit={complaint=>void current("disputes",{complaint})}/>}
        {binding && ["oakland","yoga","replacement"].map(scope=><button type="button" className="btn" key={scope} disabled={busy} onClick={async()=>{const q=await live.command<Quote>(`/runs/${id}/offers`,{binding,scope});if(q)setOffer(q);}}>Request provider {scope} offer</button>)}
        {offer && <><p>Separate offer: ${(offer.amount.amount_minor/100).toFixed(2)}. Acceptance and funding are still required.</p><button type="button" className="btn" onClick={()=>{live.resume(offer.request_id);setOffer(undefined);setPreparation(undefined);setPanel("clarify");}}>Review separate offer</button></>}
      </>}
      {Object.values(view.evidence).length>0 && <details><summary>Inspect persisted evidence</summary>{Object.values(view.evidence).map(e=><button type="button" className="cite" key={e.id} onClick={()=>inspect(e.id)}>{e.label}</button>)}{resolved && <pre className="live-data">{resolved}</pre>}</details>}
      {(panel==="investigate" || panel==="decide" || panel==="verdict") && <>
        <p>{node?.verdict?.reason ?? node?.waitingOn}</p><label htmlFor="reason">Reason or evidence answer</label><textarea id="reason" value={text} onChange={e=>setText(e.target.value)}/>
        {(["approve","reject","ask","escalate"] as const).map(action=><div key={action}><button type="button" className="btn" disabled={!enabled(action)} onClick={()=>decision(action)}>{action}</button><p>{page?.available_actions.find(a=>a.action===action)?.reason}</p></div>)}
      </>}
      {binding && page?.evidence_request && <EvidenceAnswer key={`${page.evidence_request.request_id}:${binding.revision}`} request={page.evidence_request} binding={binding} busy={busy} submit={answer=>void runAction("answers",{...answer})}/>}
      {panel==="captured" && <><h3>{payment?.payment.state}</h3><p>{view.nodes.captured?.entries?.length ? "Recorded balanced entries" : "Existing idempotent payment bookings; no double-entry accounting export."}</p><p>Cost and margin unavailable. No external accounting integration.</p></>}
      <p className="mock-note">Synthetic aggregate data. Suppression is a demo contract rule, not a general privacy guarantee. Review findings never authorize payment by themselves.</p>
      </div></aside>
    </main>
  </div>;
}
