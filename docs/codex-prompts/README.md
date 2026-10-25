# Nikita implementation prompts

These prompts preserve earlier planning and integration snapshots. Their status
and launch instructions may be superseded; inspect current Git history, HACK.md
and the relevant handoff before starting or repeating work.

Local main was fast-forwarded to published frontend main `dbf9006` (October 24,
2026). Local frontend/schema and documentation fixes remain uncommitted; combined
integration validation is incomplete. Workstreams 06/07/08 and
08b are merged. The unavailable-preview polling fix is complete; do not rerun
08 or 08b. See [main integration evidence](../reviews/main-integration.md).
Jeff's R3/R4 compiler fixes remain independent work.

## Next sessions — drafted, not executed

1. [Integrate local changes and latest main](integrate-local-and-main.md). Review
   the pending frontend/schema edits and 09b at `593e02f`, validate the combined
   tree, then merge/push only the reviewed result. The earlier session stopped
   integration at the user's request; this prompt records its exact state.
2. [10 — aggregate evaluation](10-aggregate-evaluation.md), after integration.
   Build the runner/readable report under the agreed tooling delegation, reusing
   Jeff's published audit code. [Proposed PR text](../pr-drafts/10-aggregate-evaluation.md)
   is a local scope draft, not an implemented or published PR. Payment recovery
   remains a separate later task; prompt 10 is now assigned to evaluation.

Start the integration in the existing checkout:

```sh
cd /Users/nikitaafanaskin/Documents/Developer/order-to-cash &&
codex --cd . "$(cat docs/codex-prompts/integrate-local-and-main.md)"
```

After that reviewed integration is pushed, start evaluation in a separate worktree:

```sh
cd /Users/nikitaafanaskin/Documents/Developer/order-to-cash &&
git fetch origin &&
git worktree add -b codex/aggregate-evaluation ../order-to-cash-aggregate-evaluation origin/main &&
codex --cd ../order-to-cash-aggregate-evaluation "$(cat docs/codex-prompts/10-aggregate-evaluation.md)"
```

Inspect and continue an existing evaluation worktree instead of repeating creation.
Both commands read the local prompt from this checkout, including uncommitted files.
Jeff's published branch was observed at `e774495`; it is not merged by either
launch command. The implementation prompts define their review and reuse boundaries.

## 09 review and amendment — implementation awaiting review

