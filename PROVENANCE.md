# Implementation provenance

The jobflow implementation is newly written against this repository's interfaces.
Behavioral references were inspected at revision
`5d2a50c2595014d3a6dba899270975d20b631b52`: exact source/version citations,
transactional events, current-time authorization, stable operation identity and
recovery. Their paths and target checks are recorded in `IMPORT_MANIFEST.json`.

No reference implementation source, vendored libraries, data, execution history or
credentials are copied into this application. Third-party packages remain ordinary
locked dependencies with their upstream notices. Test results describe this branch.
