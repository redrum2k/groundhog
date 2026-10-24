import type {
  Actor,
  Event,
  Issue,
  Job,
  OrderView,
} from "../lib/jobflow.generated";

export const actor: Actor = {
  id: "customer-a",
  role: "customer",
  name: "Test customer",
  customer_id: "northwind",
};
export const provider: Actor = {
  id: "provider-a",
  role: "provider",
  name: "Test provider",
};
export function job(overrides: Partial<Job> = {}): Job {
  return {
    id: "job-1",
    label: "Document 01",
    original_index: 1,
    kind: "ORIGINAL",
    processing: "FAILED",
    dispute: "NONE",
    financial_state: "PREPAID",
    source_id: "source-1",
    artifact_id: "artifact-1",
    fields: ["amount"],
    attempts: [],
    ...overrides,
  };
}
export function issue(overrides: Partial<Issue> = {}): Issue {
  return {
    id: "issue-1",
    title: "Due-date scope",
    field: "due_date",
    job_ids: ["job-1"],
    state: "WAITING_CUSTOMER",
    owner: "customer",
    next_action: "Provide the accepted amendment",
    messages: [
      {
        id: "m1",
        issue_id: "issue-1",
        author_id: "customer-a",
        author_name: "Test customer",
        text: "Please inspect this due date.",
        timestamp: "2026-10-23T10:00:00Z",
      },
    ],
    questions: [
      {
        id: "question-1",
        issue_id: "issue-1",
        recipient: "customer",
        text: "Which signed amendment includes due date?",
        status: "OPEN",
      },
    ],
    ...overrides,
  };
}
export function order(overrides: Partial<OrderView> = {}): OrderView {
  return {
    id: "order-1",
    case_id: "case-1",
    revision: 3,
    customer_id: "northwind",
    customer_name: "Northwind",
    title: "Test batch",
    created_at: "2026-10-23T10:00:00Z",
    agreement: {
      version: 1,
      fields: ["amount"],
      document_count: 100,
      source_id: "agreement-1",
    },
    jobs: [job()],
    evidence: [],
    issues: [issue()],
    finance: {
      received_minor: 10000,
      recognized_minor: 8000,
      liability_minor: 2000,
      correction_cost_minor: 0,
      operations: [],
      postings: [],
    },
    ...overrides,
  };
}
export function event(overrides: Partial<Event> = {}): Event {
  return {
    id: "event-1",
    sequence: 1,
    order_id: "order-1",
    case_id: "case-1",
    job_id: "job-1",
    attempt_id: "attempt-1",
    causal_id: "operation-1",
    timestamp: "2026-10-23T10:00:00Z",
    actor_id: "provider-a",
    type: "correction.queued",
    payload: { retry_from_stage: "extract" },
    ...overrides,
  };
}
