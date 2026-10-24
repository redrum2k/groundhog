import { useEffect, useState, type ReactNode } from "react";
import { Check, ChevronRight, Lock, X } from "lucide-react";
import TodoList, { type TodoItem } from "./TodoList";
import { CONTRACT, CONTRACT_V2, INTERVIEW, OAKLAND, ROWS, S, type Row } from "./scenario";
import type { Ending, Lane, Node, View } from "./timeline";

export type Cite = { kind: "msg"; id: string; label: string } | { kind: "row"; zip: string; label: string } | { kind: "doc"; label: string };

function CiteChip({ c, onCite }: { c: Cite; onCite: (c: Cite) => void }) {
  return <button className="cite" onClick={() => onCite(c)}>{c.label}<ChevronRight size={11} strokeWidth={1.8} /></button>;
}

type Bubble = { from: "buyer" | "agent" | "human"; text: ReactNode; id?: string };
function Chat({ items, highlight }: { items: Bubble[]; highlight?: string }) {
  return (
    <div className="chat">
      {items.map((b, i) => (
        <div key={b.id ?? i} id={b.id ? `msg-${b.id}` : undefined} className={`bub b-${b.from}${highlight && b.id === highlight ? " flash" : ""}`}>
          <span className="bub-who">{b.from === "buyer" ? S.buyerAgent : b.from === "human" ? `${S.controller} · ${S.controllerRole}` : S.agent}</span>
          <div className="bub-text">{b.text}</div>
        </div>
      ))}
    </div>
  );
}

