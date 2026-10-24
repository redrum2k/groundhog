"""Reuse the existing verified exporter for a distinct LOCAL primary delivery."""

from pathlib import Path

import export_dispute_followup as exporter

exporter.EVIDENCE = exporter.ROOT / "backend/artifacts/primary-followup"
exporter.EXTRA_EVIDENCE = (exporter.ROOT / "backend/artifacts/primary-amendment",)
exporter.DESTINATION = Path("D:/Downloads/OBJECTION_Primary_Semantics_Results_20261024.zip")
exporter.BASE = "62fe03542f18d9f7514550bcff25968ae2557c08"
exporter.REQUIRE_PUSH = False  # This task changes D: files; it does not publish new commits.

if __name__ == "__main__":
    exporter.main()