Original amendment: [09b-payment-attempt-boundaries.md](09b-payment-attempt-boundaries.md).
The [09 review](../reviews/09-results-review.md) reproduced 695 passing backend
tests and two known compiler failures at `9622fe0`, but found two additional
boundaries: unbounded streaming HTTP and a late buyer signature saved after budget
expiry. Follow-up `593e02f` now exists in that worktree and needs independent review
through the integration prompt above. Do not restart 09 or rerun 09b blindly.
Jeff continues R3/R4 independently. Current jobs are in
[responsibilities](../responsibilities.md#current-jobs-after-the-09-review--october-24).

Historical amendment launch command:

```sh
cd /Users/nikitaafanaskin/Documents/Developer/order-to-cash &&
codex --cd ../order-to-cash-payment-lease-renewal "$(cat docs/codex-prompts/09b-payment-attempt-boundaries.md)"
```

The original [09 prompt](09-payment-lease-renewal.md) implements payment
lease renewal and finite operation budgets without extending financial authority.
A worker lease expiring does not void a payment. Exact-byte transaction recovery
is a later task because it touches the same executor/journal files.

The following launch command is historical: the 09 worktree now exists. Do not
run it again. It originally created the worktree and started the complete prompt:

```sh
cd /Users/nikitaafanaskin/Documents/Developer/order-to-cash &&
git fetch origin &&
git worktree add -b codex/payment-lease-renewal ../order-to-cash-payment-lease-renewal origin/main &&
codex --cd ../order-to-cash-payment-lease-renewal "$(cat docs/codex-prompts/09-payment-lease-renewal.md)"
```

If that worktree already exists, inspect and continue it instead of running the
creation command again. The prompt is passed from the original checkout, so it
does not need to be committed or copied into the new worktree first. The installed
`codex --help` confirms `--cd` and the positional initial prompt. Creating this
guide did not launch the implementation or create its worktree. Run the
[manual demo](../TEST_PLATFORM_NOW.md) from main while 09 works independently.

## Earlier launch instructions — historical

The following describes the original workstream setup, not work to restart on
current main. Preserve existing branches and consult each completed handoff.

These prompts cover Nikita's remaining catalog runtime and payment work. Jeff owns
reasoning/document semantics, Lucas owns the frontend, and Rehan owns independent
acceptance judgments. The existing invoice workbench at `/api/jobflow` is a separate
compatibility workflow and must keep working.

Prepared against local `main` at `ac385a1`. Reinspect the checkout when starting;
the prompts describe work to perform, not completed implementation.

## Launch order

| Conversation | Prompt to paste in full | Branch | Start |
| --- | --- | --- | --- |
| 1 — Agent runtime | [01-agent-runtime.md](01-agent-runtime.md) | `codex/catalog-runtime` | Now |
| 2 — Base transport | [02-base-transport.md](02-base-transport.md) | `codex/base-transport` | Alongside 1 |
| 3 — Settlement | [03-catalog-settlement.md](03-catalog-settlement.md) | `codex/catalog-settlement` | Alongside 1 and 2, using fake transport |
| 4 — Integration | [04-integration.md](04-integration.md) | `codex/backend-integration` | After 1–3 have committed results |

Follow-up: [06-data-broker-migration.md](06-data-broker-migration.md) implements the
agreed data-brokerage pivot and connects Lucas's canvas (merged into remote main in
PR #3) to persisted backend runs, events and reviewer decisions. It also integrates
Jeff's already-merged PR #4 (`5c8dc726326bb9e3539cdb51e5aec221868223bc`), reusing his
broker semantics and scoped improvement loop while reconciling its legacy mock
policy with the new domain and integrated funding/runtime. Start it after
conversation 4 commits its validated integration result. It preserves Base Commerce
Payments and the existing durable runtime. It replaces prompt 5's narrower adapter
plan; do not launch both. If prompt 5 is already running, steer that same conversation
with prompt 6, keeping its existing branch and worktree.

Conversation 4 is now complete at `39dd58602b3f8ac0a7906b4db4ddbbdb57b3d981`;
its handoff reports 442 passing backend tests and no observed live testnet results.
Prompt 6 must retain that validated commit and merge reviewed current origin/main,
which includes both Lucas and Jeff. A merge preview against `5c8dc72` found conflicts
in `backend/app/main.py` and `README.md`; preserve the integrated background/payment
lanes and Jeff's broker/improvement startup hooks. Do not remerge their original
feature branches or treat Jeff's separate 415-test result as combined validation.
[07-payment-readiness.md](07-payment-readiness.md) is Nikita's parallel task: validate
the existing isolated payment lab and prepare testnet evidence. Prompt 6 owns
application deadlines/dataset settlement/canvas; prompt 7 owns lab-only work and
its own handoff. Neither prompt authorizes actual transaction broadcasts.
Prompt 7 stays on the integrated payment baseline; it does not need Jeff's mock
broker to validate Base mechanics. Prompt 6 owns the application integration.

After 06/07 finish, use [the local and Render run plan](../LOCAL_AND_RENDER_RUNBOOK.md)
to select the combined commit, start fresh local state and test the real canvas
journey. This is a validation/deployment guide, not another parallel implementation
prompt. Render interactive access needs a protected hosted boundary; 06's local-demo
bridge alone does not establish that. The guide records 07's completed `f8a929a`
handoff and leaves final 06 fixture/mode/browser commands to its completion handoff.

The first three conversations use separate worktrees from the same starting commit.
They do not automatically receive one another's chat messages or uncommitted files.
Conversation 4 merges their commits and owns final wiring and shared documentation.
Each prompt is self-contained: paste its full contents even if these prompt files
are not committed into the chosen worktree yet.

## VS Code Codex extension — recommended for your current setup

Keep using the extension. Use one VS Code window per worktree, with one of the
implementation conversations in each. The separate folders isolate edits; opening
several chats against the original folder does not provide that isolation.

In your current VS Code terminal, run this once from the repository root, before
launching agents. Use fresh branch/path names if any already exist:

```sh
git status --short
backend_split_base=$(git rev-parse HEAD)
git worktree add -b codex/catalog-runtime ../order-to-cash-runtime "$backend_split_base"
git worktree add -b codex/base-transport ../order-to-cash-base "$backend_split_base"
git worktree add -b codex/catalog-settlement ../order-to-cash-settlement "$backend_split_base"
git worktree add -b codex/backend-integration ../order-to-cash-integration "$backend_split_base"
git worktree list
```

Uncommitted files stay in the original checkout; these commands do not include
them. Commit any implementation changes that must be in the shared baseline first,
without staging unrelated teammate work. You can still paste these prompt texts
from the original checkout without committing the prompt files.

1. Use **File → New Window**, then **File → Open Folder** to open
   `../order-to-cash-runtime`. Start a new local Codex chat and paste prompt 1 in full.
2. Repeat in a new window for `../order-to-cash-base` with prompt 2 and another
   window for `../order-to-cash-settlement` with prompt 3.
3. Check each window's folder and branch before submitting. Leave the original
   `order-to-cash` window available for reading and coordination.
4. Once conversations 1–3 finish and commit, open `../order-to-cash-integration`
   in a fourth window. Paste prompt 4 and their final summaries/commit SHAs.

Open the extension using the Codex icon or **Codex: Open Codex Sidebar** in the
Command Palette, as documented in [OpenAI's IDE guide](https://learn.chatgpt.com/docs/codex/ide).
The prompts install backend dependencies as needed. They use temporary databases and
offline fixtures; do not copy existing `.env`, databases or private artifacts into
the new folders. The prompts themselves can be pasted from the original checkout.

## Optional CLI repair and launch

The CLI is an alternative way to run the same worktree prompts. VS Code is sufficient
for this split. Local inspection found npm-installed Codex 0.104.0 with a missing
native executable, causing `codex --version` to fail with `ENOENT`. The first repair
to try is a clean reinstall including its optional platform packages:

```sh
npm uninstall -g @openai/codex
npm install -g @openai/codex@latest --include=optional
rehash
codex --version
```

This uses OpenAI's documented [npm installation/update command](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex)
with optional dependencies explicitly included for the missing platform package.
These commands are instructions; they were not run when writing this guide. If the
version check still fails, inspect the new error and `command -v codex` before
starting any sessions. A successful reinstall is not assumed.

Once the version check works, open one terminal per worktree, change into its
directory, run `codex`, and paste the corresponding prompt. For example, from the
original repository root in the first terminal:

```sh
cd ../order-to-cash-runtime
codex
```

Repeat for Base and settlement. Start integration only when their commits are ready.
Choose ChatGPT sign-in if prompted. See [OpenAI's CLI guide](https://learn.chatgpt.com/docs/codex/cli).

## Desktop app alternative

The desktop app can create worktrees for you instead of the manual commands above:
start a new chat, select **Worktree** under the composer, choose the same starting
branch for conversations 1–3, and paste each prompt. Start conversation 4 once their
commits are ready. See [OpenAI's worktree guide](https://learn.chatgpt.com/docs/environments/git-worktrees).
Use either this creation flow or the manual checkout flow, not both for the same branch.

## How the parallel work connects

These are private Python boundaries for this work split, not new public API promises:

| Boundary | Producer | Consumer |
| --- | --- | --- |
| `CatalogWorker(service, ...).run_once() -> bool` in `app/runtime/catalog_worker.py`; one bounded attempt or idle | 1 | Startup wiring; 4's integration tests |
| Existing `PaymentTransport`, `SignedTransaction`, `ChainObservation` in `app/payments/executor.py` | 2 implements; 3 preserves | Payment executor and runner |
| `BasePaymentTransport(config, *, rpc=None)` in `app/payments/base.py`; `verified_usdc_domain() -> dict` returns the RPC-verified EIP-712 domain | 2 | 3's injectable domain/transport boundary; 4's factory |
| Optional `payment_mode="mock"`, `payment_config=None`, `payment_transport=None` on `CatalogService`; existing `payments.work(limit=20)` remains bounded | 3 | 4 wires real configuration/transport; 1 keeps existing mock defaults |
| Existing frozen HTTP routes, DTOs, errors, actions, OpenAPI and TypeScript | Shared baseline | All conversations; 4 verifies compatibility |

Keep these interfaces stable while the three branches are independent. If an
implementation exposes a necessary incompatibility, record the exact requested
change in its handoff, continue independent work, and let conversation 4 reconcile
it. Do not silently change another conversation's interface.

Ownership avoids the main collisions: 1 edits startup and scheduling; 2 edits Base
transport/runner/configuration; 3 edits catalog order/payment transitions and the
generic payment journal/executor as needed. Conversation 4 edits shared wiring only
after the branches have committed. Only 4 updates broad status/handoff documents.

## Completion and follow-up prompts

To launch the brokerage migration after conversation 4 is complete, run from the
original repository root only if the migration task has not already started.
At the October 24 prompt review, `order-to-cash-data-broker` and
`order-to-cash-payment-readiness` already existed at `39dd586`, with lab edits in
the latter. Continue those conversations with the updated prompts; do not create
competing branches, reset either worktree or discard those edits. The creation
commands below are only for a fresh setup:

```sh
git fetch origin
git worktree add -b codex/data-broker-migration ../order-to-cash-data-broker codex/backend-integration
cd ../order-to-cash-data-broker
codex
```

Paste prompt 6 in full, or ask the new CLI chat to read it at the absolute path in
the original checkout. The prompt merges current origin/main into this new branch
so it contains Jeff's PR #4, Lucas's frontend and the completed backend integration.
Do not start it from the old local main and assume that the three backend branches are
already included. The other worktrees remain separate.

For a fresh optional payment-readiness task, use another terminal/worktree from the
original repository root. If it already exists, continue that task instead:

```sh
git worktree add -b codex/payment-readiness ../order-to-cash-payment-readiness 39dd58602b3f8ac0a7906b4db4ddbbdb57b3d981
cd ../order-to-cash-payment-readiness
codex
```

Paste prompt 7 or give that chat its absolute path in the original checkout. Keep
application deadline fixes in prompt 6 to avoid overlapping changes. After readiness,
the next payment milestone is separately authorized observed Base Sepolia execution.

Every implementation conversation is asked to commit only its own changes and
provide a handoff under `docs/workstreams/`. Check the claimed acceptance criteria
against its test evidence. A successful fake-chain test is not a live receipt.

If one conversation needs another owner's change, paste this into the owner's chat:

```text
Cross-conversation integration request:
- Requesting branch and commit:
- Existing interface and the exact incompatibility:
- Smallest requested change:
- Reproduction or failing test:
Implement the fix within your ownership, preserve the other branch's behavior,
run the relevant tests, commit the fix, and return the new SHA and any contract impact.
```

When returning fixes to conversation 4:

```text
The owner completed the requested fix on <branch> at <SHA>.
Merge that exact commit into the integration branch, resolve any conflicts while
preserving both implementations, and rerun the affected integration checks.
Continue the remaining acceptance criteria from the integration prompt.
```

After reviewing the final integration result, this optional prompt publishes it:

```text
Push the validated codex/backend-integration branch to origin and create a PR
targeting main. Describe the resulting behavior, validation, and remaining live
verification limits. Do not merge the PR. Return its link.
```

The local implementation prompts authorize offline coding, tests and local commits.
They do not authorize paid application model calls, transaction broadcasts or
deployment. There is no additional live-execution prompt here: the adapter should
first produce a concrete preflight/setup report for a later authorized run.
