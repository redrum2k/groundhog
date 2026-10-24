"use client";
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import type { Step, ZipCount } from "../../lib/run/contract";
import type { View } from "../../lib/run/fold";
import { AREA_BY_ZIP, OAKLAND, S, type Case } from "../../lib/run/scenario";
import type { BuyerGate, BuyerMove } from "../../lib/run/source";
import { IcCheck, IcChevronRight, IcWallet } from "./icons";
import TodoList from "./checklist";
import { GuideProvider, OrbSlot, useOrbFlight, type Stop } from "./guide";
import Inspector, { lookFor, type Found } from "./inspector";
import Label from "./label";
import { PanelBody, checkItems, type BodyProps } from "./panel";

// What Acme's buying agent sees: the same conversation, plus the three decisions that are
// Acme's to make. On a live run the presenter makes them here; on a recorded one the cards
// show the decision Acme took. Money is shown as what it is: signed, held, or paid to us.

type Props = {
  run: Case; steps: Step[]; view: View; bodyProps: Omit<BodyProps, "step">;
  awaiting: BuyerGate | null; buyer: (m: BuyerMove) => Promise<string | null>;
  onMoved?: () => void; // after a move lands: the agent's work is what to watch next
};

const SUGGESTED_OBJECTION = "Counts look low. Oakland should be in there.";
const RECEIPT: Record<BuyerMove["action"], string> = { approve: "Approved", accept: "Accepted", object: "Objection sent" };
type Where = "contract" | "delivery" | "after"; // which of Acme's decisions a move was made on

function Wallet({ view }: { view: View }) {
  const amount = view.payments.reduce((a, p) => a + p.amount, 0);
  const captured = view.payments.length > 0 && view.payments.every((p) => p.id in view.captured);
  const state = !view.payments.length ? "empty" : captured ? "paid" : view.dispute ? "held" : "signed";
  const text = state === "empty" ? "No payment yet" : state === "signed" ? `$${amount} signed, not taken` : state === "held" ? `$${amount} held while disputed` : `$${amount} paid to ${S.us}`;
  return (
    <span className={`wallet w-${state}`} role="status">
      <IcWallet size={14} />
      <span key={`${state}-${amount}`} className="wallet-t"><Label text={state === "paid" && view.payments.some((p) => p.mock) ? `${text} · mock` : text} quiet="tail" /></span>
    </span>
  );
}

/** One of Acme's decisions: the thing to decide on, the buttons while it's open, the choice once made. */
/** `done` is the move just made here: the card keeps its place and its height, the receipt where the buttons were. */
function Decision({ title, open, taken, done, slot = "decision", orb, children, actions }: { title: string; open: boolean; taken?: ReactNode; done?: string; slot?: Stop; orb?: ReactNode; children: ReactNode; actions?: ReactNode }) {
  if (!open && !done && taken) return (
    <details className="decision taken">
      <summary className="decision-h"><IcChevronRight size={12} strokeWidth={2} className="chev" /><span className="decision-taken"><IcCheck size={12} strokeWidth={2.2} /> {taken}</span><span className="decision-t">{title}</span></summary>
      <div className="decision-body">{children}</div>
    </details>
  );
  return (
    <section className={`decision${open || done ? " open" : ""}`}>
      <div className="decision-h"><span className="decision-t">{title}</span>{(open || done) && <OrbSlot name={slot} orb={orb} />}</div>
      {children}
      {done ? <div className="decision-actions"><span className="decision-taken decision-done"><IcCheck size={12} strokeWidth={2.2} /> {done}</span></div>
        : open && actions && <div className="decision-actions">{actions}</div>}
    </section>
  );
}

/** A stretch of the conversation: open and scrolling in its own box while it is the live thing, folded once the decision it fed is taken. */
/** `compact`: it stays open but short, pinned to the latest turn, so the decision it fed stays in view. */
function Transcript({ title, count, open, compact, children }: { title: string; count?: number; open: boolean; compact?: boolean; children: ReactNode }) {
  const body = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => { if (compact && body.current) body.current.scrollTop = body.current.scrollHeight; }, [compact]);
  const [pinned, setPinned] = useState<boolean | null>(null); // the viewer's own toggle wins until the section changes state
  useEffect(() => { setPinned(null); }, [open]);
  const isOpen = pinned ?? open;
  return (
    <details className="cust-sec" open={isOpen} onToggle={(e) => { const o = e.currentTarget.open; if (o !== isOpen) setPinned(o); }}>
      <summary className="cust-step"><IcChevronRight size={12} strokeWidth={2} className="chev" />{title}{count ? <span className="faint">{count} {count === 1 ? "turn" : "turns"}</span> : null}</summary>
      <div className={`cust-body${compact ? " short" : ""}`} ref={body}>{children}</div>
    </details>
  );
}

