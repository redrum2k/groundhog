# Make aggregate brokerage the primary product

Date: 2026-10-24. Status: accepted by the explicit product migration request.

The default journey now delivers synthetic aggregate CSV and JSON under a distinct
`aggregate-brokerage-v1` domain policy. Its funded lifecycle reuses the integrated
CatalogService, CatalogWorker, gateway, journal and executor. A new typed `/runs`
facade records explicit lifecycle effects atomically in the same SQLite transactions.

Jeff's SourcePin/TermProvenance/Frozen semantics and bounded assessor interface are
reused. Integer/null counts, independent ZIP coverage and byte validation require new
versioned models. His broker/improvement services remain compatible rather than
having their accepted mock authority and deadlines silently converted to Base payments.
Lucas's canvas and visual components remain; the live feed and live panel consume
server contracts and permissions, while recorded rehearsal stays isolated.

Tradeoff: internal catalog names and legacy PDF code remain to avoid a risky broad
rename and preserve historical snapshots. The extra explicit domain adapters cost
some code, but avoid changing old commercial agreements or duplicating financial
execution. No improvement activation applies to new runs without a future versioned
adapter. The trusted local bridge is not hosted authentication.
