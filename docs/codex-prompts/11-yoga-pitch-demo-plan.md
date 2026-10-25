# Yoga objection pitch: Path B

Updated October 24, 2026 to the selected pitch direction. This is a proposal and
implementation brief, not completed implementation or paid-model authorization.

## Thesis

“We minimize staff intervention by making obligations explicit, then resolving
objections against the agreement and the evidence.”

Keep the three-minute structure, with autonomous resolution as the centerpiece.
The contract establishes what was promised; source and delivery evidence establish
whether it was delivered. Customer clarification and acceptance remain explicit.
The promise is less staff intervention, not the absence of all human participation.

## Proposed three-minute pitch

| Time | Story and demonstration | Suggested narration |
| --- | --- | --- |
| 0–20 s | Introduce the operational problem and OBJECTION. | “AI can produce the work, but staff still have to clarify what was promised, handle objections and decide when payment is earned. OBJECTION connects those steps.” |
| 20–45 s | Customer requests SF adults aged 25–34 interested in fitness. Ask what fitness means, receive a gym/app answer excluding standalone yoga, and explicitly accept the $120 agreement. | “Before doing the work, we turn an ambiguous request into a specific agreement. That answer becomes part of the contract.” |
| 45–65 s | Explicitly simulate funding. Produce actual CSV/JSON and show independent checks against the frozen sources. | “Funds are held while the dataset is produced and checked. These are actual artifacts; funding is simulated for this demo.” |
| 65–120 s | Customer objects: “Your source calls yoga fitness. Why isn't it included?” Retrieve the broad taxonomy, detailed eligibility rule and accepted scope. Show the actual bound finding and citations. | “The objection is plausible. Yoga belongs to the source's broader Fitness & Wellness category. But its eligibility rule distinguishes standalone yoga from the gym/app population this customer purchased.” |
| 120–150 s | Present the supported explanation to the customer; the customer explicitly accepts delivery. | “The agent explains how the evidence maps to the agreement. The customer can inspect the citations before accepting.” |
| 150–180 s | Show confirmed mock capture through the normal gates, then close on the thesis. | “This objection was resolved without a staff reviewer. The agreement defines what we owe; the evidence establishes whether we delivered.” |

The exact source wording above is proposed synthetic fixture content. Freeze and
verify it before showing it as evidence. The concluding no-staff-review statement
is valid only for an observed run that actually completed that way. One run does
not establish a measured reduction in intervention across cases.

Keep escalation as one sentence about the boundary: “If the evidence cannot resolve
an objection, funds remain held for human review.” Procedural learning and a staged
human decision are not part of this main pitch.

## Concrete example

- Accepted scope: gym membership or fitness-app use; standalone yoga excluded.
- Broad source classification: yoga belongs to Fitness & Wellness.
- Detailed eligibility: standalone yoga-studio membership alone does not qualify
  an adult for the gym/app aggregate. Gym/app qualification is a separate criterion.
- Complaint: the customer interprets the broad category as evidence that yoga is owed.
- Finding: the broad classification is true, but it does not establish eligibility
  under this agreement. Verify the delivered population against the specific rule.

This is consistent evidence at different levels, not a contradiction. Do not say
“yoga is not fitness,” reject the true broad statement, or assert that no one who
practices yoga appears in the dataset. People who also meet the gym/app criterion
may qualify; standalone yoga membership by itself does not.

## What the backend needs

Use the working `order-to-cash-live` checkout as the base. It was observed clean
at `800c985f520324981a75b596785c5f4aa3ef0bb6` on `codex/local-claude-live`, including
main `3d69b92` and Jeff's aggregate intake/semantic integration. Recheck status and
ancestry before starting. Preserve the main checkout's uncommitted work.

Existing capabilities cover clarification, acceptance, mock funding, CSV/JSON,
independent verification, guarded semantic attempts, citations, customer acceptance
and settlement. Reuse the current service, worker, persistence and payment ledger.
The default yoga smoke checks an unsupported claim against `yoga_is_gym=false`;
it does not establish support for the richer compound complaint above.

