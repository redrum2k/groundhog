# Frontend ownership — Lucas

Follow root AGENTS.md, HACK.md and docs/API.md. Lucas owns UI implementation and
visual classification of generated PDFs. Jeff supplies coordinates; Lucas displays
PDFs and overlays normalized highlight rectangles. Confirm crop/rotation on the fixture.

Poll the API every two seconds. Submit expected_revision, expected_binding and a stable
idempotency_key. On 409 refetch current state; do not silently resubmit a stale action.
Use server_time/review_deadline for ten-minute countdowns and available_actions for controls.
Red is operational failure. Show evidence gaps, human review and mock payment status
separately. Explain agreed extra charges and require quote acceptance when no fee exists.

Keep INTERNAL_API_TOKEN and backend credentials out of browser code/NEXT_PUBLIC variables.
Worker endpoints are not frontend endpoints. Store offline grading labels with the evaluator,
not in investigator evidence. Document dev/test commands when scaffolding the UI.
