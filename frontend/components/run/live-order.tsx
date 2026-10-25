"use client";
import { useState } from "react";
import type { Evidence, Verdict } from "../../lib/run/contract";
import type { LiveOrder } from "../../lib/run/use-live-order";
import { LIVE_API } from "../../lib/run/live";
import { formatMinor } from "../../lib/money";
import PaymentJustification from "./payment-justification";
import TodoList from "./checklist";
import LiveQuote from "./live-quote";
import ComplaintForm from "./complaint-form";
import EvidenceAnswer from "./evidence-answer";
import { Chat } from "./conversation";
import { IcCheck, IcLogo, IcWallet } from "./icons";

const PAYMENT_LABELS:Record<string,string> = {
  blocked_parent:"Waiting for parent return",awaiting_signature:"Awaiting payment",funding_pending:"Payment submitted",
  funded:"Held in escrow",capture_pending:"Release pending",captured:"Paid to provider",void_pending:"Return pending",
  voided:"Funds returned",uncertain:"Payment outcome uncertain",failed:"Payment needs attention",
  expired_not_returned:"Expired · not returned",reorg_hold:"Payment on hold",
};

export function PaymentStatus({order}:{order:LiveOrder}) {
  const payment=order.page?.payment;
  return <span className="wallet" role="status"><IcWallet size={14}/><span>{payment ? PAYMENT_LABELS[payment.payment.state] : "No payment yet"}</span>{payment?.simulated && <><span className="wallet-sep" aria-hidden/><span className="faint"><span className="sr-only">, </span>Mock</span></>}</span>;
}

export function LiveIntake({order}:{order:LiveOrder}) {
  const {live,page,busy}=order;
  if(!live.id)return <form className="live-form" onSubmit={e=>{e.preventDefault();void live.start(order.prompt);}}>
    <label htmlFor="broker-prompt">What dataset do you need?</label>
    <textarea id="broker-prompt" aria-label="Dataset request" value={order.prompt} onChange={e=>order.setPrompt(e.target.value)} required maxLength={4000}/>
    <button type="submit" className="btn solid" disabled={busy}>Create request</button>
  </form>;
  return <>
    {page?.request.error && <p className="callout">{page.request.error}</p>}
    {page?.request.status==="compiling" && <p className="live-progress" role="status">The agent is working on your request…</p>}
    {page?.request.question && order.enabled("clarify") && <form className="live-form" onSubmit={e=>{e.preventDefault();void order.answerQuestion();}}>
      <label htmlFor="broker-answer">Your answer</label><textarea id="broker-answer" value={order.answer} onChange={e=>order.setAnswer(e.target.value)} required maxLength={2000}/>
      <button type="submit" className="btn solid" disabled={busy || !order.answer.trim()}>Submit answer</button>
    </form>}
    {order.enabled("quote") && !page?.quote && <button type="button" className="btn solid" onClick={()=>void order.prepareQuote()}>Prepare quote</button>}
  </>;
}

export function LiveAgreement({order,pay}:{order:LiveOrder;pay:()=>void}) {
  const quote=order.page?.quote;
  return <>
    {order.lines.length>0 && <TodoList title="Data contract" items={order.lines.map(line=>({id:line.id,title:line.text,status:"completed"}))}/>}
    {quote && <LiveQuote quote={quote} canAccept={order.enabled("accept_quote")} pay={pay}/>}
    {order.binding && <p className="faint">Agreement accepted. Delivery checks are separate and run after confirmed funding.</p>}
  </>;
}

