# Integrate the local frontend fixes and reviewed payment work with latest main

Do the integration in this session; this document was drafted without performing
the remaining merges. Work from
`/Users/nikitaafanaskin/Documents/Developer/order-to-cash`. Inspect status, history,
worktrees and remotes before changing anything. Preserve every teammate's edits.
Read root/nested AGENTS.md, HACK.md, docs/PAYMENT_SPIKE.md, responsibilities and
the current handoffs. Do not reset, clean, force-push or stage the whole repository.

## Starting state recorded October 24

Reinspect these facts; later work takes precedence over this snapshot.

- Local main was already fast-forwarded from `62fe035` to published frontend main
  `dbf9006f4578196e93652b6de838f2e83d94b794`. The earlier session did this before the
  user requested a separate integration prompt. Do not claim this is still undone.
- The earlier session made **no new commit or push**. Main has the local changes
  listed below, along with older untracked prompts/runbooks/review notes.
- `codex/payment-lease-renewal` is clean at
  `593e02fcbc63b45d95d252e7314289eda39d4fb0`, in
  `/Users/nikitaafanaskin/Documents/Developer/order-to-cash-payment-lease-renewal`.
  It contains 09 (`9622fe0`) and 09b. **09b has not been independently reviewed.**
- Jeff has now published
  `origin/feature/aggregate-intake-integration-20261024`, observed at
  `e774495192f903d0c1191590cf13cfc4a9439977`. Reported feature commits `d2b6ba1`,
  `5946378`, and `ef8c99a` are available. His previously reported local integration
  SHA `0983c1b` is not available. Do not substitute one SHA for another or assume
  his unpublished conversational-intake amendment is qualified.

## Preserve and review the local changes

Pending integration edits:

- `backend/app/main.py`: explicitly describes 422 as `Unprocessable Content` so
  generated OpenAPI matches across Python versions. Keep the typed ErrorResponse;
  this changes documentation text, not request validation or payment behavior.
- `frontend/components/run/live-run.tsx`: the aggregate header says Groundhog;
  its return button says Run canvas because it opens `/`, which supports both feeds.
- `frontend/scripts/brokerage-smoke.cjs` and `review-remediation-smoke.cjs`:
  aggregate tests open `/live`, preserving Lucas's canvas at `/`.
- HACK.md, frontend/AGENTS.md and frontend/HANDOFF.md: document those two routes
  and the distinct aggregate versus retained-broker profiles.
- `docs/handoffs/{nikita,jeff}.md` and `docs/responsibilities.md`: previous local
  review/job updates. Preserve them, reconcile their status against the reviewed
  integration result, and retain historical findings rather than rewriting history.

Classify untracked files individually. Preserve older prompt/runbook/review drafts;
commit only reviewed task-owned documentation with intentional links. Do not absorb
unrelated work with `git add .` or `git add -A`. Do not stash/reset another worktree.
Before merging over a dirty file, safely checkpoint its intended changes in a
scoped commit or preserve a recoverable copy. Explain any exclusions in the handoff.

## Integration order and boundaries

1. Fetch origin and record exact starting SHAs and ancestry. Preserve any newer
   published main changes. Review the local frontend/schema fixes and checkpoint
   the intended changes, then integrate latest origin/main normally. Resolve
   conflicts by behavior, not blanket ours/theirs choices.
2. Independently review 09b against `09-payment-lease-renewal.md`,
   `09b-payment-attempt-boundaries.md`, `docs/reviews/09-results-review.md`, and the
   payment worktree's `docs/workstreams/09-payment-lease-renewal.md`.
   Reproduce both fixes: a continuously streaming HTTP response must have a real
   elapsed limit, and a late/cancelled buyer signature must not create a new
   persisted authorization. Use the actual new transport boundary; the historical
   review probe's private provider attributes may have changed. Adapt the probe
   to test the same requirement, not to weaken it or fail solely on an API rename.
3. Confirm lease/nonce fencing, cancellation/helper cleanup, original financial
   cutoffs and pending submitted identities remain intact. No automatic resend,
   fresh nonce/salt or invented payment result is permitted. Run the relevant
   regressions and lab examples before treating 593e02f as reviewed.
