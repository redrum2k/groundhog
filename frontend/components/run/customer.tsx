"use client";
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import type { Step, ZipCount } from "../../lib/run/contract";
import type { View } from "../../lib/run/fold";
import { S, type Case } from "../../lib/run/scenario";
import type { BuyerGate, BuyerMove } from "../../lib/run/source";
import { IcCheck, IcChevronRight, IcWallet } from "./icons";
import TodoList from "./checklist";
import { GuideProvider, OrbSlot, useOrbFlight, type Stop } from "./guide";
import Label from "./label";
import { PanelBody, checkItems, type BodyProps } from "./panel";

// What Acme's buying agent sees: the same conversation, plus the three decisions that are
// Acme's to make. On a live run the presenter makes them here; on a recorded one the cards
// show the decision Acme took. Money is shown as what it is: signed, held, or paid to us.

type Props = {
  run: Case; steps: Step[]; view: View; bodyProps: Omit<BodyProps, "step">;
  awaiting: BuyerGate | null; skew: number; buyer: (m: BuyerMove) => Promise<string | null>;
  onMoved?: () => void; // after a move lands: the agent's work is what to watch next
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
      <span key={state} className="wallet-t"><Label text={state === "paid" && view.payments.some((p) => p.mock) ? `${text} · mock` : text} quiet="tail" /></span>
    </span>
  );
}

/** One of Acme's decisions: the thing to decide on, the buttons while it's open, the choice once made. */
function Decision({ title, open, taken, children, actions }: { title: string; open: boolean; taken?: ReactNode; children: ReactNode; actions?: ReactNode }) {
  if (!open && taken) return (
    <details className="decision taken">
      <summary className="decision-h"><IcChevronRight size={12} strokeWidth={2} className="chev" /><span className="decision-taken"><IcCheck size={12} strokeWidth={2.2} /> {taken}</span><span className="decision-t">{title}</span></summary>
      <div className="decision-body">{children}</div>
    </details>
  );
  return (
    <section className={`decision${open ? " open" : ""}`}>
      <div className="decision-h"><span className="decision-t">{title}</span>{open && <OrbSlot name="decision" />}</div>
      {children}
      {open && actions && <div className="decision-actions">{actions}</div>}
    </section>
  );
}

/** A stretch of the conversation: open and scrolling in its own box while it is the live thing, folded once the decision it fed is taken. */
function Transcript({ title, count, open, stop, children }: { title: string; count?: number; open: boolean; stop?: Stop; children: ReactNode }) {
  const [pinned, setPinned] = useState<boolean | null>(null); // the viewer's own toggle wins until the section changes state
  useEffect(() => { setPinned(null); }, [open]);
  const isOpen = pinned ?? open;
  return (
    <details className="cust-sec" open={isOpen} onToggle={(e) => { const o = e.currentTarget.open; if (o !== isOpen) setPinned(o); }}>
      <summary className="cust-step"><IcChevronRight size={12} strokeWidth={2} className="chev" />{title}{count ? <span className="faint">{count} {count === 1 ? "turn" : "turns"}</span> : null}{stop && <OrbSlot name={stop} />}</summary>
      <div className="cust-body">{children}</div>
    </details>
  );
}

