"use client";
import { useEffect, useRef, useState, type ReactNode } from "react";
import type { Step, ZipCount } from "../../lib/run/contract";
import type { View } from "../../lib/run/fold";
import { S, type Case } from "../../lib/run/scenario";
import type { BuyerGate, BuyerMove } from "../../lib/run/source";
import { IcCheck, IcLock, IcWallet } from "./icons";
import Label from "./label";
import Orb from "./orb";
import { PanelBody, type BodyProps } from "./panel";

// What Acme's buying agent sees: the same conversation, plus the three decisions that are
// Acme's to make. On a live run the presenter makes them here; on a recorded one the cards
// show the decision Acme took. Money is shown as what it is: signed, held, or paid to us.

type Props = {
  run: Case; steps: Step[]; view: View; bodyProps: Omit<BodyProps, "step">;
  awaiting: BuyerGate | null; buyer: (m: BuyerMove) => Promise<string | null>;
};

const SUGGESTED_OBJECTION = "Counts look low. Oakland should be in there.";

function Wallet({ view }: { view: View }) {
  const amount = view.payments.reduce((a, p) => a + p.amount, 0);
  const captured = view.payments.length > 0 && view.payments.every((p) => p.id in view.captured);
  const state = !view.payments.length ? "empty" : captured ? "paid" : view.dispute ? "held" : "signed";
  const text = state === "empty" ? "No payment yet" : state === "signed" ? `$${amount} signed, not taken` : state === "held" ? `$${amount} held while disputed` : `$${amount} paid to ${S.us}`;
  return (
    <span className={`wallet w-${state}`} role="status">
      <IcWallet size={14} />
      <Label text={state === "paid" && view.payments.some((p) => p.mock) ? `${text} · mock` : text} quiet="tail" />
    </span>
  );
}

/** One of Acme's decisions: the thing to decide on, the buttons while it's open, the choice once made. */
function Decision({ title, open, taken, children, actions }: { title: string; open: boolean; taken?: ReactNode; children: ReactNode; actions?: ReactNode }) {
  return (
    <section className={`decision${open ? " open" : ""}`}>
      <div className="decision-h">{open ? <span className="decision-tag"><IcLock size={11} strokeWidth={2} /> Your decision</span> : taken ? <span className="decision-taken"><IcCheck size={12} strokeWidth={2.2} /> {taken}</span> : null}<span className="decision-t">{title}</span></div>
      {children}
      {open && actions && <div className="decision-actions">{actions}</div>}
    </section>
  );
}