4. If 09b aligns and passes, merge its exact reviewed commit into local main,
   preserving the frontend/schema fixes. If it fails, leave that branch unmerged,
   record reproducible findings and draft the smallest follow-up prompt. Do not
   claim the overall requested integration is complete or push it as validated.
5. Jeff's feature branch is a separate review/integration item. Do not merge it
   merely because it was fetched. Retain any reviewed Jeff work already present in
   latest main. Record the available audit/tooling commit for prompt 10 and leave
   any still-separate compiler/intake branch unchanged.

Do not implement aggregate evaluation or transaction recovery during this task.
Do not change pricing/accepted parties, review windows, funding gates, payment
authority or historical snapshots to make tests pass. Keep Groundhog display branding
separate from frozen policy IDs such as `datumco-demo-pricing-v1`.

## Validation required on the final combined tree

Run locked dependencies, focused payment/runtime/dataset/API cases, full backend
pytest, backend/tools/payment-lab Ruff lint/format, the 27 offline lab commands,
and `git diff --check`. Retain known R3/R4 expected failures only when they really
remain in this starting baseline; never add/remove markers to hide a regression.

With Node 24, run frontend tests, generated-contract freshness, production build
and typecheck. Never hand-edit generated clients to hide schema drift. The 422
description must agree between exported OpenAPI and the runtime schema.

Use fresh temporary databases and loopback-only production servers with paid models
and testnet broadcasts disabled. Preserve user-running servers. The aggregate
bridge needs `BROKER_LOCAL_DEMO=1` and distinct server-only worker/reviewer tokens;
the root broker demo also needs `JOBFLOW_DEMO=1` on the backend.

- `/live`: run both existing production smoke scripts for funded delivery/capture
  and the targeted coverage complaint, including restart/reload identity and mock
  financial disclosure. Keep the smoke origin as the bare origin; the scripts now
  append `/live` themselves.
- `/`: verify Groundhog branding and the actual retained-broker demo: contract
  approval, delivery, objection/evidence, acceptance and mock capture; customer
  actions return the view to the agent. Check the Recorded fallback separately.
  Do not describe this legacy profile as the aggregate payment journey.
- Check the React Doctor regression as instructed by its skill. Do not expand
  this integration into a general UI cleanup or suppress preexisting findings.

Earlier observations are useful context, **not final combined-tree validation**:

| Check before this handoff | Observed state |
| --- | --- |
| Frontend unit tests on fetched frontend | 109 passed |
| Generated contracts after explicit 422 fix | Passed |
| Production build and typecheck after local fixes | Passed |
| Focused runtime/exported OpenAPI test after fix | Passed |
| Backend/tools Ruff lint and format | Passed |
| Both `/live` production browser smokes | Passed, no browser errors |
| Root canvas production journey | Not yet exercised in this integration |
| React Doctor | Full score 38 before/after; changed-file scan 92 with no findings |
| First full backend run before fix | 665 passed, 2 known xfails, 1 OpenAPI-description failure |
| Full backend rerun after fix | Interrupted at the user's request; incomplete |

Browser artifacts are at `/private/tmp/datapact-frontend-integration.SALNNd/` if
still available. The earlier session stopped its servers on 8039/3039. An interrupted
pytest teardown emitted cleanup errors; do not count that run as a successful suite.

## Finish

Update an integration record with exact inputs, reviewed commits, resolutions,
commands/results, remaining blockers and current startup routes. Bring the manual
testing guide up to date without claiming unobserved live-chain or hosted success.
Keep all secrets, generated runtime artifacts, local journals and dependencies ignored.

Once the requested integration passes, commit only its reviewed changes on local
main, fetch once more and account for any intervening main changes. Push main with
a normal non-force push under the user's existing integration/push authorization,
then verify the remote SHA. If remote advances, integrate/revalidate as appropriate;
never overwrite teammates' commits. Return local/remote SHAs and any intentionally
unmerged branches or remaining local drafts.

No paid calls, real chain RPC, wallet/private-database access, broadcasts or
deployment. The user wants a reviewed local merge before remote publication.
