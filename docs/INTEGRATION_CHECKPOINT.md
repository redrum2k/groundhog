# First integration checkpoint

Target: **90 minutes after the team starts the split**, with a check-in at 30 minutes.
This is a relative work target, not an invented event deadline or a scheduled automation.
If source PDFs are not ready at 30 minutes, reduce to one invoice and one delivery PDF.

## Shared fixture

Start with four unique single-currency invoices in six short source PDFs: include a
repeated invoice and conflicting versions. Deliver a register plus exceptions section
as a PDF, retaining structured records and page-region mappings. Use neutral IDs and
filenames for runtime assets; no correctness/mutation labels in the evidence package.

Jeff produces the source/delivery PDFs and mappings. Lucas visually checks that record
links highlight the right text and classifies outputs offline. Rehan independently
records expected results. Nikita loads the accepted order and provider delivery through
the mock API. The actual fixture assets are still to be produced by their owners.

## By the first checkpoint

- Jeff: one evidence package and one cited compliant result covering all eight criteria.
- Lucas: a locally running source/delivery PDF view; clicking one citation opens the exact
  artifact/page and highlights the region. Record actual crop/rotation behavior.
- Nikita: order creation opens mock authorization, publication starts a ten-minute review,
  polling works, and the cited verdict books one clearly mocked base ledger entry.
- Rehan: independently check the displayed PDF against source invoices; record discrepancies.

Success: one complete fixture goes from accepted order to inspected, evidence-backed
mock closure; a deliberately stale acceptance/dispute request returns 409.

## Next checkpoint, after the first works

Add a supported defect with one free regeneration; a refuted complaint with the agreed
fee (and a no-fee quote variant); two question/answer rounds ending in human review; and
an engine-failure example displayed red. Test cutoff using an injected clock in automated
tests rather than waiting ten minutes. Keep the actual product window at 600 seconds.

No frontend/model/provider implementation is claimed by the existing workflow tests.
No paid calls, transaction broadcasts, or deployment are part of this checkpoint setup.
