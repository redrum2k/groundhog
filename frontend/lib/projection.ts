import type {
  Action,
  Actor,
  Command,
  Event,
  Job,
  OrderView,
} from "./jobflow.generated";

export type Tone = "green" | "red" | "orange" | "blue";
export const activeDispute = (job: Job) =>
  !!job.dispute && !["NONE", "RESOLVED"].includes(job.dispute);
export function jobTone(job: Job): Tone {
  if (activeDispute(job)) return "orange";
  if (job.processing === "FAILED") return "red";
  if (job.processing === "VALIDATED") return "green";
  return "blue";
}
export function originalProgress(order: OrderView) {
  const jobs = order.jobs.filter((j) => (j.kind ?? "ORIGINAL") === "ORIGINAL");
  return {
    jobs,
    total: order.agreement.document_count,
    validated: jobs.filter((j) => j.processing === "VALIDATED").length,
    accepted: jobs.filter(
      (j) =>
        !!j.accepted_artifact_id && j.accepted_artifact_id === j.artifact_id,
    ).length,
    counts: Object.fromEntries(
      (["green", "red", "orange", "blue"] as const).map((t) => [
        t,
        jobs.filter((j) => jobTone(j) === t).length,
      ]),
    ) as Record<Tone, number>,
  };
}
export const money = (minor: number = 0) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(
    minor / 100,
  );
export const words = (value: string = "") =>
  value.toLowerCase().replaceAll("_", " ");
export const recoverableJobs = (order: OrderView) =>
  order.jobs.filter(
    (j) =>
      (j.kind ?? "ORIGINAL") === "ORIGINAL" &&
      j.processing === "FAILED" &&
      j.recoverable !== false &&
      (j.attempts?.length ?? 0) <
        (order.agreement.correction_attempt_limit ?? 1),
  );
export const acceptableJobs = (order: OrderView) =>
  order.jobs.filter(
    (j) =>
      (j.kind ?? "ORIGINAL") === "ORIGINAL" &&
      j.processing === "VALIDATED" &&
      !activeDispute(j) &&
      !!j.artifact_id &&
      j.accepted_artifact_id !== j.artifact_id,
  );

// This controls affordances, not authority. The API rechecks identity, revision,
// policy, scope, approval independence and effective time on every command.
const roles: Record<Command["verb"], readonly Actor["role"][]> = {
  correct: ["provider"],
  accept_delivery: ["customer"],
  open_dispute: ["customer"],
  answer: ["customer", "controller"],
  amend_agreement: ["customer", "provider"],
  approve_action: ["controller"],
  decline_action: ["controller"],
  execute_action: ["executor"],
  accept_change: ["customer"],
  decline_change: ["customer"],
  receive_payment: ["executor"],
  fulfill_change: ["provider"],
  accept_change_delivery: ["customer"],
  reconcile: ["executor"],
  handoff: ["controller"],
};
export const can = (actor: Actor | undefined, verb: Command["verb"]) =>
  !!actor && roles[verb].includes(actor.role);
export function historical(action: Action, order: OrderView, now = Date.now()) {
  return (
    ["STALE", "DECLINED", "EXECUTED"].includes(action.status ?? "PROPOSED") ||
    action.agreement_version !== (order.agreement.version ?? 1) ||
    Date.parse(action.expires_at) <= now
  );
}
export function mergeSnapshot(
  current: OrderView | undefined,
  incoming: OrderView,
): OrderView {
  if (
    !current ||
    current.id !== incoming.id ||
    incoming.revision >= current.revision
  )
    return incoming;
  return current;
}
export function mergeEvents(
  current: Event[],
  incoming: Event[],
  orderId: string,
) {
  return [
    ...new Map(
      [...current, ...incoming]
        .filter((e) => e.order_id === orderId)
        .map((e) => [e.id, e]),
    ).values(),
  ].sort((a, b) => a.sequence - b.sequence);
}
export function courierEvent(event: Event) {
  if (["correction.queued", "correction.started"].includes(event.type))
    return true;
  if (!event.attempt_id) return false;
  if (["check.passed", "correction.validated"].includes(event.type))
    return true;
  return (
    event.type === "validation.completed" &&
    ["VALIDATED", "PASSED", "SUCCESS"].includes(
      String(event.payload?.status ?? ""),
    )
  );
}

/** An explicit traversal takes a snapshot of unresolved IDs, never re-enqueues. */
export function unresolvedIds(order: OrderView) {
  return order.jobs
    .filter(
      (j) =>
        activeDispute(j) ||
        j.processing === "FAILED" ||
        j.processing === "QUEUED" ||
        j.processing === "RUNNING" ||
        j.processing === "CORRECTING",
    )
    .map((j) => j.id);
}
export function nextInTraversal(
  ids: string[],
  visited: string[],
  order: OrderView,
) {
  const remaining = new Set(unresolvedIds(order));
  return ids.find((id) => !visited.includes(id) && remaining.has(id));
}
