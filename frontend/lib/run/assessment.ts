import type {Binding, RunEvent} from "./contract";

/** A prior decision must not label a new investigation or changed evidence. */
export function currentAssessment(events:RunEvent[], binding?:Binding | null) {
  const event=events.findLast(event=>event.type==="verdict");
  if(!event || event.type!=="verdict")return undefined;
  if(events.some(next=>next.seq>event.seq && (next.type==="dispute_opened" || next.type==="delivery_ready" || next.type==="step_started" && next.step==="investigate")))return undefined;
  const finding=event.verdict.finding;
  if(finding) {
    if(finding.validation==="STALE" || finding.validation==="INVALID")return undefined;
    const assessed=finding.assessed_binding;
    if(!binding || assessed.snapshot_id!==binding.snapshotId || assessed.delivery_version!==binding.deliveryVersion || assessed.evidence_revision!==binding.evidenceVersion)return undefined;
  }
  return event;
}
