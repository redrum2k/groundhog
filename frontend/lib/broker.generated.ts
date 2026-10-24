/* Generated from backend/app/contracts/broker.py. Do not edit. Run npm run generate. */

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

export interface BrokerContractExport {
  command: BrokerCommand;
  draft: IntakeDraft;
  draft_create: DraftCreate;
  order: BrokerRecord;
  source_upload: SourceUpload;
}
export interface BrokerCommand {
  amendment_id?: string | null;
  authorization_expires_at?: string | null;
  capability?: ("SUPPORTED" | "UNSUPPORTED") | null;
  decision?: ("RESUME" | "RETAIN_HOLD") | null;
  digest?: string | null;
  effective_at?: string | null;
  expected_revision: number;
  field?: string | null;
  idempotency_key: string;
  price?: Money | null;
  question_id?: string | null;
  specification?: DataSpecification | null;
  task_id?: string | null;
  text?: string | null;
  value?: string | number | string[] | null;
  verb:
    | "clarify_intake"
    | "answer_intake"
    | "offer"
    | "accept_specification"
    | "decline"
    | "produce"
    | "accept_delivery"
    | "dispute"
    | "investigate"
    | "answer"
    | "resolve_human"
    | "propose_amendment"
    | "accept_amendment";
}
/**
 * Integer minor units; asset identity/chain mapping awaits the payment spike.
 */
