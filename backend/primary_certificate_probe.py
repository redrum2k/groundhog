"""Separate development probe; never overwrite/rerun the frozen P1-P6 cohort."""

import primary_followup_eval as harness

harness.OUTPUT = harness.OUTPUT / "certificate-probe"
harness.CASES = (
    dict(
        id="P7",
        expanded=False,
        text="Standalone yoga does not belong in the agreed fitness scope.",
        expected="PASS",
        basis="Accepted explicit exclusion plus either complete independent proof certificate.",
        development_followup=(
            "New order and paraphrase after P3's observed citation-completeness failure. "
            "P3's raw PASS/effective UNKNOWN remains unchanged. This is development, "
            "not an independent held-out accuracy estimate or a regraded P3."
        ),
    ),
)

if __name__ == "__main__":
    harness.main()