function Sheet({ rows, note }: { rows: ZipCount[]; note?: string }) {
  return (
    <div className="sheet">
      <div className="sheet-h"><span>Delivered sheet</span><span className="faint">Synthetic data{note && `, ${note}`}</span></div>
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

/** The review window as time left. Run out undisputed, it accepts the delivery and the money is taken. */
function Countdown({ until, skew, price }: { until: string; skew: number; price: number }) {
  const [now, setNow] = useState(() => Date.now() + skew);
  useEffect(() => { const t = setInterval(() => setNow(Date.now() + skew), 1000); return () => clearInterval(t); }, [skew]);
  const left = Math.max(0, Math.ceil((Date.parse(until) - now) / 1000));
  return <span className="countdown" role="timer">{left ? <>Auto-accepts and pays ${price} in <b>{Math.floor(left / 60)}:{String(left % 60).padStart(2, "0")}</b></> : "Review window closed"}</span>;
}

export default function Customer({ run, steps, view, bodyProps, awaiting, skew, buyer, onMoved }: Props) {
  const [objection, setObjection] = useState("");
  const [objecting, setObjecting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const col = useRef<HTMLDivElement>(null);
  const landed = useRef(false);
  // The presenter arrives here at Acme's turn; the open decision should be in view, not below the fold.
  // With nothing to decide, opening the view mid-run lands once on the newest activity instead of the top.
  useLayoutEffect(() => {
    const open = col.current?.querySelector<HTMLElement>(".decision.open"), pane = col.current?.parentElement;
    if (open) open.scrollIntoView?.({ block: "center", behavior: "smooth" });
    else if (!landed.current && pane) pane.scrollTop = pane.scrollHeight;
    landed.current = true;
  }, [awaiting]);
  const move = async (m: BuyerMove) => { setBusy(true); setError(null); const err = await buyer(m); setBusy(false); setError(err); if (!err) { setObjecting(false); onMoved?.(); } };
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
  // The orb stands beside Acme's open decision, rides the magnifier while the sheet is checked, and sits by the interview while it asks
  const want: Stop = awaiting ? "decision" : view.orb.mode === "inspect" ? "sheet" : view.orb.mode === "look" ? "transcript" : "home";
  const at = useOrbFlight(col, want);
  const home = view.orb.mode === "wait" || view.orb.mode === "happy" ? view.orb.mode : "float";

  return (
    <main className="customer">
      <GuideProvider value={{ at, home }}>
        <div className="cust-col" ref={col}>
          <div className="cust-h">
            <div className="cust-who"><span className="avatar" aria-hidden>{S.buyer.split(" ").map((w) => w[0]).join("")}</span><div className="title">{S.buyerAgent}</div></div>
            <div className="cust-money"><OrbSlot name="home" /><Wallet view={view} /></div>
          </div>

          {clarify && (n.clarify?.messages.length ?? 0) > 0 && (
            <Transcript title={clarify.title} count={n.clarify?.messages.length} open={n.clarify?.status === "running" && awaiting !== "approve"} stop="transcript"><PanelBody step={clarify} {...bodyProps} customer /></Transcript>
          )}

          {contractLines.length > 0 && (
            <Decision title={`Data contract${view.contract.version >= 2 ? ` v${view.contract.version}` : ""}`} open={live && awaiting === "approve"} taken={approved ? `Approved and $${price} authorized` : undefined}
              actions={<button className="btn solid" disabled={busy} onClick={() => move({ action: "approve" })}>Approve and authorize ${price}</button>}>
              {live && awaiting === "approve" && <p className="decision-lead">The agent wrote these {contractLines.length} terms from the interview. Approving signs them and authorizes ${price}; nothing is taken until you accept the data.</p>}
              <TodoList title="Terms" items={contractLines.map((l) => ({ id: l.id, title: l.text, status: "completed" }))} />
            </Decision>
          )}

          {delivery && review && review.status !== "idle" && (
            <Decision title={`Delivery${delivery.version >= 2 ? ` v${delivery.version}` : ""}`} open={reviewOpen && !disputed} taken={accepted && disputed ? "Objected, answered, then accepted" : accepted ? "Accepted" : disputed ? `Objected: “${view.dispute?.claim}”` : undefined}
              actions={<>{objecting ? <>
                <textarea className="objection" rows={2} value={objection} onChange={(e) => setObjection(e.target.value)} placeholder="What's wrong with the delivery?" aria-label="Your objection" />
                <div className="decision-row">
                  <button className="btn solid" disabled={busy || !objection.trim()} onClick={() => move({ action: "object", text: objection.trim() })}>Send objection</button>
                  <button className="btn" disabled={busy} onClick={() => setObjecting(false)}>Back</button>
                </div>
              </> : <>
                <button className="btn solid" disabled={busy} onClick={() => move({ action: "accept" })}>Accept delivery</button>
                <button className="btn" disabled={busy} onClick={() => { setObjection((o) => o || SUGGESTED_OBJECTION); setObjecting(true); }}>Object</button>
              </>}{delivery.reviewClosesAt && <Countdown until={delivery.reviewClosesAt} skew={skew} price={price} />}</>}>
              {/* the data and the contract it was checked against, side by side, so the buyer can judge both before the window closes */}
              <div className="review-grid">
                <Sheet rows={delivery.rows} note={changedSince ? `${changedSince} rows changed since v${delivery.version - 1}` : withheld(delivery.rows) ? `${withheld(delivery.rows)} withheld for privacy` : undefined} />
                {n.produce && <TodoList title="Contract checks" items={checkItems(view.contract.lines, n.produce)} />}
              </div>
            </Decision>
          )}

          {investigate && investigate.messages.length > 0 && step("investigate") && (
            <Transcript title="Your objection, answered" open={!accepted}><PanelBody step={step("investigate")!} {...bodyProps} customer /></Transcript>
          )}

          {n.amend && n.amend.messages.length > 0 && step("amend") && (
            <Transcript title="Amendment" open={n.amend.status !== "done"}><PanelBody step={step("amend")!} {...bodyProps} customer /></Transcript>
          )}

          {n.decide && n.decide.status !== "idle" && step("decide") && (
            <Transcript title="Under review" open={n.decide.status !== "done"}><PanelBody step={step("decide")!} {...bodyProps} customer /></Transcript>
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
      </GuideProvider>
    </main>
  );
}

const withheld = (rows: ZipCount[]) => rows.filter((r) => r.flag === "withheld").length;
