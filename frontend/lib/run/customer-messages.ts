import type {RunEvent} from "./contract";

// Findings have their own structured result card. Their persisted audit narration
// includes model/provenance metadata and must not become a customer chat message.
export function isAssessmentAudit(event:RunEvent) {
  return event.type==="message" && event.step==="verdict" && event.message.from==="agent";
}
