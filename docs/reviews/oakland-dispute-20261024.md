# Oakland dispute and citation overflow

Two separate Astra High agents investigated and fixed the backend decision path
and frontend presentation. The exact reported interaction now reaches an
evidence-backed unsupported-complaint explanation, followed by explicit buyer
acceptance and mock capture, without regeneration or human approval.

## Culprits

The existing local run `request-35844cd6c3e441ccb42cb667d909703d` preserved a raw
Claude candidate with `FAIL`, `GEOGRAPHY_OUTSIDE_ACCEPTED_SCOPE`, and citations to
the frozen coverage and dataset geography cells identifying San Francisco.
The independent server guard did not implement a geographic-scope predicate.
It downgraded the correct model result to `UNKNOWN`/`ADVISORY`, then supplied the
generic frozen-source/cell question. The model's answer was not the original
failure in this run. Waiting for that unnecessary answer eventually exhausted the
dispute deadline.

Separately, `LiveStep` unconditionally inserted the human-review form into
investigation and verdict panels, even when all reviewer actions were disabled.
The canvas also rendered every evidence event as a new, unrestricted pill.
Repeated citations across mandatory checks consequently formed a long stack.

## Changes

- `investigation/dataset.py` recognizes complete geographic-scope assertions,
  derives available locations from the specification schema, and compares the
  assertion to the accepted geography. Proof requires a passing independent
  report plus reopening both frozen coverage and selected-source geography cells.
  It does not assign a verdict from the word Oakland. An accepted Oakland order
  supports Oakland scope and contradicts SF scope. Qualifiers, mixed allegations,
  empirical residency claims, unavailable bytes and conflicting model results
  continue to require investigation. Model instructions now distinguish contractual
  geography from empirical city-boundary claims.
- The canvas shows at most two grouped evidence pills plus an inspection control.
  Evidence and status text are width-bounded. Full reasons remain in the panel;
  all persisted evidence IDs remain inspectable in grouped, scrollable lists.
- Human-review controls now depend on current server permissions and belong in
  Admin review. Historical human-review events alone do not request fresh approval.
- Customer view shows the persisted assessment and its citations, and scrolls
  that explanation into view above the ordinary delivery-acceptance flow. Sticky
  headers do not obscure its heading on desktop or mobile.

No new regeneration action, fee, payment authority, ledger or scripted demo verdict
was introduced. Separate paid offers retain their own explicit consent.

## Verification

The new `frontend/scripts/oakland-dispute-smoke.cjs` performs these actual UI actions
against an isolated running mock backend:

1. Enter `SF adults 25–34 interested in fitness, counts by ZIP.`
2. Answer `Gym membership or fitness-app use`.
3. Prepare and explicitly accept/fund the mock quote.
4. Dispute `Oakland should be there`.
5. Observe `disagree`, no evidence request, no enabled reviewer action, and
   available buyer acceptance. Verify the explanation is in the viewport at
   1440×900 and 390×844, clear of the sticky header, with no regenerate/approval
   controls.
6. Click **Accept verified delivery** and observe confirmed mock capture.

Before the fix, this same browser journey failed with `grey` and an evidence
question. After the fix it passes with no browser errors. The browser redirects
only its own `/api/live` requests to the isolated backend; it does not mutate the
user's live Base Sepolia order. Local evidence is retained in
`.local/oakland-dispute-check/baseline/` and `final-viewport/`, including events,
screenshots and Playwright traces. The final run is
`request-c2ad532ec5814968ae7c3ddbeee4ae8b`.

The archived pre-fix investigation was also rendered with the new UI: its 15
canvas references occupy two pills and an inspection control, approximately
80.5 rendered pixels high. Clicking that control opens evidence inspection without
a human-approval form. This is an archived visual check, not a new verdict.

Validation also passed:

- 21 new backend geography tests, including both reported Oakland phrasings,
  the exact intake/answer, an injected response through the actual Claude gateway
  boundary, explicit acceptance/capture, alternate accepted geography, negation,
  mixed claims, bad citations, contradictory model output and missing bytes.
- Affected backend dataset, catalog, investigation, payment and API suites.
- All 158 frontend tests; TypeScript; changed Python Ruff lint/format; diff checks.
- React Doctor reported no issues in changed files. Its 87/100 final score covers
  eight files; the earlier 92/100 scan covered two files and is not a comparable
  score regression.

No new paid model call, live transfer, deployment or mutation of the existing
live order was performed. Tests of model integration inject a response; they do
not claim a fresh paid-model qualification. The existing port-8000 process was
not restarted and still needs to reload the updated backend code before a fresh
live run can exercise it. Existing expired disputes and accepted deadlines were
not reset or rewritten. The temporary mock validation servers are stopped after
verification.