export function LiveFunding({order,pay}:{order:LiveOrder;pay:()=>void}) {
  const payment=order.page?.payment;
  const quote=order.page?.quote;
  return <>
    <h3>Funding · {payment?.payment.state ?? "Accept a quote first"}</h3>
    {order.stage && <p className="live-progress" role="status">{order.stage}</p>}
    {payment?.payment.last_error && <p className="review-err">{payment.payment.last_error}</p>}
    {order.enabled("prepare_funding") && quote && <button type="button" className="btn solid" onClick={pay}>{quote.payment_terms?.mode==="mock"?"Simulate":"Pay"} ${formatMinor(quote.amount.amount_minor, quote.amount.decimals)}</button>}
    {payment?.payment.state==="funding_pending" && <p role="status">Payment submitted. Waiting for confirmed funds before starting work.</p>}
    {payment?.payment.state==="funded" && <p role="status">Funds confirmed and held in escrow.</p>}
    {payment?.payment.state==="capture_pending" && <p role="status">Review complete. Payment release is pending confirmation.</p>}
    <p className="faint">{payment?.simulated?"Simulated payment; no funds move on-chain.":"After funding is confirmed, payment stays in escrow during verification and review."}</p>
    {!!payment?.operations.length && <details className="live-details"><summary>Payment activity</summary>{payment.operations.map(op=><p key={op.operation_id}>{op.intent.action}: {op.state} · {op.reconciliation_status}{op.transaction_hash && !payment.simulated && <span> · {op.transaction_hash}</span>}</p>)}<p>Expiry alone does not mean funds were returned.</p></details>}
  </>;
}

export function LiveChecks({order}:{order:LiveOrder}) {
  const node=order.view.nodes.produce;
  return <TodoList title="Delivery checks" items={order.lines.map(line=>{
    const check=node?.checks[line.id];
    return {id:line.id,title:line.text,status:check?(check.passed?"completed":"cancelled"):"pending",detail:check?.reason};
  })}/>;
}

function DeliveryReviewStatus({page}:{page:LiveOrder["page"]}) {
  const paymentState=page?.payment?.payment.state;
  if(paymentState==="capture_pending")return <p role="status">Review complete. Payment release is pending confirmation.</p>;
  if(paymentState==="captured")return <p role="status">Review complete. Payment confirmed.</p>;
  const remaining=page?.reviewClosesAt ? Math.max(0,Math.ceil((Date.parse(page.reviewClosesAt)-Date.parse(page.server_time))/1000)) : undefined;
  return remaining===undefined?null:<p className="faint">Review window: {remaining>0?`${remaining}s remaining`:"ended"}</p>;
}

export function LiveDelivery({order,working}:{order:LiveOrder;working:()=>void}) {
  const [objecting,setObjecting]=useState(false);
  const {page,delivery,binding}=order;
  return <>
    {delivery ? <>
      <div className="review-grid"><div className="sheet"><div className="sheet-h"><span>{delivery.file}</span><span className="faint">Synthetic data</span></div><div className="sheet-rows"><table><thead><tr><th>ZIP</th><th>Area</th><th className="num">People</th><th>Status</th></tr></thead><tbody>{delivery.rows.map(row=><tr key={row.zip}><td className="mono">{row.zip}</td><td>{row.area}</td><td className="num">{row.count ?? "—"}</td><td>{row.status}</td></tr>)}</tbody></table></div></div><LiveChecks order={order}/></div>
      <a className="btn" href={`${LIVE_API}/orders/${binding?.orderId}/artifacts/${delivery.artifactId}`} download={delivery.file}>Download CSV</a>
      <DeliveryReviewStatus page={page}/>
      <div className="decision-actions">
        {order.enabled("accept") && <button type="button" className="btn solid" onClick={async()=>{if(await order.acceptDelivery())working();}}>Accept verified delivery</button>}
        {order.enabled("dispute") && <button type="button" className="btn" onClick={()=>setObjecting(!objecting)}>{objecting?"Close objection":"Object"}</button>}
      </div>
      {objecting && <ComplaintForm key={`${binding?.orderId}:${delivery.version}`} disabled={!order.enabled("dispute")} submit={async text=>{if(await order.complain(text)){setObjecting(false);working();}}}/>}
      <details className="live-details"><summary>Delivery and review details</summary><p>SHA-256: {delivery.sha256}</p><p>Review closes: {page?.reviewClosesAt}<br/>Dispute closes: {page?.disputeClosesAt ?? "Not opened"}<br/>Latest safe capture submission: {page?.latestSafeSubmissionAt}<br/>Authorization expires: {page?.captureClosesAt}</p></details>
    </> : <><LiveChecks order={order}/><p className="faint">{order.binding?"The delivery will appear here after funded production and independent checks.":"Agree on a dataset first."}</p></>}
  </>;
}

