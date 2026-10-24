import type { Actor, OrderView } from "../lib/jobflow.generated";
import type { CommandInput } from "../lib/api";
import { can, money, words } from "../lib/projection";
import { Badge, Button } from "./ui";
import { SourceCard } from "./evidence";
import { useState } from "react";

export function BaseReview({ order, actor, token, busy, command }: {
  order: OrderView; actor: Actor; token: string; busy: boolean;
  command: (input: CommandInput, label: string) => void;
}) {
  const [quoteCents, setQuoteCents] = useState("");
  const view = order.base_order;
  if (!view) return null;
  const base = view.order;
  const remaining = base.review_deadline
    ? Math.max(0, Math.ceil((Date.parse(base.review_deadline) - Date.parse(view.server_time)) / 1000))
    : null;
  const unresolved = order.issues?.some((issue) => issue.state !== "RESOLVED");
  const delivery = base.deliveries?.at(-1);
  const source = order.evidence.find((item) => item.id === delivery?.artifacts[0]?.evidence_id);
  return <section className="panel" aria-label="Base order review">
    <div className="section-heading"><div><span className="eyebrow">Accepted MVP policy · v0.2</span>
      <h2>Base order review</h2></div><Badge>{words(base.payment_phase)} · mock</Badge></div>
    <p>Authorized {money(base.snapshot.price.amount_minor)}. {remaining === null
      ? "No active delivery review." : `Review remaining: ${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, "0")} / 10:00.`}
      {" "}Authorization expires independently: {new Date(base.authorization_expires_at).toLocaleString()}.</p>
    <p className="small">Delivery: {words(view.display_status)}. Free regenerations: {base.free_regenerations_used ?? 0} / 1.
      {" "}Unresolved disputes hold payment. Capture does not itself prove the PDF correct.</p>
    {base.failure && <p role="status">{base.failure}</p>}
    <div className="row">
      {can(actor, "verify_base") && delivery && !base.result && <Button disabled={busy || unresolved || remaining === 0 || remaining === null}
        onClick={() => command({ verb: "verify_base" }, "Verify eight invoice criteria")}>Verify register evidence</Button>}
      {can(actor, "accept_base") && view.available_actions.includes("accept") && <Button disabled={busy || unresolved}
        onClick={() => command({ verb: "accept_base" }, "Accept base delivery and capture")}>Accept base delivery · {money(base.snapshot.price.amount_minor)}</Button>}
    </div>
    {source && <details><summary>Inspect delivered register PDF</summary><SourceCard order={order} sourceId={source.id} token={token} /></details>}
    {!!base.ledger?.length && <details><summary>Base payment ledger · mock</summary>
      {base.ledger.map((entry) => <p key={entry.entry_id}>{words(entry.kind)} · {money(entry.amount.amount_minor)} · {words(entry.reason)}</p>)}
    </details>}
    {base.requires_quote && <p role="status">The complaint was refuted, but no processing fee was agreed. A separately accepted and authorized processing quote is required; no extra charge has been made.</p>}
    {base.requires_quote && can(actor, "quote_processing") && <form onSubmit={(event) => {
      event.preventDefault(); command({ verb: "quote_processing", amount_minor: Number(quoteCents) }, "Propose processing quote");
    }}><label>Processing quote in cents <input type="number" min="1" step="1" required value={quoteCents}
      onChange={(event) => setQuoteCents(event.target.value)} /></label><Button disabled={busy} type="submit">Propose processing quote</Button></form>}
    {base.requires_quote && base.quote && can(actor, "accept_processing_quote") && <Button disabled={busy}
      onClick={() => command({ verb: "accept_processing_quote", processing_quote_id: base.quote!.quote_id }, "Accept and authorize processing quote")}>Accept & authorize processing fee · {money(base.quote.amount.amount_minor)}</Button>}
    {!!base.result && <details><summary>Eight-criterion evidence verdict · {base.result.verdict}</summary>
      {base.result.checks.map((check) => <p key={check.criterion}><strong>{words(check.criterion)}: {check.status}.</strong> {check.explanation}</p>)}
    </details>}
  </section>;
}
