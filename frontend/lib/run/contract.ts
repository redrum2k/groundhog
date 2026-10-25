// Wire types are generated from Pydantic. This module preserves Lucas's useful aliases.
import type * as Wire from "../runs.generated";
/** What the agent reads at the source while it investigates: one line per check, ticked when the check is done. */
export interface SourceLine { id: string; text: string; checked: boolean }
/** Plus two canvas-only events the narration adds; never on the wire: a caption and the source checks. */
export type RunEvent = Wire.RunContractExport["event"]
  | { seq: number; at: string; track: Track; type: "caption"; text: string }
  | { seq: number; at: string; track: Track; type: "source_checked"; step: string; lines: SourceLine[] };
export type RunEventType = RunEvent["type"];
export type Track = NonNullable<Wire.RunContractExport["event"]["track"]>;
export type LaneId = Exclude<Track, "shared">;
export type ControllerAction = Wire.RunDecision["action"];
export type StepKind = Wire.Step["kind"];
export type VerdictKind = Wire.Verdict["kind"];
export type Evidence = Wire.EvidenceFound["evidence"];
export type Source = Evidence["source"];
export type Attachment = NonNullable<Wire.Message["attach"]>[number];
export type Money = number; // Display dollars only; settlement uses generated decimal-string quantities.
export type { ContractLine, DataContract, ZipCount, Dispute, Verdict, RuleUpdate, JournalEntry, Margin, Message, Step } from "../runs.generated";
export type { CanvasBinding as Binding, CanvasPayment as Payment, CanvasDelivery as Delivery, CanvasAmendment as Amendment } from "../runs.generated";
