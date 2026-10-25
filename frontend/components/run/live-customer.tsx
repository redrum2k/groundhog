"use client";
import { useLayoutEffect, useRef } from "react";
import type { LiveOrder } from "../../lib/run/use-live-order";
import { Chat, Decision, Transcript } from "./conversation";
import { GuideProvider, OrbSlot, useOrbFlight } from "./guide";
import { LiveAgreement, LiveDelivery, LiveEvidence, LiveFunding, LiveIntake, LiveVerdict, PaymentStatus } from "./live-order";

export default function LiveCustomer({order,pay,working,customer,admin}:{order:LiveOrder;pay:()=>void;working:()=>void;customer:()=>void;admin:()=>void}) {
  const {col,decision,assessment,at,funding,quote}=useConversationGuide(order);
  return <main className="customer live-conversation" aria-label="Customer view" tabIndex={-1}>
    <GuideProvider value={{at,mood:{home:order.view.orb.mode,decision:"wait"}}}>
      <div className="cust-col" ref={col}>
        <div className="customer-payment"><OrbSlot name="home"/><PaymentStatus order={order}/></div>
        {!order.live.id && <div className="live-welcome"><h1>What should we find for you?</h1><p>Describe the people, place and counts you need. We’ll clarify the requirements, agree on a price, then produce and check the dataset.</p></div>}
        {order.messages.length>0 && <Transcript title="Your conversation with Groundhog" count={order.messages.length} open compact={!!quote || !!order.delivery}>
          <Chat items={order.messages} view={order.view} onCite={order.cite} guide/>
        </Transcript>}
        <LiveIntake order={order}/>
        {order.assessment && <div ref={assessment} className="live-assessment"><LiveVerdict order={order} verdict={order.assessment.verdict} showEvidence={false} review={()=>decision.current?.scrollIntoView({block:"start",behavior:"instant"})} customer={customer}/></div>}
        <div ref={decision} className="live-decisions">
          <OrderDecisions order={order} pay={pay} working={working} funding={funding}/>
        </div>
        {order.hasHumanReview && <div className="callout">{order.page?.payment?.payment.state==="voided"?"Funds returned after human review.":order.page?.payment?.payment.state==="void_pending"?"Return approved; waiting for confirmation.":order.needsHumanReview?"This order needs human review.":"A human review decision is recorded."} <button type="button" className="btn" onClick={admin}>Open human review</button></div>}
        <LiveEvidence order={order}/>
      </div>
    </GuideProvider>
  </main>;
}

function OrderDecisions({order,pay,working,funding}:{order:LiveOrder;pay:()=>void;working:()=>void;funding:boolean}) {
  const quote=order.page?.quote;
  const payment=order.page?.payment?.payment;
  return <>
          {(quote || order.lines.length>0) && <Decision title="Data contract" open={!order.binding} taken={order.binding?"Accepted":undefined}>
            <LiveAgreement order={order} pay={pay}/>
          </Decision>}
          {(payment || order.stage) && <Decision title="Payment" open={funding || !!order.stage} taken={payment?.state==="funded"?"Held in escrow":payment?.state==="captured"?"Captured":payment?.state==="voided"?"Returned":undefined}>
            <LiveFunding order={order} pay={pay}/>
          </Decision>}
          {order.delivery && <Decision title={`Your dataset${order.delivery.version>1?` · version ${order.delivery.version}`:""}`} open={order.enabled("accept") || order.enabled("dispute")}>
            <LiveDelivery order={order} working={working}/>
          </Decision>}
  </>;
}

function useConversationGuide(order:LiveOrder) {
  const col=useRef<HTMLDivElement>(null);
  const decision=useRef<HTMLDivElement>(null);
  const assessment=useRef<HTMLDivElement>(null);
  const payment=order.page?.payment?.payment;
  const quote=order.page?.quote;
  const funding=!!payment && !["funded","captured","voided"].includes(payment.state);
  const needsDecision=!!order.stage || funding || !order.binding && !!quote || order.enabled("accept");
  const at=useOrbFlight(col,needsDecision?"decision":order.messages.length?"transcript":"home");
  const verdict=order.assessment?.verdict;
  const turn=verdict?JSON.stringify([verdict.reason,verdict.evidenceIds]):order.page?.request.question?.question_id ?? (order.enabled("accept")?order.delivery?.artifactId:!order.binding?quote?.quote_id:undefined);
  useLayoutEffect(()=>{
    if(turn){
      if(assessment.current)assessment.current.scrollIntoView?.({block:"start",behavior:"instant"});
      else decision.current?.scrollIntoView?.({block:"nearest",behavior:"instant"});
    }
  },[turn]);
  return {col,decision,assessment,at,funding,quote};
}
