import type { Actor, OrderView } from "../lib/jobflow.generated";
import type { CommandInput } from "../lib/api";
import { can, money, words } from "../lib/projection";
import { Badge, Button } from "./ui";
import { SourceCard } from "./evidence";

export function ChangeOrders({
  order,
  actor,
  token,
  busy,
  command,
}: {
  order: OrderView;
  actor?: Actor;
  token: string;
  busy: boolean;
  command: (input: CommandInput, label: string) => void;
}) {
  if (!order.change_orders?.length) return null;
  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Separate from original delivery</span>
          <h2>Added scope</h2>
        </div>
        <Badge>{order.change_orders.length} change orders</Badge>
      </div>
      {order.change_orders.map((change) => (
        <article className="change-order" key={change.id}>
          <div className="row spread">
            <strong>{change.fields.join(", ")}</strong>
            <span>
              <strong>{money(change.amount_minor)}</strong>{" "}
              <Badge tone={change.status === "UNKNOWN" ? "orange" : "neutral"}>
                {words(change.status)}
              </Badge>
            </span>
          </div>
          <p className="small muted">
            {change.id} · {change.job_ids.length} units · proposal{" "}
            {change.action_id}
          </p>
          <p className="small">
            Quote acceptance ≠ payment. Payment ≠ earned revenue. New delivery
            must be accepted separately.
          </p>
          <div className="row">
            {change.status === "DRAFT" && can(actor, "accept_change") && (
              <>
                <Button
                  variant="primary"
                  disabled={busy}
                  onClick={() =>
                    command(
                      { verb: "accept_change", change_order_id: change.id },
                      "Accept quote",
                    )
                  }
                >
                  Accept quote · {money(change.amount_minor)}
                </Button>
                <Button
                  disabled={busy}
                  onClick={() =>
                    command(
                      { verb: "decline_change", change_order_id: change.id },
                      "Decline quote",
                    )
                  }
                >
                  Decline quote
                </Button>
              </>
            )}
            {["ACCEPTED", "PAYMENT_PENDING"].includes(change.status) &&
              can(actor, "receive_payment") && (
                <Button
                  disabled={busy}
                  onClick={() =>
                    command(
                      {
                        verb: "receive_payment",
                        change_order_id: change.id,
                        provider_outcome: "SUCCESS",
                      },
                      "Simulated receipt",
                    )
                  }
                >
                  Record simulated receipt
                </Button>
              )}
            {change.status === "UNKNOWN" && can(actor, "reconcile") && (
              <Button
                disabled={busy || !change.operation_id}
                onClick={() =>
                  command(
                    {
                      verb: "reconcile",
                      operation_id: change.operation_id,
                      change_order_id: change.id,
                    },
                    "Reconcile existing payment",
                  )
                }
              >
                Reconcile UNKNOWN
              </Button>
            )}
            {change.status === "PAID" && can(actor, "fulfill_change") && (
              <Button
                disabled={busy}
                variant="primary"
                onClick={() =>
                  command(
                    { verb: "fulfill_change", change_order_id: change.id },
                    "Fulfill added scope",
                  )
                }
              >
                Fulfill added scope
              </Button>
            )}
            {change.status === "FULFILLED" &&
              can(actor, "accept_change_delivery") && (
                <Button
                  disabled={busy}
                  variant="primary"
                  onClick={() =>
                    command(
                      {
                        verb: "accept_change_delivery",
                        change_order_id: change.id,
                      },
                      "Accept extra delivery",
                    )
                  }
                >
                  Accept extra delivery
                </Button>
              )}
          </div>
          {!!change.artifact_ids?.length && (
            <details>
              <summary>
                Inspect {change.artifact_ids.length} delivered artifacts
              </summary>
              {change.artifact_ids.map((id) => (
                <SourceCard
                  key={id}
                  order={order}
                  sourceId={id}
                  token={token}
                />
              ))}
            </details>
          )}
        </article>
      ))}
    </section>
  );
}
