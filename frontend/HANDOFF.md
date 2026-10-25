# Current integration pickup

The Groundhog run canvas is at `/`, with retained broker live-demo and recorded
feeds. The funded aggregate intake is at `/live`; these are distinct backend
profiles. Use [workstream 06](../docs/workstreams/06-data-broker.md) for production
local-demo commands, generated contracts, signing/events/actions and smoke tests.
The aggregate smoke scripts target `/live`. The root canvas's live demo also needs
`JOBFLOW_DEMO=1` on the loopback backend; the aggregate bridge needs
`BROKER_LOCAL_DEMO=1` and distinct server-only worker/reviewer tokens on Next.
The historical design brief below is preserved as reference, not implementation status.

# UI handoff: order-to-cash agent for a data broker (Cal Hacks 13.0)

> Ported into this Next.js app on Oct 24, 2026: the run canvas lives in `components/run/` and `lib/run/`,
> the scenario in `lib/run/scenario.ts`, the styles in `app/run.css`. The Vite preview this document
> describes (`src/Flow.tsx` and friends) is retired; `references/old-preview.html` is its last build.

This folder is the design preview Lucas and Claude built in chat. It is a working React + Vite app on
sample data. It still shows the **old** case (DocuParse, invoices). The **new** design below is decided
but not built yet. Build it here, against real backend events, instead of in the old preview.

Run it: `npm install` then `npm run dev` (open the printed URL). `npm run build` makes one HTML file.

## What we're building

Positioning: "Existing platforms handle transactions and delivery. We connect a custom order's
requirements to fulfillment checks, evidence gathering, correction and authorized settlement."

One-liner: we turn the buyer's conversation into a data contract, check every delivery against it, and
settle the money based on it.

Tracks: Hyphenate (order-to-cash finance seat), Coinbase (x402 payments, visible on Basescan).

## The demo story

- Us: **Groundhog**, a data broker. Builds custom datasets from rented vendor data, so every rerun
  costs us a license fee plus compute.
- Customer: **Summit Fitness's buying agent** (an agent, not a person).
- Controller: **Human**.
- Order: "SF adults 25–34 interested in fitness, counts by ZIP." Aggregated counts only, no personal
  records. Demo data is synthetic.
- Sample numbers (to confirm with team): $120 order, $6 rerun cost (license + compute), $60 Oakland
  amendment, $30 yoga amendment (show the math: yoga adds ~9% more people × rate card = $30).

### Shared path (redrum's diagram), shown once
Customer describes the job → agent clarifies requirements (interview) → customer approves contract and
price (**Data contract v1**) → payment **authorized** ($120, x402) → produce data and check it against
the contract (each contract line is a JSON-schema / code check that ticks) → deliver → customer review
(48h window) → accepted or window expires → payment **captured**.

Contract v1 lines: fitness = gym members or fitness-app users · SF city only · ages 25–34 · every ZIP
count ≥ 50 (privacy) · all SF ZIPs present.

### Three lanes after a dispute (Lucas's notes: "is the complaint justified?")
- **Red · agree (our fault).** "ZIP 94110 is missing." Why our check passed: it compared against the
  vendor's ZIP list, which lacked 94110. The orb carries the work back to Produce, it's rerun free ($6
  cost shown), it's rechecked, then captured. Rule update shown: "check against the official SF ZIP
  list" (a second "learns from mistakes" moment).
- **Green · disagree (we were right).** "Add Oakland." The orb pulls the interview line "SF city only"
  as evidence. If Summit still wants it: contract amendment + new price ($60) → customer approves → new
  authorization → orb walks back to Produce.
- **Amber · grey.** "Yoga studios should count as fitness." Interview said gyms + fitness apps; the
  vendor files yoga under "Wellness." The agent investigates (camera zooms into the chat). A switch
  picks one of 3 endings:
  1. internal rules sort it as disagree → merges into green (optional $30 yoga amendment)
  2. internal rules sort it as agree → merges into red
  3. rules can't decide → Human reviews → **Data contract v2** ("yoga counts") → decision saved to
     improve the rules
  Grey is minimized by the interview; it should be rare.

Demo order: shared path once, then red, green, amber.

## Screens

### 1. Run canvas (the whole main screen)
- Attio-style canvas (see `src/Flow.tsx` for the current node/edge/camera code): nodes on a dotted
  grid, status chip above each node (Running → Completed / Waiting), green connectors that draw in,
  camera pans to the active node.
- **Three stacked lanes** (red / green / amber). Click a lane to zoom into it. Zooming into a step shows
  that step's context inline: the chat lines, the evidence cards, the spreadsheet with highlighted
  cells, the contract checklist ticking. **No side chat panel, no reconciliation table.**
