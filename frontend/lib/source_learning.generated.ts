/* Generated from backend/app/contracts/source_learning.py. Do not edit. Run npm run generate. */

export interface SourceLearningContractExport {
  command: LearningCommand;
  resolution: ResolveSource;
  result: LearningResult;
  state: LearningState;
  upload: BundleUpload;
}
export interface LearningCommand {
  idempotency_key: string;
  target_id: string;
}
export interface ResolveSource {
  applicability?: "source_edition";
  column: string;
  encounter_id: string;
  explanation: string;
  idempotency_key: string;
}
export interface LearningResult {
  detail?: string;
  record_id: string;
  status: string;
}
export interface LearningState {
  active_current?: boolean;
  active_version?: string | null;
  attempts?: AttemptView[];
  bundle_id?: string | null;
  candidates?: CandidateView[];
  disclosure?: string;
  enabled: boolean;
  events?: LearningEvent[];
  mode?: "controlled_local_mock";
  qualification?: QualificationView | null;
  reviews?: ReviewView[];
  versions?: CandidateView[];
}
export interface AttemptView {
  active_version: string | null;
  baseline_operations?: number | null;
  baseline_reviews?: number | null;
  id: string;
  internal_reviews: number;
  machine_operations: number;
  request_id: string;
  source_hashes?: string[];
}
export interface CandidateView {
  component_ids: string[];
  id: string;
  status: string;
}
export interface LearningEvent {
  actor: string;
  created_at: string;
  evidence_ids?: string[];
  id: string;
  kind: string;
  request_id?: string | null;
  text: string;
}
export interface QualificationView {
  baseline_operations: number;
  baseline_reviews: number;
  candidate_id: string;
  candidate_operations: number;
  candidate_reviews: number;
  capsule_sha256: string;
  cases: number;
  correct_both: number;
  id: string;
  passed: boolean;
  violations: string[];
}
export interface ReviewView {
  authority_sha256: string;
  columns: string[];
  encounter_id: string;
  reason: string;
  request_id: string;
  resolved: boolean;
  source_family: string;
  source_sha256: string;
}
export interface BundleUpload {
  idempotency_key: string;
  origin?: "simulated_source_owner_demo";
  /**
   * @minItems 2
   * @maxItems 4
   */
  partitions:
    | [PartitionInput, PartitionInput]
    | [PartitionInput, PartitionInput, PartitionInput]
    | [PartitionInput, PartitionInput, PartitionInput, PartitionInput];
}
export interface PartitionInput {
  authority: AuthorityHead;
  export: VendorExport;
}
export interface AuthorityHead {
  definitions?: Definition[];
  epoch: string;
  publisher: string;
  schema_hash: string;
  scope: SourceScope;
  source_id: string;
  source_version: number;
  status?: "active" | "revoked" | "conflict";
  valid_until: string;
}
export interface Definition {
  column: string;
  unit: string;
}
export interface SourceScope {
  age_max?: 34;
  age_min?: 25;
  category?: "gym_or_fitness_app" | "gym_app_or_yoga";
  geography: "San Francisco" | "Oakland";
  groups_disjoint?: true;
  population?: "synthetic_adults";
}
export interface VendorExport {
  /**
   * @minItems 1
   * @maxItems 8
   */
  columns:
    | [string]
    | [string, string]
    | [string, string, string]
    | [string, string, string, string]
    | [string, string, string, string, string]
    | [string, string, string, string, string, string]
    | [string, string, string, string, string, string, string]
    | [string, string, string, string, string, string, string, string];
  edition: string;
  publisher: string;
  /**
   * @minItems 1
   * @maxItems 100
   */
  rows: [VendorRow, ...VendorRow[]];
  schema_version: number;
  scope: SourceScope;
  source_family: string;
  source_id: string;
  version: number;
}
export interface VendorRow {
  area: string;
  status: "released" | "suppressed" | "unknown";
  values: {
    [k: string]: number | null;
  };
  zip: string;
}
