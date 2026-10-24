# Broker dispute assessment contract (published before implementation)

Backend follow-up starts 2026-10-24T10:25:38-07:00, hour-one checkpoint
11:25:38, hard cutoff 12:25:38. Base: c2f561956fc5189688e70918967ef5c9eb87f5fe.
This is a new authorization, not a restart of V6's 02:10–10:10 window.
V6 delivery 0b1127f and frozen experiment f388fe3 remain untouched.

Use existing `/api/broker/entities/{id}/events` and its `Event` envelope.
New event type: `dispute.assessed`. Payload fields:

- `kind`: effective `justified | not_justified | unclear`.
- `reason`, `evidence_ids`, `decided_by`: server-owned effective outcome and
  provenance (`model | rules | unresolved`; controller uses `human.decision`).
- `binding`: order ID, issue ID, broker/order revision, delivery/evidence binding,
  accepted/effective specification hashes and evidence digest. No UI-derived revisions.
- `attempt_id`: durable logical operation, one dispatch per issue snapshot.
- `raw_candidate`: model proposal, never itself an applied disposition.
- `validation`: status and reasons; identity/location integrity is not entailment.
- `effective_decision`: disposition and permitted effect, separately recorded.
- `references`: exact artifact ID/version/hash, JSON pointer or precise text location,
  and exact quoted content. Artifact bytes use the existing read-only artifact route.

UI mapping: `justified -> agree`, `not_justified -> disagree`, `unclear -> grey`.
Fallbacks/overrides must not say model-decided. A validated model interpretation
without independently supported facts stays unclear/advisory. Controller provenance
remains distinct. Source counts, polls, navigation and replay never initiate calls.

Only explicit investigative commands may dispatch after evidence acquisition.
Reserve the logical attempt transactionally; perform model I/O outside the transaction;
recheck all binding fields before applying. Preserve failed/stale/uncertain attempts;
never redispatch an uncertain operation on replay/restart.

Justified can only reserve the existing eligible free correction. Not justified can
only record supported NO_REMEDY. Unclear holds for clarification/controller handling.
No execution, acceptance, capture, fee, refund, approval or clock authority is granted.

Default feature flag: `ENABLE_BROKER_DISPUTE_ASSESSMENT=false`. Keep OFF unless
acceptance passes. Frontend implementation belongs to Lucas and is not modified here.
Shared cumulative API ceiling $45 including V6 reservations; concurrency <=2;
no aggregate request count ceiling. Register this new window explicitly in the shared
guard, retaining V6's original cutoff. No billing changes or automatic retries.