- When evidence is found during the investigation it **pops onto the canvas** as a card attached to the
  step and visibly changes the path.
- **Mascot:** a flat single-blue orb with two eyes (reference: 21st.dev "AI Orb Avatar" by odysseyui,
  but our own drawing). States: float along, carry a sheet back, look around (investigating), slow
  blink (waiting on Human). It carries a **coin** labeled "$120 authorized" that locks during a
  dispute and becomes "$120 captured" at the end, with a Basescan link. No separate escrow step.
- Ends at a **Books** step you zoom into: journal entries (deferred revenue → revenue, rerun cost),
  Basescan link to the real capture transaction.

### 2. Customer view (second tab, same app; shown if judges ask)
- Summit's buying agent chatting with our agent. Follows whichever lane is selected.
- The intake interview turns into a **checklist that ticks off live** while the data is produced
  (21st.dev Agent Todo List pattern, already ported in `src/TodoList.tsx`).
- Dispute replies cite evidence **inline**: specific spreadsheet cells and interview quotes.

### Also on screen
- **Agent seat line** under the title: "Order-to-cash agent for a data broker", with the positioning line.
- **Margin after cost** on the order: revenue minus data license and compute, updated when a rerun adds cost.
- **Colors:** red = our side failed (an operational failure, matching AGENTS.md), green = we were right /
  working as intended, amber = grey. Color only for state.
- **Mock labels:** until a real capture exists, the coin reads "captured" and the Captured panel says "Demo payment: no funds move"; the Basescan
  link only appears once there's a real transaction.
- **Scripted timeline:** until the backend sends these events, the canvas runs from a scripted event
  timeline kept in one file, so it can be swapped for real backend state without touching the UI.
  Per-step hold times are demo pacing only.

### Removed
Controls page, reconciliation table, side chat panel, payments table, the old escrow bar, the old
4-branch canvas (free fix / change order / grey area), and all DocuParse/Northwind/invoice content. (Old code for them is still in
`src/` and can be deleted.)

## Style rules (keep)
- Planhat-style white product: pure white, neutral greys, near-black text, regular weight everywhere,
  hierarchy by size and grey, hairline borders, small radii (3–4px), black primary buttons.
