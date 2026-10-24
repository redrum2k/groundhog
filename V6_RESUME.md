# V6 pickup

Read V6_RUN_MANIFEST.json and V6_WORK_LOG.md plus root/nested AGENTS.md.
Deadline is absolute: 2026-10-24 10:10 Pacific, export reserve at 09:25.
Do not restart the eight-hour window. Native execution only; no RAP/Goal Autopilot.

Current main base 5c8dc72 already includes useful V5 modules. Next: implement persisted
catalog events in the existing transaction, typed read-only event API, and explicit
live canvas commands using actual revisions and accepted bindings. Add behavioral
tests for replay/reconnect/idempotency and preserve all canonical financial gates.
Provider readiness was rechecked after explicit user configuration/authorization.
MISSING_MODEL_ACCESS RESOLVED: claude-opus-5-5 smoke succeeded (237 input/9 output,
4 seconds, $0.001128, 1 request used). C:/Users/sajee/order-to-cash/backend/.env is
the explicit private configuration source; load with uv --env-file and never print
its contents. $45 aggregate/concurrency 2 are authorized, same absolute cutoff.
The user REMOVED ALL aggregate request-count ceilings. Count requests only as telemetry.
Retain dollars, concurrency, provider rate limits, per-request bounds and loop controls.
Initial final-evaluation holdback is $20; revise after measured pilot before final reveal.
Budget state: backend/artifacts/v6-model-budget.sqlite3. Do not reset it. All real
SDK paths now use bounded clients. Continue genuine catalog-model proposal work.

Current local demo supervisor: backend/artifacts/v6-live-b/supervisor.json; inspect
actual PID/health before assuming it is live. Backend 8106/frontend 3106. It was
started offline and has not adopted paid configuration. Browser failures a/b/c are
retained: initial same-origin mismatch fixed, startup observation raced readiness,
then harness expected a transient funding button after the durable sweep completed.
Harness now waits for committed funded state. Re-run to fresh browser evidence path.

UPDATE: browser run d PASSED, report at frontend/artifacts/v6-browser-d/report.json.
Actual three-page delivered.pdf rendered and all pages visually inspected. 65 frontend
tests, generated contract drift and TS pass. Read V6_WORK_LOG for resource amendment.
Full backend regression passed 430 tests; latest resource-specific suite passed 8.
Lint, format and git whitespace checks pass. No test sessions remain running at this
checkpoint. Budget ledger currently 1 smoke request/$0.001128; no real proposal yet.
All new work is currently uncommitted; no push yet. Original C:/... repository is
clean on main apart from ignored private configuration. Keep implementation in D:.

## Next concrete work (not done yet)

1. Complete catalog-specific improvement adapter using existing immutable im_records,
   im_state/im_active and implementation_digest; no replacement financial engine.
   The single new allowable edit is retrieval of already registered exact-edition
   evidence. app/catalog/acquisition.py implements the shared capability and its
   three tests prove same-information checks and unresolved boundaries. All arms get
   this capability; competent static already reaches the manual-upload floor.
2. Pin prospective procedure versions to new drafts/orders using a separate immutable
   pin mapping, never modifying accepted snapshot/contract. Add incident/propose/probe/
   approve/activate/revoke API and canvas display. Use ClaudeGateway (budgeted parse)
   for real typed proposals; retain raw response, schema and implementation hashes.
   Do not hand-edit proposals or describe injected rejection controls as model output.
3. Isolated catalog probes must execute real CatalogService commands and compare actual
   outcome/held money/accepted bindings; approval binds exact source/candidate/probe.
   Prepare source-grounded independent oracle and fresh 12-world final batch BEFORE
   candidate selection/reveal; explicit six-world fallback only on forecast. Keep truth
   outside runtime. Functional memory must consume actual scoped incident context.
4. Finish live backend's paid config adoption safely. Existing supervisor v6-live-b
   loaded offline before model authorization and uses private ephemeral worker/reviewer
   tokens shared with frontend. Do not claim it adopted new config. User requested only
   backend restart if loading environment; preserve frontend and mission clock. A
   later code/build restart must preserve saved DB/events and be recorded separately.
5. Browser FAIL/correction, restart/revoke, source highlights, improvement chain and
   new accepted order still required. Browser run d proves supported PASS/UNKNOWN,
   actual PDF, explicit funding, review-before-capture and replay no-mutation only.