export function LiveOffers({order,customer}:{order:LiveOrder;customer:()=>void}) {
  if(!order.binding)return null;
  return <details className="live-details"><summary>Request additional work</summary><p>Each offer needs its own agreement and payment.</p><div className="decision-actions">{["oakland","yoga","replacement"].map(scope=><button type="button" className="btn" key={scope} disabled={order.busy} onClick={()=>void order.requestOffer(scope)}>Request provider {scope} offer</button>)}</div>
    {order.offer && <><p>Separate offer: ${formatMinor(order.offer.amount.amount_minor, order.offer.amount.decimals)}.</p><button type="button" className="btn" onClick={()=>{order.reviewOffer();customer();}}>Review separate offer</button></>}
  </details>;
}

export function LiveEvidence({order,showInspector=true}:{order:LiveOrder;showInspector?:boolean}) {
  return <>
    {order.binding && order.page?.evidence_request && <EvidenceAnswer key={`${order.page.evidence_request.request_id}:${order.binding.revision}`} request={order.page.evidence_request} binding={order.binding} busy={order.busy} submit={answer=>void order.evidenceAnswer({...answer})}/>}
    {showInspector && Object.keys(order.view.evidence).length>0 && <details className="live-details"><summary>Inspect persisted evidence</summary><EvidenceReferences evidence={Object.values(order.view.evidence)} inspect={order.inspect}/></details>}
    {showInspector && order.resolved && <details className="live-details" open><summary>Selected evidence</summary><pre className="live-data">{order.resolved}</pre></details>}
  </>;
}

function EvidenceReferences({evidence,inspect}:{evidence:Evidence[];inspect:(id:string)=>void}) {
  const groups=new Map<string,Evidence[]>();
  for(const item of evidence)groups.set(item.label,[...(groups.get(item.label) ?? []),item]);
  return <>{[...groups].map(([label,items])=><details className="live-details" key={label}><summary>{label} · {items.length} {items.length===1?"reference":"references"}</summary><div className="live-evidence-list">{items.map(item=>{
    const source=item.source;
    const locator="row" in source?`Row ${source.row} · ${source.column} · v${source.version}`:"messageId" in source?`Message ${source.messageId}`:source.reason;
    return <button type="button" className="cite" key={item.id} title={item.note} onClick={()=>inspect(item.id)}>{locator}</button>;
  })}</div></details>)}</>;
}

export function LiveVerdict({order,verdict,showEvidence=true}:{order:LiveOrder;verdict?:Verdict;showEvidence?:boolean}) {
  if(!verdict)return null;
  const evidence=verdict.evidenceIds.flatMap(id=>order.view.evidence[id]?[order.view.evidence[id]]:[]);
  return <section className="live-verdict live-agent-message" aria-label="Complaint assessment"><div className="live-agent-message-header"><IcLogo size={16}/><span>Groundhog</span><h3 className="faint">Complaint assessment</h3></div><p className="live-agent-message-text">{verdict.reason}</p>{showEvidence && evidence.length>0 && <details className="live-details"><summary>Evidence for this assessment · {evidence.length} references</summary><EvidenceReferences evidence={evidence} inspect={order.inspect}/></details>}</section>;
}