export interface Money {
  amount_minor: number;
  currency: string;
  decimals: number;
}
export interface DataSpecification {
  original_intent: string;
  product_id?: string;
  /**
   * @minItems 1
   * @maxItems 32
   */
  requirements: [Requirement, ...Requirement[]];
  /**
   * @minItems 1
   * @maxItems 16
   */
  sources:
    | [SourcePin]
    | [SourcePin, SourcePin]
    | [SourcePin, SourcePin, SourcePin]
    | [SourcePin, SourcePin, SourcePin, SourcePin]
    | [SourcePin, SourcePin, SourcePin, SourcePin, SourcePin]
    | [SourcePin, SourcePin, SourcePin, SourcePin, SourcePin, SourcePin]
    | [SourcePin, SourcePin, SourcePin, SourcePin, SourcePin, SourcePin, SourcePin]
    | [SourcePin, SourcePin, SourcePin, SourcePin, SourcePin, SourcePin, SourcePin, SourcePin]
    | [SourcePin, SourcePin, SourcePin, SourcePin, SourcePin, SourcePin, SourcePin, SourcePin, SourcePin]
    | [SourcePin, SourcePin, SourcePin, SourcePin, SourcePin, SourcePin, SourcePin, SourcePin, SourcePin, SourcePin]
    | [
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin
      ]
    | [
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin
      ]
    | [
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin
      ]
    | [
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin
      ]
    | [
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin
      ]
    | [
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin,
        SourcePin
      ];
  template_version?: string;
  version?: number;
}
export interface Requirement {
  conflict_policy?: "UNKNOWN";
  dimension:
    | "freshness"
    | "geography"
    | "reference_period"
    | "metric"
    | "entity_unit"
    | "coverage"
    | "source_lineage"
    | "output_schema"
    | "unsupported";
  id: string;
  meaning: string;
  missing_policy?: "UNKNOWN";
  parameters: Parameters;
  provenance?: TermProvenance[];
  recipe:
    | "age_within_days"
    | "region_version"
    | "period_equals"
    | "metric_equals"
    | "unique_entity"
    | "coverage_ids"
    | "exact_sources"
    | "market_schema_v1"
    | "unsupported";
}
export interface Parameters {
  as_of?: string | null;
  boundary_version?: string | null;
  conflict_policy?: "UNKNOWN" | null;
  /**
   * @maxItems 1000
   */
  coverage_ids?: string[];
  entity_unit?: ("establishment" | "legal_entity" | "household" | "person" | "region") | null;
  freshness_basis?: ("observed_at" | "published_at" | "exported_at") | null;
  geography?: string | null;
  max_age_days?: number | null;
  max_missing_records?: number | null;
  metric_name?: string | null;
  metric_unit?: string | null;
  output_format?: ("json" | "csv") | null;
  output_schema?: "market-v1" | null;
  reference_period?: string | null;
  /**
   * @maxItems 250
   */
  region_ids?: string[];
  revision_policy?: "exact_accepted_versions" | null;
}
export interface TermProvenance {
  actor_id: string;
  origin: "original_intent" | "customer_answer" | "provider_confirmation" | "accepted_source" | "approved_template";
  reference_id: string;
}
export interface SourcePin {
  sha256: string;
  source_id: string;
  version: number;
}
export interface IntakeDraft {
  acceptance_digest?: string | null;
  created_at: string;
  customer_accepted_digest?: string | null;
  customer_id: string;
  human_tasks?: HumanTask[];
  id: string;
  messages: IntentMessage[];
  offered_price?: Money | null;
  order_id?: string | null;
  parameters?: Parameters;
  parent_order_id?: string | null;
  product_id?: string;
  provider_accepted_digest?: string | null;
  provider_actor_id?: string | null;
  provider_capability?: "UNREVIEWED" | "SUPPORTED" | "UNSUPPORTED";
  provider_reason?: string | null;
  questions?: DraftQuestion[];
  revision?: number;
  sources?: SourcePin[];
  specification?: DataSpecification | null;
  status?: "DRAFT" | "CLARIFYING" | "READY" | "ACCEPTED" | "UNSUPPORTED" | "DECLINED";
  template_approved_by?: string | null;
  template_version?: string;
  unresolved_fields?: string[];
  validator_bindings?: {
    [k: string]: string;
  };
}
export interface HumanTask {
  binding: ProposalBinding | null;
  created_at: string;
  decided_by?: string | null;
  decision?: string | null;
  evidence: SourcePin[];
  id: string;
  issue_id: string;
  missing_facts: string[];
  next_action?: string;
  owner?: "controller";
  reason: string;
  resolved_at?: string | null;
  state?: "OPEN" | "RESOLVED";
}
export interface ProposalBinding {
  delivery_version: number;
  evidence_version: number;
  order_id: string;
  proposal_version: number;
  snapshot_id: string;
}
export interface IntentMessage {
  actor_id: string;
  created_at: string;
  field?: string | null;
  id: string;
  text: string;
}
export interface DraftQuestion {
  answer_id?: string | null;
  field: string;
  id: string;
  prompt: string;
}
export interface DraftCreate {
  idempotency_key: string;
  intent: string;
  parent_order_id?: string | null;
  product_id?: string;
}
export interface BrokerRecord {
  amendments?: BrokerAmendment[];
  base_order?: OrderView | null;
  colour?: "green" | "red" | "orange";
  customer_id: string;
  delivery_artifact_ids?: string[];
  draft_id: string;
  human_tasks?: HumanTask[];
  id: string;
  issue_id?: string | null;
  messages?: IntentMessage[];
  next_action?: string;
  original_specification: DataSpecification;
  overall_case_deadline: string;
  owner?: string;
  parent_order_id?: string | null;
  question_count?: number;
  questions?: BrokerQuestion[];
  resolution?: ("NO_REMEDY" | "CORRECTED" | "HUMAN_REVIEW") | null;
  revision?: number;
  source_artifact_ids: string[];
}
export interface BrokerAmendment {
  customer_accepted_by?: string | null;
  digest: string;
  effective_at: string;
  id: string;
  provider_accepted_by?: string | null;
  specification: DataSpecification;
}
export interface OrderView {
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
  data_amendments?: AcceptedDataAmendment[];
  data_verification?: DataVerification | null;
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
  review_requires_customer_acceptance?: boolean;
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
export interface AcceptedDataAmendment {
  accepted_by_customer: string;
  accepted_by_provider: string;
  amendment_id: string;
  effective_at: string;
  specification: DataSpecification;
}
export interface DataVerification {
  /**
   * @minItems 1
   */
  checks: [RequirementAssessment, ...RequirementAssessment[]];
  evidence_sha256: string;
  proposal: ProposalBinding;
  specification_sha256: string;
  verdict?: ("PASS" | "FAIL" | "UNKNOWN") | null;
  verified_at: string;
}
export interface RequirementAssessment {
  cause:
    | "NONE"
    | "MISSING_SPECIFICATION"
    | "MISSING_EVIDENCE"
    | "CONFLICTING_AUTHORITY"
    | "VALIDATOR_FAILURE"
    | "PROVIDER_DEFECT"
    | "SCOPE_CHANGE"
    | "UNSUPPORTED_SUBJECTIVE";
  citations?: DataCitation[];
  explanation: string;
  requirement_id: string;
  verdict: "PASS" | "FAIL" | "UNKNOWN";
}
export interface DataCitation {
  artifact_id?: string | null;
  locator: string;
  sha256: string;
  source_id: string;
  value: string;
  version: number;
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
  data_specification?: DataSpecification | null;
  /**
   * @minItems 1
   */
  input_versions: [EvidenceReference, ...EvidenceReference[]];
  job_type?: "invoice_register" | "regional_market_intelligence";
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
  overall_case_seconds?: 1800 | null;
  policy_version: string;
  review_window_seconds?: 600;
}
export interface BrokerQuestion {
  answer_id?: string | null;
  binding: ProposalBinding;
  id: string;
  issue_id: string;
  recipient: "customer" | "provider" | "controller";
  requirement_id: string;
  specification_sha256: string;
  status?: "OPEN" | "ANSWERED" | "CANCELLED";
  text: string;
}
export interface SourceUpload {
  content_base64: string;
  expected_revision: number;
  filename: string;
  idempotency_key: string;
}
