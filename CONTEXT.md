# Custom data deliverables

Shared language for specifying, producing, reviewing and paying for catalog shortlist work.

## Language

**Request draft**: A customer's requested outcome and the agent's proposed requirements,
including any unresolved clarification. It is not an accepted order.

**Specification**: The typed requirements and readable wording describing the requested
selection and delivery, including thresholds and source policy.

**Requirement**: An accepted statement of what the deliverable must satisfy, with a stable identity.

**Verification obligation**: A specific evidence-backed check of a requirement for a source,
product, field or whole deliverable.

**Assessment**: A cited PASS, FAIL, UNKNOWN or CONFLICT result for one obligation, with its
provenance and any missing or contradictory facts.

**Material blocker**: An unresolved obligation whose dependencies could change compliance,
remedy or settlement eligibility.

**Grey zone**: The lifecycle outcome where material evidence remains unresolved and prevents
a justified decision. It is not a model-confidence score.

**Source manifest**: The exact set of provider-registered source editions and artifact versions
selected for an agreement.

**Source policy**: The accepted rules for source authority, precedence and later evidence or
substantive amendments.

**Quote**: A provider-issued offer binding work, specification, source manifest, price, policy
and expiry, awaiting explicit customer acceptance.

**Accepted snapshot**: The immutable agreement resulting from acceptance of a quote.

**Evidence request**: A targeted, bounded request for information needed to resolve specified
verification obligations.

**Evidence-only repair**: New evidence that restores access to the same agreed information
without changing the relevant facts or scope.

**Substantive amendment**: A proposed change to agreed facts, source edition, requirements
or scope that requires a new agreement.

**Consent**: Explicit approval by the required commercial actor. It is distinct from evidence
that a factual claim is true.

**Evidence revision**: A version of the evidence used to assess an order, independent of its
published delivery version.

**Delivery version**: One published provider output, retained together with its verification
and customer review context.

**Structured sidecar**: Internal source-derived records and citations accompanying a PDF.

**Provider defect**: An established failure of produced work to satisfy the accepted agreement.
An unresolved source fact does not by itself establish provider fault.

**Free correction**: The single additional fulfillment job authorized to remedy an established
provider defect without increasing the customer's price.

**Additional work**: Separately offered work requiring explicit acceptance and its own payment
authority; a complaint is not acceptance of additional work.

**Review window**: The customer's bounded opportunity to accept or dispute a published delivery.

**Dispute window**: The bounded investigation period following a newly opened complaint.

**Authorization expiry**: The independent end of the authority to capture an accepted amount.
It does not establish that held funds have been returned.

**Human review**: A decision stage presenting cited facts, uncertainty, remedies, financial
effects and required authority to a trusted reviewer.

**Negotiated exception**: A proposed commercial departure from the original agreement, recorded
as a negotiation rather than a changed factual finding.

**Release**: Returning uncaptured held funds through a void, or its explicitly simulated
equivalent. It is distinct from a refund of captured money.
_Avoid_: Refund, expiry

**Payment terms**: The accepted amount, asset, parties, escrow, funding conditions and deadlines
that define a customer-to-provider payment.

**Payer**: The customer wallet authorizing the payment.

**Receiver**: The provider wallet entitled to the accepted amount after capture.

**Platform operator**: The trusted platform wallet with authority to capture or void held funds
under the accepted settlement rules.

**Funding authorization**: The payer's signed permission to collect the exact accepted payment.
It is distinct from order acceptance, submission and confirmed funding.

**Confirmed funding**: Evidence that the accepted payment is held for possible capture or return.
It does not mean the provider has been paid.
_Avoid_: Paid, captured

**Capture**: Transfer of the held payment to the provider under the accepted settlement rules.

**Void**: Return of uncaptured held funds to the payer by the platform operator.

**Payer reclaim**: Return of held funds initiated by the payer once capture authority expires.

**Expired but not returned**: A payment whose capture deadline has passed without established
evidence of return to the payer.

**Payment operation**: A distinct attempt to fund, capture, void or reclaim one accepted payment.
Its failure does not by itself establish whether funds remain held.

**Settlement pending**: An order awaiting the outcome of a reserved or submitted payment action.

**Uncertain operation**: A payment action whose authoritative outcome is not yet established.
_Avoid_: Success, returned

**Confirmation threshold**: The agreed level of chain evidence for accepting a payment outcome.
It is distinct from irreversible finality.

**Confirmed settlement**: A payment outcome established by authoritative reconciliation.
A mock booking or submitted transaction is not confirmed settlement.
