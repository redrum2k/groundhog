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
import { IcCheck, IcDownload, IcLogo, IcWallet, IcX } from "./icons";

const PAYMENT_LABELS:Record<string,string> = {
  blocked_parent:"Waiting for parent return",awaiting_signature:"Awaiting payment",funding_pending:"Payment submitted",
  funded:"Held in escrow",capture_pending:"Release pending",captured:"Paid to provider",void_pending:"Return pending",
  voided:"Funds returned",uncertain:"Payment outcome uncertain",failed:"Payment needs attention",
  expired_not_returned:"Expired · not returned",reorg_hold:"Payment on hold",
};

export function PaymentStatus({order}:{order:LiveOrder}) {
  const payment=order.page?.payment;
  return <span className="wallet" role="status"><IcWallet size={14}/><span>{payment ? PAYMENT_LABELS[payment.payment.state] : "No payment yet"}</span>{payment?.simulated && <><span className="wallet-sep" aria-hidden/><span className="faint"><span className="sr-only">, </span>Demo: no funds move</span></>}</span>;
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

function isLateComplaint(order:LiveOrder) {
  const closesAt=order.page?.reviewClosesAt;
  if(!order.delivery || order.deliveryAccepted || !closesAt)return false;
  return !order.enabled("accept") && order.enabled("dispute")
    && Date.parse(order.page!.server_time)>=Date.parse(closesAt);
}

/** `audit`: the Run panel also shows hashes and deadlines; the customer view keeps to the decision. */
export function LiveDelivery({order,working,audit}:{order:LiveOrder;working:()=>void;audit?:boolean}) {
  const {page,delivery,binding}=order;
  return <>
    {delivery ? <>
      <div className="review-grid"><div className="sheet"><div className="sheet-h"><span>{delivery.file}</span><a className="sheet-dl" href={`${LIVE_API}/orders/${binding?.orderId}/artifacts/${delivery.artifactId}`} download={delivery.file}><IcDownload size={13} strokeWidth={1.8} aria-hidden/>Download CSV</a></div><div className="sheet-rows"><table><thead><tr><th>ZIP</th><th>Area</th><th className="num">People</th><th>Status</th></tr></thead><tbody>{delivery.rows.map(row=><tr key={row.zip}><td className="mono">{row.zip}</td><td>{row.area}</td><td className="num">{row.count ?? "—"}</td><td>{row.status}</td></tr>)}</tbody></table></div></div><LiveChecks order={order}/></div>
      <DeliveryReviewStatus page={page}/>
      <DeliveryDecisions order={order} working={working}/>
      {audit && <details className="live-details"><summary>Delivery and review details</summary><p>SHA-256: {delivery.sha256}</p><p>Review closes: {page?.reviewClosesAt}<br/>Dispute closes: {page?.disputeClosesAt ?? "Not opened"}<br/>Latest safe capture submission: {page?.latestSafeSubmissionAt}<br/>Authorization expires: {page?.captureClosesAt}</p></details>}
    </> : <><LiveChecks order={order}/><p className="faint">{order.binding?"The delivery will appear here after funded production and independent checks.":"Agree on a dataset first."}</p></>}
  </>;
}

function DeliveryDecisions({order,working}:{order:LiveOrder;working:()=>void}) {
  const [objecting,setObjecting]=useState(false);
  const {binding}=order;
  const late=isLateComplaint(order);
  return <>
      {/* the backend keeps a complaint open after the review window, but it goes to human review and can't stop payment */}
      {late && <p className="faint">The delivery review window has ended. Further complaints go to human review and cannot cancel a submitted payment.</p>}
      <div className="decision-actions">
        {order.enabled("accept") && <button type="button" className="btn solid" onClick={async()=>{if(await order.acceptDelivery())working();}}>Accept verified delivery</button>}
        <button type="button" className="btn" disabled={!objecting && !order.enabled("dispute")} onClick={()=>setObjecting(!objecting)}>{objecting?"Close":late?"File a late complaint":order.view.dispute?"Object again":"Object"}</button>
      </div>
      {objecting && <ComplaintForm key={`${binding?.orderId}:${order.delivery!.version}`} disabled={!order.enabled("dispute")} submit={async text=>{if(await order.complain(text)){setObjecting(false);working();}}}/>}
  </>;
}

export function LiveOffers({order,customer}:{order:LiveOrder;customer:()=>void}) {
  if(!order.binding)return null;
  return <details className="live-details"><summary>Request additional work</summary><p>Each offer needs its own agreement and payment.</p><div className="decision-actions">{["oakland","yoga","replacement"].map(scope=><button type="button" className="btn" key={scope} disabled={order.busy} onClick={()=>void order.requestOffer(scope)}>Request provider {scope} offer</button>)}</div>
    {order.offer && <><p>Separate offer: ${formatMinor(order.offer.amount.amount_minor, order.offer.amount.decimals)}.</p><button type="button" className="btn" onClick={()=>{order.reviewOffer();customer();}}>Review separate offer</button></>}
  </details>;
}

export function LiveEvidence({order,audit}:{order:LiveOrder;audit?:boolean}) {
  return <>
    {order.binding && order.page?.evidence_request && <EvidenceAnswer key={`${order.page.evidence_request.request_id}:${order.binding.revision}`} request={order.page.evidence_request} binding={order.binding} busy={order.busy} submit={answer=>void order.evidenceAnswer({...answer})}/>}
    {audit && Object.keys(order.view.evidence).length>0 && <details className="live-details"><summary>Inspect persisted evidence</summary><EvidenceReferences evidence={Object.values(order.view.evidence)} inspect={order.inspect}/></details>}
    {audit && order.resolved && <details className="live-details" open><summary>Selected evidence</summary><pre className="live-data">{order.resolved}</pre></details>}
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

function ReviewerGuidance({order,verdict}:{order:LiveOrder;verdict:Verdict}) {
  const memories=verdict.finding?.reviewer_guidance;
  if(!memories?.length)return null;
  return <details className="live-details"><summary>Prior reviewer guidance consulted</summary>
    <p className="faint">Retrieved reference material. Consultation alone does not establish a successful answer; the current assessment and evidence checks determine the result.</p>
    {memories.map(memory=><div key={memory.memory_id}>
      <p>{memory.guidance}</p><p>Previous explanation: {memory.explanation}</p>
      <p className="faint">{memory.actor} · Originating case: {memory.originating_case} · Order: {memory.originating_order}</p>
      <details className="live-details"><summary>Current supporting citations</summary>{memory.current_citations.map(ref=><p key={`${ref.sha256}:${ref.source_id}:${ref.version}:${ref.row}:${ref.column}`}><a className="cite" href={`${LIVE_API}/orders/${order.binding?.orderId}/artifacts/${ref.artifact_id}`} target="_blank" rel="noreferrer">{ref.source_id} · {ref.row} · {ref.column} · v{ref.version}</a>: {ref.value ?? "Unknown / null"}<br/><span className="faint">SHA-256: {ref.sha256}</span></p>)}</details>
    </div>)}
  </details>;
}

export function LiveVerdict({order,verdict,showEvidence=true,review,customer}:{order:LiveOrder;verdict?:Verdict;showEvidence?:boolean;review?:()=>void;customer?:()=>void}) {
  if(!verdict)return null;
  if(verdict.kind==="disagree")return <ObjectionDecision order={order} verdict={verdict} review={review} customer={customer}/>;
  const evidence=verdict.evidenceIds.flatMap(id=>order.view.evidence[id]?[order.view.evidence[id]]:[]);
  return <section className="live-verdict live-agent-message" aria-label="Complaint assessment"><div className="live-agent-message-header"><IcLogo size={16}/><span>Groundhog</span><h3 className="faint">Complaint assessment</h3></div><p className="live-agent-message-text">{verdict.reason}</p><ReviewerGuidance order={order} verdict={verdict}/>{showEvidence && evidence.length>0 && <details className="live-details"><summary>Evidence for this assessment · {evidence.length} references</summary><EvidenceReferences evidence={evidence} inspect={order.inspect}/></details>}</section>;
}

const assessmentSentences=new Intl.Segmenter("en",{granularity:"sentence"});

function objectionDetails(order:LiveOrder,verdict:Verdict) {
  const field=verdict.finding?.effective.obligation_id.replace(/^dataset:/,"");
  const term=order.lines.find(line=>line.id===`R-${field?.toUpperCase()}`);
  const terms=order.page?.quote?.specification.terms;
  const geography=terms && "geography" in terms?terms.geography:undefined;
  const evidence=verdict.evidenceIds.flatMap(id=>order.view.evidence[id]?[order.view.evidence[id]]:[]);
  const oakland=geography==="San Francisco" && /\bOakland\b/i.test(order.view.dispute?.claim ?? "");
  const outsideArea=oakland && field==="geography";
  const summary=outsideArea?"Oakland falls outside the accepted San Francisco scope. This order does not include Oakland data.":Array.from(assessmentSentences.segment(verdict.reason),part=>part.segment).slice(0,2).join("").trim();
  const canOffer=!!order.binding && !order.busy && !order.needsHumanReview && !!order.page?.latestSafeSubmissionAt && Date.parse(order.page.server_time)<Date.parse(order.page.latestSafeSubmissionAt);
  const title=outsideArea?"Oakland wasn’t included in this order":field==="geography" && geography?`Your order covers ${geography}`:"The assessment did not support this objection";
  const agreed=term?.text || order.view.contract.title || "The accepted contract below.";
  return {title,agreed,summary,evidence,oakland,canOffer};
}

function ObjectionDecision({order,verdict,review,customer}:{order:LiveOrder;verdict:Verdict;review?:()=>void;customer?:()=>void}) {
  const {title,agreed,summary,evidence,oakland,canOffer}=objectionDetails(order,verdict);
  return <section className="objection-decision" aria-label="Complaint assessment">
    <div className="objection-outcome"><IcX size={15}/><span>Objection not upheld</span></div>
    <h3>{title}</h3>
    <dl className="objection-facts">
      {order.view.dispute && <><dt>You requested</dt><dd>{order.view.dispute.claim}</dd></>}
      <dt>You agreed to</dt><dd>{agreed}</dd>
      <dt>Reason</dt><dd>{summary}</dd>
    </dl>
    <div className="objection-payment"><PaymentStatus order={order}/><p>No fee is charged for this objection. The assessment alone does not release payment.</p></div>
    <div className="objection-actions">
      {review && <button type="button" className="btn solid" onClick={review}>Review delivery</button>}
      {oakland && <button type="button" className="btn" disabled={!canOffer} onClick={()=>void order.requestOffer("oakland")}>Request an Oakland quote</button>}
    </div>
    {order.offer && <div className="callout"><p>Separate quote: ${formatMinor(order.offer.amount.amount_minor,order.offer.amount.decimals)}. Review and accept it before any additional work.</p><button type="button" className="btn" disabled={order.busy} onClick={()=>{order.reviewOffer();customer?.();}}>Review separate offer</button></div>}
    <details className="live-details"><summary>View agreement and supporting evidence</summary>
      <ul>{order.lines.map(line=><li key={line.id}>{line.text}</li>)}</ul>
      {evidence.map(item=><blockquote key={item.id}><strong>{item.label}</strong><p>{"quote" in item?item.quote:"value" in item?item.value:item.note}</p><p className="faint">{item.note}</p></blockquote>)}
      {!evidence.length && <p className="faint">No linked evidence references were supplied with this assessment.</p>}
    </details>
    <ReviewerGuidance order={order} verdict={verdict}/>
    {summary!==verdict.reason && <details className="live-details"><summary>Read full assessment</summary><p>{verdict.reason}</p></details>}
  </section>;
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
    {decision.guidanceMemoryId && <p role="status">Guidance saved for similar cases</p>}
    <details className="live-details"><summary>Reviewer note</summary><p>{decision.note}</p></details>
    {order.page?.payment?.simulated && <span className="faint">Simulated payment</span>}
    {payment?.state==="voided" && <p className="faint">Returning funds does not resolve any factual uncertainty. The complaint and evidence remain inspectable.</p>}
  </section>;
}

const REVIEW_ACTIONS = { approve: "Approve", reject: "Reject", ask: "Ask", escalate: "Escalate" } as const;

function ReviewEvidence({order}:{order:LiveOrder}) {
  const selected=new Set(order.reviewEvidence ?? []);
  const seen=new Set<string>();
  const evidence=Object.values(order.view.evidence).filter(item=>{
    const source=item.source;
    if(source.kind!=="cell" || !source.reference)return false;
    const ref=source.reference;
    if(ref.source_id==="delivery" && ref.version!==order.binding?.deliveryVersion)return false;
    const key=JSON.stringify(ref);
    if(seen.has(key))return false;
    seen.add(key);return true;
  });
  return <details className="live-details"><summary>Supporting evidence</summary>
    <p className="faint">Select up to eight current citations for reusable guidance. A remedy decision alone does not create guidance.</p>
    <fieldset className="required-evidence"><legend>Review citations</legend>{evidence.map(item=><label key={item.id}>
      <input type="checkbox" checked={selected.has(item.id)} disabled={order.busy || !selected.has(item.id) && selected.size>=8}
        onChange={e=>order.setReviewEvidence(e.target.checked?[...selected,item.id]:[...selected].filter(id=>id!==item.id))}/>
      <span>{item.label} · {item.source.kind==="cell"?`${item.source.row} · ${item.source.column}`:""}</span>
    </label>)}</fieldset>
  </details>;
}

export function LiveReview({order}:{order:LiveOrder}) {
  const paymentState=order.page?.payment?.payment.state;
  if(!order.needsHumanReview || paymentState==="void_pending" || paymentState==="voided")return <ReviewReceipt order={order}/>;
  return <>{order.view.nodes.decide?.decision && <ReviewReceipt order={order}/>}<div className="review live-review">
    <div className="review-tag">Needs a person&apos;s decision</div>
    <p className="live-review-note">Review the evidence and the proposed remedy. Approval can release eligible uncaptured funds; it can&apos;t override verification or force a capture.</p>
    <label htmlFor="reason">Reason or evidence answer</label><textarea id="reason" value={order.reason} onChange={e=>order.setReason(e.target.value)}/>
    <label htmlFor="review-guidance">Guidance for similar cases (optional)</label><textarea id="review-guidance" maxLength={1200} value={order.guidance ?? ""} onChange={e=>order.setGuidance(e.target.value)}/>
    <ReviewEvidence order={order}/>
    {/* one row per action: the button, then why it is or isn't available right now */}
    <ul className="live-review-choices">{(["approve","reject","ask","escalate"] as const).map(action=><li key={action}><button type="button" className="btn" disabled={!order.enabled(action)} onClick={()=>void order.decide(action)}>{REVIEW_ACTIONS[action]}</button><span>{order.page?.available_actions.find(a=>a.action===action)?.reason}</span></li>)}</ul>
  </div></>;
}

export function LiveStep({order,step,pay,working,customer,review}:{order:LiveOrder;step:string;pay:()=>void;working:()=>void;customer:()=>void;review?:()=>void}) {
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
    {step==="review" && <><LiveDelivery order={order} working={working} audit/><LiveOffers order={order} customer={customer}/></>}
    {node?.verdict && <LiveVerdict order={order} verdict={step==="verdict"?order.assessment?.verdict:node.verdict} review={review} customer={customer}/>}
    {step==="decide" && <LiveReview order={order}/>}
    {step==="captured" && <><LiveFunding order={order} pay={pay}/><p>Settlement reflects confirmed payment evidence. No external accounting integration.</p></>}
    <LiveEvidence order={order} audit/>
    {order.binding && <PaymentJustification key={`${order.binding.orderId}:${order.binding.revision}`} orderId={order.binding.orderId}/>}
  </>;
}
