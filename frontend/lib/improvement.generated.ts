/* Generated from backend/app/contracts/improvement.py. Do not edit. Run npm run generate. */

export interface ImprovementContractExport {
  command: ImprovementCommand;
  command_result: ImprovementCommandResult;
  experience: ImprovementExperience;
  incident: GreyAreaIncident;
  incident_outcome: IncidentOutcome;
  patch: ImprovementPatch;
  probe: ProbeRun;
  version: ImprovementVersion;
}
export interface ImprovementCommand {
  customer_id: string;
  idempotency_key: string;
  incident_ids?: string[];
  mode?: "DETERMINISTIC_INFRASTRUCTURE" | "ANTHROPIC";
  patch_id?: string | null;
  product_id?: string;
  verb: "propose" | "probe" | "approve" | "activate" | "revoke";
  version_id?: string | null;
}
export interface ImprovementCommandResult {
  active_version?: string | null;
  experience_ids?: string[];
  input_tokens?: number | null;
  job_id?: string | null;
  mode?: ("DETERMINISTIC_INFRASTRUCTURE" | "ANTHROPIC" | "ANTHROPIC_TEST_DOUBLE") | null;
  model_calls?: number;
  output_tokens?: number | null;
  patch_id?: string | null;
  patch_ids?: string[];
  patch_status?: ("VALIDATED" | "REJECTED") | null;
  probe_id?: string | null;
  promotion_eligible?: boolean | null;
  proposer_model?: string | null;
  reason?: string | null;
  rejection_ids?: string[];
  status: "BLOCKED" | "COMPLETE" | "FAILED" | "UNKNOWN" | "RUNNING" | "APPROVED" | "ACTIVE" | "REVOKED";
  summary?: {
    [k: string]: ProbeSummary;
  } | null;
  usage_known?: boolean;
  version_id?: string | null;
  violations?: string[];
}
export interface ProbeSummary {
  accepted: number;
  company_staff_touches: number;
  completed: number;
  customer_answers: number;
  dollar_savings: number | null;
  incoming: number;
  measured_staff_seconds: number | null;
  model_calls: number;
  outcomes: {
    [k: string]: number;
  };
  required_review_tasks: number;
  seller_rework_attempts: number;
}
export interface ImprovementExperience {
  attempted_change: PatchEdit[];
  created_at: string;
  cue: string;
  customer_id: string;
  id: string;
  lesson: string;
  observed_contrast: string;
  patch_id: string;
  probe_ids: string[];
  product_id: string;
  rejection_reason?: string | null;
  tested_questions?: {
    [k: string]: string;
  };
}
export interface PatchEdit {
  field?:
    | (
        | "freshness_basis"
        | "max_age_days"
        | "as_of"
        | "geography"
        | "boundary_version"
        | "region_ids"
        | "reference_period"
        | "metric_name"
        | "metric_unit"
        | "entity_unit"
        | "coverage_ids"
        | "max_missing_records"
        | "revision_policy"
        | "conflict_policy"
        | "output_schema"
        | "output_format"
      )
    | null;
  op: "require_intake_field" | "replace_question" | "bind_validator";
  parameters_from?: (
    | "freshness_basis"
    | "max_age_days"
    | "as_of"
    | "geography"
    | "boundary_version"
    | "region_ids"
    | "reference_period"
    | "metric_name"
    | "metric_unit"
    | "entity_unit"
    | "coverage_ids"
    | "max_missing_records"
    | "revision_policy"
    | "conflict_policy"
    | "output_schema"
    | "output_format"
  )[];
  question?: string | null;
  recipe?:
    | (
        | "age_within_days"
        | "region_version"
        | "period_equals"
        | "metric_equals"
        | "unique_entity"
        | "coverage_ids"
        | "exact_sources"
        | "market_schema_v1"
        | "unsupported"
      )
    | null;
}
export interface GreyAreaIncident {
  binding?: ProposalBinding | null;
  cause:
    | "MISSING_SPECIFICATION"
    | "MISSING_EVIDENCE"
    | "CONFLICTING_AUTHORITY"
    | "VALIDATOR_FAILURE"
    | "SCOPE_CHANGE"
    | "UNSUPPORTED_SUBJECTIVE"
    | "REPEATED_INTERVENTION";
  company_staff_touches?: number;
  created_at: string;
  customer_id: string;
  entity_id: string;
  id: string;
  issue_id?: string | null;
  material_unknowns: string[];
  measured_staff_seconds?: number | null;
  outcome: string;
  product_id: string;
  questions?: string[];
  sources?: SourcePin[];
  specification_sha256?: string | null;
  template_version: string;
}
export interface ProposalBinding {
  delivery_version: number;
  evidence_version: number;
  order_id: string;
  proposal_version: number;
  snapshot_id: string;
}
export interface SourcePin {
  sha256: string;
  source_id: string;
  version: number;
}
export interface IncidentOutcome {
  binding?: ProposalBinding | null;
  company_staff_touches: number;
  created_at: string;
  customer_id: string;
  entity_id: string;
  id: string;
  incident_id: string;
  measured_staff_seconds?: number | null;
  outcome: "ACCEPTED_AFTER_CLARIFICATION" | "EVIDENCE_RESOLVED";
  product_id: string;
  touch_basis?: "entity_cumulative";
}
export interface ImprovementPatch {
  created_at: string;
  cycle_id: string;
  id: string;
  input_tokens?: number;
  mode: "DETERMINISTIC_INFRASTRUCTURE" | "ANTHROPIC" | "ANTHROPIC_TEST_DOUBLE";
  output_tokens?: number;
  proposal: PatchProposal;
  proposer_model?: string | null;
}
export interface PatchProposal {
  baseline_version: string;
  customer_id: string;
  expected_mechanism: string;
  experience_ids?: string[];
  /**
   * @minItems 1
   * @maxItems 8
   */
  incident_ids:
    | [string]
    | [string, string]
    | [string, string, string]
    | [string, string, string, string]
    | [string, string, string, string, string]
    | [string, string, string, string, string, string]
    | [string, string, string, string, string, string, string]
    | [string, string, string, string, string, string, string, string];
  /**
   * @minItems 1
   * @maxItems 8
   */
  operations:
    | [PatchEdit]
    | [PatchEdit, PatchEdit]
    | [PatchEdit, PatchEdit, PatchEdit]
    | [PatchEdit, PatchEdit, PatchEdit, PatchEdit]
    | [PatchEdit, PatchEdit, PatchEdit, PatchEdit, PatchEdit]
    | [PatchEdit, PatchEdit, PatchEdit, PatchEdit, PatchEdit, PatchEdit]
    | [PatchEdit, PatchEdit, PatchEdit, PatchEdit, PatchEdit, PatchEdit, PatchEdit]
    | [PatchEdit, PatchEdit, PatchEdit, PatchEdit, PatchEdit, PatchEdit, PatchEdit, PatchEdit];
  product_id: string;
  rationale: string;
}
export interface ProbeRun {
  active_staff_seconds_measured: boolean;
  approval_touch_cost: number;
  candidate_sha256: string;
  composition: string;
  customer_id: string;
  elapsed_ms: number;
  execution_interface?: "in_process_application_commands";
  id: string;
  implementation_sha256: string;
  improved: boolean;
  manifest_sha256: string;
  mode: "DETERMINISTIC_INFRASTRUCTURE";
  outcomes: ScenarioComparison[];
  patch_id: string;
  product_id: string;
  promotion_eligible: boolean;
  selection: "RETAIN_TESTED_CANDIDATE" | "RETAIN_BASE";
  summary: {
    [k: string]: ProbeSummary;
  };
  template_sha256: string;
  violations: string[];
}
export interface ScenarioComparison {
  arms: {
    [k: string]: ScenarioRun;
  };
  case_id: string;
}
export interface ScenarioRun {
  accepted: boolean;
  arm: "static" | "memory_only" | "evolving_process";
  artifact_hashes: string[];
  case_id: string;
  company_staff_touches: number;
  completed: boolean;
  customer_answers: number;
  elapsed_ms: number;
  error?: string | null;
  experience_ids: string[];
  financial_effects: number;
  input_tokens: number;
  measured_staff_seconds: number | null;
  mode: "DETERMINISTIC_INFRASTRUCTURE";
  model_calls: number;
  observed_answer_fidelity: boolean;
  order_state?: string | null;
  outcome:
    "PASS" | "FAIL" | "UNKNOWN" | "DECLINED" | "BLOCKED" | "UNSUPPORTED" | "OPERATIONAL_FAILURE" | "ERROR" | "TIMEOUT";
  output_tokens: number;
  payment_phase?: string | null;
  required_review_tasks: number;
  seller_rework_attempts: number;
  specification_sha256?: string | null;
  trace: Event[];
  trace_sha256: string;
  violations: string[];
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
export interface ImprovementVersion {
  approved_at: string;
  approved_by: string;
  customer_id: string;
  id: string;
  patch_ids: string[];
  previous_version: string;
  probe_ids: string[];
  product_id: string;
  provenance_fields?: (
    | "freshness_basis"
    | "max_age_days"
    | "as_of"
    | "geography"
    | "boundary_version"
    | "region_ids"
    | "reference_period"
    | "metric_name"
    | "metric_unit"
    | "entity_unit"
    | "coverage_ids"
    | "max_missing_records"
    | "revision_policy"
    | "conflict_policy"
    | "output_schema"
    | "output_format"
  )[];
  questions?: {
    [k: string]: string;
  };
  required_fields: (
    | "freshness_basis"
    | "max_age_days"
    | "as_of"
    | "geography"
    | "boundary_version"
    | "region_ids"
    | "reference_period"
    | "metric_name"
    | "metric_unit"
    | "entity_unit"
    | "coverage_ids"
    | "max_missing_records"
    | "revision_policy"
    | "conflict_policy"
    | "output_schema"
    | "output_format"
  )[];
  validators?: (
    | "age_within_days"
    | "region_version"
    | "period_equals"
    | "metric_equals"
    | "unique_entity"
    | "coverage_ids"
    | "exact_sources"
    | "market_schema_v1"
    | "unsupported"
  )[];
}
