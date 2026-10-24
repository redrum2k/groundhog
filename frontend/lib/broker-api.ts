import { request } from "./api";
import type {
  BrokerCommand,
  BrokerRecord,
  DraftCreate,
  IntakeDraft,
  SourceUpload,
} from "./broker.generated";
import type {
  ImprovementCommand,
  ImprovementCommandResult,
} from "./improvement.generated";
import type { Event } from "./jobflow.generated";

export type ProfileMutation = Readonly<{
  base: "/api/broker" | "/api/improvements";
  path: string;
  body: string;
}>;
type DraftMutation<T> = T extends unknown
  ? Omit<T, "idempotency_key" | "expected_revision">
  : never;

export const brokerOrder = (id: string, token: string) =>
  request<BrokerRecord>(
    `/orders/${encodeURIComponent(id)}`,
    token,
    {},
    "/api/broker",
  );
export const brokerDraft = (id: string, token: string) =>
  request<IntakeDraft>(
    `/drafts/${encodeURIComponent(id)}`,
    token,
    {},
    "/api/broker",
  );
export const profileEvents = (
  base: ProfileMutation["base"],
  id: string,
  token: string,
  after = 0,
) =>
  request<Event[]>(
    `/entities/${encodeURIComponent(id)}/events?after=${after}`,
    token,
    {},
    base,
  );

export function prepareBrokerMutation(
  path: string,
  payload: DraftMutation<BrokerCommand | DraftCreate | SourceUpload>,
  revision?: number,
): ProfileMutation {
  return Object.freeze({
    base: "/api/broker",
    path,
    body: JSON.stringify({
      ...payload,
      idempotency_key: crypto.randomUUID(),
      ...(revision === undefined ? {} : { expected_revision: revision }),
    }),
  });
}

export function prepareImprovementMutation(
  payload: Omit<ImprovementCommand, "idempotency_key">,
): ProfileMutation {
  return Object.freeze({
    base: "/api/improvements",
    path: "/commands",
    body: JSON.stringify({ ...payload, idempotency_key: crypto.randomUUID() }),
  });
}

export const sendProfileMutation = (mutation: ProfileMutation, token: string) =>
  request<BrokerRecord | IntakeDraft | ImprovementCommandResult>(
    mutation.path,
    token,
    { method: "POST", body: mutation.body },
    mutation.base,
  );

export function mergeProfileSnapshot<
  T extends { id: string; revision: number },
>(current: T | undefined, incoming: T): T {
  return !current ||
    current.id !== incoming.id ||
    incoming.revision >= current.revision
    ? incoming
    : current;
}
