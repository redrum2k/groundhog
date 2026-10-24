# Primary follow-up incidents and retained negative evidence

1. Before paid evaluation, the initial draft treated `yoga_is_gym=true` as sufficient
   under an accepted category whose actual meaning explicitly excluded standalone
   yoga. The implementation now holds that conflicting taxonomy interpretation.
   Regression: `test_missing_or_contradicting_authority_cannot_override_accepted_exclusion`.

2. The first malformed-hash test supplied an invalid SHA string, so Pydantic rejected
   the test candidate before citation validation. Changed only the synthetic hash to
   a well-shaped wrong digest; the invalid-citation assertion remains. Early XML kept.
   Seed-compilation scheduling also initially selected the wrong test job; fixtures
   now dispatch the specified owned order through the existing service.
   The earlier compiler-before-unxfail XML also records a gateway test failing the
   newly retained paid-call guard. That test now injects an explicitly enabled
   temporary ledger and fake SDK usage, and verifies one real reservation without
   any provider dispatch. The two R3/R4 failures in that XML are strict XPASS.

3. Offline HTTP rehearsal exposed explicit built-in catalog compiler injection
   sending aggregate intake through storage questions (409 at quote). Reused the
   existing aggregate compiler for built-in OfflineCompiler/ClaudeGateway while
   preserving custom injection. Regression exercises paid gateway selection without
   any API transport. No paid cohort ran until the full HTTP rehearsal passed.

4. Frozen real P3: raw PASS was correct but effective UNKNOWN was a genuine gate
   false-negative. The model cited the exact definition and false taxonomy cell,
   not the gate's sole category-cell certificate. Added a complete alternative proof
   restricted to the excluding accepted contract; tests reject either missing cell,
   wrong polarity and expanded-contract misuse. Original P3 was NOT rerun/regraded.
   Separately declared P7 is a new-order development probe, not confirmatory recovery.

5. Frozen real P6: model incorrectly returned FAIL when the frozen taxonomy value
   was null. Effective UNKNOWN correctly held it. No label or accepted evidence was
   changed. This remains negative model-quality evidence.

6. Full Windows backend suite exposed 11 failures in byte-unchanged main tests:
   nine subprocess environments remove SystemRoot (WinError 10106 importing asyncio),
   one requires POSIX chmod 0600, and one hard-codes `.venv/bin/python` (WinError 2).
   These were not skipped, xfailed or edited. Full failing XML remains, and final
   regression reporting must disclose them rather than claim a clean full suite.
   An isolated asyncio import reproduced WinError 10106 with PATH only and passed
   when SystemRoot was retained. `.venv/bin/python` is absent, while Scripts/python.exe
   exists. Receipt: `windows-portability-diagnosis.json`. Private payment-journal ACL
   equivalence on Windows is not established; no live payment qualification follows.

7. Final compiler review found a prior unbound cohort contradiction stayed latched
   even after a valid second, question-bound correction. Conflict tracking is now
   field-specific and clears only for the field explicitly corrected. The regression
   keeps both answers, the initial prompt, original deadline and two-question limit.

8. The final full suite additionally observed two unchanged asynchronous settlement
   tests failing `len(rpc.broadcasts)==1` immediately after seeing persisted submitted
   state. `payments/executor.py:166` commits that state before `transport.broadcast`
   at line 170; the observation can race. Both code and tests match main byte-for-byte.
   All four parameterized settlement scenarios passed separately without changes
   (`settlement-race-diagnostic.xml`). Final full-suite failures are retained as 13,
   not overwritten with the earlier 11 or diagnostic passes. No payment behavior changed.
