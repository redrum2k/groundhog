import type { Actor, Event, OrderView } from "../lib/jobflow.generated";
import { can, money, words } from "../lib/projection";
import type { CommandInput } from "../lib/api";
import { Badge, Button, Drawer } from "./ui";

export function FinanceDrawer({
  order,
  actor,
  busy,
  command,
  events,
}: {
  order: OrderView;
  actor?: Actor;
  busy: boolean;
  command: (input: CommandInput, label: string) => void;
  events: Event[];
}) {
  const finance = order.finance;
  return (
    <Drawer
      title="Finance receipts"
      description="Simulated USD cents · saas-unit-acceptance-v1. UNKNOWN is not received cash."
      trigger={<Button>View receipts ↗</Button>}
    >
      <dl className="receipt-summary">
        <div>
          <dt>Cash received</dt>
          <dd>{money(finance?.received_minor)}</dd>
        </div>
        <div>
          <dt>Earned</dt>
          <dd>{money(finance?.recognized_minor)}</dd>
        </div>
        <div>
          <dt>Contract liability</dt>
          <dd>{money(finance?.liability_minor)}</dd>
        </div>
        <div>
          <dt>Correction cost</dt>
          <dd>{money(finance?.correction_cost_minor)}</dd>
        </div>
        <div>
          <dt>Approved additions</dt>
          <dd>{money(finance?.approved_additions_minor)}</dd>
        </div>
        <div>
          <dt>Uncertain payment · not cash</dt>
          <dd>{money(finance?.unknown_minor)}</dd>
        </div>
      </dl>
      <h3>Payment operations</h3>
      {!finance?.operations?.length && (
        <p className="muted">No payment operations recorded.</p>
      )}
      {finance?.operations?.map((op) => (
        <article className="inset" key={op.id}>
          <div className="row spread">
            <strong>{money(op.amount_minor)}</strong>
            <Badge tone={op.status === "UNKNOWN" ? "orange" : "neutral"}>
              {op.status} · simulated
            </Badge>
          </div>
          <p className="small wrap">
            Operation {op.id}
            <br />
            Provider reference: {op.provider_reference}
            <br />
            Change order: {op.change_order_id ?? "Original prepayment"}
          </p>
          {op.status === "UNKNOWN" && can(actor, "reconcile") && (
            <Button
              disabled={busy}
              onClick={() =>
                command(
                  { verb: "reconcile", operation_id: op.id },
                  "Reconcile existing payment",
                )
              }
            >
              Reconcile UNKNOWN
            </Button>
          )}
        </article>
      ))}
      <h3>Posted ledger entries</h3>
      <p className="muted small">
        Only persisted postings are shown. Acceptance and payment are separate
        from recognition.
      </p>
      {finance?.postings?.map((posting) => (
        <details key={posting.id}>
          <summary>
            {posting.description}{" "}
            <span className="muted">· {posting.mode ?? "SIMULATED"}</span>
          </summary>
          <p className="small wrap">
            Posting {posting.id}
            <br />
            Source business event: {posting.business_event_id}
            <br />
            {posting.timestamp}
          </p>
          <details>
            <summary>Inspect linked business event</summary>
            {events.some(
              (event) =>
                event.id === posting.business_event_id ||
                event.causal_id === posting.business_event_id,
            ) ? (
              events
                .filter(
                  (event) =>
                    event.id === posting.business_event_id ||
                    event.causal_id === posting.business_event_id,
                )
                .map((event) => (
                  <div key={event.id}>
                    <strong>{event.type}</strong>
                    <p className="small wrap">
                      {event.id} · {event.timestamp} · {event.actor_id}
                    </p>
                    <pre>{JSON.stringify(event.payload, null, 2)}</pre>
                  </div>
                ))
            ) : (
              <p className="muted small">
                The posting's source ID is recorded above; a matching event is
                not in the loaded event stream.
              </p>
            )}
          </details>
          <table className="ledger">
            <caption className="sr-only">{posting.description}</caption>
            <thead>
              <tr>
                <th>Account</th>
                <th>Debit</th>
                <th>Credit</th>
              </tr>
            </thead>
            <tbody>
              {posting.lines.map((line, i) => (
                <tr key={i}>
                  <th>{words(line.account)}</th>
                  <td>{money(line.debit_minor)}</td>
                  <td>{money(line.credit_minor)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      ))}
    </Drawer>
  );
}
