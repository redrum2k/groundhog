/* Generated from backend/app/contracts/jobflow.py. Do not edit. Run npm run generate. */

export interface ContractExport {
  actor: Actor;
  command: Command;
  create: OrderCreate;
  event: Event;
  investigation_request: InvestigationRequest;
  order: OrderView;
  outcome: InvestigationOutcome;
  upload: DocumentUpload;
}
export interface Actor {
  customer_id?: string | null;
  id: string;
  name: string;
  role: "customer" | "provider" | "investigator" | "controller" | "executor";
}
export interface Command {
  action_id?: string | null;
  amendment_id?: string | null;
  approval_id?: string | null;
  change_order_id?: string | null;
  effective_at?: string | null;
  expected_revision: number;
  fields?: string[];
  idempotency_key: string;
  issue_id?: string | null;
  job_ids?: string[];
  operation_id?: string | null;
  provider_outcome?: "SUCCESS" | "FAILURE" | "UNKNOWN";
  question_id?: string | null;
  text?: string | null;
  verb:
    | "correct"
    | "accept_delivery"
    | "open_dispute"
    | "answer"
    | "amend_agreement"
    | "approve_action"
    | "decline_action"
    | "execute_action"
    | "accept_change"
    | "decline_change"
    | "receive_payment"
    | "fulfill_change"
    | "accept_change_delivery"
    | "reconcile"
    | "handoff";
}
export interface OrderCreate {
  agreement_fields?: string[];
  customer_name?: string;
  disputed_field?: string | null;
  document_count?: number;
  failed_count?: number;
  idempotency_key: string;
  initial_receipt?: "CONFIRMED" | "UNKNOWN" | "NONE";
  requested_fields?: string[];
  title?: string;
  unit_price_minor?: number;
}
export interface Event {
  actor_id: string;
  attempt_id?: string | null;
  case_id: string;
  causal_id: string;
  id: string;
  job_id?: string | null;
  mode?: "SIMULATED" | "LIVE" | "READ_ONLY_REPLAY";
  order_id: string;
  payload?: {
    [k: string]: unknown;
  };
  schema_version?: 1;
  sequence: number;
  timestamp: string;
  type: string;
}
export interface InvestigationRequest {
  expected_revision: number;
  idempotency_key: string;
  issue_id: string;
  mode?: "DETERMINISTIC" | "ANTHROPIC";
}
export interface OrderView {
  actions?: Action[];
  agreement: Agreement;
  approvals?: Approval[];
  case_id: string;
  change_orders?: ChangeOrder[];
  created_at: string;
  customer_id: string;
  customer_name: string;
  evidence: Evidence[];
  finance?: Finance;
  id: string;
  investigations?: InvestigationRun[];
  issues?: Issue[];
  jobs: Job[];
  last_event_sequence?: number;
  mode?: "SIMULATED";
  model_available?: boolean;
  revision: number;
  status?: "ACTIVE" | "WAITING" | "COMPLETE" | "HANDED_OFF";
  title: string;
}
export interface Action {
  agreement_version: number;
  amount_minor?: number;
  basis: string;
  citations?: SourceLocation[];
  evidence_digest: string;
  expires_at: string;
  fields?: string[];
  id: string;
  issue_id?: string | null;
  job_ids?: string[];
  kind: "CORRECT" | "QUOTE" | "INCLUDED_FIELD" | "CONCESSION" | "HUMAN_REVIEW";
  owner: string;
  revision: number;
  scope_digest: string;
  status?: "PROPOSED" | "APPROVED" | "DECLINED" | "EXECUTED" | "STALE";
}
export interface SourceLocation {
  locator: string;
  page?: number | null;
  quote: string;
  rectangle?: [number, number, number, number] | null;
  sha256: string;
  source_id: string;
  version: number;
}
export interface Agreement {
  additional_field_price_minor?: number;
  amendments?: Amendment[];
  correction_attempt_limit?: 1;
  correction_budget_minor?: number;
  correction_unit_cost_minor?: number;
  currency?: "USD_SIM";
  decimals?: 2;
  document_count: number;
  fields: string[];
  policy_id?: "saas-unit-acceptance-v1";
  source_id: string;
  unit_price_minor?: number;
  version?: number;
}
export interface Amendment {
  accepted_by_customer?: string | null;
  accepted_by_provider?: string | null;
  effective_at: string;
  fields: string[];
  id: string;
  source_id: string;
}
export interface Approval {
  action_id: string;
  actor_id: string;
  created_at: string;
  digest: string;
  expires_at: string;
  id: string;
  role: "customer" | "provider" | "investigator" | "controller" | "executor";
}
export interface ChangeOrder {
  accepted_artifact_ids?: string[];
  accepted_by?: string | null;
  action_id: string;
  amount_minor: number;
  artifact_ids?: string[];
  fields: string[];
  id: string;
  job_ids: string[];
  operation_id?: string | null;
  status: "DRAFT" | "ACCEPTED" | "DECLINED" | "PAYMENT_PENDING" | "PAID" | "FULFILLED" | "RECOGNIZED" | "UNKNOWN";
}
export interface Evidence {
  authority: "COMPANY_RECORD" | "ACCEPTED_AGREEMENT" | "PARTY_ASSERTION";
  created_at: string;
  derived_from?: string[];
  filename: string;
  id: string;
  kind: "agreement" | "amendment" | "message" | "source" | "artifact" | "verification";
  media_type: string;
  origin_actor_id: string;
  sha256: string;
  text: string;
  version?: number;
}
export interface Finance {
  approved_additions_minor?: number;
  correction_cost_minor?: number;
  currency?: "USD_SIM";
  decimals?: 2;
  liability_minor?: number;
  operations?: PaymentOperation[];
  postings?: Posting[];
  received_minor?: number;
  recognized_minor?: number;
  unknown_minor?: number;
}
export interface PaymentOperation {
  amount_minor: number;
  change_order_id?: string | null;
  id: string;
  mode?: "SIMULATED";
  provider_reference: string;
  status: "PENDING" | "CONFIRMED" | "UNKNOWN" | "FAILED";
}
export interface Posting {
  business_event_id: string;
  description: string;
  id: string;
  lines: PostingLine[];
  mode?: "SIMULATED" | "LIVE" | "READ_ONLY_REPLAY";
  timestamp: string;
}
export interface PostingLine {
  account: "cash" | "contract_liability" | "revenue" | "correction_expense" | "compute_payable";
  credit_minor?: number;
  debit_minor?: number;
}
export interface InvestigationRun {
  elapsed_ms?: number | null;
  error?: string | null;
  id: string;
  input_tokens?: number;
  issue_id: string;
  mode: "DETERMINISTIC" | "ANTHROPIC";
  output_tokens?: number;
  revision: number;
  status: "QUEUED" | "RUNNING" | "COMPLETE" | "FAILED" | "STALE" | "BLOCKED";
}
export interface Issue {
  field: string;
  findings?: Finding[];
  id: string;
  job_ids: string[];
  messages?: Message[];
  next_action?: string;
  owner?: string;
  questions?: Question[];
  resolution?: string | null;
  state?: "NONE" | "OPEN" | "INVESTIGATING" | "WAITING_CUSTOMER" | "WAITING_INTERNAL" | "RESOLVED";
  title: string;
}
export interface Finding {
  citations?: SourceLocation[];
  id: string;
  issue_id: string;
  statement: string;
  status: "SUPPORTED" | "CONTRADICTED" | "CONFLICTING" | "INSUFFICIENT";
}
export interface Message {
  author_id: string;
  author_name: string;
  id: string;
  issue_id: string;
  question_id?: string | null;
  source_id?: string | null;
  text: string;
  timestamp: string;
}
export interface Question {
  answer_id?: string | null;
  id: string;
  issue_id: string;
  recipient: "customer" | "controller";
  status?: "OPEN" | "ANSWERED" | "CANCELLED";
  text: string;
}
export interface Job {
  accepted_artifact_id?: string | null;
  artifact_id?: string | null;
  attempts?: Attempt[];
  checks?: Check[];
  dispute?: "NONE" | "OPEN" | "INVESTIGATING" | "WAITING_CUSTOMER" | "WAITING_INTERNAL" | "RESOLVED";
  fields: string[];
  financial_state?: string;
  id: string;
  issue_ids?: string[];
  kind?: "ORIGINAL" | "CORRECTION" | "CHANGE_ORDER" | "DISPUTED_FIELD";
  label: string;
  next_action?: string;
  obligation?: "OPEN" | "FULFILLED" | "CANCELLED_WITH_AUTHORITY" | "HANDED_OFF";
  original_index?: number | null;
  owner?: string;
  parent_id?: string | null;
  processing: "QUEUED" | "RUNNING" | "FAILED" | "CORRECTING" | "VALIDATED" | "CANCELLED";
  recoverable?: boolean;
  source_id: string;
}
export interface Attempt {
  cost_minor?: number;
  error?: string | null;
  id: string;
  input_artifact_id: string;
  number: number;
  operation_id: string;
  output_artifact_id?: string | null;
  retry_from_stage?: "extract" | "validate";
  status: "QUEUED" | "RUNNING" | "VALIDATED" | "FAILED" | "UNKNOWN";
}
export interface Check {
  citations?: SourceLocation[];
  detail: string;
  id: string;
  label: string;
  state: "PASSED" | "FAILED" | "PENDING" | "DISPUTED";
}
export interface InvestigationOutcome {
  findings: Finding[];
  issue_id: string;
  model_mode: "DETERMINISTIC" | "ANTHROPIC";
  questions: Question[];
  recommendations: ("INCLUDED_FIELD" | "QUOTE" | "HUMAN_REVIEW")[];
  revision: number;
  summary: string;
}
export interface DocumentUpload {
  content_base64: string;
  expected_revision: number;
  filename: string;
  idempotency_key: string;
  issue_id?: string | null;
  kind?: "agreement" | "amendment" | "message" | "source";
  media_type: "text/plain" | "application/pdf" | "application/json" | "text/csv";
}
