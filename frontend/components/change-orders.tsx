import type { Actor, OrderView } from "../lib/jobflow.generated";
import type { CommandInput } from "../lib/api";
import { can, historical, money, words } from "../lib/projection";
import { Badge, Button } from "./ui";
import { CitationList, SourceCard } from "./evidence";

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
  const proposals = (order.actions ?? []).filter(
    (a) => a.kind === "QUOTE" && !a.issue_id,
  );
  if (!order.change_orders?.length && !proposals.length) return null;
  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Separate from original delivery</span>
          <h2>Added scope</h2>
        </div>
        <Badge>{order.change_orders?.length ?? 0} change orders</Badge>
      </div>
      {proposals.map((action) => {
        const old = historical(action, order);
        const approval = order.approvals?.find(
          (a) =>
            a.action_id === action.id &&
            a.actor_id !== actor?.id &&
            Date.parse(a.expires_at) > Date.now(),
        );
        return (
          <article
            key={action.id}
            className={`inset ${old ? "historical" : ""}`}
          >
            <div className="row spread">
              <strong>
                Additional-field quote · {money(action.amount_minor)}
              </strong>
              <Badge>
                {old
                  ? `Historical · ${action.status}`
                  : (action.status ?? "PROPOSED")}
              </Badge>
            </div>
            <p>
              {action.fields?.join(", ")} · {action.job_ids?.length ?? 0}{" "}
              documents
            </p>
            <p className="small muted">{action.basis}</p>
            <details>
              <summary>Quote evidence</summary>
              <CitationList
                order={order}
                citations={action.citations ?? []}
                token={token}
              />
            </details>
            {!old && (
              <div className="row">
                {(action.status ?? "PROPOSED") === "PROPOSED" &&
                  can(actor, "approve_action") && (
                    <>
                      <Button
                        variant="primary"
                        disabled={busy}
                        onClick={() =>
                          command(
                            { verb: "approve_action", action_id: action.id },
                            "Approve quote",
                          )
                        }
                      >
                        Approve quote
                      </Button>
                      <Button
                        disabled={busy}
                        onClick={() =>
                          command(
                            { verb: "decline_action", action_id: action.id },
                            "Decline quote proposal",
                          )
                        }
                      >
                        Decline quote proposal
                      </Button>
                    </>
                  )}
                {action.status === "APPROVED" &&
                  can(actor, "execute_action") && (
                    <Button
                      variant="primary"
                      disabled={busy || !approval}
                      onClick={() =>
                        command(
                          {
                            verb: "execute_action",
                            action_id: action.id,
                            approval_id: approval?.id,
                          },
                          "Create approved quote",
                        )
                      }
                    >
                      Create approved quote
                    </Button>
                  )}
              </div>
            )}
          </article>
        );
      })}
      {(order.change_orders ?? []).map((change) => (
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
            {change.status === "ACCEPTED" && !change.payment_authorization && can(actor, "authorize_change") && (
              <Button disabled={busy} onClick={() => command(
                { verb: "authorize_change", change_order_id: change.id }, "Authorize additional payment",
              )}>Authorize payment · {money(change.amount_minor)}</Button>
            )}
            {change.status === "ACCEPTED" && !!change.payment_authorization &&
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
