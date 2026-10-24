# Frontend — Lucas

No frontend application is scaffolded yet. Lucas owns Next.js/TypeScript/shadcn UI,
PDF display and highlight overlays, review controls and frontend deployment.

Jeff supplies PDF coordinates. Lucas visually reviews generated PDFs and classifies
correct, operationally failed, disputed and ambiguous examples with Rehan. Red means
an engine failure, not an imperfect generated PDF.

Consume the existing [polling API](../docs/API.md) using current revisions and evidence
bindings. Poll every two seconds; refetch on 409. Show server-driven ten-minute deadlines,
questions/answers, evidence-backed closure, free regeneration, human review and quotes
for unpriced additional processing. Every payment remains explicitly mock.

Do not expose the worker token or implement payment authority in the client. Add package
manager, dev/test and deployment commands here when the UI exists. Follow the
[shared checkpoint](../docs/INTEGRATION_CHECKPOINT.md).
