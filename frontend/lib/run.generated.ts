/* Generated from backend/app/contracts/run.py. Do not edit. Run npm run generate. */

export interface CatalogRunContractExport {
  acceptance: AcceptQuoteCommand;
  clarification: ClarifyCommand;
  draft: RequestDraft;
  event: CatalogEvent;
  events: CatalogEvents;
  funding_authorization: FundingAuthorization;
  funding_preparation: FundingPreparation;
  order_command: OrderCommand;
  order_view: OrderView;
  quote: Quote;
  request: RequestCommand;
  revision_command: RevisionCommand;
  summary: CatalogRunSummary;
}
export interface AcceptQuoteCommand {
  customer_actor: string;
  idempotency_key: string;
  quote_id: string;
}
export interface ClarifyCommand {
  expected_revision: number;
  idempotency_key: string;
  question_id: string;
  text: string;
}
export interface RequestDraft {
  answers?: ClarificationAnswer[];
  compiler_calls?: number;
  corpus_id: string;
  created_at: string;
  deadline: string;
  error?: string | null;
  order_id?: string | null;
  prompt: string;
  question?: Clarification | null;
  questions_asked?: number;
  request_id: string;
  revision?: number;
  specification?: Specification | null;
  status?: "compiling" | "clarification" | "ready" | "accepted" | "human_review";
}
export interface ClarificationAnswer {
  question_id: string;
  text: string;
}
export interface Clarification {
  field: string;
  prompt: string;
  question_id: string;
}
export interface Specification {
  limitations: string[];
  requirements: Requirement[];
  revision: number;
  summary: string;
  terms: Terms;
}
export interface Requirement {
  check: "category" | "weight" | "price" | "fields" | "completeness" | "provenance" | "pdf";
  requirement_id: string;
  wording: string;
}
export interface Terms {
  category?: "storage";
  completeness?: "all_qualifying_records";
  corpus_id: string;
  currency?: "USD";
  price_basis?: "unit";
  price_operator: "lt" | "lte";
  price_threshold: number | string;
  required_fields?: ("product_id" | "name" | "supplier" | "weight" | "unit_price" | "citation")[];
  source_policy?: SourcePolicy;
  unknown_values?: "explicit_unresolved_and_block_if_material";
  weight_concept: "net_unit" | "shipping";
  weight_operator: "lt" | "lte";
  weight_threshold: number | string;
  weight_unit?: "kg" | "g";
}
export interface SourcePolicy {
  accepted_authority?: ("registered_supplier_publication" | "authorized_representative")[];
  evidence_repair?: "preauthorized" | "customer_and_provider";
  precedence?: "frozen_edition_only";
  substantive_change?: "customer_and_provider";
}
export interface CatalogEvent {
  accepted_snapshot_sha256: string;
  actor: string;
  aggregate_revision: number;
  binding: Binding;
  correlation_id?: string | null;
  event_id: string;
  mode?: "live_backend";
  occurred_at: string;
  operation: string;
  order: CatalogOrder;
  payment?: PaymentView | null;
  procedure_version?: string;
  run_id: string;
  seq: number;
  type?: "catalog.committed";
}
export interface Binding {
  delivery_version: number;
  evidence_revision: number;
  snapshot_id: string;
}
export interface CatalogOrder {
  amendments?: Amendment[];
  approvals?: Approval[];
  artifacts: Artifact[];
  authority_state?: "clear" | "pending_source_authority" | "pending_consent" | "rejected" | "human_review";
  authorization: Authorization;
  binding: Binding;
  cases?: Case[];
  children?: string[];
  customer_acceptance?: Binding | null;
  decisions?: ReviewerDecision[];
  deliveries?: Delivery[];
  delivery_state?: "absent" | "verified" | "needs_review" | "operational_failure";
  error?: string | null;
  evidence_requests?: EvidenceRequest[];
  free_corrections_used?: number;
  jobs?: Job[];
  ledger?: Booking[];
  order_state?:
    | "awaiting_authorization"
    | "processing"
    | "waiting_evidence"
    | "pending_approval"
    | "delivered"
    | "human_review"
    | "operational_failure"
    | "closed";
  payment_id?: string | null;
  repair_deadline?: string | null;
  revision?: number;
  schema_version?: 3 | 4;
  semantic_findings?: Assessment[];
  snapshot: Snapshot;
  sources: Source[];
  verification?: Verification | null;
  verification_history?: Verification[];
}
export interface Amendment {
  actor: string;
  amendment_id: string;
  applied_revision?: number | null;
  artifact: Artifact;
  assessment?: Assessment[];
  classification?: "pending" | "evidence_only" | "substantive" | "unresolved";
  evidence_request_id: string;
  history?: string[];
  reason: string;
  relationship: "replacement_page" | "supplement";
  submitted_at: string;
  target_source_id: string;
  target_version: number;
}
export interface Artifact {
  artifact_id: string;
  media_type: "application/pdf" | "application/json";
  sha256: string;
  storage_key: string;
  version?: number;
}
export interface Assessment {
  citations?: Span[];
  conflicting_evidence?: Span[];
  explanation: string;
  missing_facts?: string[];
  obligation_id: string;
  provenance: Provenance;
  reason_code: string;
  requested_evidence?: string | null;
  result: "PASS" | "FAIL" | "UNKNOWN" | "CONFLICT";
}
export interface Span {
  artifact_id: string;
  end: number;
  highlight: PdfHighlight;
  page: number;
  quote: string;
  sha256: string;
  start: number;
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
export interface Provenance {
  assessor: string;
  kind: "deterministic" | "model";
  model_score?: number | null;
  version: string;
}
export interface Approval {
  amendment_id: string;
  approval_id: string;
  binding: Binding;
  customer_actor?: string | null;
  provider_actor?: string | null;
  reason: string;
  status?: "pending" | "approved" | "rejected" | "invalidated";
}
export interface Authorization {
  amount: Money;
  authorization_id: string;
  expires_at: string;
  receipt?: PaymentReceipt | null;
  status: "pending" | "mock_authorized" | "authorized" | "uncertain" | "expired" | "released";
}
/**
 * Integer minor units; asset identity/chain mapping awaits the payment spike.
 */
export interface Money {
  amount_minor: number;
  currency: string;
  decimals: number;
}
export interface PaymentReceipt {
  idempotency_key: string;
  mode: "mock" | "live";
  operation: "authorize" | "capture" | "release" | "additional_processing";
  operation_id: string;
  status: "mock" | "submitted" | "uncertain" | "confirmed" | "failed";
  transaction_id?: string | null;
}
export interface Case {
  answers?: string[];
  case_id: string;
  complaint: Complaint;
  deadline: string;
  opened_at: string;
  question?: string | null;
  questions_asked?: number;
  status?: "open" | "supported" | "unsupported" | "scope_change" | "human_review";
}
export interface Complaint {
  artifact_id: string;
  field: "weight" | "unit_price" | "completeness" | "provenance" | "pdf";
  intent?: "dispute_fact" | "change_scope";
  product_id: string;
  requirement_id: string;
  text: string;
}
export interface ReviewerDecision {
  action: "request_evidence" | "release_authorization" | "propose_exception";
  actor: string;
  binding: Binding;
  negotiated_exception?: boolean;
  reason: string;
  recorded_at: string;
  supporting_evidence: Span[];
}
export interface Delivery {
  binding: Binding;
  pdf: Artifact;
  published_at: string;
  review_deadline: string;
  sidecar: Artifact;
  version: number;
}
export interface EvidenceRequest {
  answered?: boolean;
  deadline: string;
  obligation_ids: string[];
  prompt: string;
  request_id: string;
  round: number;
  target_source: Source;
}
export interface Source {
  artifact: Artifact;
  authority: "registered_supplier_publication" | "authorized_representative" | "unverified";
  authority_record?: string | null;
  corpus_id: string;
  edition: string;
  effective_date: string;
  source_id: string;
  supplier_id: string;
  version: number;
}
export interface Job {
  attempts?: number;
  binding: Binding;
  error?: string | null;
  job_id: string;
  kind: "fulfill" | "correct" | "reverify";
  lease_token?: string | null;
  lease_until?: string | null;
  status?: "queued" | "running" | "done" | "failed" | "stale";
}
export interface Booking {
  amount: Money;
  binding: Binding;
  kind: "capture" | "release";
  operation_id: string;
  receipt: PaymentReceipt;
  recorded_at: string;
}
export interface Snapshot {
  accepted_at: string;
  customer_actor: string;
  order_id: string;
  quote: Quote;
  schema_version?: 3 | 4;
  snapshot_id: string;
}
export interface Quote {
  amendment_id?: string | null;
  amount: Money;
  expires_at: string;
  parent_binding?: Binding | null;
  parent_order_id?: string | null;
  payment_terms?: PaymentTerms | null;
  policy?: Policy;
  provider_actor?: string;
  purpose?: "initial" | "additional_work" | "substantive_amendment";
  quote_id: string;
  request_id: string;
  request_revision: number;
  sources: Source[];
  specification: Specification;
  work_description: string;
}
export interface PaymentTerms {
  amount_atomic: string;
  asset_address: string;
  authorization_nonce: string;
  chain_id?: 84532;
  collector_address: string;
  confirmations?: number;
  decimals?: 6;
  deployment_version?: "v1.1.0";
  display_amount: Money;
  escrow_address: string;
  mode: "mock" | "base_sepolia";
  payment_hash: string;
  payment_id: string;
  payment_info: PaymentInfo;
  policy_version?: "catalog-payments-v1";
  pricing_rule: "catalog-usd-usdc-1to1-v1" | "isolated-test-usdc-0.10-v1";
  settlement_terms: string;
  source_commit?: "b748fdd7a830a655a19a530edcf2a94b9dc7d25f";
  symbol?: "USDC";
}
export interface PaymentInfo {
  authorization_expiry: string;
  fee_receiver: string;
  max_amount: string;
  max_fee_bps?: 0;
  min_fee_bps?: 0;
  operator: string;
  payer: string;
  pre_approval_expiry: string;
  receiver: string;
  refund_expiry: string;
  salt: string;
  token: string;
}
export interface Policy {
  authorization_seconds?: 3600;
  clarification_rounds?: 3;
  clarification_seconds?: 300;
  dispute_seconds?: 60;
  evidence_attempts?: 2;
  evidence_repair_seconds?: 120;
  free_corrections?: 1;
  max_questions?: 2;
  review_seconds?: 60;
  version?: "catalog-v0.3";
}
export interface Verification {
  assessments: Assessment[];
  binding: Binding;
  created_at: string;
  material_blockers: string[];
  obligations: Obligation[];
  passed: boolean;
  provider_defect: boolean;
  stage: "fulfillment" | "delivery" | "dispute";
}
export interface Obligation {
  check: string;
  decision_effect?: "compliance" | "remedy" | "settlement" | "none";
  dependencies?: string[];
  field: string;
  mandatory?: boolean;
  obligation_id: string;
  requirement_id: string;
  subject: string;
}
export interface PaymentView {
  explorer_links?: string[];
  finality_note?: "Receipt confirmation threshold is not Ethereum/L1 finality.";
  operations: PaymentOperation[];
  payment: PaymentAccount;
  simulated: boolean;
}
export interface PaymentOperation {
  attempts?: number;
  block_evidence?: BlockEvidence | null;
  created_at: string;
  error?: string | null;
  fingerprint: string;
  intent: CatalogPaymentIntent;
  nonce?: string | null;
  observation?: EscrowObservation | null;
  operation_id: string;
  reconciliation_status?: "not_submitted" | "pending" | "confirmed" | "failed" | "uncertain" | "orphaned";
  state?: "reserved" | "signed" | "submitted" | "uncertain" | "confirmed" | "failed" | "invalidated" | "orphaned";
  transaction_hash?: string | null;
  updated_at: string;
}
export interface BlockEvidence {
  amount_atomic: string;
  block_hash: string;
  block_number: string;
  canonical: boolean;
  confirmations: number;
  event: "PaymentAuthorized" | "PaymentCaptured" | "PaymentVoided" | "PaymentReclaimed";
  observed_head: string;
  payment_hash: string;
  transaction_hash: string;
}
export interface CatalogPaymentIntent {
  action: "fund" | "capture" | "void" | "reclaim";
  amount_atomic: string;
  binding: PaymentBinding;
  chain_id?: 84532;
  idempotency_key: string;
  mode: "mock" | "base_sepolia";
  operation_id: string;
  order_id: string;
  payment_hash: string;
  payment_id: string;
  reason: string;
  snapshot_id: string;
}
export interface PaymentBinding {
  delivery_version: number;
  evidence_revision: number;
  snapshot_id: string;
}
export interface EscrowObservation {
  block_hash: string;
  block_number: string;
  buyer_balance?: string | null;
  capturable_amount: string;
  has_collected_payment: boolean;
  payment_hash: string;
  provider_balance?: string | null;
  refundable_amount: string;
  token_store?: string | null;
  token_store_balance?: string | null;
}
export interface PaymentAccount {
  blocked_by_payment_id?: string | null;
  created_at: string;
  last_error?: string | null;
  latest_observation?: EscrowObservation | null;
  order_id: string;
  payment_id: string;
  snapshot_id: string;
  state:
    | "blocked_parent"
    | "awaiting_signature"
    | "funding_pending"
    | "funded"
    | "capture_pending"
    | "captured"
    | "void_pending"
    | "voided"
    | "uncertain"
    | "failed"
    | "expired_not_returned"
    | "reorg_hold";
  terms: PaymentTerms;
  updated_at: string;
}
export interface CatalogEvents {
  events: CatalogEvent[];
  next_cursor: number;
  poll_after_ms?: 2000;
  run_id: string;
  server_time: string;
}
export interface FundingAuthorization {
  expected_binding: PaymentBinding;
  expected_revision: number;
  funding_attempt_id: string;
  idempotency_key: string;
  payment_hash: string;
  signature?: string | null;
  simulate?: boolean;
}
export interface FundingPreparation {
  binding: PaymentBinding;
  expires_at: string;
  funding_attempt_id: string;
  order_id: string;
  payment_id: string;
  prepared_at: string;
  terms: PaymentTerms;
  typed_data: AuthorizationTypedData;
}
export interface AuthorizationTypedData {
  domain: AuthorizationDomain;
  message: AuthorizationMessage;
  primaryType: "ReceiveWithAuthorization";
  types: AuthorizationTypes;
}
export interface AuthorizationDomain {
  chainId?: 84532;
  name: string;
  verifyingContract: string;
  version?: "2";
}
export interface AuthorizationMessage {
  from: string;
  nonce: string;
  to: string;
  validAfter: string;
  validBefore: string;
  value: string;
}
export interface AuthorizationTypes {
  EIP712Domain: TypedDataField[];
  ReceiveWithAuthorization: TypedDataField[];
}
export interface TypedDataField {
  name: string;
  type: string;
}
export interface OrderCommand {
  expected_binding: Binding;
  expected_revision: number;
  idempotency_key: string;
}
export interface OrderView {
  available_actions: (
    | "accept"
    | "dispute"
    | "answer"
    | "upload_evidence"
    | "approve_amendment"
    | "prepare_funding"
    | "submit_funding_authorization"
  )[];
  human_review: ReviewRow[];
  order: CatalogOrder;
  payment?: PaymentView | null;
  payment_mode?: "mock" | "base_sepolia";
  poll_after_ms?: 2000;
  server_time: string;
}
export interface ReviewRow {
  accepted_wording: string;
  amendment_status: string;
  delivered_citations: Span[];
  delivered_value: string | null;
  field: string;
  financial_effect: string;
  issue: string;
  missing_fact_or_contradiction: string;
  product: string;
  recommended_remedy: string;
  required_authority: string;
  requirement_id: string;
  result: "PASS" | "FAIL" | "UNKNOWN" | "CONFLICT";
  source_citations: Span[];
  source_fact: string;
}
export interface RequestCommand {
  corpus_id: string;
  idempotency_key: string;
  prompt: string;
}
export interface RevisionCommand {
  expected_revision: number;
  idempotency_key: string;
}
export interface CatalogRunSummary {
  last_seq: number;
  revision: number;
  run_id: string;
  state: string;
}
