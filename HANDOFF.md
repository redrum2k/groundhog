# V6 current handoff

## Verified state

V6 demonstrates bounded application-generated adaptation, **not an operating-cost advantage**.
The unedited Claude Opus 5.5 candidate schedules existing registered same-edition evidence
retrieval. Actual isolated probes, separate synthetic reviewer approval, prospective activation,
new accepted order, real model clarification/answer, verified PDF, mock capture, restart and
prospective revocation are evidenced. The previous V5 handoff is preserved verbatim in
HANDOFF_V5_PRESERVED.md; original V5 results/branches were not reset or relabeled.

Read V6_RESULTS.md, V6_LIMITATIONS.md, V6_API_CONTRACT.md and POLICY_DELTA.md.
The source branch is feature/objection-v6-integrated-adaptation-20261024, based on main 5c8dc72.
Frozen experiment commit: f388fe32e56de671d6fb3fc957061c4031647806.
Backend/lockfile digest: 6b8e4101af7b1da9a3c13baf5078f835c48c7c54bf26d294e42dd3714f7e97ef.
Subsequent changes are frontend presentation/reviewer controls, test/demo/report tools and
documentation only. The final delivery manifest records exact delivery/remote SHA and archive
hash. Do not transfer these results to a changed backend digest.

Twelve fresh worlds x four arms, one run each, all 48 independently correct. Each arm closed 8
and correctly held 4. Manual evidence uploads: current static 4, competent static 0, functional
memory 0, evolving 2. Evolving's two uploads are the out-of-scope/historically pinned cases.
No recurring-action benefit or payroll savings is established. Optional second cycle was not
run: no demonstrated headroom beyond the functioning expert checklist, and the one-operation
surface cannot support a broad improve-the-improver claim.

## Resource and credential boundaries

Original mission: 2026-10-24 02:10 through 10:10 America/Los_Angeles; no reset or successor.
All mission-wide request ceilings were REMOVED. The original $45 aggregate expenditure ceiling,
concurrency <= 2, per-request output/timeout/retry limits, anti-loop rules and final reserve remain.
The ledger includes all earlier calls and failures. Do not replace it with an empty file.

Private configuration remains only at C:/Users/sajee/order-to-cash/backend/.env, ignored by Git.
It is explicitly loaded with uv --env-file; repository startup does not implicitly load it.
Never print/copy the key. Use CLAUDE_MODEL=claude-opus-5-5, not OBJECTION_MODEL.
ENABLE_PAID_MODELS is the existing explicit enablement flag. Native codex-raw was used, no RAP
or Goal Autopilot. No billing changes, automatic recharge, purchases, deployment or chain
broadcast were performed. Every payment in these results is mock.

At the final paid-call checkpoint: 17 reservations (15 successful reported-usage calls, one
pretransport SDK failure, one API timeout), $0.399756 estimated known usage and $0.772092
conservative committed cost. Unknown failures retain their maximum reservation. Exact final
values are in the delivery ledger/report. Thinking is billed within output tokens, not twice.
The final 8 memory calls cost $0.207772 (30,393 input / 4,310 output, including 1,624 thinking).
No further paid work is needed to inspect/reproduce the existing evidence.

## Where the evidence is

All paths below are relative to this repository and retained in the results archive:

- backend/artifacts/v6-model-smoke.json: organization model access and real schema smoke.
- backend/artifacts/v6-real-cycle-1: original development incident, raw generation, unedited
  patch and database. Later browser lifecycle records are in its development/orders.sqlite3.
- backend/artifacts/v6-independent-evaluator: separate native read-only model review and
  independent blueprints. Model-authored and independently arithmetic-checked, not human audited.
- backend/artifacts/v6-final-worlds: pre-reveal visible cases, separate oracle, source-byte audit.
- backend/artifacts/v6-final-capsule: frozen source/model/prompt/candidate/baseline/protocol.
- backend/artifacts/v6-final-runs: 48 immutable first-attempt workflow results and actual PDFs.
- backend/artifacts/v6-final-score: frozen offline grader outcomes.
- backend/artifacts/v6-final-reporting: ledger-enriched metrics and 8 unique rendered deliveries.
- frontend/artifacts/v6-model-browser-c: genuine model adaptation/new-order/clarification chain.
- frontend/artifacts/v6-reviewer-resume: same held order, cited reviewer release, no new model call.
- frontend/artifacts/v6-failure-browser: actual wrong PDF, single corrected PDF, validation/review.
- backend/artifacts/v6-model-restart.json: backend-only restart; frontend, accepted hash, pin,
  event cursor and exact capture unchanged.
- backend/artifacts/v6-v5-regression: 12+6 known historical regression worlds, all passing.
  Its real_model_status=BLOCKED reflects deliberate offline mode, NOT current model access.

