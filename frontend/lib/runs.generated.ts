/* Generated from backend/app/contracts/runs.py. Do not edit. Run npm run generate. */

export interface RunContractExport {
  acknowledgement: DecisionAcknowledgement;
  answer: RunEvidenceAnswer;
  create: RunCreate;
  created: RunCreated;
  decision: RunDecision;
  event:
    | StepsPlanned
    | StepStarted
    | StepWaiting
    | MessageEvent
    | ContractLineEvent
    | ContractApproved
    | DeliveryReady
    | CheckPassed
    | CheckFailed
    | CheckFixed
    | EvidenceFound
    | DisputeOpened
    | VerdictEvent
    | ControllerDecided
    | AmendmentSigned
    | RuleUpdated
    | BooksPosted
    | PaymentAuthorized
    | PaymentCaptured
    | StateChanged;
  funding_authorization: FundingAuthorization;
  funding_preparation: FundingPreparation;
  offer: RunOffer;
  page: RunPage;
  resolution: ResolvedCell | ResolvedMessage;
}
export interface DecisionAcknowledgement {
  decision_id: string;
  ok?: true;
}
export interface RunEvidenceAnswer {
  binding: DecisionBinding;
  references?: DatasetReference[];
  text: string;
}
export interface DecisionBinding {
  deliveryVersion: number;
  evidenceVersion: number;
  orderId: string;
  revision: number;
  runId: string;
  snapshotId: string;
}
export interface DatasetReference {
  artifact_id: string;
  column: string;
  coverage_sha256?: string | null;
  expected_key?: string | null;
  kind?: "dataset";
  row: string;
  sha256: string;
  source_id: string;
  value: string | null;
  version: number;
}
export interface RunCreate {
  corpus_id?: "sf-aggregate-v1";
  prompt?: string;
}
export interface RunCreated {
  id: string;
  poll_after_ms?: 1000;
}
export interface RunDecision {
  action: "approve" | "reject" | "ask" | "escalate";
  binding: DecisionBinding;
  evidence_ids?: string[];
  reason?: string;
}
export interface StepsPlanned {
  at: string;
  seq: number;
  steps: Step[];
  track?: "shared" | "red" | "green" | "amber";
  type: "steps_planned";
}
export interface Step {
  detail: string;
  id: string;
  kind:
    "clarify" | "paid" | "produce" | "review" | "captured" | "investigate" | "verdict" | "amend" | "grey" | "decide";
  panel?: boolean;
  title: string;
}
export interface StepStarted {
  at: string;
  attempt?: number;
  seq: number;
  step: string;
  track?: "shared" | "red" | "green" | "amber";
  type: "step_started" | "step_completed";
}
export interface StepWaiting {
  at: string;
  attempt?: number;
  seq: number;
  step: string;
  track?: "shared" | "red" | "green" | "amber";
  type: "step_waiting";
  waitingOn: string;
}
export interface MessageEvent {
  at: string;
  attempt?: number;
  message: Message;
  seq: number;
  step: string;
  track?: "shared" | "red" | "green" | "amber";
  type: "message";
}
export interface Message {
  asks?: string | null;
  attach?: (ChecklistAttachment | EvidenceAttachment)[];
  from: "buyer" | "agent" | "controller";
  id: string;
  text: string;
}
export interface ChecklistAttachment {
  kind?: "checklist";
}
export interface EvidenceAttachment {
  evidenceId: string;
  kind?: "evidence";
}
export interface ContractLineEvent {
  at: string;
  attempt?: number;
  line: ContractLine;
  seq: number;
  step: string;
  track?: "shared" | "red" | "green" | "amber";
  type: "contract_line_drafted" | "contract_line_approved";
}
export interface ContractLine {
  check: "schema" | "code";
  id: string;
  text: string;
}
export interface ContractApproved {
  allowedBy: string;
  at: string;
  attempt?: number;
  contract: DataContract;
  seq: number;
  step: string;
  track?: "shared" | "red" | "green" | "amber";
  type: "contract_approved";
}
export interface DataContract {
  buyer: string;
  lines: ContractLine[];
  price: number;
  title: string;
  version: number;
}
export interface DeliveryReady {
  at: string;
  attempt?: number;
  delivery: CanvasDelivery;
  seq: number;
  step: string;
  track?: "shared" | "red" | "green" | "amber";
  type: "delivery_ready";
}
export interface CanvasDelivery {
  artifactId?: string | null;
  file: string;
  previewArtifactId?: string | null;
  reviewClosesAt?: string | null;
  rows: ZipCount[];
  sha256?: string | null;
  version: number;
}
export interface ZipCount {
  area: string;
  count: number | null;
  flag?: ("withheld" | "missing" | "added" | "yoga") | null;
  status?: ("released" | "suppressed" | "unknown") | null;
  zip: string;
}
export interface CheckPassed {
  at: string;
  attempt?: number;
  detail?: string | null;
  lineId: string;
  seq: number;
  step: string;
  track?: "shared" | "red" | "green" | "amber";
  type: "check_passed";
}
export interface CheckFailed {
  assessment?: "FAIL" | "UNKNOWN" | "CONFLICT";
  at: string;
  attempt?: number;
  lineId: string;
  reason: string;
  seq: number;
  step: string;
  track?: "shared" | "red" | "green" | "amber";
  type: "check_failed";
}
export interface CheckFixed {
  at: string;
  attempt?: number;
  fix: string;
  lineId: string;
  seq: number;
  step: string;
  track?: "shared" | "red" | "green" | "amber";
  type: "check_fixed";
}
export interface EvidenceFound {
  at: string;
  attempt?: number;
  evidence: InterviewEvidence | CellEvidence | CategoryEvidence;
  seq: number;
  step: string;
  track?: "shared" | "red" | "green" | "amber";
  type: "evidence_found";
}
export interface InterviewEvidence {
  id: string;
  kind: "interview_quote" | "claim";
  label: string;
  note: string;
  quote: string;
  source: MessageSource | CellSource | NoSource;
  speaker: string;
}
export interface MessageSource {
  kind?: "message";
  messageId: string;
}
export interface CellSource {
  column: string;
  kind?: "cell";
  reference?: DatasetReference | null;
  row: string;
  version: number;
}
export interface NoSource {
  kind?: "none";
  reason: string;
}
export interface CellEvidence {
  column: string;
  file: string;
  id: string;
  kind?: "sheet_cell";
  label: string;
  note: string;
  row: string;
  source: MessageSource | CellSource | NoSource;
  value: string | null;
}
export interface CategoryEvidence {
  category: string;
  id: string;
  item: string;
  kind?: "vendor_category";
  label: string;
  note: string;
  source: MessageSource | CellSource | NoSource;
  vendor: string;
}
export interface DisputeOpened {
  at: string;
  attempt?: number;
  dispute: Dispute;
  seq: number;
  step: string;
  track?: "shared" | "red" | "green" | "amber";
  type: "dispute_opened";
}
export interface Dispute {
  claim: string;
  id: string;
  raisedBy: string;
}
export interface VerdictEvent {
  allowedBy: string;
  at: string;
  attempt?: number;
  seq: number;
  step: string;
  track?: "shared" | "red" | "green" | "amber";
  type: "verdict";
  verdict: Verdict;
}
export interface Verdict {
  decidedBy: "rules" | "controller" | "contract";
  evidenceIds: string[];
  kind: "agree" | "disagree" | "grey";
  reason: string;
}
export interface ControllerDecided {
  action: "approve" | "reject" | "ask" | "escalate";
  at: string;
  attempt?: number;
  binding: CanvasBinding;
  by: string;
  note: string;
  seq: number;
  step: string;
  track?: "shared" | "red" | "green" | "amber";
  type: "controller_decided";
}
export interface CanvasBinding {
  deliveryVersion: number;
  evidenceVersion: number;
  orderId?: string | null;
  revision?: number | null;
  runId?: string | null;
  snapshotId?: string | null;
}
export interface AmendmentSigned {
  allowedBy: string;
  amendment: CanvasAmendment;
  at: string;
  attempt?: number;
  seq: number;
  step: string;
  track?: "shared" | "red" | "green" | "amber";
  type: "amendment_signed";
}
export interface CanvasAmendment {
  id: string;
  line: ContractLine;
  price: number;
  summary: string;
}
export interface RuleUpdated {
  at: string;
  attempt?: number;
  rule: RuleUpdate;
  seq: number;
  step: string;
  track?: "shared" | "red" | "green" | "amber";
  type: "rule_updated";
}
export interface RuleUpdate {
  activationId?: string | null;
  decidedBy: string;
  id: string;
  illustration?: boolean;
  label: string;
  scope?: string | null;
  text: string;
  version?: string | null;
}
export interface BooksPosted {
  at: string;
  attempt?: number;
  entries: JournalEntry[];
  margin?: Margin | null;
  note?: string | null;
  operationIds?: string[];
  seq: number;
  step: string;
  track?: "shared" | "red" | "green" | "amber";
  type: "books_posted";
}
export interface JournalEntry {
  amount: number;
  credit: string;
  debit: string;
  id: string;
  memo: string;
}
export interface Margin {
  cost: number | null;
  revenue: number;
}
export interface PaymentAuthorized {
  allowedBy: string;
  at: string;
  payment: CanvasPayment;
  seq: number;
  track?: "shared" | "red" | "green" | "amber";
  type: "payment_authorized";
}
export interface CanvasPayment {
  amount: number;
  id: string;
  mock: boolean;
  network?: "base-sepolia";
  rail?: "commerce-payments";
}
export interface PaymentCaptured {
  allowedBy: string;
  at: string;
  captureTx: string | null;
  paymentId: string;
  seq: number;
  track?: "shared" | "red" | "green" | "amber";
  type: "payment_captured";
}
export interface StateChanged {
  at: string;
  attempt?: number;
  binding: CanvasBinding;
  paymentState?: string | null;
  reason?: string | null;
  seq: number;
  state: string;
  step: string;
  track?: "shared" | "red" | "green" | "amber";
  type: "state_changed";
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
export interface PaymentBinding {
  delivery_version: number;
  evidence_revision: number;
  snapshot_id: string;
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
/**
 * Integer minor units; asset identity/chain mapping awaits the payment spike.
 */
export interface Money {
  amount_minor: number;
  currency: string;
  decimals: number;
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
export interface RunOffer {
  binding: DecisionBinding;
  scope: "oakland" | "yoga" | "replacement";
}
export interface RunPage {
  available_actions: ActionAvailability[];
  binding: DecisionBinding | null;
  captureClosesAt: string | null;
  caught_up: boolean;
  disputeClosesAt: string | null;
  events: (
    | StepsPlanned
    | StepStarted
    | StepWaiting
    | MessageEvent
    | ContractLineEvent
    | ContractApproved
    | DeliveryReady
    | CheckPassed
    | CheckFailed
    | CheckFixed
    | EvidenceFound
    | DisputeOpened
    | VerdictEvent
    | ControllerDecided
    | AmendmentSigned
    | RuleUpdated
    | BooksPosted
    | PaymentAuthorized
    | PaymentCaptured
    | StateChanged
  )[];
  high_watermark: number;
  latestSafeSubmissionAt: string | null;
  next_after: number;
  payment: PaymentView | null;
  poll_after_ms?: 1000;
  quote: Quote | null;
  request: RequestDraft;
  reviewClosesAt: string | null;
  server_time: string;
}
export interface ActionAvailability {
  action: string;
  enabled: boolean;
  reason: string;
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
export interface Quote {
  amendment_id?: string | null;
  amount: Money;
  expires_at: string;
  parent_binding?: Binding | null;
  parent_order_id?: string | null;
  payment_terms?: PaymentTerms | null;
  policy?: Policy | BrokeragePolicy;
  provider_actor?: string;
  purpose?: "initial" | "additional_work" | "substantive_amendment";
  quote_id: string;
  request_id: string;
  request_revision: number;
  sources: Source[];
  specification: Specification;
  work_description: string;
}
export interface Binding {
  delivery_version: number;
  evidence_revision: number;
  snapshot_id: string;
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
export interface BrokeragePolicy {
  authorization_seconds?: 3600;
  clarification_rounds?: 2;
  clarification_seconds?: 300;
  correction_seconds?: 135;
  dispute_seconds?: 60;
  evidence_attempts?: 2;
  evidence_repair_seconds?: 120;
  free_corrections?: 1;
  fulfillment_seconds?: 135;
  max_questions?: 2;
  pricing_version?: "datumco-demo-pricing-v1";
  review_seconds?: 60;
  scheduling_version?: "broker-budget-v1";
  transaction_margin_seconds?: 120;
  version?: "aggregate-brokerage-v1";
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
export interface Artifact {
  artifact_id: string;
  media_type: "application/pdf" | "application/json" | "text/csv";
  sha256: string;
  storage_key: string;
  version?: number;
}
export interface Specification {
  limitations: string[];
  requirements: Requirement[];
  revision: number;
  summary: string;
  terms: Terms | DatasetSpecification;
}
export interface Requirement {
  check:
    | "category"
    | "weight"
    | "price"
    | "fields"
    | "completeness"
    | "provenance"
    | "pdf"
    | "cohort"
    | "geography"
    | "schema"
    | "coverage"
    | "suppression"
    | "artifact";
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
export interface DatasetSpecification {
  age_max?: 34;
  age_min?: 25;
  category?: "gym_or_fitness_app" | "gym_app_or_yoga";
  category_meaning?: string;
  completeness?: "every_registry_key_once";
  corpus_id?: string;
  count_unit?: "unique_adults_per_zip";
  coverage: CoverageUniverse;
  domain?: "aggregate_dataset";
  geography?: "San Francisco" | "Oakland";
  grouping?: "zip";
  groups_disjoint?: true;
  policy_version?: "aggregate-brokerage-v1";
  population?: "synthetic_adults";
  provenance?: TermProvenance[];
  required_columns?: ("zip" | "area" | "count" | "status")[];
  /**
   * @minItems 1
   * @maxItems 8
   */
  sources:
    | [SourcePin]
    | [SourcePin, SourcePin]
    | [SourcePin, SourcePin, SourcePin]
    | [SourcePin, SourcePin, SourcePin, SourcePin]
    | [SourcePin, SourcePin, SourcePin, SourcePin, SourcePin]
    | [SourcePin, SourcePin, SourcePin, SourcePin, SourcePin, SourcePin]
    | [SourcePin, SourcePin, SourcePin, SourcePin, SourcePin, SourcePin, SourcePin]
    | [SourcePin, SourcePin, SourcePin, SourcePin, SourcePin, SourcePin, SourcePin, SourcePin];
  suppressed_count?: null;
  suppression_threshold?: 50;
}
export interface CoverageUniverse {
  authority_record: string;
  boundary_notice?: string;
  /**
   * @minItems 1
   * @maxItems 100
   */
  expected_keys: [string, ...string[]];
  geography: "San Francisco" | "Oakland";
  pin: SourcePin;
}
export interface SourcePin {
  sha256: string;
  source_id: string;
  version: number;
}
export interface TermProvenance {
  actor_id: string;
  origin: "original_intent" | "customer_answer" | "provider_confirmation" | "accepted_source" | "approved_template";
  reference_id: string;
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
export interface ResolvedCell {
  kind?: "cell";
  reference: DatasetReference;
  value: string | null;
}
export interface ResolvedMessage {
  kind?: "message";
  message: Message;
}
