// Wire types are generated from Pydantic. This module preserves Lucas's useful aliases.
import type * as Wire from "../runs.generated";
export type RunEvent = Wire.RunContractExport["event"];
export type RunEventType = RunEvent["type"];
export type Track = NonNullable<RunEvent["track"]>;
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
