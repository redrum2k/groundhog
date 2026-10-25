"use client";
import { useState } from "react";
import type { components } from "../../api.generated";
import { LIVE_API } from "../../lib/run/live";

type Record = components["schemas"]["PaymentJustification"];

export default function PaymentJustification({orderId}: {orderId: string}) {
  const [record, setRecord] = useState<Record | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const path = `${LIVE_API}/orders/${encodeURIComponent(orderId)}/payment-justification`;
  async function inspect() {
    setBusy(true); setError(null);
    try {
      const response = await fetch(path, {cache:"no-store"});
      if (!response.ok) throw new Error(`Evidence unavailable (${response.status})`);
      setRecord(await response.json());
    } catch (e) { setError(e instanceof Error ? e.message : "Evidence unavailable"); }
    finally { setBusy(false); }
  }
  return <details className="live-details"><summary>Why may money move?</summary>
    <button className="btn" type="button" onClick={()=>void inspect()} disabled={busy}>{busy ? "Checking evidence…" : "Inspect financial evidence"}</button>
    {error && <p role="alert">{error}</p>}
    {record && <>
      <p><b>Promised:</b> {record.agreement.quote.specification.summary} · ${record.exact_price} ({record.amount_atomic} atomic USDC).</p>
      <p><b>Delivered:</b> {Object.keys(record.delivery_hashes).length} persisted artifacts; current byte checks {record.bytes_revalidated ? "pass" : "do not pass"}.</p>
      <p><b>Challenged:</b> {record.cases.length ? record.cases.map(c=>c.complaint.text).join("; ") : "No recorded objection."}</p>
      <p><b>Money:</b> {record.state}{record.payment?.simulated ? " (simulated, no on-chain transfer)" : ""}. {record.capture_eligible_now ? "The execution guard currently permits capture; it must recheck at submission." : "Another capture is not currently permitted."}</p>
      {!!record.blockers.length && <ul>{record.blockers.map(b=><li key={b}>{b}</li>)}</ul>}
      <p>{record.bookings.length} persisted terminal booking(s). {record.decisions.length} reviewer decision(s).</p>
      <p className="faint">Observed revision {record.revision} at {record.observed_at}. This record is an explanation, not payment authorization.</p>
      <a className="btn" href={path} target="_blank" rel="noreferrer">Open full justification and evidence references</a>
    </>}
  </details>;
}