- Font: Helvetica Neue first, Geist fallback (Planhat's exact font is unconfirmed).
- Icons: our own SVG set in `src/Icons.tsx`, black on white tiles; color only for state. Official
  partner logos (Coinbase) only as official files via `logoUrl`.
- Plain-language labels: finance terms stay (books, change order/amendment, deferred revenue,
  reconciliation); engineering terms get rewritten (no rule codes, IDs or "idempotency" on screen).
- Motion (Emil Kowalski's rules): animate only on state changes, never on page load; transform and
  opacity only; strong ease-out for entrances, strong ease-in-out for movement
  (`--ease-out: cubic-bezier(0.23,1,0.32,1)`, `--ease-in-out: cubic-bezier(0.77,0,0.175,1)`);
  interruptible CSS transitions; always ship a reduced-motion version.
- Overall polish (Impeccable): text contrast ≥ 4.5:1, no decorative glows or side stripes, no
  hero-metric stat tiles, theme selection/scrollbars/focus rings.
- Useful skills to install in Claude Code: emilkowalski/skill (animate, review-animations) and
  pbakaus/impeccable (polish, critique). Install them per their READMEs.


## References
See `references/README.md`: Planhat and Attio frames, the orb reference, redrum's flow diagram,
Lucas's notes, the 21st.dev component prompts, and the old built preview.

## Agreed engineering rules from Nikita's checklist (affect the UI)
Written before the data-broker switch (it says PDFs); adapted here.
- **A model recommendation alone never authorizes a rerun or a payment.** Deterministic contract checks
  plus the agreed policy decide; the UI shows which check or policy line allowed each action.
- **Citations.** Clicking a citation opens the exact source: dataset ID + version, sheet, row and column
  (cells), or the interview transcript message ID. If the target can't be found, show that plainly.
  First integration checkpoint: Lucas clicks one of Jeff's findings and sees the exact cited cell/quote.
- **Versions.** Every delivery, evidence set and proposal has a version. A new delivery or evidence
  version makes earlier checks and acceptance stale. The UI shows which version each decision is bound
  to; acting on a stale version returns 409 Conflict and the UI says "this changed, review again".
- **Review clock.** Delivery time and the 48h deadline come from the server; the browser never decides
  capture. Each regenerated delivery gets its own review window. A dispute blocks capture.
- **Questions and human review.** An investigation can pause waiting for the customer's answer. Escalation
  needs a real destination: Human's review view, showing the question, evidence, and their actions (approve,
  reject, ask for more, send up).
- **Payments wording.** Show mock / submitted / uncertain / confirmed honestly until the real x402 path
  works. Rules: no charge for raising a complaint, disputes block capture, a failed free rerun escalates
  to a person.
- **API.** Start with polling, not live streaming. Example JSON first for: order details, artifact
  retrieval, acceptance, disputes, question answers, with lifecycle state, current version, review
  deadline, available actions and payment mode.

**Conflict to resolve:** redrum's dispute rule says "evidence proves the customer wrong → charge for
additional processing", but Nikita's list says "no additional complaint debit". Recommended: never
charge for a wrong complaint; only charge when the customer chooses an amendment (new scope, new price,
approved by them), as in the green lane.

## Hyphenate checklist: learns, runs, escalates, learns from escalation, saves to books
- Learns: the interview turns the conversation into Data contract v1. Show it.
- Runs: the pipeline runs on its own: produce, check, deliver, capture.
- Escalates: amber goes to Human; a failed free rerun goes to Human.
- Learns from escalation: Human's decision becomes contract v2 and a rule update. **Prove it in the demo:**
  after their decision, replay the same yoga dispute and show it now resolves automatically.
- Saves to books: Books step with real double-entry entries in our ledger.
- Real systems: our real rails are x402 / Coinbase on Base Sepolia and our own ledger. POS and payroll
  are not part of order-to-cash and are out of scope. Optional stretch: also post the journal entries to
  an accounting sandbox (e.g. QuickBooks) if there's time.

## Open items for the team
1. **Data shapes (Nikita + Jeff, Lucas for UI).** `src/fixtures.ts` is the old invoice version. New
   shapes needed: DataContract + lines, CheckResult, Dispute, Verdict (agree / disagree / grey),
   Amendment, Payment (authorized / captured + tx id), Evidence (interview quote, sheet cell, vendor
   category), RuleUpdate. Draft them, then agree as a team.
2. **Events.** The canvas is driven by backend state changes, polled at first (live streaming later),
   e.g. step_started, check_passed / check_failed, evidence_found, verdict, payment_authorized,
   payment_captured. Confirm names.
3. **Demo data.** Synthetic SF fitness audience dataset with ZIP 94110 missing, plus the vendor
   category list (yoga under "Wellness") and the interview transcript.
4. **Real payments.** x402 / Coinbase for Agents on Base Sepolia so the Basescan link is real.
5. **Stack.** Redrum's doc said Next.js + shadcn/ui; this preview is Vite + plain CSS. Moving to Next.js
   is easy; keep our own styling.

## Suggested first prompt for Claude Code
"Read HANDOFF.md. Then: (1) draft the new data shapes in a new `src/contract.ts` and sample data for
the three lanes, (2) replace the old canvas with a three-lane run canvas driven by a simple event
timeline, (3) add the orb mascot with the coin. Keep the style rules. Don't build the customer view
yet."

## Decisions (grill with Lucas, Oct 24 2026)

### Context
The data-broker pivot is agreed by the whole team; the backend still runs the invoice domain.
Judging is Sunday morning, about 30 hours from Saturday 1:30 AM.

### What is real on stage
Only the amber lane's verdict and the final x402 capture are live; the shared path, red and green replay recorded events.
The amber verdict comes from the live agent; the 3-ending switch becomes a rehearsal and fallback replay.
Summit's buying agent is a scripted client that calls the real backend API, labeled as scripted.
During the amber investigation the agent asks Summit one question; the scripted answer keeps it grey, so it goes to Human.
Human rules inside the zoomed "Human reviews" step (approve, reject, ask for more, send up); a teammate clicks on stage.
If the live run stalls or errors, the canvas shows the failure and the presenter clicks "Play recorded ending".
After the grey dispute resolves, a visual step shows Human's rule now decides this case automatically; a live rerun is decided later.

### Data and events
The "data contract" is the buyer-facing name; functionally it is a checklist whose boxes tick as each delivery passes its checks.
Live events reach the canvas by polling GET /runs/{id}/events?after=<seq> about once a second, not server-sent events.
Recorded events stay in the browser (sample.ts); live amber events append to the same fold from the dispute onward.
Versions bind only human or buyer actions (Human's ruling, acceptance, amendment approval): they send {deliveryVersion, evidenceVersion} and get 409 when stale.
Evidence carries a source reference ({step, messageId} or {dataset, version, row, column}); clicking a citation flies the camera to that source.
Messages carry attachments by reference (checklist, evidence); contract lines are drafted live during the interview and render as the 21st.dev checklist inside the chat.
Every event that acts carries allowedBy (a check line or a policy line), shown as one quiet line in the step detail.
Each delivery has its own server review deadline, shown on its Deliver step; capture follows acceptance.
Pydantic models are the source of truth; contract.ts is the proposal and is deleted once the generated types land.

### Payments
x402 with a held signature: "authorized" means Summit signed an EIP-3009 authorization, not escrowed funds, and the UI says so.
We submit that authorization at capture, which is the one real Basescan transaction.
Payment states on screen: signed, submitted, confirmed, uncertain, and mock until the real path works.
Nikita decides when and how the real authorization is signed; recommendation: a setup script pre-stages the live order and signature before the demo.

### UI
Lanes are "what if" branches under "Three ways a dispute can go"; red and green are tagged Recorded, amber is tagged Live.
Margin after cost appears inside Books only; the first production run is assumed to cost $6 (sample value).
The shared Check shows a small self-fix: ZIP 94129 is under 50, held back for privacy, rechecked, and passes; held-back ZIPs stay in the file as "held back".
The customer view is minimal, built in parallel, and reuses the same chat component as the zoom-ins.

### Stack
The canvas moves into frontend/; Next.js stays as a thin shell that only proxies /api to the backend; ui/ is retired after the port.

### Build order (Lucas, Claude building)
1. Port the canvas into frontend/.
2. Features that work on recorded data: rich chat with the live-drafted checklist, inline citations with camera fly, lane tags, deliver deadlines, Books margin, privacy self-fix, payment states, the learned step, Human's actions, allowed-by lines.
3. Live seam: poll events into the fold against a stub until Nikita's endpoint lands.
4. Customer view in parallel once the chat component exists.

### Asks
Nikita: events endpoint with a seq cursor; Human and acceptance mutations with version binding and 409; x402 sign-and-settle on Base Sepolia; Pydantic models for the RunEvent shapes.
Jeff: amber investigator that asks one question and returns agree, disagree or grey with citations to message IDs and dataset cells; saved rules are checked before any model call.

## Decisions (grill with Lucas, Oct 24 2026, afternoon)

### Demo
One order is the demo, not three cases. Redrum's flow: interview, contract, produce, deliver, Summit objects, the agent proves by contract with cited evidence, Summit accepts, captured.
Escalation is act two: a second order where a check the sources can't settle goes through two questions, Human, a clarification and the free correction. Shown if time allows or a judge asks.
The moment the video opens with is the agent defending the decision: the objection answered with the interview line and the contract line, the citation jumping to the message, then capture.
"Improves" is the recorded "Next time" replay after Human's clarification; the backend's incident record for its improvement loop is explained in words.
The presenter advances Summit's three moves (approve the contract, object or accept, accept) by clicking on the customer view; everything between runs on its own.
A judge can type their own objection; the backend investigates it against the accepted spec and the model answers with code-checked evidence.
The All-cases map and the grey-area ending switch leave the screen; recorded mode stays as the fallback if the backend dies.

### Backend facts behind it
Jeff's broker profile on main is the backend: the UNKNOWN verdict, two bounded questions and the controller task already exist, and a source revision accepted by both sides as a clarification lets the free correction pass.
Jeff agreed to a bounded model verdict with the existing money controls; its event will be mapped when it lands.
Measured live with scripted parties: redrum's flow 28 seconds unattended, the escalation flow about 75 seconds.

## Merge with main, Oct 24 evening

Main brought Nikita's aggregate brokerage: generated wire types (`lib/runs.generated.ts`, `lib/run/contract.ts` now re-exports them), a form-based intake `components/run/live-run.tsx` against `/api/live` (server-only bridge, needs `BROKER_LOCAL_DEMO=1` and distinct `INTERNAL_API_TOKEN` / `REVIEWER_API_TOKEN`), and payment-state folding.
Resolution, per the demo decision above: the canvas stays at `/` and is the demo; Nikita's intake is mounted at `/live`.
The feed that polls Jeff's broker is still called `live` (main had renamed it `fixture`), and the header toggle still says Live.
`caption` is a canvas-only event the translator narrates with; it is not on the wire, so `contract.ts` adds it to the generated union.
`npm run generate:check` reports drift in `docs/openapi.json` on Python 3.13 only because the 422 reason phrase changed ("Unprocessable Content"); it is not a contract change.

## Jeff's dispute assessment (PR #12, flag `ENABLE_BROKER_DISPUTE_ASSESSMENT`, off by default)

The translator maps `dispute.assessed` from his published contract: justified → agree, not_justified → disagree, unclear → the grey-area detour.
The verdict step reads "Decided by model, verified by code" only when `decided_by` is `model`; rules or unresolved never read as model-decided.
Each quoted reference becomes an evidence card on Investigate, attached to the agent's message; the verdict carries the reason and the reference ids.
Until his branch regenerates the wire types with `model` in `decidedBy`, the words carry the provenance and the typed field stays `rules`.
