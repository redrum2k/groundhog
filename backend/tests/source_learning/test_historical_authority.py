"""Release incident: re-publishing historical authority must not install stale pins."""

from datetime import timedelta

import pytest
from tools.learning_examples import example_bundle

from app.orders.service import DomainError
from tests.source_learning.test_live_learning import compile, create


@pytest.mark.parametrize("status", ["revoked", "conflict", "expired"])
def test_historical_authority_republication_is_rejected_atomically(live, status):
    service, learning = live
    original = example_bundle(service.clock(), 1)
    original_result = learning.publish(original, "provider:local-worker")
    changed = example_bundle(service.clock(), 2)
    changed = changed.model_copy(
        update={
            "partitions": tuple(
                p.model_copy(
                    update={
                        "authority": p.authority.model_copy(
                            update=(
                                {"valid_until": service.clock() - timedelta(seconds=1)}
                                if status == "expired"
                                else {"status": status}
                            )
                        )
                    }
                )
                for p in changed.partitions
            )
        }
    )
    current = learning.publish(changed, "provider:local-worker")
    with service.repository.transaction() as db:
        before_sources = db.execute(
            "SELECT source_id,version,selectable,data FROM catalog_sources "
            "ORDER BY source_id,version"
        ).fetchall()
    # A new command containing old authority bytes is not an exact command replay.
    with pytest.raises(DomainError, match="historical authority") as exc:
        learning.publish(example_bundle(service.clock(), 3), "provider:local-worker")
    assert exc.value.status == 409
    assert learning.state().bundle_id == current.record_id
    with service.repository.transaction() as db:
        assert (
            db.execute(
                "SELECT source_id,version,selectable,data FROM catalog_sources "
                "ORDER BY source_id,version"
            ).fetchall()
            == before_sources
        )
    # Idempotent replay stays readable and cannot change the current authority/bundle.
    assert learning.publish(original, "provider:local-worker") == original_result
    assert learning.state().bundle_id == current.record_id
    request = create(service, "after-rejected-historical-authority")
    assert compile(service, request, "current-authority-hold").status == "human_review"


def test_fresh_batch_with_unchanged_current_authority_is_allowed(live):
    service, learning = live
    learning.publish(example_bundle(service.clock(), 1), "provider:local-worker")
    result = learning.publish(example_bundle(service.clock(), 2), "provider:local-worker")
    assert learning.state().bundle_id == result.record_id
    with service.repository.transaction() as db:
        rows = db.execute(
            "SELECT source_id,max(version) FROM catalog_sources "
            "WHERE source_id LIKE '%learning-authority%' GROUP BY source_id"
        ).fetchall()
    assert len(rows) == 2 and all(row[1] == 1 for row in rows)


def test_historical_source_batch_cannot_replace_current_bundle(live):
    service, learning = live
    old = example_bundle(service.clock(), 1)
    learning.publish(old, "provider:local-worker")
    current = learning.publish(example_bundle(service.clock(), 2), "provider:local-worker")
    with pytest.raises(DomainError, match="historical source"):
        learning.publish(
            old.model_copy(update={"idempotency_key": "old-batch-new-command"}),
            "provider:local-worker",
        )
    assert learning.state().bundle_id == current.record_id
