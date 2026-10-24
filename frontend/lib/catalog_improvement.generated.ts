/* Generated from backend/app/contracts/catalog_improvement.py. Do not edit. Run npm run generate. */

export interface CatalogImprovementContractExport {
  bundle: CatalogProposalBundle;
  command: CatalogImprovementCommand;
  observe_command: OrderCommand;
  proposal: CatalogPatchProposal;
  result: CatalogImprovementResult;
  view: CatalogImprovementView;
}
export interface CatalogProposalBundle {
  /**
   * @maxItems 2
   */
  candidates: [] | [CatalogPatchProposal] | [CatalogPatchProposal, CatalogPatchProposal];
  retain_base_reason?: string | null;
}
export interface CatalogPatchProposal {
  baseline_version: string;
  corpus_id: string;
  expected_mechanism: string;
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
   * @maxItems 1
   */
  operations: [CatalogAcquisitionEdit];
  rationale: string;
}
export interface CatalogAcquisitionEdit {
  op: "retrieve_registered_same_edition";
  trigger: "REQUIRED_VALUE_UNREADABLE";
}
export interface CatalogImprovementCommand {
  corpus_id: string;
  cycle?: 1 | 2;
  expected_active_version: string;
  idempotency_key: string;
  /**
   * @maxItems 8
   */
  incident_ids?:
    | []
    | [string]
    | [string, string]
    | [string, string, string]
    | [string, string, string, string]
    | [string, string, string, string, string]
    | [string, string, string, string, string, string]
    | [string, string, string, string, string, string, string]
    | [string, string, string, string, string, string, string, string];
  mode?: "ANTHROPIC" | "DETERMINISTIC_INFRASTRUCTURE";
  patch_id?: string | null;
  probe_id?: string | null;
  reason: string;
  verb: "propose" | "probe" | "approve" | "activate" | "revoke";
  version_id?: string | null;
}
export interface OrderCommand {
  expected_binding: Binding;
  expected_revision: number;
  idempotency_key: string;
}
export interface Binding {
  delivery_version: number;
  evidence_revision: number;
  snapshot_id: string;
}
export interface CatalogImprovementResult {
  job_id?: string | null;
  mode?: string | null;
  patch_ids?: string[];
  probe_id?: string | null;
  reason?: string | null;
  status: "COMPLETE" | "FAILED" | "UNKNOWN" | "NOT_QUALIFIED" | "APPROVED" | "ACTIVE" | "REVOKED";
  version_id?: string | null;
}
export interface CatalogImprovementView {
  active_version: string;
  corpus_id: string;
  local_demo_no_tenant_auth?: true;
  model_generation: "CONFIGURED" | "NOT_CONFIGURED";
  records: CatalogImprovementRecord[];
  statuses: {
    [k: string]: string;
  };
}
export interface CatalogImprovementRecord {
  corpus_id: string;
  data: {
    [k: string]: unknown;
  };
  id: string;
  kind: string;
}