6. Freeze exact revision/config/candidate/baselines/oracle; run honest four-arm final
   comparisons, preserve failures/ties, final policy/API handoff, sanitize/test/push
   new feature branch or patch, verify SHA, results ZIP <512MB, stop owned processes.

No request-count enforcement remains in backend/app. Counts are telemetry. Budget
reserves conservative costs, retains unknown failure cost, tracks cache/thinking usage,
honors Retry-After, stops identical/no-new-info loops, and has a $20 final holdback.
ModelBudget.allocate_final updates the dollar holdback and records frozen plan digest.
Final dispatch needs final_evaluation=True plus that digest. All prior costs retained.

## LATEST UPDATE — 03:30 (supersedes completed steps above)

Catalog adapter/probe/pins/API/canvas COMPLETE. Genuine untouched candidate
catalog-patch_205bd864000148ee818e6d36c55e0f56 generated, probed, separatelyapproved/activated.
Current version catalog-version_01694b18823a4b4f961bbd6c6282b751. Actual browser c passes full
chain including realClaude clarification/answer, newacceptedorder, autoacquisition, verifiedPDF,
exactlyone mockcapture, 0 replay/refreshmutations. Evidence frontend/artifacts/v6-model-browser-c.
Neworder order-quote-3ba4712f4ba14e4f8f989576815a7d7b. PDF rendered/visually checked.

Independent evaluator review backend/artifacts/v6-independent-evaluator/review.json finished.
Found/reproduced/fixed shared PDF line-swap, precisionrounding, conflictingregisteredrepair and
archiveddefectmeasurement bugs. First five regressions failed, nowpass. Allarms get these fixes.
Strongstatic baseline reachesfloor; no economicbenefit claim. Twelve freshworlds materialized
with separateoracle/Decimal/sourcebyteaudit BEFOREselection, nofinalarmrun:
backend/artifacts/v6-final-worlds/manifest.json. Defaultscope mappedstorage-2026, siblingoutside;
candidate unchanged. FunctionalCatalogMemory actual2developmentpilots retained, secondusedtool
withscopedexperience and0manualuploads; rawcontext/responses/usage in v6-memory-pilot*.

Fullbackend441 passedpre-memory; latesttargeted8 passaftertimeout/sourceguardchanges;
67frontendtests/types/build passed. SDKnow60sec clippedoriginaldeadline, noautoretries. Browser
firstattempt actualAPItimeout retaineddraft human_review; secondstartupfailure no writes; cpass.
Execution-time sourcehash nowholds staleactiveversions; newdrafts fall backbase, neverrewritepins.
Thus ANY app-source edit requires revokeexactoldversion,reprobeunchangedcandidate,approve/activate
beforeclaiming newlearnedexecution. Isolatedprobes bindhash too. Avoid unnecessary appedits now.

Model supervisor v6-live-model-b/supervisor.json ports8107/3107, CURRENT existing database
backend/artifacts/v6-real-cycle-1/development/orders.sqlite3 and artifacts sibling. CheckPID/health.
Private .envloaded; frontenddoesNOTreceiveAnthropic key. RESTART_BACKEND marker reloadsonlybackend,
STOP stopsownedtree. v6-live-model predecessorSTOPPED afterproxy/UI source reload, DB/cutoffsame.
Older offlinev6-live-b still8106/3106. Stopownedinstances atcompletion. Original10:10clockunchanged.
Ledger8reservations, known$0.168036/conservative$0.540372 inclpretransporterror+actualtimeout,
$20reserve,noactivecall. ALLchangesuncommitted,nopush. V6_WORK_LOG haschronologicalevidence.

NEXT: offlinefinalrunner/grader (visibleinputONLYat runtime, oracleoffline), immutablefreeze
source/dependencies/model/prompts/candidate/baselines/replyprotocol/oracle. Forecast12x4workflows,
actualmemorypilot$0.027540; allocate_final(...plan_sha256) beforefinaldispatch. No countceiling.
Runallfourarms once, preservefailures/ties/nullunmeasuredcategories, inspectactualPDFs/finance/
acceptedpins/pendingobligations. Needfinalrestart/revokeevidence, fullgates, sanitizecommit/feature
push (nomainmerge), policy/APIhandoff, RESULTS/LIMITATIONS/metrics/rawtraces/SHA, verifiedZIP<512MB.
Optionalcycle2 onlyaftercore/exportsecure,equal-budgetwith/withoutexperience,newcause/freshbatch;
otherwiseNOT_QUALIFIED. Do not markcompleteuntil requiredworkdone.
