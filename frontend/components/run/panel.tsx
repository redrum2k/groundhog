"use client";
import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import type { Binding, ContractLine, ControllerAction, Delivery, Evidence, Message, Source, Step, ZipCount } from "../../lib/run/contract";
import { bindingFor, type NodeState, type View } from "../../lib/run/fold";
import type { CellEvidence } from "../../lib/runs.generated";
import { CONTRACT, CONTRACT_V2, S, type Case, type Ending } from "../../lib/run/scenario";
import TodoList, { type ChecklistItem } from "./checklist";
import { IcCheck, IcChevronRight, IcLens, IcLock, IcX } from "./icons";
import { OrbSlot } from "./guide";
import Label from "./label";

// One right-side panel holds every step's detail. It renders whatever the event stream attached
// to the step, so there is no per-step layout to keep in sync with the backend.

export type Decide = (action: ControllerAction, binding: Binding) => Promise<string | null>;
type Hl = { msg?: string; row?: string; tab?: "interview" };

function CiteChip({ e, onCite }: { e: Evidence; onCite: (s: Source) => void }) {
  return <button className="cite" onClick={() => onCite(e.source)}><Label text={e.label} /><IcChevronRight size={11} strokeWidth={1.8} /></button>;
}

function Chat({ items, view, highlight, onCite }: { items: Message[]; view: View; highlight?: string; onCite: (s: Source) => void }) {
  const box = useRef<HTMLDivElement>(null);
  const seen = useRef(items.length);
  const height = useRef(0); // the pane's scroll height before the latest messages landed
  // New messages glide into view unless the viewer had scrolled up to reread earlier ones.
  // Judged against the height before this batch, so a burst of bubbles never reads as the viewer scrolling away.
  useEffect(() => {
    const added = items.length > seen.current;
    seen.current = items.length;
    const last = box.current?.lastElementChild as HTMLElement | null | undefined;
    const pane = box.current?.closest(".cust-body, .panel-b, .customer");
    if (!last || !pane) return;
    const following = height.current - pane.scrollTop - pane.clientHeight < 160;
    height.current = pane.scrollHeight;
    if (!added || !following) return;
    const below = last.getBoundingClientRect().bottom - pane.getBoundingClientRect().bottom;
    if (below > 0) pane.scrollBy?.({ top: below + 12, behavior: window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }, [items.length]);
  return (
    <div className="chat" ref={box}>
      {items.map((m) => (
        <div key={m.id} id={`msg-${m.id}`} className={`bub b-${m.from}${highlight === m.id ? " flash" : ""}`}>
          <span className="bub-who">{m.from === "buyer" ? S.buyerAgent : m.from === "controller" ? <Label text={`${S.controller} · ${S.controllerRole}`} quiet="tail" /> : S.agent}</span>
          <div className="bub-text">
            {m.text}
            {m.attach?.map((a, i) => a.kind === "evidence" && view.evidence[a.evidenceId] ? <span key={i}> <CiteChip e={view.evidence[a.evidenceId]} onCite={onCite} /></span> : null)}
          </div>
        </div>
      ))}
    </div>
  );
}

/** `lens` puts the orb's magnifier on the sheet: it sweeps the delivered rows, then rests on `row` once evidence names one. */
function Sheet({ rows, highlight, note, lens }: { rows: ZipCount[]; highlight?: string; note?: string; lens?: { row?: string } }) {
  const box = useRef<HTMLDivElement>(null);
  const [at, setAt] = useState<{ y0: number; y1: number; y: number; h: number } | null>(null);
  const lensOn = !!lens, lensRow = lens?.row;
  useLayoutEffect(() => {
    const el = box.current;
    if (!lensOn || !el) { setAt(null); return; }
    const top = el.getBoundingClientRect().top;
    const y = (r: Element | null) => (r ? r.getBoundingClientRect().top - top : 0);
    const delivered = el.querySelectorAll("tbody tr:not(.f-missing)");
    setAt({ y0: y(delivered[0]), y1: y(delivered[delivered.length - 1]), y: y(lensRow ? el.querySelector(`#row-${lensRow}`) : null), h: delivered[0]?.getBoundingClientRect().height ?? 0 });
  }, [lensOn, lensRow, rows.length]);
  return (
    <div className="sheet" ref={box}>
      {/* mounted with the lens, hidden until measured, so the customer view's orb has its slot in the same render */}
      {lens && (
        <div className={`sheet-lens${lensRow ? "" : " scan"}`} aria-hidden
          style={at ? { height: at.h, "--y0": `${at.y0}px`, "--y1": `${at.y1}px`, "--y": `${lensRow ? at.y : at.y0}px` } as CSSProperties : { visibility: "hidden" }}>
          <OrbSlot name="sheet" fallback={<IcLens size={15} strokeWidth={1.7} />} />
        </div>
      )}
      <div className="sheet-h"><span>Delivered sheet</span><span className="faint">Synthetic data{note && `, ${note}`}</span></div>
      <table>
        <thead><tr><th style={{ width: 34 }} /><th>ZIP</th><th>Area</th><th className="num">People</th></tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.zip} id={`row-${r.zip}`} className={`${r.flag ? "f-" + r.flag : ""}${highlight === r.zip ? " flash" : ""}`}>
              <td className="rn">{i + 1}</td><td className="mono">{r.zip}</td><td>{r.area}</td>
              <td className="num">{r.flag === "missing" ? "missing" : r.flag === "withheld" ? "withheld" : r.count?.toLocaleString("en-US") ?? "unknown"}{r.flag === "yoga" && <span className="delta"> +yoga</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** The delivered rows as this step saw them, with rows the evidence says are missing shown in place. */
function sheetRows(view: View, node: NodeState): ZipCount[] {
  const d = node.delivery ?? view.deliveries[view.deliveries.length - 1];
  if (!d) return [];
  const missing = node.evidence.filter((e): e is CellEvidence => e.kind === "sheet_cell" && e.value === null && e.source.kind === "cell" && e.source.version === d.version);
  const rows = [...d.rows];
  for (const m of missing) if (!rows.some((r) => r.zip === m.row)) rows.push({ zip: m.row, area: AREA[m.row] ?? "", count: 0, flag: "missing" });
  return rows.sort((a, b) => a.zip.localeCompare(b.zip));
}
const AREA: Record<string, string> = { "94110": "Mission" };

function Contract({ view, extra }: { view: View; extra?: ContractLine }) {
  const c = view.contract;
  const lines = [...c.lines, ...(extra ? [extra] : [])];
  return (
    <div className="contract">
      <div className="contract-h"><span>Data contract v{c.version}</span><span className="faint">${c.price}, approved by {S.buyerAgent}</span></div>
      <ol>{lines.map((l, i) => <li key={l.id} className={i >= CONTRACT.length ? "new" : ""}><IcCheck size={13} strokeWidth={2.2} /><span>{l.text}</span><span className="faint mono">line {i + 1}</span></li>)}</ol>
    </div>
  );
}

function Books({ node }: { node: NodeState }) {
  const { entries = [], margin } = node;
  return (
    <div className="books">
      <table>
        <thead><tr><th>Entry</th><th>Debit</th><th>Credit</th><th className="num">Amount</th></tr></thead>
        <tbody>{entries.map((e) => <tr key={e.id}><td>{e.memo}</td><td>{e.debit}</td><td>{e.credit}</td><td className="num">${e.amount.toFixed(2)}</td></tr>)}</tbody>
      </table>
      {margin && margin.cost !== null && <div className="margin">Margin <b>${(margin.revenue - margin.cost).toFixed(2)}</b> <span className="faint">after ${margin.cost.toFixed(2)} of data and compute</span></div>}
      <div className="mock-note"><IcLock size={12} strokeWidth={1.8} /> Capture is a mock until the observed Commerce Payments transaction lands on Base Sepolia. The Basescan link appears then.</div>
    </div>
  );
}

/** The interview with the contract checklist ticking above it as answers settle lines. */
function Interview({ view, highlight, onCite }: { view: View; highlight?: string; onCite: (s: Source) => void }) {
  const n = view.nodes.clarify;
  const drafted = new Set(n?.drafted.map((l) => l.id));
  const asked = new Set(n?.asked);
  // Recorded runs ask about the scenario's lines; a live stream names its own as it goes
  const known: ContractLine[] = [...(n?.drafted ?? []), ...Object.values(n?.pending ?? {})];
  const source = known.length ? known : CONTRACT.filter((l) => asked.has(l.id) || drafted.has(l.id));
  // A live interview asks everything up front; only the line being answered spins, the rest wait
  let open = true;
  const items: ChecklistItem[] = source.map((l) => { const done = drafted.has(l.id); const status = done ? "completed" : open ? "in-progress" : "pending"; if (!done) open = false; return { id: l.id, title: l.text, status }; });
  if (view.contract.version >= 2) items.push({ id: CONTRACT_V2.id, title: CONTRACT_V2.text, status: "completed", detail: "v2" });
  return (
    <>
      <div className="panel-sec sticky">
        <TodoList title={`Data contract v${view.contract.version}`} items={items.length ? items : [{ id: "x", title: "Waiting for the first answer", status: "pending" }]} />
      </div>
      <Chat items={n?.messages ?? []} view={view} highlight={highlight} onCite={onCite} />
    </>
  );
}

/** Each contract line with the produce step's check result for it; the first unchecked line spins while the step runs. */
export function checkItems(lines: ContractLine[], node: NodeState): ChecklistItem[] {
  const next = node.status === "running" ? lines.find((l) => !(l.id in node.checks)) : undefined;
  return lines.map((l) => {
    const c = node.checks[l.id];
    return { id: l.id, title: l.text, status: c ? (c.passed ? "completed" : "cancelled") : l === next ? "in-progress" : "pending", detail: c?.detail };
  });
}

function Checks({ node, view }: { node: NodeState; view: View }) {
  const items = checkItems(CONTRACT, node);
  const privacy = node.checks.privacy;
  return (
    <>
      <div className="panel-sec"><TodoList title="Contract checks" items={items} /></div>
      {privacy?.fix && node.attempt === 1 && <div className="callout">Privacy self-fix: ZIP 94129 has suppressed people, under the 50 minimum, so it's held back before delivery. No customer involved.</div>}
      <Sheet rows={sheetRows(view, node)} highlight={privacy && !("coverage" in node.checks) ? "94129" : undefined} note={node.attempt > 1 ? "rerun" : undefined} />
    </>
  );
}

const ACTIONS: [ControllerAction, string][] = [["approve", "Yoga counts, rerun free"], ["reject", `No, offer $${S.yoga}`], ["ask", "Ask Acme for more"], ["escalate", "Send to CFO"]];
// The live backend's controller can resume or hold; the other two are not commands it has
const LIVE_ACTIONS: [ControllerAction, string][] = [["approve", "Resume, evidence holds up"], ["reject", "Hold the payment"]];
function Review({ node, view, decide, onCite, live }: { node: NodeState; view: View; decide: Decide; onCite: (s: Source) => void; live?: boolean }) {
  const [busy, setBusy] = useState<ControllerAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const question = node.messages.find((m) => m.from === "agent"); // the escalation itself, not later notes
  const act = async (a: ControllerAction) => {
    setBusy(a); setError(null);
    const err = await decide(a, bindingFor(view));
    setBusy(null); setError(err);
  };
  return (
    <div className="review">
      <div className="review-tag"><IcLock size={11} strokeWidth={2} /> <Label text="Needs your decision · records don't settle it" quiet="tail" /></div>
      <p className="review-q">{question?.text}</p>
      <p className="faint" style={{ margin: "0 0 12px" }}>{live ? "Resume re-checks the delivery against the accepted sources; hold keeps the payment held until new evidence or an accepted amendment." : `Counting them adds about 9% more people. If yes, we rerun free and the contract becomes v2 so this is automatic next time. If no, we offer a $${S.yoga} amendment.`}</p>
      <div className="review-ev">
        {question?.attach?.map((a, i) => a.kind === "evidence" && view.evidence[a.evidenceId] ? <CiteChip key={i} e={view.evidence[a.evidenceId]} onCite={onCite} /> : null)}
      </div>
      <div className="review-actions">
        {(live ? LIVE_ACTIONS : ACTIONS).map(([a, label]) => <button key={a} className={`btn${a === "approve" ? " solid" : ""}`} disabled={busy !== null} onClick={() => act(a)}>{label}</button>)}
      </div>
      {error && <p className="review-err">{error}</p>}
      <div className="faint" style={{ fontSize: 12, marginTop: 10 }}>Applies to this dispute and evidence set. Your name, time and reason are recorded.</div>
    </div>
  );
}

export type BodyProps = {
  step: Step; view: View; lane: Case; ending: Ending; learned: boolean; done: boolean; live?: boolean;
  decide: Decide; onReplayLearned: () => void; customer?: boolean;
};
export function PanelBody({ step, view, lane, learned, done, live, decide, onReplayLearned, customer }: BodyProps) {
  const [hl, setHl] = useState<Hl>({});
  useEffect(() => { setHl({}); }, [step.id]);
  useEffect(() => {
    const el = hl.msg ? document.getElementById(`msg-${hl.msg}`) : hl.row ? document.getElementById(`row-${hl.row}`) : null;
    el?.scrollIntoView?.({ behavior: "smooth", block: "center" });
  }, [hl]);
  const onCite = (s: Source) => {
    if (s.kind === "message") setHl(s.messageId.startsWith("m-") ? { msg: s.messageId } : { tab: "interview", msg: s.messageId });
    else if (s.kind === "cell") setHl({ row: s.row });
  };
  const node = view.nodes[step.id];
  const investigate = view.nodes.investigate;
  const rerunDone = (view.nodes.produce?.attempt ?? 1) > 1 && view.nodes.produce?.status === "done";

  let content: ReactNode;
  if (hl.tab === "interview") content = (<>
    <button className="back" onClick={() => setHl({})}><IcChevronRight size={13} style={{ transform: "rotate(180deg)" }} /> Back to {step.title}</button>
    <Interview view={view} highlight={hl.msg} onCite={onCite} />
  </>);
  else if (!node) content = <p className="faint">{step.detail}</p>;
  else switch (step.kind) {
    case "clarify": content = <Interview view={view} onCite={onCite} />; break;
    case "paid": {
      const pay = view.payments[0];
      content = (<div className="pay"><div className="pay-amt">${(pay?.amount ?? S.price).toFixed(2)}</div>
        {pay?.rail === "mock" ? <div>Mock authorization opened by the backend on acceptance.</div> : <div>x402 authorization signed by {S.buyerAgent}.</div>}
        <div className="faint">Captured only after Acme accepts or the review window passes. "Authorized" means signed, not funds held.</div></div>);
      break;
    }
    case "produce": content = <Checks node={node} view={view} />; break;
    case "review": {
      const d = view.deliveries[view.deliveries.length - 1];
      const held = d?.rows.filter((r) => r.flag === "withheld").length ?? 0;
      content = (<div className="pay"><div>Delivered to {S.buyerAgent}: {d?.rows.length ?? 0} ZIPs, {held} withheld for privacy.</div>
        {d?.reviewClosesAt && <div className="deadline">Review window closes <b>{new Date(d.reviewClosesAt).toLocaleString("en-US", { weekday: "short", hour: "numeric", minute: "2-digit" })}</b> <span className="faint">server time</span></div>}</div>);
      break;
    }
    case "captured": content = <Books node={node} />; break;
    case "investigate": case "verdict": case "grey": {
      const msgs = investigate?.messages ?? [];
      const cited = investigate?.evidence.find((e): e is CellEvidence => e.kind === "sheet_cell");
      const lens = step.kind === "investigate" && investigate && (investigate.status === "running" || cited) ? { row: cited?.row } : undefined;
      content = (<>
        <Chat items={msgs} view={view} highlight={hl.msg} onCite={onCite} />
        {lane === "amber" && learned ? <Contract view={view} /> : <Sheet rows={sheetRows(view, investigate ?? node)} highlight={hl.row} lens={lens}
          note={lane === "red" ? (rerunDone ? "94110 added" : "as delivered") : lane === "green" ? "SF only, as agreed" : "fitness = gyms + apps"} />}
      </>);
      break;
    }
    case "amend": content = (<><Chat items={node.messages} view={view} highlight={hl.msg} onCite={onCite} /><Contract view={view} extra={node.amendment?.line} /></>); break;
    case "decide": {
      if (node.status === "waiting" && customer) content = <Chat items={[{ id: "x", from: "agent", text: "The contract doesn't settle this, so our controller is reviewing the evidence. Payment stays on hold until it's decided." }]} view={view} onCite={onCite} />;
      else if (node.status === "waiting") content = <Review node={node} view={view} decide={decide} onCite={onCite} live={live} />;
      else if (node.decision?.action === "approve") content = (<>
        {node.rule && <div className="learned"><IcCheck size={14} strokeWidth={2.2} /> Learned: {node.rule.text.toLowerCase()}. Saved as Data contract v2.</div>}
        <Chat items={node.messages.filter((m) => m.from !== "agent" || m.id !== "m-escalate")} view={view} highlight={hl.msg} onCite={onCite} />
        <Contract view={view} />
        {done && <button className="btn solid replay-learned" onClick={onReplayLearned}>Replay the yoga dispute with the new rule</button>}
      </>);
      else content = (<>
        <Chat items={node.messages} view={view} highlight={hl.msg} onCite={onCite} />
        {node.amendment ? <Contract view={view} extra={node.amendment.line} /> : rerunDone && <Sheet rows={sheetRows(view, view.nodes.produce)} highlight={hl.row} note="yoga added" />}
      </>);
      break;
    }
  }
  return <>{content}</>;
}

export default function Panel(p: BodyProps & { onClose: () => void; closing?: boolean; onClosed?: () => void }) {
  const el = useRef<HTMLElement>(null);
  // Gone once its exit transition finishes; with none running (reduced motion, tests) at once
  useEffect(() => {
    if (!p.closing) return;
    let live = true;
    Promise.all((el.current?.getAnimations?.() ?? []).map((a) => a.finished)).then(() => { if (live) p.onClosed?.(); }, () => {});
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.closing]);
  return (
    <aside ref={el} className={`panel${p.closing ? " closing" : ""}`} key={p.step.id} aria-label={`${p.step.title} details`}>
      <div className="panel-h">
        <div><div className="panel-t">{p.step.title}</div><div className="faint" style={{ fontSize: 12.5 }}>{p.step.detail}</div></div>
        <button className="sq" aria-label="Close" onClick={p.onClose}><IcX size={15} strokeWidth={1.5} /></button>
      </div>
      <div className="panel-b"><PanelBody {...p} /></div>
    </aside>
  );
}