1. Add an isolated, separately identified synthetic source fixture with both the
   umbrella label and detailed eligibility evidence. Register it before intake;
   freeze editions/hashes at acceptance. Preserve default and historical sources.
2. Verify that the bounded claim interpreter and evidence resolver can handle the
   actual natural complaint. Add only narrow, tested support if needed. Preserve
   the true taxonomy premise separately from the unsupported entitlement inference.
   Do not force all yoga phrases into one predicate or substitute an easier claim
   without disclosure. This is the main semantic implementation uncertainty.
3. Reuse guarded Claude assessment and independent proof checks. Persist candidate,
   effective finding, provenance and binding. Build the explanation from resolving
   citations. Sufficient existing evidence should not trigger a redundant question
   asking the customer to locate a passage already available to the agent.
4. Present the finding, obtain actual delivery acceptance and observe mock capture
   exactly once. Resolution alone grants no payment authority. Missing, conflicting,
   stale or unsupported evidence must still block and follow existing review rules.
5. Add a thin reproducible offline runner, chronological report and API runbook.
   Preserve the four-case smoke runner. Cover restart/replay, exact artifacts and
   citations, consent, question/deadline bounds and fallback hold/escalation.

No human-decision projection or new learning subsystem is needed for the main
journey. Backend payload examples remain part of the implementation handoff;
visual design and UI changes are outside this backend prompt.

## Validation and rehearsal

Run offline first using explicit mock funding and disclosed fake model clients.
Both `ENABLE_PAID_MODELS` and `ENABLE_DATASET_MODEL_ASSESSMENT` affect the real
Claude path. Old qualification windows do not authorize new paid calls. Separately
authorized rehearsal must establish actual model behavior and latency; offline
results cannot be presented as live Claude qualification.

The 60-second review starts at publication. Prepare the objection beforehand and
file it promptly. The dispute has a separate 60-second window, at most two questions,
and no clock reset on answers. Never stretch deadlines to fit the presentation.
If model latency prevents the sequence fitting three minutes, use a clearly labeled
recording of a real run with its original timing, not scripted backend verdicts.

Preserve synthetic-source and mock-payment disclosure throughout. Never expose
suppressed counts, fabricate a successful model answer or turn a favorable finding
into direct capture authority. Do not claim full browser integration from backend
acceptance alone: `/live` is the funded aggregate flow, while the current root canvas
uses a separate retained compatibility flow.

Implementation prompt: [11-yoga-pitch-demo.md](11-yoga-pitch-demo.md).

## Launch implementation

Run once from a terminal. This creates a separate worktree from the current
committed live-demo HEAD and passes the saved prompt on stdin. It does not change
the running checkout. If the branch/worktree already exists, resume there instead
of rerunning creation. Uncommitted live-demo changes would not be included.

```sh
cd /Users/nikitaafanaskin/Documents/Developer/order-to-cash &&
git -C ../order-to-cash-live worktree add \
  -b codex/yoga-pitch-demo ../order-to-cash-yoga-pitch-demo HEAD &&
ENABLE_PAID_MODELS=false ENABLE_DATASET_MODEL_ASSESSMENT=false \
PAYMENT_ADAPTER=mock ENABLE_TESTNET_BROADCAST=false \
codex exec --sandbox workspace-write \
  --cd /Users/nikitaafanaskin/Documents/Developer/order-to-cash-yoga-pitch-demo \
  - < docs/codex-prompts/11-yoga-pitch-demo.md
```

Checked against installed `codex exec --help` and the
[official non-interactive CLI documentation](https://learn.chatgpt.com/docs/non-interactive-mode).
The command is drafted, not executed. The Codex coding session uses your configured
model; the environment flags disable the application's paid Claude execution.