function ReviewReceipt({order}:{order:LiveOrder}) {
  const decision=order.view.nodes.decide?.decision;
  const payment=order.page?.payment?.payment;
  if(!decision)return <p className="faint">No human decision is currently required.</p>;
  const titles={approve:"Return approved",reject:"Remedy rejected",escalate:"Escalated for review",ask:"Evidence requested"};
  const lastReturn=order.page?.payment?.operations?.findLast(op=>op.intent.action==="void");
  const returnFailed=lastReturn?.state==="failed" && payment?.state!=="voided";
  const statuses:Record<string,string>={voided:"Funds returned",void_pending:"Waiting for confirmation"};
  const status=returnFailed?"Return could not be submitted":statuses[payment?.state ?? ""] ?? "Payment needs attention";
  return <section className="review-receipt" aria-label="Human review decision">
    <header className="review-receipt-heading"><span className="review-receipt-icon"><IcCheck size={16}/></span><div><span className="faint">Human review</span><h3>{titles[decision.action]}</h3></div></header>
    {decision.action==="approve" && <div className="review-receipt-payment" role="status"><strong>{status}</strong><p>{payment?.state==="voided"?"The buyer’s funds have been returned.":"Funds remain held until the return is confirmed."}</p>{returnFailed && <p className="review-err">{lastReturn.error}</p>}</div>}
    <details className="live-details"><summary>Reviewer note</summary><p>{decision.note}</p></details>
    {order.page?.payment?.simulated && <span className="faint">Simulated payment</span>}
    {payment?.state==="voided" && <p className="faint">Returning funds does not resolve any factual uncertainty. The complaint and evidence remain inspectable.</p>}
  </section>;
}

export function LiveReview({order}:{order:LiveOrder}) {
  const paymentState=order.page?.payment?.payment.state;
  if(!order.needsHumanReview || paymentState==="void_pending" || paymentState==="voided")return <ReviewReceipt order={order}/>;
  return <>{order.view.nodes.decide?.decision && <ReviewReceipt order={order}/>}<div className="review">
    <div className="review-tag">Human review · current order</div>
    <p>Review the evidence and proposed remedy. Approval can release eligible uncaptured funds; it cannot override verification or force a capture.</p>
    <label htmlFor="reason">Reason or evidence answer</label><textarea id="reason" value={order.reason} onChange={e=>order.setReason(e.target.value)}/>
    {(["approve","reject","ask","escalate"] as const).map(action=><div key={action}><button type="button" className="btn" disabled={!order.enabled(action)} onClick={()=>void order.decide(action)}>{action}</button><p className="faint">{order.page?.available_actions.find(a=>a.action===action)?.reason}</p></div>)}
  </div></>;
}

export function LiveStep({order,step,pay,working,customer}:{order:LiveOrder;step:string;pay:()=>void;working:()=>void;customer:()=>void}) {
  const node=order.view.nodes[step];
  const question=order.page?.evidence_request;
  const messages=node?.messages.filter(message=>message.from!=="agent" || message.text!==question?.prompt) ?? [];
  return <>
    {step==="clarify" && <LiveAgreement order={order} pay={pay}/>}
    {!!messages.length && <Chat items={messages} view={order.view} onCite={order.cite}/>}
    {node?.waitingOn && !question && !(step==="decide" && node.decision?.action==="approve") && <p role="status">{node.waitingOn}</p>}
    {step==="clarify" && <LiveIntake order={order}/>}
    {step==="paid" && <LiveFunding order={order} pay={pay}/>}
    {step==="produce" && <LiveChecks order={order}/>}
    {step==="review" && <><LiveDelivery order={order} working={working}/><LiveOffers order={order} customer={customer}/></>}
    {node?.verdict && <LiveVerdict order={order} verdict={node.verdict}/>}
    {step==="decide" && <LiveReview order={order}/>}
    {step==="captured" && <><LiveFunding order={order} pay={pay}/><p>Settlement reflects confirmed payment evidence. No external accounting integration.</p></>}
    <LiveEvidence order={order}/>
    {order.binding && <PaymentJustification key={`${order.binding.orderId}:${order.binding.revision}`} orderId={order.binding.orderId}/>}
  </>;
}
