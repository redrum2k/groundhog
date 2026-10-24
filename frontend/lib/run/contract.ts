// DRAFT data contract between the backend and the run canvas, for Nikita + Jeff to confirm.
// The backend will own these as Pydantic models; this file is the proposal and goes away once
// the generated types land. The canvas renders only from a fold of RunEvents, so a recorded
// scenario and a live poll feed the same code.

export type Money = number; // USD, settled as USDC on Base

export type LaneId = "red" | "green" | "amber";
/** "shared" is the path every order takes once; a lane is one way a dispute can go. */
export type Track = "shared" | LaneId;

/** One line of the data contract. "Contract" is the buyer-facing name; functionally it is a
 *  checklist whose boxes tick as each delivery passes the line's automated check. */
export interface ContractLine {
  id: string;
  text: string;
  check: "schema" | "code"; // how the backend verifies it; never shown on screen
}

export interface DataContract {
  version: number; // 1 at order time; 2 after a controller ruling changes a line
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
  lines: ContractLine[]; // the full contract once the amendment applies
}

/** count null means the ZIP was withheld; note says why. */
export interface ZipCount { zip: string; count: number | null; note?: string }
export interface Delivery {
  version: number;
  file: string;
  rows: ZipCount[];
  changed?: string[]; // ZIPs added or changed since the previous delivery
  reviewClosesAt?: string; // server time; each delivery gets its own review window
}

/** Where a citation points on the canvas. */
export type Source =
  | { kind: "message"; track: Track; step: string; messageId: string }
  | { kind: "cell"; track: Track; step: string; version: number; row: string; column: string }
  | { kind: "none"; reason: string }; // the card says the source can't be shown

export type Evidence =
  | { id: string; kind: "interview_quote"; speaker: string; quote: string; note: string; source: Source }
  | { id: string; kind: "sheet_cell"; file: string; row: string; column: string; value: string | null; note: string; source: Source }
  | { id: string; kind: "vendor_category"; vendor: string; item: string; category: string; note: string; source: Source };

export interface Dispute { id: string; claim: string; raisedBy: string }

/** Is the complaint justified? agree = our fault, disagree = we were right, grey = rules can't tell. */
export type VerdictKind = "agree" | "disagree" | "grey";
export interface Verdict {
  kind: VerdictKind;
  reason: string;
  decidedBy: "rules" | "controller";
  evidenceIds: string[];
}

/** What the controller can do with an escalated dispute. */
export type ControllerAction = "approve" | "reject" | "ask" | "escalate";

export interface Payment {
  id: string;
  amount: Money;
  rail: "x402";
  network: "base-sepolia";
  mock: boolean; // a mock payment never carries a transaction and is labeled mock on screen
}

/** A controller ruling saved so the next similar dispute is decided by rules alone. */
export interface RuleUpdate { id: string; text: string; decidedBy: string }

export interface JournalEntry { id: string; memo: string; debit: string; credit: string; amount: Money }
export interface Margin { revenue: Money; cost: Money } // margin = revenue - cost

/** What a chat line carries besides its text, by reference so it never goes stale. */
export type Attachment =
  | { kind: "checklist" } // the contract lines drafted so far on this track
  | { kind: "evidence"; evidenceId: string }
  | { kind: "sheet"; version: number; rows: string[] }; // a few delivery rows, by ZIP

export interface Message {
  id: string;
  from: "buyer" | "agent" | "controller";
  name: string;
  text: string;
  attach?: Attachment[];
}

export type StepKind =
  | "request" | "interview" | "contract" | "produce" | "check" | "deliver" | "review"
  | "dispute" | "verdict" | "investigate" | "amend" | "controller" | "learned" | "books";
export interface Step { id: string; kind: StepKind; title: string; detail: string }

/** Versions a human action is bound to; the server answers 409 when they moved on. */
export interface Binding { deliveryVersion: number; evidenceVersion: number }

/** seq is the poll cursor (GET /runs/{id}/events?after=seq); at is server time. */
interface Base { seq: number; at: string; track: Track }
type StepEvent<T> = Base & { step: string } & T;
/** allowedBy is the plain-language check or policy line that let the action happen. */
type Acts = { allowedBy: string };

export type RunEvent =
  | (Base & { type: "steps_planned"; steps: Step[] }) // appends to the track; a verdict plans the rest of its lane
  | StepEvent<{ type: "step_started" }>
  | StepEvent<{ type: "step_waiting"; waitingOn: string }>
  | StepEvent<{ type: "step_completed" }>
  | StepEvent<{ type: "message"; message: Message }>
  | StepEvent<{ type: "contract_line_drafted"; line: ContractLine }>
  | StepEvent<{ type: "contract_approved"; contract: DataContract } & Acts>
  | StepEvent<{ type: "delivery_ready"; delivery: Delivery }>
  | StepEvent<{ type: "check_passed"; lineId: string }>
  | StepEvent<{ type: "check_failed"; lineId: string; reason: string }>
  | StepEvent<{ type: "check_fixed"; lineId: string; fix: string }> // the agent corrected its own output and the line passes
  | StepEvent<{ type: "evidence_found"; evidence: Evidence }>
  | StepEvent<{ type: "dispute_opened"; dispute: Dispute }>
  | StepEvent<{ type: "verdict"; verdict: Verdict } & Acts>
  | StepEvent<{ type: "controller_decided"; action: ControllerAction; by: string; note: string; binding: Binding }>
  | StepEvent<{ type: "amendment_approved"; amendment: Amendment } & Acts>
  | StepEvent<{ type: "rule_updated"; rule: RuleUpdate }>
  | StepEvent<{ type: "rule_applied"; ruleId: string; outcome: VerdictKind } & Acts> // decided by a saved rule, no person
  | StepEvent<{ type: "books_posted"; entries: JournalEntry[]; margin: Margin }>
  | (Base & { type: "payment_authorized"; payment: Payment } & Acts)
  | (Base & { type: "payment_captured"; paymentId: string; captureTx: string | null } & Acts);

export type RunEventType = RunEvent["type"];
