import base64
from datetime import UTC, datetime, timedelta

import pytest

from app.contracts.broker import BrokerCommand, DraftCreate, SourceUpload
from app.contracts.data_product import Parameters
from app.contracts.models import Money
from app.data_products import FIELDS
from app.runtime.broker import Broker
from app.runtime.jobflow import DEMO_ACTORS, Jobflow
from app.storage.jobflow import canonical, uid

ACTORS = {actor.id: actor for actor in DEMO_ACTORS}
NOW = datetime(2026, 10, 24, 6, 0, tzinfo=UTC)


class Clock:
    def __init__(self):
        self.now = NOW

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


def source_bytes(**changes):
    values = dict(
        source_id="regional-census",
        version=1,
        geography="Bay Metro",
        boundary_version="2026-Q3",
        reference_period="2026-Q3",
        metric_name="median_household_income",
        metric_unit="USD_per_household",
        entity_unit="region",
        published_at="2026-10-20T00:00:00Z",
        exported_at="2026-10-24T00:00:00Z",
        rows=[
            dict(
                entity_id="region-001",
                region_id="R001",
                value=95000.0,
                observed_at="2026-10-10T00:00:00Z",
            )
        ],
    )
    values.update(changes)
    return canonical(values).encode()


def parameters(**changes):
    values = dict(
        freshness_basis="observed_at",
        max_age_days=30,
        as_of=NOW.isoformat(),
        geography="Bay Metro",
        boundary_version="2026-Q3",
        region_ids=["R001"],
        reference_period="2026-Q3",
        metric_name="median_household_income",
        metric_unit="USD_per_household",
        entity_unit="region",
        coverage_ids=["region-001"],
        max_missing_records=0,
        output_schema="market-v1",
        output_format="json",
        revision_policy="exact_accepted_versions",
        conflict_policy="UNKNOWN",
    )
    values.update(changes)
    return Parameters.model_validate(values)


def command(broker, record, role, verb, **kwargs):
    record = broker.view(ACTORS[role], record.id)
    return broker.command(
        ACTORS[role],
        record.id,
        BrokerCommand(
            idempotency_key=uid("command"), expected_revision=record.revision, verb=verb, **kwargs
        ),
    )


def enable_clarity(broker):
    """Explicit test template, not a claimed runtime-generated improvement."""
    from app.contracts.improvement import ImprovementVersion
    from app.storage.improvement import put

    with broker.store.connect(write=True) as db:
        if db.execute("SELECT 1 FROM im_records WHERE id='test-template'").fetchone():
            return
        version = ImprovementVersion(
            id="test-template",
            customer_id="northwind",
            product_id="aggregate_regional_market_intelligence",
            previous_version="intake-v1",
            required_fields=FIELDS,
            patch_ids=("explicit-test-fixture",),
            probe_ids=("not-runtime-learning",),
            approved_by="controller",
            approved_at=broker.clock(),
        )
        put(db, "version", version)
        db.execute(
            "INSERT OR REPLACE INTO im_active VALUES(?,?,?)",
            (version.customer_id, version.product_id, version.id),
        )


def accept_order(broker, *, raw=None, params=None, auth_seconds=3600, parent=None, clarity=True):
    if clarity:
        enable_clarity(broker)
    params = (params or parameters()).model_dump(mode="json")
    draft = broker.create_draft(
        ACTORS["customer"],
        DraftCreate(
            idempotency_key=uid("draft"),
            intent="Recent median household income for the Bay Metro regional market.",
            parent_order_id=parent,
        ),
    )
    draft = broker.upload(
        ACTORS["provider"],
        draft.id,
        SourceUpload(
            idempotency_key=uid("source"),
            expected_revision=draft.revision,
            filename="regional-source.json",
            content_base64=base64.b64encode(raw or source_bytes()).decode(),
        ),
    )
    for question in list(draft.questions):
        draft = broker.draft_command(
            ACTORS["customer"],
            draft.id,
            BrokerCommand(
                idempotency_key=uid("answer"),
                expected_revision=draft.revision,
                verb="answer_intake",
                question_id=question.id,
                value=params[question.field],
            ),
        )
    for field in list(draft.unresolved_fields):
        draft = broker.draft_command(
            ACTORS["controller"],
            draft.id,
            BrokerCommand(
                idempotency_key=uid("manual"),
                expected_revision=draft.revision,
                verb="clarify_intake",
                field=field,
            ),
        )
        question = next(q for q in reversed(draft.questions) if q.field == field)
        draft = broker.draft_command(
            ACTORS["customer"],
            draft.id,
            BrokerCommand(
                idempotency_key=uid("answer"),
                expected_revision=draft.revision,
                verb="answer_intake",
                question_id=question.id,
                value=params[field],
            ),
        )
    draft = broker.draft_command(
        ACTORS["provider"],
        draft.id,
        BrokerCommand(
            idempotency_key=uid("offer"),
            expected_revision=draft.revision,
            verb="offer",
            capability="SUPPORTED",
            price=Money(amount_minor=1000, currency="USDSIM", decimals=2),
        ),
    )
    draft = broker.draft_command(
        ACTORS["customer"],
        draft.id,
        BrokerCommand(
            idempotency_key=uid("accept"),
            expected_revision=draft.revision,
            verb="accept_specification",
            digest=draft.acceptance_digest,
            authorization_expires_at=broker.clock() + timedelta(seconds=auth_seconds),
        ),
    )
    return broker.view(ACTORS["customer"], draft.order_id)


@pytest.fixture
def broker(tmp_path):
    return Broker(Jobflow(tmp_path / "workflow.sqlite3", demo=True, clock=Clock()))
