/* Generated from backend/app/contracts/jobflow.py. Do not edit. Run npm run generate. */

export type CaseState = "none" | "open" | "resolved" | "human_review";
export type DeliveryState = "pending_verification" | "passed" | "needs_review" | "operational_failure";
export type OrderState = "accepted" | "processing" | "failed" | "delivered" | "human_review" | "closed";
export type PaymentState =
  "unauthorized" | "authorized" | "submitted" | "uncertain" | "captured" | "released" | "expired" | "mock";
export type InvoiceCriterion =
  | "complete_coverage"
  | "no_double_counting"
  | "accurate_extraction"
  | "correct_arithmetic"
  | "traceable_evidence"
  | "honest_uncertainty"
  | "correct_final_delivery"
  | "defined_scope";

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
  amount_minor?: number | null;
  approval_id?: string | null;
  change_order_id?: string | null;
  effective_at?: string | null;
  expected_revision: number;
  fields?: string[];
  idempotency_key: string;
  issue_id?: string | null;
  job_ids?: string[];
  operation_id?: string | null;
  processing_quote_id?: string | null;
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
    | "authorize_change"
    | "decline_change"
    | "receive_payment"
    | "fulfill_change"
    | "accept_change_delivery"
    | "reconcile"
    | "handoff"
    | "verify_base"
    | "accept_base"
    | "quote_processing"
    | "accept_processing_quote";
}
export interface OrderCreate {
  additional_processing_fee_minor?: number;
  agreement_fields?: string[];
  authorization_seconds?: number;
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
  base_order?: OrderView1 | null;
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
  kind: "CORRECT" | "QUOTE" | "INCLUDED_FIELD" | "CONCESSION" | "HUMAN_REVIEW" | "NO_REMEDY";
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
  policy_id?: "invoice-review-v0.2";
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
export interface OrderView1 {
  available_actions: string[];
  display_status: "processing" | "correct" | "needs_review" | "operational_failure" | "human_review";
  order: OrderRecord;
  poll_after_ms?: 2000;
  server_time: string;
}
/**
 * Mutable only inside the repository's serialized transaction.
 */
export interface OrderRecord {
  answers?: CustomerAnswer[];
  authorization_expires_at: string;
  authorization_id: string;
  authorization_receipt: PaymentReceipt;
  binding?: ProposalBinding | null;
  case_id?: string | null;
  case_state?: CaseState;
  complaint?: string | null;
  deliveries?: DeliveryVersion[];
  delivery_state?: DeliveryState;
  evidence: EvidenceReference[];
  failure?: string | null;
  free_regenerations_used?: number;
  ledger?: LedgerEntry[];
  order_state?: OrderState;
  payment_phase?: "open" | "held" | "booked" | "expired";
  payment_state?: PaymentState;
  questions?: InvestigationQuestion[];
  questions_asked?: number;
  quote?: ProcessingQuote | null;
  quote_authorization?: QuoteAuthorization | null;
  refund_requested?: boolean;
  regeneration_pending?: boolean;
  requires_quote?: boolean;
  result?: InvestigationResult | null;
  review_deadline?: string | null;
  revision?: number;
  scope_obligations?: ScopeObligation[];
  snapshot: OrderSnapshot;
}
export interface CustomerAnswer {
  evidence: EvidenceReference;
  question_id: string;
  text: string;
}
export interface EvidenceReference {
  derived_from?: EvidencePointer[];
  evidence_id: string;
  kind: "accepted_input" | "delivery_artifact" | "customer_evidence" | "verification_report" | "structured_data";
  media_type: string;
  sha256: string;
  storage_key: string;
  version: number;
}
export interface EvidencePointer {
  evidence_id: string;
  sha256: string;
  version: number;
}
export interface PaymentReceipt {
  idempotency_key: string;
  mode: "mock" | "live";
  operation: "authorize" | "capture" | "release" | "additional_processing";
  operation_id: string;
  status: "mock" | "submitted" | "uncertain" | "confirmed" | "failed";
  transaction_id?: string | null;
}
export interface ProposalBinding {
  delivery_version: number;
  evidence_version: number;
  order_id: string;
  proposal_version: number;
  snapshot_id: string;
}
export interface DeliveryVersion {
  /**
   * @minItems 1
   */
  artifacts: [EvidenceReference, ...EvidenceReference[]];
  delivered_at: string;
  order_id: string;
  snapshot_id: string;
  structured_data?: EvidenceReference[];
  version: number;
}
export interface LedgerEntry {
  amount: Money;
  entry_id: string;
  kind: "base" | "additional_processing";
  reason: "evidence_verdict" | "customer_acceptance" | "review_cutoff" | "accepted_quote";
  receipt: PaymentReceipt;
  recorded_at: string;
}
/**
 * Integer minor units; asset identity/chain mapping awaits the payment spike.
 */
export interface Money {
  amount_minor: number;
  currency: string;
  decimals: number;
}
export interface InvestigationQuestion {
  missing_evidence: string;
  prompt: string;
  question_id: string;
}
export interface ProcessingQuote {
  amount: Money;
  binding: ProposalBinding;
  expires_at: string;
  quote_id: string;
}
export interface QuoteAuthorization {
  amount: Money;
  authorized_by: string;
  expires_at: string;
  quote_id: string;
  receipt: PaymentReceipt;
}
export interface InvestigationResult {
  case_id: string;
  checks: CriterionAssessment[];
  claim_assessment: "not_applicable" | "supported" | "refuted" | "unresolved";
  findings: Finding[];
  proposal: ProposalBinding;
  /**
   * @maxItems 1
   */
  questions: [] | [InvestigationQuestion];
  /**
   * @minItems 1
   */
  recommendations: [Recommendation, ...Recommendation[]];
  unresolved_issues: string[];
  verdict: "compliant" | "provider_defect" | "insufficient_evidence";
}
export interface CriterionAssessment {
  citations?: Citation[];
  criterion: InvoiceCriterion;
  explanation: string;
  status: "passed" | "failed" | "unknown";
}
export interface Citation {
  evidence_id: string;
  highlights?: PdfHighlight[];
  locator: string;
  sha256: string;
  version: number;
}
/**
 * One-based page; normalized rectangle on the displayed page, top-left origin.
 */
export interface PdfHighlight {
  page_number: number;
  x0: number;
  x1: number;
  y0: number;
  y1: number;
}
export interface Finding {
  /**
   * @minItems 1
   */
  citations: [Citation, ...Citation[]];
  statement: string;
}
export interface Recommendation {
  action: "capture" | "additional_processing" | "free_regeneration" | "request_evidence" | "human_review";
  rationale: string;
}
export interface ScopeObligation {
  amendment_id: string;
  effective_at: string;
  fields: string[];
  fulfilled?: boolean;
}
export interface OrderSnapshot {
  accepted_at: string;
  accepted_brief: string;
  /**
   * @minItems 1
   */
  input_versions: [EvidenceReference, ...EvidenceReference[]];
  job_type?: "invoice_register";
  order_id: string;
  policy: AcceptedPolicy;
  price: Money;
  snapshot_id: string;
  structured_data?: EvidenceReference[];
}
export interface AcceptedPolicy {
  additional_processing_price?: Money | null;
  free_regenerations?: 1;
  max_question_rounds?: 2;
  max_questions?: 2;
  policy_version: string;
  review_window_seconds?: 600;
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
  payment_authorization?: QuoteAuthorization | null;
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
  findings?: Finding1[];
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
export interface Finding1 {
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
  findings: Finding1[];
  input_tokens?: number;
  issue_id: string;
  model_id?: string | null;
  model_mode: "DETERMINISTIC" | "ANTHROPIC";
  output_tokens?: number;
  questions: Question[];
  recommendations: ("INCLUDED_FIELD" | "QUOTE" | "HUMAN_REVIEW" | "NO_REMEDY")[];
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