function Sheet({ rows, highlight, note }: { rows: Row[]; highlight?: string; note?: string }) {
  return (
    <div className="sheet">
      <div className="sheet-h"><span>Delivered sheet</span>{note && <span className="faint">{note}</span>}</div>
      <table>
        <thead><tr><th style={{ width: 34 }} /><th>ZIP</th><th>Area</th><th className="num">People</th></tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.zip} id={`row-${r.zip}`} className={`${r.flag ? "f-" + r.flag : ""}${highlight === r.zip ? " flash" : ""}`}>
              <td className="rn">{i + 1}</td><td className="mono">{r.zip}</td><td>{r.area}</td>
              <td className="num">{r.flag === "missing" ? "missing" : r.flag === "withheld" ? "withheld" : r.people.toLocaleString()}{r.flag === "yoga" && <span className="delta"> +yoga</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function sheetRows(lane: Lane | "shared", phase: "before" | "after", yoga: boolean): Row[] {
  let rows = ROWS.map((r) => (r.zip === "94129" ? { ...r, flag: "withheld" as const } : r));
  if (lane === "red" && phase === "before") rows = rows.map((r) => (r.zip === "94110" ? { ...r, flag: "missing" as const } : r));
  if (lane === "red" && phase === "after") rows = rows.map((r) => (r.zip === "94110" ? { ...r, flag: "added" as const } : r));
  if (lane === "green" && phase === "after") rows = [...rows, ...OAKLAND];
  if (yoga) rows = rows.map((r) => (r.flag === "withheld" ? r : { ...r, people: Math.round(r.people * 1.09), flag: "yoga" as const }));
  return rows;
}

function Contract({ version, extra }: { version: 1 | 2; extra?: string }) {
  const lines = [...CONTRACT, ...(version === 2 ? [CONTRACT_V2] : []), ...(extra ? [extra] : [])];
  return (
    <div className="contract">
      <div className="contract-h"><span>Data contract v{version}</span><span className="faint">${S.price} · approved by {S.buyerAgent}</span></div>
      <ol>{lines.map((l, i) => <li key={l} className={i >= CONTRACT.length ? "new" : ""}><Check size={13} strokeWidth={2.2} /><span>{l}</span><span className="faint mono">line {i + 1}</span></li>)}</ol>
    </div>
  );
}

function Books({ lane, ending, learned }: { lane: Lane | "shared"; ending: Ending; learned: boolean }) {
  const yogaPaid = lane === "amber" && ending === "rules_no" && !learned;
  const rows: [string, string, string, number][] = [["Payment captured", "Cash", "Revenue", S.price], ["Data + compute, first run", "Data cost", "Cash", S.rerunCost]];
  if (lane === "red") rows.push(["Rerun 94110, our cost", "Data cost", "Cash", S.rerunCost]);
  if (lane === "green") rows.push(["Amendment: Oakland", "Cash", "Revenue", S.oakland], ["Oakland run", "Data cost", "Cash", S.rerunCost]);
  if (lane === "amber") rows.push(yogaPaid ? ["Amendment: yoga", "Cash", "Revenue", S.yoga] : ["Rerun with yoga, our cost", "Data cost", "Cash", S.rerunCost], ...(yogaPaid ? [["Yoga run", "Data cost", "Cash", S.rerunCost] as [string, string, string, number]] : []));
  const rev = rows.filter((r) => r[2] === "Revenue").reduce((a, r) => a + r[3], 0);
  const cost = rows.filter((r) => r[1] === "Data cost").reduce((a, r) => a + r[3], 0);
  return (
    <div className="books">
      <table>
        <thead><tr><th>Entry</th><th>Debit</th><th>Credit</th><th className="num">Amount</th></tr></thead>
        <tbody>{rows.map((r) => <tr key={r[0]}><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td className="num">${r[3].toFixed(2)}</td></tr>)}</tbody>
      </table>
      <div className="margin">Margin <b>${(rev - cost).toFixed(2)}</b> <span className="faint">after ${cost.toFixed(2)} of data and compute</span></div>
      <div className="mock-note"><Lock size={12} strokeWidth={1.8} /> Capture is a mock until the real x402 transaction lands on Base Sepolia. The Basescan link appears then.</div>
    </div>
  );
}

function Interview({ animate, highlight, contract }: { animate: boolean; highlight?: string; contract: 1 | 2 }) {
  const [n, setN] = useState(animate ? 1 : INTERVIEW.length);
  useEffect(() => {
    if (!animate || n >= INTERVIEW.length) return;
    const id = setTimeout(() => setN(n + 1), 780);
    return () => clearTimeout(id);
  }, [n, animate]);
  const shown = INTERVIEW.slice(0, n);
  useEffect(() => {
    if (!animate || n < 2) return;
    document.getElementById(`msg-${INTERVIEW[n - 1].id}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [n, animate]);
  const asked = (k: number) => shown.some((m, i) => m.from === "agent" && INTERVIEW[i + 1]?.tick === k) || shown.some((m) => m.tick === k);
  const items: TodoItem[] = CONTRACT.map((l, k) => ({ id: String(k), title: l, status: (shown.some((m) => m.tick === k) ? "completed" : "in-progress") as TodoItem["status"] }))
    .filter((_, k) => asked(k) || (k === 0 && n > 1));
  if (contract === 2) items.push({ id: "5", title: CONTRACT_V2, status: "completed", detail: "v2" });
  return (
    <>
      <div className="panel-sec sticky">
        <TodoList title={`Data contract v${contract}`} items={items.length ? items : [{ id: "x", title: "Waiting for the first answer", status: "pending" }]} />
      </div>
      <Chat items={shown.map((m) => ({ from: m.from, text: m.text, id: m.id }))} highlight={highlight} />
    </>
  );
}

function Checks({ animate, lane }: { animate: boolean; lane: Lane | "shared" }) {
  const [n, setN] = useState(animate ? 0 : 6);
  useEffect(() => {
    if (!animate || n >= 6) return;
    const id = setTimeout(() => setN(n + 1), 700);
    return () => clearTimeout(id);
  }, [n, animate]);
  const items: TodoItem[] = CONTRACT.map((l, k) => ({
    id: String(k), title: l,
    status: n > k ? "completed" : n === k ? "in-progress" : "pending",
    detail: k === 3 && n > 3 ? "94129 withheld (42)" : k === 4 && n > 4 ? (lane === "red" ? "vs vendor list" : "10 of 10") : undefined,
  }));
  return (
    <>
      <div className="panel-sec"><TodoList title="Contract checks" items={items} /></div>
      {n > 3 && <div className="callout">Privacy self-fix: ZIP 94129 has 42 people, under the 50 minimum, so it's held back before delivery. No customer involved.</div>}
      <Sheet rows={sheetRows("shared", "before", false)} highlight={n > 3 && n < 5 ? "94129" : undefined} />
    </>
  );
}

type BodyProps = {
  node: Node; view: View; lane: Lane | "shared"; ending: Ending; learned: boolean; firstVisit: boolean;
  onHuman: () => void; onReplayLearned: () => void; customer?: boolean;
};
export function PanelBody({ node, view, lane, ending, learned, firstVisit, onHuman, onReplayLearned, customer }: BodyProps) {
  const [hl, setHl] = useState<{ msg?: string; row?: string; tab?: "interview" }>({});
  useEffect(() => { setHl({}); }, [node.id]);
  useEffect(() => {
    const el = hl.msg ? document.getElementById(`msg-${hl.msg}`) : hl.row ? document.getElementById(`row-${hl.row}`) : null;
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [hl]);
  const cite = (c: Cite) => {
    if (c.kind === "msg") setHl({ tab: "interview", msg: c.id });
    else if (c.kind === "row") setHl({ row: c.zip });
  };
  const C = (c: Cite) => <CiteChip c={c} onCite={cite} />;

  let content: ReactNode;
  const id = node.id;
  const fixed = view.loops.length > 0 && view.status.s3 === "done";
  const yogaDone = lane === "amber" && fixed;
  if (hl.tab === "interview") {
    content = (<>
      <button className="back" onClick={() => setHl({})}><ChevronRight size={13} style={{ transform: "rotate(180deg)" }} /> Back to {node.title}</button>
      <Interview animate={false} highlight={hl.msg} contract={view.contract} />
    </>);
  } else if (id === "s0") content = <Interview animate={firstVisit} contract={view.contract} />;
  else if (id === "s1") content = <Contract version={view.contract} />;
  else if (id === "s2") content = (<div className="pay"><div className="pay-amt">${S.price}.00</div><div>x402 authorization signed by {S.buyerAgent}.</div><div className="faint">Signed now, captured only after Acme accepts or the 48h window passes. "Authorized" means signed, not funds held.</div></div>);
  else if (id === "s3") content = lane === "shared" || view.status.s3 !== "running" ? <Checks animate={firstVisit && lane === "shared"} lane={lane} /> : <Checks animate={false} lane={lane} />;
  else if (id === "s4" || id === "s5") content = (<div className="pay"><div>Delivered to {S.buyerAgent}: 10 SF ZIPs, 1 withheld for privacy.</div><div className="deadline">Review window closes <b>Sun 9:00 AM</b> <span className="faint">· server time</span></div></div>);
  else if (["s6", "rK", "gK", "aK"].includes(id)) content = <Books lane={lane} ending={ending} learned={learned} />;
  else if (id === "rI" || id === "rD" || id === "rV") content = (<>
    <Chat items={[
      { from: "buyer", text: "ZIP 94110 is missing from the delivery." },
      { from: "agent", text: <>Checking against your contract {C({ kind: "doc", label: "Contract · line 5" })}. You're right: there's no 94110 row {C({ kind: "row", zip: "94110", label: "Sheet · 94110" })}. Our check used the vendor's ZIP list, which lacked it. Rerunning now at our cost.</> },
    ]} />
    <Sheet rows={sheetRows("red", fixed ? "after" : "before", false)} highlight={hl.row} note={fixed ? "94110 added" : "as delivered"} />
  </>);
  else if (id === "gI" || id === "gD" || id === "gV") content = (<>
    <Chat items={[
      { from: "buyer", text: "Counts look low. Oakland should be in there." },
      { from: "agent", text: <>Your order covers San Francisco city only {C({ kind: "msg", id: "m5", label: "Interview · “SF city only.”" })} {C({ kind: "doc", label: "Contract · line 2" })}. Nothing's missing from what was agreed, and there's no charge for asking. Want Oakland added as an amendment for ${S.oakland}?</> },
    ]} />
    <Sheet rows={sheetRows("green", "before", false)} highlight={hl.row} note="SF only, as agreed" />
  </>);
  else if (id === "gA" || id === "gC") content = (<>
    <Chat items={[
      { from: "buyer", text: "Yes, add Oakland." },
      { from: "agent", text: `Amendment: + Oakland (3 ZIPs), $${S.oakland}. Same rules otherwise. Approve and sign?` },
      { from: "buyer", text: `Approved. Signed $${S.oakland} via x402.` },
    ]} />
    <Contract version={view.contract} extra={`Amendment: add Oakland ZIPs · +$${S.oakland}`} />
  </>);
  else if (id === "aI" || id === "aD" || id === "aG") content = learned ? (<>
    <Chat items={[
      { from: "buyer", text: "Yoga studio members should count as fitness." },
      { from: "agent", text: <>Contract v2 already says yoga counts {C({ kind: "doc", label: "Contract v2 · line 6" })}. Adding yoga members now at no cost. No review needed.</> },
    ]} />
    <Contract version={2} />
  </>) : (<>
    <Chat items={[
      { from: "buyer", text: "Yoga studio members should count as fitness." },
      { from: "agent", text: <>Your definition was gym members or fitness-app users {C({ kind: "msg", id: "m3", label: "Interview · m3" })}. Our data vendor files yoga under “Wellness” {C({ kind: "doc", label: "Vendor categories" })}. The contract doesn't settle it either way.</> },
    ]} />
    <Sheet rows={sheetRows("amber", "before", false)} highlight={hl.row} note="fitness = gyms + apps" />
  </>);
  else if (id === "aX" && ending === "human" && !learned && customer && view.status.aX !== "done") content = <Chat items={[{ from: "agent", text: "The contract doesn't settle this, so our controller is reviewing the evidence. Payment stays on hold until it's decided." }]} />;
  else if (id === "aX" && ending === "human" && !learned && view.status.aX !== "done") content = (
    <div className="review">
      <div className="review-tag"><Lock size={11} strokeWidth={2} /> Needs your decision · records don't settle it</div>
      <p className="review-q">Should yoga studio members count as fitness for Acme's order?</p>
      <p className="faint" style={{ margin: "0 0 12px" }}>Counting them adds about 9% more people. If yes, we rerun free and the contract becomes v2 so this is automatic next time. If no, we offer a ${S.yoga} amendment.</p>
      <div className="review-ev">
        {C({ kind: "msg", id: "m3", label: "Interview · m3" })}{C({ kind: "doc", label: "Vendor: yoga → Wellness" })}{C({ kind: "doc", label: "Acme's claim" })}
      </div>
      <div className="review-actions">
        <button className="btn solid" onClick={onHuman}>Yoga counts · rerun free</button>
        <button className="btn" disabled title="Not wired in this preview">No · offer ${S.yoga}</button>
        <button className="btn" disabled title="Not wired in this preview">Ask Acme for more</button>
        <button className="btn" disabled title="Not wired in this preview">Send to CFO</button>
      </div>
      <div className="faint" style={{ fontSize: 12, marginTop: 10 }}>Applies to this dispute and evidence set. Your name, time and reason are recorded.</div>
    </div>);
  else if (id === "aN" || id === "aX" || id === "aC") content = ending === "human" && !learned ? (<>
    <div className="learned"><Check size={14} strokeWidth={2.2} /> Learned: yoga counts as fitness. Saved as Data contract v2.</div>
    <Chat items={[{ from: "human", text: "Yoga counts. They're right that it's fitness." }, { from: "agent", text: <>Our controller reviewed it: yoga counts {C({ kind: "doc", label: "Contract v2 · line 6" })}. Adding yoga members now at no cost.</> }]} />
    <Contract version={2} />
    {yogaDone && <button className="btn solid replay-learned" onClick={onReplayLearned}>Replay the yoga dispute with the new rule</button>}
  </>) : ending === "rules_no" && !learned ? (<>
    <Chat items={[
      { from: "agent", text: <>Our rule: when the interview is silent, the vendor's category decides {C({ kind: "doc", label: "Policy · categories" })}. Yoga isn't in your order. Want it added for ${S.yoga}?</> },
      { from: "buyer", text: `Yes. Signed $${S.yoga} via x402.` },
    ]} />
  </>) : (<>
    <Chat items={[{ from: "agent", text: <>Our rule: an unclear spec is on us {C({ kind: "doc", label: "Policy · unclear spec" })}. Adding yoga members now at no cost.</> }]} />
    <Sheet rows={sheetRows("amber", "after", yogaDone)} highlight={hl.row} note={yogaDone ? "yoga added" : ""} />
  </>);
  else content = <p className="faint">{node.desc}</p>;

  return <>{content}</>;
}

export default function Panel(p: BodyProps & { onClose: () => void }) {
  return (
    <aside className="panel" key={p.node.id} aria-label={`${p.node.title} details`}>
      <div className="panel-h">
        <div><div className="panel-t">{p.node.title}</div><div className="faint" style={{ fontSize: 12.5 }}>{p.node.desc}</div></div>
        <button className="sq" aria-label="Close" onClick={p.onClose}><X size={15} strokeWidth={1.5} /></button>
      </div>
      <div className="panel-b">
        <PanelBody {...p} />
      </div>
    </aside>
  );
}
