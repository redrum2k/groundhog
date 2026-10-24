"""Materialize independently authored worlds without executing any final application arm.

Only visible-cases.json is a runtime input. Oracle/blueprints remain offline.
Files use exclusive creation; any correction requires a separately labeled capsule.
"""

import argparse
import base64
import hashlib
import io
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pdfplumber

from app.catalog.documents import pdf_document
from app.improvement.catalog_probe import VisibleCatalogCase


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def pdf_lines(raw):
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        return [line for page in pdf.pages for line in (page.extract_text() or "").splitlines()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    review = json.loads(args.review.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    visible, gold, source_audit = [], [], []
    defaults = review["baseline_protocol"]["blueprint_conventions"]
    columns = defaults["row_columns"]
    for blueprint in review["twelve_world_blueprints"]:
        identifier = blueprint["id"]
        world = blueprint["visible_blueprint"]
        corpus = world.get("corpus_id", defaults["default_corpus_id"])
        # The model proposal's actual development scope is immutable. This mapping
        # is declared before final execution/selection, not a candidate edit.
        corpus = "storage-2026" if corpus == "final-main" else "storage-2026-sibling"
        supplier = f"supplier-{identifier}"
        publications, publication_rows = [], []
        for pub in world["publications"]:
            edition = pub.get("edition", world["edition"])
            effective = pub.get("effective_date", world["effective_date"])
            rows = [dict(zip(columns, row, strict=True)) for row in world["rows"]]
            for slot, value in pub.get("replace", {}).items():
                pid, field = slot.split(".")
                next(row for row in rows if row["product_id"] == pid)[field] = value
            lines = [
                f"Supplier: {supplier} / Edition: {pub.get('header_edition', edition)} / Effective: {pub.get('header_effective_date', effective)}",
                "Records: " + ", ".join(row["product_id"] for row in rows),
            ]
            for row in rows:
                pid = row["product_id"]
                lines.extend([f"{pid} | storage | Box {pid}",
                    f"net={row['net_kg']} kg | shipping={row['shipping_kg']} kg | unit=USD {row['unit_price_USD']}"])
            raw = pdf_document("Supplier catalog", lines)
            extracted = pdf_lines(raw)
            # Inspect materialized actual bytes, not merely inputs to a renderer.
            if any(line not in extracted for line in lines):
                raise ValueError(f"Materialized source text mismatch: {identifier}")
            publications.append({
                "source_id": supplier, "supplier_id": supplier, "version": pub["version"],
                "edition": edition, "effective_date": effective,
                "authority": pub["authority"],
                "authority_record": None if pub["authority"] == "unverified" else f"synthetic-registry:{identifier}:{pub['version']}",
                "selectable": pub["version"] == 1,
                "pdf_base64": base64.b64encode(raw).decode(),
            })
            publication_rows.append(rows)
            source_audit.append({"case_id": identifier, "version": pub["version"], "sha256": sha(raw),
                                 "actual_text_lines": extracted, "source_cells": rows})
        bad_output = None
        if "provider_output_lines" in world:
            raw_source = base64.b64decode(publications[0]["pdf_base64"])
            lines = [line.replace("{sha12}", sha(raw_source)[:12]) for line in world["provider_output_lines"]]
            raw = pdf_document("Cited product shortlist", lines)
            if any(line not in pdf_lines(raw) for line in lines):
                raise ValueError(f"Materialized faulty delivery text mismatch: {identifier}")
            bad_output = base64.b64encode(raw).decode()
        case = VisibleCatalogCase.model_validate({
            "id": identifier, "corpus_id": corpus,
            "prompt": world.get("prompt", defaults["default_prompt"]), "publications": publications,
            "provider_output_base64": bad_output,
            "historical_procedure": world.get("historical_procedure", False),
            "observation_seconds": 121,
        })
        visible.append(case.model_dump(mode="json"))
        oracle = blueprint["oracle"]
        item = {"case_id": identifier, "family": blueprint["family"], "authored_oracle": oracle}
        if oracle["finance_profile"] == "C":
            # Independent reference arithmetic, not production disposition/output_lines.
            restored = any(row["net_kg"] == "UNREADABLE" or row["shipping_kg"] == "UNREADABLE"
                           or row["unit_price_USD"] == "UNREADABLE" for row in publication_rows[0])
            # Immaterial unknowns remain on the accepted original source.
            restore = restored and identifier not in ("w147",)
            rows = publication_rows[1 if restore else 0]
            source_pub = publications[1 if restore else 0]
            records = []
            selected, numeric_audit = [], []
            for row in rows:
                pid = row["product_id"]
                shipping = identifier == "w027"
                weight = Decimal(row["shipping_kg"] if shipping else row["net_kg"])
                weight_ok = weight <= Decimal("2.5") if shipping else weight < Decimal("2")
                price = None if row["unit_price_USD"] == "UNREADABLE" else Decimal(row["unit_price_USD"])
                price_ok = price is not None and (price < Decimal("33.50") if shipping else price <= Decimal("40"))
                included = weight_ok and price_ok
                numeric_audit.append({"product_id": pid, "weight": str(weight), "price": str(price),
                                      "weight_ok": weight_ok, "price_ok": price_ok, "included": included})
                if included:
                    selected.append(pid)
                    records.append({"product_id": pid, "name": f"Box {pid}", "supplier_id": supplier,
                                    "concept": "shipping" if shipping else "net_unit",
                                    "weight_kg": str(weight), "price_USD": str(price),
                                    "source_id": supplier, "source_version": source_pub["version"],
                                    "source_page": 1, "source_sha256": sha(base64.b64decode(source_pub["pdf_base64"]))})
            expected = oracle.get("selected_ids", oracle.get("selected_ids_after_correction"))
            if selected != expected:
                raise ValueError(f"Independent arithmetic disagrees with authored oracle: {identifier}")
            item.update(expected_records=records, reference_arithmetic=numeric_audit,
                        expected_source_version=source_pub["version"])
        gold.append(item)
    files = {
        "visible-cases.json": visible,
        "oracle.json": gold,
        "source-byte-audit.json": source_audit,
        "protocol.json": {
            "primary_estimand": review["baseline_protocol"]["primary_estimand"],
            "baseline_protocol": review["baseline_protocol"], "reply_protocol": review["reply_protocol"],
            "authorship": review["oracle_authorship"],
            "scope_mapping": {"final-main": "storage-2026", "final-sibling": "storage-2026-sibling"},
            "qualification": "Structured synthetic interaction, independent model-authored blueprints plus offline Decimal/source-byte audit; not human audited",
            "arms": ["current_static", "competent_static", "functional_memory", "evolving_process"],
            "workflow_runs": 48, "case_count": 12, "observation_seconds": 121,
            "recurring_primary_category": "manual_evidence_acquisition",
            "unmeasured_categories": ["financial_reconciliation", "maintenance", "human_handling_time"],
            "retry_policy": "One final run per world/arm. No automatic application-model retries. Failures remain in denominator; infrastructure recovery requires separately retained attempts and cannot erase outcomes.",
            "resource_policy": {"maximum_usd_including_prior_attempts": 45, "request_count_ceiling": None,
                                "concurrency": 2, "cutoff": "2026-10-24T10:10:00-07:00"},
        },
    }
    hashes = {}
    for name, value in files.items():
        raw = (json.dumps(value, indent=2) + "\n").encode()
        with (args.output / name).open("xb") as handle:
            handle.write(raw)
        hashes[name] = sha(raw)
    manifest = {"kind": "V6_PREREVEAL_WORLD_CAPSULE", "created_at": datetime.now(UTC).isoformat(),
                "files": hashes, "independent_review_sha256": sha(args.review.read_bytes()),
                "materializer_sha256": sha(Path(__file__).read_bytes()),
                "final_outcomes_executed": False, "selection_performed": False}
    with (args.output / "manifest.json").open("x") as handle:
        json.dump(manifest, handle, indent=2)
    print(json.dumps({"output": str(args.output), "worlds": len(visible),
                      "manifest_sha256": sha((args.output / "manifest.json").read_bytes()),
                      "final_application_runs": 0}, indent=2))


if __name__ == "__main__":
    main()
