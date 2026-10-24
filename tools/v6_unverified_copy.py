"""Readable synthetic source copy with different actual bytes, deliberately unregistered."""
import argparse
from pathlib import Path

from app.catalog.documents import pdf_document

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
raw = pdf_document("Customer-submitted supplier copy", [
    "Supplier: supplier-probe / Edition: 2026-A / Effective: 2026-10-01",
    "Records: S01, S02, S03",
    "S01 | storage | Small storage box", "net=1.00 kg | shipping=1.80 kg | unit=USD 30",
    "S02 | storage | Medium storage box", "net=1.50 kg | shipping=2.20 kg | unit=USD 25",
    "S03 | storage | Large storage box", "net=3.00 kg | shipping=4.00 kg | unit=USD 20",
    "Customer-submitted copy; no registry authority asserted.",
])
with args.output.open("xb") as handle:
    handle.write(raw)
print("Created unregistered synthetic PDF fixture")