function Sheet({ rows, note }: { rows: ZipCount[]; note?: string }) {
  return (
    <div className="sheet">
      <div className="sheet-h"><span>Delivered sheet</span><span className="faint">Synthetic data{note && ` · ${note}`}</span></div>
      <table>
        <thead><tr><th style={{ width: 34 }} /><th>ZIP</th><th>Area</th><th className="num">People</th></tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.zip} className={r.flag ? `f-${r.flag}` : ""}>
              <td className="rn">{i + 1}</td><td className="mono">{r.zip}</td><td>{r.area}</td>
              <td className="num">{r.flag === "missing" ? "missing" : r.flag === "withheld" ? "withheld" : r.count?.toLocaleString("en-US") ?? "unknown"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Customer({ run, steps, view, bodyProps, awaiting, buyer }: Props) {
  const [objection, setObjection] = useState("");
  const [objecting, setObjecting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const col = useRef<HTMLDivElement>(null);
  // The presenter arrives here at Acme's turn; the open decision should be in view, not below the fold
  useEffect(() => { col.current?.querySelector<HTMLElement>(".decision.open")?.scrollIntoView?.({ block: "center", behavior: "smooth" }); }, [awaiting]);
  const move = async (m: BuyerMove) => { setBusy(true); setError(null); const err = await buyer(m); setBusy(false); setError(err); if (!err) setObjecting(false); };
  const step = (id: string) => view.nodes[id]?.step ?? steps.find((s) => s.id === id);
  const n = view.nodes;
  const live = !!bodyProps.live;

  const clarify = step("clarify");
  const contractLines = view.contract.version >= 1 && n.clarify?.status === "done" ? view.contract.lines : (n.clarify?.drafted ?? []);
  const approved = n.clarify?.status === "done" && view.contract.lines.length > 0;
  const price = view.payments[0]?.amount ?? view.contract.price ?? S.price;
  const delivery = view.deliveries.at(-1);
  const review = n.review;
  const investigate = n.investigate;
  const disputed = !!view.dispute;
  const reviewOpen = live && awaiting === "review";
  const accepted = review?.status === "done";
  const changedSince = delivery && view.deliveries.length > 1 ? delivery.rows.filter((r) => r.flag === "added" || r.flag === "yoga").length : 0;

  return (
    <main className="customer">
      <div className="cust-col" ref={col}>
        <div className="cust-h">
          <div className="cust-who"><span className="avatar" aria-hidden>{S.buyer.split(" ").map((w) => w[0]).join("")}</span><div><div className="title">{S.buyerAgent}</div><div className="faint" style={{ fontSize: 13 }}>Buying from {S.us}. Shown the way the customer sees it.</div></div></div>
          <div className="cust-money"><Orb mode={view.orb.mode === "wait" || view.orb.mode === "inspect" ? view.orb.mode : "float"} /><Wallet view={view} /></div>
        </div>

        {clarify && (n.clarify?.messages.length ?? 0) > 0 && (
          <section className="cust-sec"><div className="cust-step">{clarify.title}</div><PanelBody step={clarify} {...bodyProps} customer /></section>
        )}

        {contractLines.length > 0 && (
          <Decision title={`Data contract v${Math.max(1, view.contract.version)}`} open={live && awaiting === "approve"} taken={approved ? `Approved and $${price} authorized` : undefined}
            actions={<>
              <button className="btn solid" disabled={busy} onClick={() => move({ action: "approve" })}>Approve and authorize ${price}</button>
              <span className="faint" style={{ fontSize: 12.5 }}>Authorized means signed, not taken. {S.us} is paid only when you accept the data.</span>
            </>}>
            <ol className="lines">{contractLines.map((l) => <li key={l.id}>{l.text}</li>)}</ol>
            <div className="faint" style={{ fontSize: 13 }}>Price ${price}. Every line is a check the delivery has to pass.</div>
          </Decision>
        )}

        {delivery && review && review.status !== "idle" && (
          <Decision title={`Delivery v${delivery.version}`} open={reviewOpen && !disputed} taken={accepted && disputed ? "Objected, answered, then accepted" : accepted ? "Accepted" : disputed ? `Objected: “${view.dispute?.claim}”` : undefined}
            actions={objecting ? <>
              <textarea className="objection" rows={2} value={objection} onChange={(e) => setObjection(e.target.value)} placeholder="What's wrong with the delivery?" aria-label="Your objection" />
              <div className="decision-row">
                <button className="btn solid" disabled={busy || !objection.trim()} onClick={() => move({ action: "object", text: objection.trim() })}>Send objection</button>
                <button className="btn" disabled={busy} onClick={() => setObjecting(false)}>Back</button>
              </div>
            </> : <>
              <button className="btn solid" disabled={busy} onClick={() => move({ action: "accept" })}>Accept delivery</button>
              <button className="btn" disabled={busy} onClick={() => { setObjection((o) => o || SUGGESTED_OBJECTION); setObjecting(true); }}>Object</button>
            </>}>
            <Sheet rows={delivery.rows} note={changedSince ? `${changedSince} rows changed since v${delivery.version - 1}` : withheld(delivery.rows) ? `${withheld(delivery.rows)} withheld for privacy` : undefined} />
            {delivery.reviewClosesAt && <div className="faint" style={{ fontSize: 12.5 }}>Review window closes {new Date(delivery.reviewClosesAt).toLocaleString("en-US", { weekday: "short", hour: "numeric", minute: "2-digit" })}.</div>}
          </Decision>
        )}

        {investigate && investigate.messages.length > 0 && step("investigate") && (
          <section className="cust-sec"><div className="cust-step">Your objection, answered</div><PanelBody step={step("investigate")!} {...bodyProps} customer /></section>
        )}

        {n.amend && n.amend.messages.length > 0 && step("amend") && (
          <section className="cust-sec"><div className="cust-step">Amendment</div><PanelBody step={step("amend")!} {...bodyProps} customer /></section>
        )}

        {n.decide && n.decide.status !== "idle" && step("decide") && (
          <section className="cust-sec"><div className="cust-step">Under review</div><PanelBody step={step("decide")!} {...bodyProps} customer /></section>
        )}

        {disputed && reviewOpen && !accepted && (
          <Decision title="Delivery, after your objection" open taken={undefined}
            actions={<>
              <button className="btn solid" disabled={busy} onClick={() => move({ action: "accept" })}>Accept delivery</button>
              <span className="faint" style={{ fontSize: 12.5 }}>Accepting releases the ${price} to {S.us}.</span>
            </>}>
            <p className="faint" style={{ margin: 0, fontSize: 13.5 }}>The agent answered your objection with the contract and the evidence above. Nothing was missing from what was agreed, and there is no charge for asking.</p>
          </Decision>
        )}

        {n.captured?.status === "done" && (
          <section className="cust-sec"><div className="cust-step">Paid</div><p className="cust-paid"><IcCheck size={14} strokeWidth={2.2} /> ${price} paid to {S.us}{view.payments.some((p) => p.mock) && <span className="faint"> (mock capture)</span>}. The dataset is yours.</p></section>
        )}

        {error && <p className="review-err" role="alert">{error}</p>}
      </div>
    </main>
  );
}

const withheld = (rows: ZipCount[]) => rows.filter((r) => r.flag === "withheld").length;
