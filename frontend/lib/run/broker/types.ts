// The slices of Jeff's broker API the translator and driver read. Generated types for the full
// shapes live in lib/broker.generated.ts; these are narrowed on purpose so the translator's
// inputs stay small and testable against recorded fixtures.

export interface BrokerEvent {
  id: string;
  sequence: number;
  type: string;
  timestamp: string;
  actor_id: string;
  payload: Record<string, unknown>;
}

export interface BrokerMessage { id: string; actor_id: string; text: string; field?: string | null }
export interface BrokerQuestion { id: string; text: string; recipient: "customer" | "provider" | "controller"; status: string; issue_id?: string }
export interface BrokerTask { id: string; state: "OPEN" | "RESOLVED"; reason: string; missing_facts: string[]; decision?: string | null; decided_by?: string | null }
export interface BrokerCheck { requirement_id: string; verdict: "PASS" | "FAIL" | "UNKNOWN" | "CONFLICT"; explanation: string }
export interface BrokerMoney { amount_minor: number; currency: string; decimals: number }

export interface BrokerOrder {
  id: string;
  revision: number;
  resolution: "NO_REMEDY" | "CORRECTED" | "HUMAN_REVIEW" | null;
  messages: BrokerMessage[];
  questions: BrokerQuestion[];
  human_tasks: BrokerTask[];
  amendments?: { id: string; digest: string }[];
  delivery_artifact_ids?: string[]; // absent on a draft
  original_specification?: Specification | null;
  base_order?: {
    order: {
      order_state: string;
      payment_phase: string;
      review_deadline: string | null;
      complaint?: string | null;
      binding: { delivery_version: number; evidence_version: number } | null; // null until the first delivery
      regeneration_pending?: boolean;
      snapshot?: { price: BrokerMoney } | null;
      ledger: { entry_id: string; kind: string; amount: BrokerMoney; reason: string }[];
      data_verification?: { verdict: string; checks: BrokerCheck[] } | null;
    };
  } | null;
}

/** The accepted specification as the backend returns it; an amendment resends it with a higher version. */
export interface Specification { version: number; sources: { source_id: string; version: number; sha256: string }[]; requirements: { id: string; dimension: string; parameters: Record<string, unknown> }[]; [key: string]: unknown }

/** One delivered row of market-v1 data. */
export interface DataRow { entity_id: string; region_id: string; value: number; observed_at: string | null }

/** What the translator needs for one poll: the stream so far, the current record, and what earlier
 *  verifications and deliveries held (the record only keeps the latest of each). */
export interface BrokerSnapshot {
  events: BrokerEvent[];
  order: BrokerOrder;
  checksBySeq: Record<number, BrokerCheck[]>; // by the verification.completed event's sequence
  rowsByVersion: Record<number, DataRow[]>; // by delivery version
}
