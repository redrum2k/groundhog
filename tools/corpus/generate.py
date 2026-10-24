"""Offline synthetic fixture producer. Never import this module from runtime agent code."""

from datetime import date
from decimal import Decimal

from app.catalog.documents import pdf_document
from app.contracts.catalog import Source


def supplier_pdf(
    supplier, start, *, unreadable=False, effective="2026-10-01", price_change=False, note=None
):
    ids = [f"S{i:02d}" for i in range(start, start + 12)]
    lines = [
        f"Supplier: {supplier} / Edition: 2026-A / Effective: {effective}",
        "Records: " + ", ".join(ids),
    ]
    for i, product_id in enumerate(ids, start):
        net = Decimal("0.50") + Decimal(i % 5) * Decimal("0.50")
        price = str(Decimal(20 + i % 7 * 5))
        if unreadable and 17 <= i <= 22:
            price = "UNREADABLE"
        elif price_change and i == 13:
            price = "35"
        lines.extend(
            [
                f"{product_id} | storage | Storage box {i}",
                f"net={net} kg | shipping={net + Decimal('0.80')} kg | unit=USD {price}",
            ]
        )
    if note:
        lines.append(note)
    return pdf_document("Supplier catalog", lines)


def seed(service):
    registered = []
    for index in range(4):
        supplier = f"supplier-{chr(97 + index)}"
        source = Source(
            source_id=supplier,
            version=1,
            corpus_id="storage-2026",
            supplier_id=supplier,
            edition="2026-A",
            effective_date=date(2026, 10, 1),
            artifact=service.store.put(
                supplier_pdf(supplier, index * 12 + 1, unreadable=index == 1)
            ),
            authority="registered_supplier_publication",
            authority_record=f"synthetic-registry:{supplier}:edition-A",
        )
        service.registry.register(source)
        registered.append(source)
    clean = registered[1].model_copy(
        update={"version": 2, "artifact": service.store.put(supplier_pdf("supplier-b", 13))}
    )
    service.registry.register(clean, selectable=False)
    # A registered edition with changed facts is available only as a proposed amendment.
    changed = clean.model_copy(
        update={
            "version": 3,
            "artifact": service.store.put(supplier_pdf("supplier-b", 13, price_change=True)),
        }
    )
    service.registry.register(changed, selectable=False)
    conflict = clean.model_copy(
        update={
            "version": 4,
            "artifact": service.store.put(supplier_pdf("supplier-b", 13, effective="2026-11-01")),
        }
    )
    service.registry.register(conflict, selectable=False)
    return {
        "sources": registered,
        "repair": clean,
        "substantive": changed,
        "date_conflict": conflict,
        "unregistered": service.store.put(
            supplier_pdf("supplier-b", 13, note="Copy submitted by customer.")
        ),
    }
