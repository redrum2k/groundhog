# Document-processing order settlement

Shared language for accepted document-processing work, delivery review, investigation,
and authorized settlement.

## Language

**Accepted snapshot**: The frozen brief, input versions, price, and policy agreed by
the customer for an order.

**Delivery version**: One immutable provider output and its relationship to the
accepted snapshot. A regeneration produces a new delivery version.

**Evidence version**: A revision of the complete evidence set used to assess a delivery.
It changes when any evidence is added, removed, or replaced.

**Evidence highlight**: A marked region on an exact source or delivery PDF version
that a finding cites for customer inspection.

**Structured sidecar**: Internal records linked to an exact source or delivery
artifact, retained to reproduce checks and connect their results to evidence regions.

**Proposal version**: A revision of an investigation recommendation for a particular
snapshot, delivery version, and evidence version.

**Provider defect**: A verified failure to satisfy the accepted snapshot, eligible
for one free regeneration before repeated failure requires human review.

**Review window**: The customer's 60-second opportunity to review a delivery and
raise a dispute.

**Authorization expiry**: The independent deadline after which a payment
authorization cannot be used.

**Settlement intent**: A proposed payment operation to be checked and executed by
the application under its own authority. An investigation cannot grant that authority.

**Confirmed settlement**: A payment outcome established by authoritative reconciliation.
A mock outcome or a submitted transaction is not confirmed settlement.
