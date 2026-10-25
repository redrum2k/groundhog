"use client";
import { useLayoutEffect, useRef } from "react";
import type { LiveOrder } from "../../lib/run/use-live-order";
import { S } from "../../lib/run/scenario";
import { Chat, Decision, Transcript } from "./conversation";
import { GuideProvider, OrbSlot, useOrbFlight } from "./guide";
import { IcSummit } from "./icons";
import { LiveAgreement, LiveDelivery, LiveEvidence, LiveFunding, LiveIntake, LiveOffers, PaymentStatus } from "./live-order";

export default function LiveCustomer({order,pay,working,customer,admin}:{order:LiveOrder;pay:()=>void;working:()=>void;customer:()=>void;admin:()=>void}) {
  const {col,decision,at,funding,quote}=useConversationGuide(order);
  return <main className="customer live-conversation" aria-label="Customer view">
    <GuideProvider value={{at,mood:{home:order.view.orb.mode,decision:"wait"}}}>
      <div className="cust-col" ref={col}>
        <div className="cust-h"><div className="cust-who"><span className="avatar" aria-hidden><IcSummit size={19}/></span><div className="title">{S.buyer}</div></div><div className="cust-money"><OrbSlot name="home"/><PaymentStatus order={order}/></div></div>
        {!order.live.id && <div className="live-welcome"><h1>What should we find for you?</h1><p>Describe the people, place and counts you need. We’ll clarify the requirements, agree on a price, then produce and check the dataset.</p></div>}
        {order.messages.length>0 && <Transcript title="Your conversation with Groundhog" count={order.messages.length} open compact={!!quote || !!order.delivery}>
          <Chat items={order.messages} view={order.view} onCite={order.cite} guide/>
        </Transcript>}
        <LiveIntake order={order}/>
        <div ref={decision} className="live-decisions">
          <OrderDecisions order={order} pay={pay} working={working} funding={funding}/>
        </div>
        {order.view.nodes.decide && order.view.nodes.decide.status!=="idle" && <div className="callout">This order needs human review. <button type="button" className="btn" onClick={admin}>Open admin review</button></div>}
        <LiveEvidence order={order}/>
        {order.delivery && <LiveOffers order={order} customer={customer}/>}
        <p className="mock-note">Synthetic aggregate data. The dataset is produced and checked against the accepted sources; the operator applies the agreed payment rules.</p>
      </div>
    </GuideProvider>
  </main>;
}

function OrderDecisions({order,pay,working,funding}:{order:LiveOrder;pay:()=>void;working:()=>void;funding:boolean}) {
  const quote=order.page?.quote;
  const payment=order.page?.payment?.payment;
  return <>
          {(quote || order.lines.length>0) && <Decision title="Data contract" open={!order.binding} taken={order.binding?"Agreement accepted":undefined}>
            <LiveAgreement order={order} pay={pay}/>
          </Decision>}
          {(payment || order.stage) && <Decision title="Payment" open={funding || !!order.stage} taken={payment?.state==="funded"?"Funds held in escrow":payment?.state==="captured"?"Payment captured":payment?.state==="voided"?"Funds returned":undefined}>
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
  const payment=order.page?.payment?.payment;
  const quote=order.page?.quote;
  const funding=!!payment && !["funded","captured","voided"].includes(payment.state);
  const needsDecision=!!order.stage || funding || !order.binding && !!quote || order.enabled("accept");
  const at=useOrbFlight(col,needsDecision?"decision":order.messages.length?"transcript":"home");
  const turn=order.page?.request.question?.question_id ?? (order.enabled("accept")?order.delivery?.artifactId:!order.binding?quote?.quote_id:undefined);
  useLayoutEffect(()=>{
    if(turn)decision.current?.scrollIntoView?.({block:"nearest",behavior:"instant"});
  },[turn]);
  return {col,decision,at,funding,quote};
}
