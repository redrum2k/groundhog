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

**Review window**: A ten-minute review period for a delivery or disputed work.
An unresolved dispute at the cutoff moves to human review with payment held.

**Authorization expiry**: The independent deadline after which a payment
authorization cannot be used.

**Evidence verdict**: An agent's cited assessment that the invoice job is compliant,
has a provider defect, or still lacks enough evidence to decide. A complete compliant
verdict can authorize early settlement under the accepted policy.

**Operational failure**: Failure of execution, such as an engine error that prevents
a usable delivery. It is distinct from a delivered PDF requiring evidence review.

**Additional processing charge**: The agreed fee for additional processing following
an evidence-backed refutation of a customer's claim. An absent agreed fee requires a quote.

**Settlement intent**: A version-bound payment operation authorized by the accepted
policy and an evidence verdict or review cutoff.

**Confirmed settlement**: A payment outcome established by authoritative reconciliation.
A mock outcome or a submitted transaction is not confirmed settlement.
