// DRAFT data contract between the backend and the run canvas, for Nikita + Jeff to confirm.
// The backend will own these as Pydantic models; this file is the proposal and goes away once
// the generated types land. The canvas renders only from a fold of RunEvents, so a recorded
// scenario and a live poll feed the same code.

export type Money = number; // USD, settled as USDC on Base

export type LaneId = "red" | "green" | "amber";
/** "shared" is the normal path; a lane is one way a dispute can go. */
export type Track = "shared" | LaneId;

/** One line of the data contract. "Contract" is the buyer-facing name; functionally it is a
 *  checklist whose boxes tick as each delivery passes the line's automated check. */
export interface ContractLine {
  id: string;
  text: string;
  check: "schema" | "code"; // how the backend verifies it; never shown on screen
}

export interface DataContract {
  version: number; // 1 at order time; 2 after a controller ruling adds a line
  buyer: string;
  title: string;
  price: Money;
  lines: ContractLine[];
}

/** New scope after delivery: its own price and its own payment authorization. */
export interface Amendment {
  id: string;
  summary: string;
  price: Money;
  line: ContractLine; // the line the amendment adds to the contract
}

/** A delivered row. flag says how the row differs from what the contract promised. */
export interface ZipCount { zip: string; area: string; count: number; flag?: "withheld" | "missing" | "added" | "yoga" }
export interface Delivery {
  version: number;
  file: string;
  rows: ZipCount[];
  reviewClosesAt?: string; // server time; each delivery gets its own review window
}

/** Where a citation points: an interview line, a sheet row, or a document that isn't on screen. */
export type Source =
  | { kind: "message"; messageId: string }
  | { kind: "cell"; version: number; row: string; column: string }
  | { kind: "none"; reason: string };

interface EvidenceBase { id: string; label: string; note: string; source: Source } // label is the short text of the canvas card
export type Evidence =
  | (EvidenceBase & { kind: "interview_quote"; speaker: string; quote: string })
  | (EvidenceBase & { kind: "sheet_cell"; file: string; row: string; column: string; value: string | null })
  | (EvidenceBase & { kind: "vendor_category"; vendor: string; item: string; category: string })
  | (EvidenceBase & { kind: "claim"; speaker: string; quote: string });

export interface Dispute { id: string; claim: string; raisedBy: string }

/** Is the complaint justified? agree = they're right, disagree = we're right, grey = rules can't tell. */
export type VerdictKind = "agree" | "disagree" | "grey";
export interface Verdict {
  kind: VerdictKind;
  reason: string;
  decidedBy: "rules" | "controller" | "contract"; // contract: a line added earlier settles it, no person
  evidenceIds: string[];
}

/** What the controller can do with an escalated dispute. */
export type ControllerAction = "approve" | "reject" | "ask" | "escalate";

export interface Payment {
  id: string;
  amount: Money;
  rail: "x402" | "mock";
  network: "base-sepolia";
  mock: boolean; // a mock payment never carries a transaction and is labeled mock on screen
}

/** A controller ruling saved so the next similar dispute is decided without a person. */
export interface RuleUpdate { id: string; label: string; text: string; decidedBy: string }

export interface JournalEntry { id: string; memo: string; debit: string; credit: string; amount: Money }
export interface Margin { revenue: Money; cost: Money } // margin = revenue - cost

/** What a chat line carries besides its text, by reference so it never goes stale. */
export type Attachment =
  | { kind: "checklist" } // the contract lines drafted so far
  | { kind: "evidence"; evidenceId: string }; // rendered as a citation chip

export interface Message {
  id: string;
  from: "buyer" | "agent" | "controller";
  text: string;
  asks?: string; // the contract line this question is pinning down
  attach?: Attachment[];
}

export type StepKind = "clarify" | "paid" | "produce" | "review" | "captured" | "investigate" | "verdict" | "amend" | "grey" | "decide";
/** panel: the canvas opens this step's panel when the step starts while following. */
export interface Step { id: string; kind: StepKind; title: string; detail: string; panel?: boolean }

/** Versions a human action is bound to; the server answers 409 when they moved on. */
export interface Binding { deliveryVersion: number; evidenceVersion: number }

/** seq is the poll cursor (GET /runs/{id}/events?after=seq); at is server time. */
interface Base { seq: number; at: string; track: Track }
/** A rerun or an amendment re-enters produce with attempt 2; the step id stays the same. */
type StepEvent<T> = Base & { step: string; attempt?: number } & T;
/** allowedBy is the plain-language check or policy line that let the action happen. */
type Acts = { allowedBy: string };

export type RunEvent =
  | (Base & { type: "steps_planned"; steps: Step[] })
  | StepEvent<{ type: "step_started" }>
  | StepEvent<{ type: "step_waiting"; waitingOn: string }>
  | StepEvent<{ type: "step_completed" }>
  | StepEvent<{ type: "message"; message: Message }>
  | StepEvent<{ type: "contract_line_asked"; line: ContractLine }> // the agent is pinning this line down
  | StepEvent<{ type: "contract_line_drafted"; line: ContractLine }>
  | StepEvent<{ type: "contract_approved"; contract: DataContract } & Acts>
  | StepEvent<{ type: "delivery_ready"; delivery: Delivery }>
  | StepEvent<{ type: "check_passed"; lineId: string; detail?: string }>
  | StepEvent<{ type: "check_failed"; lineId: string; reason: string }>
  | StepEvent<{ type: "check_fixed"; lineId: string; fix: string }> // the agent corrected its own output and the line passes
  | StepEvent<{ type: "evidence_found"; evidence: Evidence }>
  | StepEvent<{ type: "dispute_opened"; dispute: Dispute }>
  | StepEvent<{ type: "verdict"; verdict: Verdict } & Acts>
  | StepEvent<{ type: "controller_decided"; action: ControllerAction; by: string; note: string; binding: Binding }>
  | StepEvent<{ type: "amendment_signed"; amendment: Amendment } & Acts>
  | StepEvent<{ type: "rule_updated"; rule: RuleUpdate }>
  | StepEvent<{ type: "books_posted"; entries: JournalEntry[]; margin: Margin }>
  | (Base & { type: "caption"; text: string }) // a live translator's own words for the caption bar
  | (Base & { type: "payment_authorized"; payment: Payment } & Acts)
  | (Base & { type: "payment_captured"; paymentId: string; captureTx: string | null } & Acts);

export type RunEventType = RunEvent["type"];
