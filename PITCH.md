# Groundhog — Devpost video script

Prepared October 25, 2026. Target: roughly 2–2½ minutes including pauses. This is
the team's selected correct-delivery defense story, not an executed qualification.
Use the primary aggregate app at `/` or `/live`, synthetic sources and explicit
mock funding. Record the actual finding before narrating its conclusion.

Demo scope: one request-to-cash journey within the three-minute slot. Reviewer
memory and source learning remain background implementation work, outside the
demo. Do not enter reusable guidance, open learning controls, or start a second
order to demonstrate improvement. Human review remains the uncertainty branch;
it does not need to teach the agent. The story is delivery, evidence-backed
judgment and the resulting permission to collect or hold funds.

## Full script

| Beat | Screen / driver action | Spoken narration |
| --- | --- | --- |
| Opening · 0:00–0:15 | Show Groundhog's request screen immediately. | “When a customer disputes a custom dataset, the broker has to connect what was promised, what was delivered, and whether it can collect. Groundhog handles that order-to-cash workflow for Bayline Data.” |
| Request · 0:15–0:28 | In Customer view, type `SF adults 25–34 interested in fitness, counts by ZIP.` | “We're playing Summit Fitness, buying an audience dataset. We ask for San Francisco adults aged 25 to 34, interested in fitness, with counts by ZIP.” |
| Clarification · 0:28–0:40 | When asked, type `Gym membership or fitness-app use.` | “Fitness could mean several things. Groundhog asks us to define it, so we agree on gym membership or fitness-app use before production starts.” |
| Agreement and funding · 0:40–0:57 | Prepare the quote if prompted. Show geography, age, definition and coverage; accept the agreement, then use the displayed Simulate funding control. | “The agreement fixes the scope and price. We accept and fund the order. This demo uses synthetic data and simulated payments; no real money moves.” |
| Production · 0:57–1:12 | Show the Run canvas, completed checks and actual CSV preview. | “Groundhog produces the dataset. A separate verifier opens the actual files and checks them against the agreed requirements and accepted sources. The delivery is now ready for review.” |
| Objection · 1:12–1:25 | Promptly click Object; enter `Oakland should be in there.` and Send complaint. | “Now we challenge it: ‘Oakland should be in there.’ Groundhog investigates the complaint against the agreement and delivery evidence, while collection stays on hold.” |
| Evidence reveal · 1:25–1:45 | Open Finding and its actual agreement/source citations. Keep the relevant geography visible. Speak this conclusion only if the recorded finding supports it. | “Here's the agreement we accepted: San Francisco. Groundhog cites that scope and the supporting evidence to explain why Oakland wasn't owed. It defends the delivery, and the original agreement stays intact.” |
| Acceptance and settlement · 1:45–2:02 | Click Accept verified delivery when available. Show the resulting confirmed mock capture and payment record, waiting or cutting forward honestly if needed. | “We accept the verified delivery. The system checks the remaining payment conditions, then records the simulated collection. The finding alone didn't authorize payment.” |
| Close · 2:02–2:15 | Hold on the completed order and inspectable financial result. | “Groundhog connects the customer's request, the delivered data, and the evidence behind collection—giving the broker a clear record of why it can get paid.” |

Timing is an editing target, not a promise of backend latency. Preserve the order's
causal sequence; label sped-up waits. Use one actual order for the main story.

## Recording cues

- Driver operates Customer view and switches to Run/Finding; narrator follows the
  visible result. Team members have not been assigned these recording roles yet.
- Open the complaint promptly after delivery: the review window is 60 seconds.
  Record the interactions first and add voiceover afterward if narration risks
  letting the window expire. Do not present expiry capture as buyer acceptance.
- Keep the complaint exactly scope-only. An additional allegation requires its
  own investigation. Do not accept an Oakland expansion for this main story.
- Frame the evidence reveal tightly enough to read the agreement and citation.
  Do not narrate an expected verdict over an unresolved or different actual result.
- Show confirmed mock collection before saying it was recorded; submitted or
  uncertain is not completed. Keep the simulated-payment label visible.
- For a shorter cut, enter `SF adults 25–34, gym membership or fitness app use,
  counts by ZIP.` and omit the clarification beat.
- Keep escalation available for Q&A; this selected order does not demonstrate it.
  Self-improvement is not a demo beat or a claimed outcome. If asked, explain that
  reviewer guidance can be persisted and retrieved, but reliable improvement from
  that feedback has not been demonstrated. Do not claim live model inference
  unless the recorded run's provenance supports it.

## Thirty-second version

“Groundhog handles order-to-cash for a data broker. Summit Fitness ordered a
San Francisco dataset, then complained that Oakland was missing. Here, Groundhog
opens the accepted agreement, cites the San Francisco scope, and explains why
the delivery meets that promise. The customer accepts; the system checks payment
eligibility and records collection. This demo uses synthetic data and simulated
payments. The value is an inspectable connection between the promise, the work,
and permission to collect.”

## Concise Q&A

**Who is the user, and what validates the need?** A data broker coordinating custom
deliveries, customer objections and collection. This is our commercial hypothesis;
we have not established customer demand or measured savings.

**What did you build?** The agreement-to-delivery workflow, independent artifact
checks, evidence-linked investigation, durable order state and payment eligibility
controls. It uses Python/FastAPI/SQLite and Next.js/React; configured model providers
supply inference, and the separate testnet integration uses Base Commerce Payments.

**What's simulated?** The company roles, source data and payments in this video.
The application processes the order; whether a particular finding used a model or
deterministic logic must be read from that run's provenance.

**What was the hard technical problem?** Keeping interpretation separate from
financial authority: a finding must refer to current evidence, and collection
still needs verified delivery, resolved disputes and valid payment authorization.

**Why not a chatbot plus a payment button?** The product persists the accepted
terms, verifies actual delivery files and binds financial actions to the order's
current state. Its contribution is connecting those responsibilities in one flow.

**What breaks first at scale?** We have not load-qualified production use. Human
exceptions and source-owner questions are plausible operating bottlenecks, and
production identity and tenant isolation remain outside this demo.

**What would another week buy?** Proposed next work: independently authored dispute
cases and a small broker pilot measuring total review time, unnecessary escalations
and collection delays. These are next steps, not completed results.

**Which track does this address?** The Hyphenate story is a bounded finance task
bundle with evidence-backed operating judgment. The repo separately integrates Base
Commerce Payments; this mock-payment video does not establish testnet execution or
sponsor eligibility. Do not claim a Microsoft integration without showing one.

**Why not simply include Oakland?** That changes the agreed geography. Additional
work requires a separate offer and explicit acceptance/funding; a complaint is
not consent to another purchase.

**Can the system collect without this acceptance click?** Policy also permits
eligible undisputed review expiry, subject to all other gates. This video's chosen
path shows explicit customer acceptance before collection.
