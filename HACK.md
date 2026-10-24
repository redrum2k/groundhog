# Cal Hacks: document-processing order settlement

Initial product baseline recorded from the team's setup request and PDF amendment.
The checkout was empty: no earlier HACK.md or payment-spike results were available.
Deadline, sponsor requirements, and final demo script still need Rehan's input.

## Product and demo scope

Manage document-processing orders from accepted requirements through delivery
verification, customer disputes, and authorized settlement. Inspect PDF sources and
deliveries with linked evidence highlights; retain structured data internally for
reproducible checks. A synthetic corpus supplies repeatable examples. Independent
evaluation answer keys must never reach the investigator.

## Confirmed rules

- Freeze the accepted brief, input versions, price, and policy.
- Give customers 60 seconds to review each delivered version.
- Capture requires passing verification and either customer acceptance or review
  expiry without a dispute. An open dispute blocks automatic capture.
- One verified provider defect permits one free regeneration per order. If that
  regeneration fails, escalate to human review. Ambiguity also requires human review.
- Keep order, delivery, case, and payment states separate. New delivery/evidence
  versions invalidate prior verification and approvals; proposals are versioned too.
- Onchain authorization expiry is separate from the review deadline.
- Additional charging for unsupported complaints remains unresolved. There is no
  automatic additional debit; `no_remedy` is not payment authorization.
- Pre-delivery cancellation UI is out of scope.

## Stack and scaffold boundary

Python, uv, FastAPI, Pydantic, SQLite, LangGraph, Anthropic Python SDK;
React/TypeScript, Next.js and shadcn/ui; Railway hosting planned. CDP and the existing
Base escrow contracts depend on the isolated [payment spike](docs/PAYMENT_SPIKE.md).
No additional infrastructure is selected.

This scaffold provides `/health`, shared contracts, an investigator protocol,
deterministic policy checks, and a durable local mock payment adapter. It does not
implement the full order lifecycle, investigator, provider, frontend, PDF renderer,
or deployment. XLSX is not selected; PDF inspection supersedes the earlier output
format suggestion, while artifact references remain format-independent.

## Open decisions

- Nikita + Jeff: approve initial contracts, how verified defects are established,
  proposal allocation, question/answer resumption, and structured-data provenance.
- Nikita + Jeff + Lucas: agree PDF rotation/crop handling and highlight mapping;
  approve the proposed one-based page and normalized top-left coordinate convention.
- Nikita + Jeff: whether new evidence during a delivery review restarts the clock.
  Current pure guard measures 60 seconds from that delivery's `delivered_at`; new
  evidence always invalidates verification and acceptance.
- Nikita: payment asset/network, decimals mapping, authorization lifetime, escrow
  semantics, confirmation/finality rule, release policy, and human-review settlement.
- Rehan + team: any future complaint-fee policy, acceptance criteria, sponsor claims,
  demo deadline, and disclosure. No complaint fee is authorized by this scaffold.

See [responsibilities](docs/responsibilities.md) for ownership and independent work,
and [architecture](docs/architecture.md) for contracts and integration boundaries.