Raw failures remain beside successes. Do not rerun final worlds and call them untouched transfer.
A new scientific candidate needs new frozen evaluation worlds and appropriate existing authority.
Generated evidence is not in Git. In the delivery ZIP, source/ is the repository, while
evidence/backend/ maps to the original backend/artifacts/ and evidence/frontend/ maps to
frontend/artifacts/. Keep the offline oracle outside the runtime image; do not copy it into app/.

## Decisions and gotchas

- Reused canonical CatalogService/payment journal, V5 im_records/approval/version primitives
  and Lucas canvas. No replacement frontend, financial engine or general orchestration framework.
- Compiler case limit 4 and contractual question/repair limits remain: those are accepted safety
  policy, not a mission-wide application request ceiling.
- Installed Anthropic SDK raw namespace exposes create, not parse. The bounded adapter saves raw
  proposal/memory responses before schema validation; compiler question/term responses are also
  retained at browser/domain level. Do not claim full provider raw bodies for every compiler call.
- A 20s compiler timeout failed; bounded timeout is now 60s, clipped by original cutoff, retries 0.
  Next bridge timeout is 75s; browser waits for readiness and model completion. Lost responses must
  reuse exact keys, never create a fresh financial operation.
- selectable=false means not selected for initial contracts; it does not ban same-edition repair.
  Memory pilot 1 misread that flag. Its result is retained; clarified-contract pilot 2 succeeded.
- PDF verification must bind product identity, numbers and citation together; line bags are unsafe.
  Exact source Decimal precision is preserved. Contradictory registered repairs hold, even via upload.
- Archived verification and amendment citations remain necessary for human review after invalidation.
  UI supports them; no capture override is offered. Uncaptured release is not a refund.
- Source changes invalidate approved execution. Accepted pins stay immutable; stale versions hold
  and new drafts use base. Re-probe on new source, then separate approval/activation. Byte-level
  implementation hashes can change with line endings; use packaged source bytes or revalidate.
- Active procedure was intentionally revoked by the rollback demonstration. Accepted orders keep
  their prior version. Current future drafts use catalog-static-v1; this is not lost state.
- Four final arms use explicit fixed-term synthetic inputs/deterministic compilation. Only memory
  needs per-order model decisions. Genuine proposal and browser clarification are separate real calls.
  Structured reply tests do not establish unrestricted language understanding.

## Verification and safe commands

From repository root:

```powershell
uv run --locked --directory backend pytest
uv run --locked --directory backend ruff check .
uv run --locked --directory backend ruff format --check .
```

From frontend (run npm ci first in a fresh unpacked source tree):

```powershell
npm run generate:check
npm run typecheck
npm test
npm run build
```

Latest full backend 444 passed plus the separately added offline-grader regression passed.
The final full frontend suite passed 72 tests; its JSON report is included in the archive.
Exact evidence and final validation totals are in V6_RESULTS.md/delivery manifest.

Read-only existing-score reproduction (choose a NEW output path; no model call):

```powershell
uv run --locked --directory backend python ../tools/v6_final_grade.py --capsule artifacts/v6-final-capsule/run-capsule.json --runs artifacts/v6-final-runs --oracle artifacts/v6-final-worlds/oracle.json --output artifacts/v6-score-readonly-recheck
```

From the unpacked delivery's source/ folder instead:

```powershell
uv run --locked --directory backend python ../tools/v6_final_grade.py --capsule ../../evidence/backend/v6-final-capsule/run-capsule.json --runs ../../evidence/backend/v6-final-runs --oracle ../../evidence/backend/v6-final-worlds/oracle.json --output ../../inspection-score
```

Do not automatically rerun paid experiments. The recorded mission cutoff is deliberately permanent.
For an explicitly requested continuation within the original authorized envelope, use
tools/v6_demo.py with --existing, the exact saved DB/artifact paths, fresh supervisor output
directory, localhost ports and the ORIGINAL cutoff. It never extends that cutoff.
Use --enable-application-model only with the explicitly loaded private environment and shared
ledger. Omit that flag for an offline demonstration. After cutoff, inspection/tests remain useful;
a later paid mission needs its own explicit scope that accounts for prior expenditure.

Each owned supervisor writes supervisor.json. Its STOP marker stops only its own child tree.
RESTART_BACKEND reloads only backend code while preserving frontend PID, role tokens, database
and absolute cutoff. Never inspect process memory for tokens or kill broad process names.
Final completion stops owned workers; observed shutdown/port verification is in the delivery
manifest. There is no unattended successor or recurring paid task.

## Remaining non-blocking work

Production customer identity/tenant isolation, real labor timing, live settlement, broader PDF
formats, statistical generalization and a genuinely new improvement operation are NOT qualified.
They require separately scoped work, not continuation of this completed bounded experiment.
No known required V6 engineering/evaluation task remains after delivery verification; use the
completion manifest rather than stale chronological notes to determine terminal state.
