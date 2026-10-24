import importlib.util
from pathlib import Path

from app.catalog.documents import pdf_document


def test_offline_grader_detects_shared_false_pass_without_production_verifier():
    path = Path(__file__).resolve().parents[3] / "tools/v6_final_grade.py"
    spec = importlib.util.spec_from_file_location("offline_v6_grader", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    records = [
        {
            "product_id": "S801",
            "name": "Box S801",
            "supplier_id": "supplier-test",
            "concept": "net_unit",
            "weight_kg": "1.125",
            "price_USD": "18.65",
            "source_id": "supplier-test",
            "source_version": 1,
            "source_page": 1,
            "source_sha256": "a" * 64,
        },
        {
            "product_id": "S802",
            "name": "Box S802",
            "supplier_id": "supplier-test",
            "concept": "net_unit",
            "weight_kg": "1.875",
            "price_USD": "38.95",
            "source_id": "supplier-test",
            "source_version": 1,
            "source_page": 1,
            "source_sha256": "a" * 64,
        },
    ]
    oracle = {
        "expected_records": records,
        "reference_arithmetic": [
            {"product_id": "S801", "included": True},
            {"product_id": "S802", "included": True},
        ],
    }
    lines = [
        "SELECT S801 | Box S801 | supplier-test",
        "net_unit=1.125 kg | unit=USD 18.65",
        "source=supplier-test@1 p1 sha=aaaaaaaaaaaa",
        "SELECT S802 | Box S802 | supplier-test",
        "net_unit=1.875 kg | unit=USD 38.95",
        "source=supplier-test@1 p1 sha=aaaaaaaaaaaa",
    ]
    assert module.independently_correct_pdf(pdf_document("Cited product shortlist", lines), oracle)
    assert module.independently_correct_pdf(
        pdf_document("Cited product shortlist", lines[3:] + lines[:3]), oracle
    )
    lines[1], lines[4] = lines[4], lines[1]
    assert not module.independently_correct_pdf(
        pdf_document("Cited product shortlist", lines), oracle
    )
