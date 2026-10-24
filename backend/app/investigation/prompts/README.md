# Semantic strategy — Jeff

Use the bounded Claude gateway or an injected offline SemanticAssessor. Jeff owns semantics,
questions, evidence selection, amendment criteria and evaluation; Nikita owns runtime enforcement.
Inspect accepted catalog requirements and exact supplied passages. Return cited assessments,
missing/conflicting facts and useful requested evidence. The initial templates live in
app/agents/gateway.py and app/investigation/catalog.py and are deliberately replaceable.

Never invent authority, turn model confidence into a fact, execute generated check code or
request payment directly. A failed authenticity check is UNKNOWN. Two models agreeing is not
independent truth. At most two questions/60 seconds per dispute; answers do not reset time.
Use distinct precontract/fulfillment/repair/dispute contexts. No evaluator labels, supplier
credentials, worker/reviewer tokens or repository-wide tools belong in model context.

Offline interpretation is conservative and bounded; unknown semantic complaints escalate after
questions. Jev is absent and optional. Any future adapter needs official API verification and
independent false-pass/contradiction/abstention/latency/cost evaluation before adoption.