/** `gap`: a ZIP the inspection found missing, given a row where it belongs and red once the orb points at it. `ghosts`: asked for, never ordered. */
function Sheet({ rows, note, gap, ghosts }: { rows: ZipCount[]; note?: string; gap?: { zip: string; found: boolean }; ghosts?: ZipCount[] }) {
  const shown = gap && !rows.some((r) => r.zip === gap.zip) ? [...rows, { zip: gap.zip, area: AREA_BY_ZIP[gap.zip] ?? "", count: null, flag: "missing" as const }].sort((a, b) => a.zip.localeCompare(b.zip)) : rows;
  return (
    <div className="sheet">
      <div className="sheet-h"><span>Delivered sheet</span><span className="faint">{rows.length} ZIPs, synthetic data{note && `, ${note}`}</span></div>
      <div className="sheet-rows"><table>
        <thead><tr><th style={{ width: 34 }} /><th>ZIP</th><th>Area</th><th className="num">People</th></tr></thead>
        <tbody>
          {shown.map((r, i) => (
            <tr key={r.zip} data-zip={r.zip} className={r.zip === gap?.zip ? (gap.found ? "f-missing" : "f-gap") : r.flag ? `f-${r.flag}` : ""}>
              <td className="rn">{i + 1}</td><td className="mono">{r.zip}</td><td>{r.area}</td>
              <td className="num">{r.flag === "missing" ? "missing" : r.flag === "withheld" ? "withheld" : r.count?.toLocaleString("en-US") ?? "unknown"}</td>
            </tr>
          ))}
        </tbody>
      </table></div>
      {ghosts && (
        <div className="ghosts">
          <div className="faint">Asked for, not in your contract</div>
          {ghosts.map((g) => <div key={g.zip} className="ghost"><span className="mono">{g.zip}</span><span>{g.area}</span><span>not ordered</span></div>)}
        </div>
      )}
    </div>
  );
}

