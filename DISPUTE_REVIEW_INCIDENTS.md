# Follow-up review incidents

Before any follow-up paid calls, independent read-only review identified an overly
broad complaint recognizer: an observation-age complaint could be checked against
export time, a different alleged limit could be ignored, and a named location could
be ignored. This was a genuine implementation defect, not an API-provider failure.
The fix requires observed_at, the exact accepted age threshold, and exact named
geography/entity identity. Unsupported paraphrases abstain. Regression coverage is
in tests/broker/test_dispute_assessment.py. Citation membership still is not entailment.

First local slice test run failed because `kind` collided with the event helper's
positional event-name parameter. Renamed that parameter to `event_type`; the existing
event envelope is unchanged. All first-run failures remain in session evidence;
none were presented as successful evaluations or retried model attempts.

The frozen justified cases encounter an existing protective gate: production checks
detect corrupt JSON and reserve correction before dispute eligibility. They must be
reported BLOCKED through the public API, not made to pass by bypassing verification.
