"use client";
import type { Delivery, Evidence, JournalEntry, Margin, RuleUpdate, Source, Verdict } from "../../lib/run/contract";
import { basescan, type Coin } from "../../lib/run/fold";
import { CO, LANE_NAME, VERDICT_LANE } from "../../lib/run/scenario";
import { IcGoto } from "./icons";

// Small pieces a step's context is made of. Each renders one thing the event stream attached.

export type OnSource = (source: Source) => void;

const EVIDENCE_FROM: Record<Evidence["kind"], string> = {
  interview_quote: "From the interview", sheet_cell: "In the delivered file", vendor_category: "Vendor's categories",
};

export function EvidenceCard({ e, onSource }: { e: Evidence; onSource?: OnSource }) {
  return (
    <div className="ev">
      <div className="sec-k">{EVIDENCE_FROM[e.kind]}</div>
      {e.kind === "interview_quote" && <p className="ev-main">“{e.quote}” <span className="faint">{e.speaker}</span></p>}
      {e.kind === "vendor_category" && <p className="ev-main">{e.item} <span className="faint">filed under</span> {e.category}</p>}
      {e.kind === "sheet_cell" && (
        <table className="sheet cell">
          <thead><tr><th>ZIP</th><th>{e.column}</th></tr></thead>
          <tbody><tr><td>{e.row}</td><td className="miss">{e.value ?? "missing"}</td></tr></tbody>
        </table>
      )}
      <p className="ev-note">{e.note}</p>
      {onSource && (e.source.kind === "none"
        ? <p className="ev-src faint">Source not on this canvas: {e.source.reason}</p>
        : <button type="button" className="ev-src" onClick={() => onSource(e.source)}>Show the source <IcGoto size={12} /></button>)}
    </div>
  );
}

export function RuleCard({ rule }: { rule: RuleUpdate }) {
  return (
    <div className="ev">
      <div className="sec-k">Saved to the rules</div>
      <p className="ev-main">{rule.text}</p>
      <p className="ev-note">Decided by {rule.decidedBy}. It applies to every order from now on.</p>
    </div>
  );
}

export function VerdictNote({ v }: { v: Verdict }) {
  const lane = VERDICT_LANE[v.kind];
  return (
    <section className={`verdict v-${lane}`}>
      <div className="verdict-k"><i className="sq" />{LANE_NAME[lane]}</div>
      <p>{v.reason}</p>
      <p className="ev-note">Decided by {v.decidedBy === "rules" ? "our rules" : "the controller"}</p>
    </section>
  );
}

export function LearnedNote({ ruleId, outcome }: { ruleId: string; outcome: Verdict["kind"] }) {
  const lane = VERDICT_LANE[outcome];
  return (
    <section className={`verdict v-${lane}`}>
      <div className="verdict-k"><i className="sq" />{LANE_NAME[lane]} · by rule</div>
      <p>Decided by the rule {CO.controller} saved. No person needed.</p>
      <p className="ev-note">Rule {ruleId.replace("rule-", "")}</p>
    </section>
  );
}

/** A window of delivery rows; the highlighted ZIP is shown even when the file lacks it. */
export function Sheet({ d, rows, highlight, title }: { d: Delivery; rows?: string[]; highlight?: string; title?: string }) {
  const changed = new Set(d.changed);
  const want = new Set([...(rows ?? []), ...(highlight ? [highlight] : [])]);
  const anchor = d.rows.findIndex((r) => want.has(r.zip) || changed.has(r.zip) || (want.size === 0 && changed.size === 0 && r.count === null));
  const from = anchor < 0 ? 0 : Math.max(0, Math.min(anchor - 2, d.rows.length - 6));
  const shown = d.rows.slice(from, from + 6);
  const missing = highlight && !d.rows.some((r) => r.zip === highlight);
  return (
    <section>
      <div className="sec-k">{title ?? `${d.file} · ${d.rows.length} ZIPs${changed.size > 0 ? ` · ${changed.size} changed` : ""}`}</div>
      <table className="sheet">
        <thead><tr><th>ZIP</th><th>Count</th></tr></thead>
        <tbody>
          {missing && <tr className="hl miss-row"><td>{highlight}</td><td className="miss">missing</td></tr>}
          {shown.map((r) => (
            <tr key={r.zip} className={r.zip === highlight ? "hl" : changed.has(r.zip) ? "chg" : undefined}>
              <td>{r.zip}</td>
              <td className={r.count === null ? "miss" : undefined}>{r.count === null ? `withheld · ${r.note ?? ""}` : r.count.toLocaleString("en-US")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export function Books({ entries, margin, coin }: { entries: JournalEntry[]; margin: Margin; coin: Coin | null }) {
  return (
    <section>
      <div className="sec-k">Journal entries</div>
      <table className="journal">
        <thead><tr><th>Entry</th><th>Debit</th><th>Credit</th><th className="num">Amount</th></tr></thead>
        <tbody>
          {entries.map((e) => <tr key={e.id}><td>{e.memo}</td><td>{e.debit}</td><td>{e.credit}</td><td className="num">${e.amount.toFixed(2)}</td></tr>)}
        </tbody>
      </table>
      <p className="margin">Margin ${(margin.revenue - margin.cost).toFixed(2)} <span className="faint">= ${margin.revenue.toFixed(2)} revenue − ${margin.cost.toFixed(2)} data cost</span></p>
      {coin?.state === "captured" && (
        <p className="tx">
          {coin.mock || !coin.tx
            ? <span className="faint">Mock capture, so there is no transaction yet. The Basescan link appears with a real x402 payment.</span>
            : <a className="cta-link" href={basescan(coin.tx)} target="_blank" rel="noreferrer">View the capture on Basescan</a>}
        </p>
      )}
    </section>
  );
}

/** When a human or the buyer must act, their window as the server set it. */
export function Deadline({ closesAt }: { closesAt: string }) {
  const d = new Date(closesAt);
  return <p className="deadline faint">Review closes {d.toLocaleString("en-US", { weekday: "short", hour: "numeric", minute: "2-digit" })}</p>;
}
