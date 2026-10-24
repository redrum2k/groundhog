# Synthetic supplier catalog tooling — Jeff

`generate.py` creates four reproducible supplier PDFs with 12 products each, including an
unreadable price region, a registered same-edition repair and substantive/unresolved alternatives.
This producer is outside the runtime app package. `tools/offline_journey.py` seeds a provider
registry and passes only actual artifacts/approved registry metadata to runtime; it never supplies
an expected verdict. Extraction sidecars derive from PDF parsing, not generator records.

Use README.md's offline commands. Output goes to ignored artifacts directories. Runtime source
names are neutral supplier IDs; no grading labels or mutation recipes enter evidence. The
fixture authority records are synthetic provider attestations, not real supplier confirmations.
Jeff owns extending corpus diversity, extraction/normalization/provenance, PDF layout/coordinates
and generation. Rehan independently reviews labels; those remain outside runtime.
