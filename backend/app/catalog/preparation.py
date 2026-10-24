"""Internal request-scoped source selection; never a customer/API input."""

import json

from pydantic import AwareDatetime

from app.contracts.catalog import Source
from app.contracts.data_product import Frozen
from app.orders.service import DomainError


def preparation_fingerprint(encounter_id):
    # The content-addressed encounter binds the complete preparation input.
    return json.dumps({"operation": "prepare_source", "encounter_id": encounter_id}, sort_keys=True)


class PreparedSources(Frozen):
    encounter_id: str
    registry_sources: tuple[Source, ...]
    sources: tuple[Source, ...]
    valid_until: AwareDatetime

    def validate_current(self, registry_sources, now):
        if self.registry_sources != registry_sources or now >= self.valid_until:
            raise DomainError(409, "prepared source registry/authority changed or expired")


def request_sources(service, draft, db):
    current = service.registry.manifest(draft.corpus_id, db)
    row = db.execute(
        "SELECT data FROM catalog_records WHERE kind='prepared_sources' AND id=?",
        (draft.request_id,),
    ).fetchone()
    if not row:
        return current
    prepared = PreparedSources.model_validate_json(row[0])
    prepared.validate_current(current, service.clock())
    return prepared.sources
