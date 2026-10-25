"""Explicitly synthetic input examples for the local demonstration, never runtime rules."""

from datetime import timedelta

from app.agents.source_knowledge import AuthorityHead, SourceScope, VendorExport, VendorRow
from app.contracts.source_learning import BundleUpload, PartitionInput
from app.datasets import SF_KEYS


def example_bundle(now, batch=1, *, conflict=False):
    parts = []
    for index, columns in enumerate((("v_count", "v_devices"), ("p_devices", "p_adults"))):
        rows = []
        for offset, key in enumerate(SF_KEYS):
            if offset % 2 != index:
                continue
            values = (300 + offset * 11 + batch * 23, 800 + offset * 13 + batch * 31)
            if index:
                values = values[::-1]
            rows.append(
                VendorRow(
                    zip=key,
                    area="Mission" if key == "94110" else "San Francisco",
                    values=dict(
                        zip(columns, (None, None) if key == "94129" else values, strict=True)
                    ),
                    status="suppressed" if key == "94129" else "released",
                )
            )
        raw = VendorExport(
            source_id=f"sf-aggregate-v1:learning:partition-{index}",
            source_family=f"local-demo-partition-{index}",
            schema_version=1,
            version=batch,
            publisher="DatumCo",
            edition="synthetic-partition-schema-2026-10",
            scope=SourceScope(geography="San Francisco"),
            columns=columns,
            rows=tuple(rows),
        )
        head = AuthorityHead(
            publisher="DatumCo",
            source_id=raw.source_family,
            source_version=1,
            schema_hash=raw.schema_hash,
            epoch="controlled-local-dictionary-1",
            scope=raw.scope,
            valid_until=now + timedelta(hours=24),
            status="conflict" if conflict else "active",
        )
        parts.append(PartitionInput(export=raw, authority=head))
    return BundleUpload(idempotency_key=f"example-{batch}-{conflict}", partitions=tuple(parts))