export default function Customer({ run, steps, view, bodyProps, awaiting, buyer, onMoved }: Props) {
  const [objection, setObjection] = useState("");
  const [objecting, setObjecting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const col = useRef<HTMLDivElement>(null);
  const landed = useRef(false);
  // The move just made, held in place while the view hands back to Run: the stream confirms it a poll later,
  // and without this the cards would fold and reopen in between. A new turn for Acme clears it.
  const [moved, setMoved] = useState<{ at: Where; action: BuyerMove["action"] } | null>(null);
  useEffect(() => { if (awaiting) setMoved(null); }, [awaiting]);
  const move = async (m: BuyerMove, at: Where) => { setBusy(true); setError(null); const err = await buyer(m); setBusy(false); setError(err); if (!err) { setObjecting(false); setMoved({ at, action: m.action }); if (m.action !== "object") onMoved?.(); } }; // an objection stays here: the inspection that answers it is what to watch
  const done = (at: Where) => (moved?.at === at ? RECEIPT[moved.action] : undefined);
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
  // The objected delivery stays open, receipt in place, while the orb inspects it and the answer comes back
  const held = disputed && !accepted && !!delivery;
  const look = lookFor(investigate?.evidence ?? [], view.contract.lines, delivery?.rows ?? []);
  // what the inspection has shown so far, for this evidence only: new evidence starts it over without an effect racing the orb's report
  const lookKey = look ? `${look.row}|${look.term}|${look.failed}` : "";
  const [inspected, setInspected] = useState<Found & { key?: string }>({});
  const found: Found = inspected.key === lookKey ? inspected : {};
  const onFound = (stage: keyof Found) => setInspected((f) => ({ ...(f.key === lookKey ? f : {}), key: lookKey, [stage]: true }));
  // it finishes the inspection, and points at the evidence, before it goes to Acme's next decision
  const showing = held && !found.done && (!!look || investigate?.status === "running");
  // The orb inspects an objected delivery, stands beside Acme's open decision, and sits by the interview while it asks
  const want: Stop = held && (!awaiting || showing) ? "inspect" : awaiting || moved ? "decision" : view.orb.mode === "look" ? "transcript" : "home";
  // Acme's turn brings its decision into view, once any inspection has finished pointing, not mid-way through it.
  // With nothing to decide, opening the view mid-run lands once on the newest activity instead of the top.
  const turn = awaiting && !showing ? awaiting : null;
  useLayoutEffect(() => {
    // the card with buttons: an objected delivery stays open too, but only to show its receipt
    const open = [...(col.current?.querySelectorAll<HTMLElement>(".decision.open") ?? [])].find((d) => d.querySelector(":scope > .decision-actions button"));
    const pane = col.current?.parentElement;
    if (open) open.scrollIntoView?.({ block: "center", behavior: "smooth" });
    else if (!landed.current && pane) pane.scrollTop = pane.scrollHeight;
    landed.current = true;
  }, [turn]);
  const at = useOrbFlight(col, want);
  const mood = { home: view.orb.mode === "wait" || view.orb.mode === "happy" ? view.orb.mode : "float", decision: moved ? "happy" : "wait" } as const;

  return (
    <main className="customer">
      <GuideProvider value={{ at, mood }}>
        <div className="cust-col" ref={col}>
          <div className="cust-h">
            <div className="cust-who"><span className="avatar" aria-hidden>{S.buyer.split(" ").map((w) => w[0]).join("")}</span><div className="title">{S.buyerAgent}</div></div>
            <div className="cust-money"><OrbSlot name="home" /><Wallet view={view} /></div>
          </div>

          {clarify && (n.clarify?.messages.length ?? 0) > 0 && (
            <Transcript title={clarify.title} count={n.clarify?.messages.length} open compact={n.clarify?.status !== "running" || awaiting === "approve" || moved?.at === "contract"}><PanelBody step={clarify} {...bodyProps} customer /></Transcript>
          )}

          {contractLines.length > 0 && (
            <Decision title={`Data contract${view.contract.version >= 2 ? ` v${view.contract.version}` : ""}`} open={live && awaiting === "approve"} taken={approved ? `Approved and $${price} authorized` : undefined} done={done("contract")}
              actions={<button className="btn solid" disabled={busy} onClick={() => move({ action: "approve" }, "contract")}>Approve and authorize ${price}</button>}>
              {(live && awaiting === "approve" || done("contract")) && <p className="decision-lead">The agent wrote these {contractLines.length} terms from the interview. Approving signs them and authorizes ${price}; nothing is taken until you accept the data.</p>}
              <TodoList title="Terms" items={contractLines.map((l) => ({ id: l.id, title: l.text, status: "completed" }))} />
            </Decision>
          )}

          {delivery && review && review.status !== "idle" && (
            <Decision title={`Delivery${delivery.version >= 2 ? ` v${delivery.version}` : ""}`} open={reviewOpen && !disputed} done={held ? `Objection sent: “${view.dispute?.claim}”` : done("delivery")} slot={held ? "inspect" : "decision"}
              orb={held ? <Inspector look={look} found={found} onFound={onFound} /> : undefined} taken={accepted && disputed ? "Objected, answered, then accepted" : accepted ? "Accepted" : disputed ? `Objected: “${view.dispute?.claim}”` : undefined}
              actions={objecting ? <>
                <textarea className="objection" rows={2} value={objection} onChange={(e) => setObjection(e.target.value)} placeholder="What's wrong with the delivery?" aria-label="Your objection" />
                <div className="decision-row">
                  <button className="btn solid" disabled={busy || !objection.trim()} onClick={() => move({ action: "object", text: objection.trim() }, "delivery")}>Send objection</button>
                  <button className="btn" disabled={busy} onClick={() => setObjecting(false)}>Back</button>
                </div>
              </> : <>
                <button className="btn solid" disabled={busy} onClick={() => move({ action: "accept" }, "delivery")}>Accept delivery</button>
                <button className="btn" disabled={busy} onClick={() => { setObjection((o) => o || SUGGESTED_OBJECTION); setObjecting(true); }}>Object</button>
              </>}>
              {/* the data and the contract it was checked against, side by side, so the buyer judges both at once */}
              <div className="review-grid">
                <Sheet rows={delivery.rows} note={changedSince ? `${changedSince} rows changed since v${delivery.version - 1}` : withheld(delivery.rows) ? `${withheld(delivery.rows)} withheld for privacy` : undefined}
                  gap={held && look?.row ? { zip: look.row, found: !!found.row } : undefined}
                  ghosts={held && found.term && look && !look.failed && /oakland/i.test(view.dispute?.claim ?? "") ? OAKLAND : undefined} />
                {n.produce && <TodoList title="Contract checks" items={checkItems(view.contract.lines, n.produce).map((i) => (held && found.term && i.id === look?.term ? { ...i, mark: look.failed ? "fail" : "settles" } : i))} />}
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

          {((disputed && reviewOpen && !accepted) || done("after")) && (
            <Decision title="Delivery, after your objection" open={reviewOpen} done={done("after")} taken={undefined}
              actions={<>
                <button className="btn solid" disabled={busy} onClick={() => move({ action: "accept" }, "after")}>Accept delivery</button>
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
