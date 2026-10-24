from app.improvement.catalog_reply import current_reply_frame, reply_is_current
from tests.catalog.fixtures import accepted


def test_semantic_frames_accept_paraphrases_not_keyword_bait_or_stale_requests(setup):
    service, clock, _ = setup
    order = service.run_one(accepted(service).snapshot.order_id)
    frame = current_reply_frame(order)
    for text in (
        "Please supply a legible copy of the per-item price from the registered edition.",
        "Can you provide that same-edition page which makes the amount for one item readable?",
    ):
        assert reply_is_current(frame.model_copy(update={"wording": text}), order, clock())
    # Semantic slots come from structured state, NOT these keywords. These examples
    # test a structured simulator contract; they make no language-understanding claim.
    for kind, text in (
        (
            "historical_reference",
            "The old request said registered edition readable price; do not answer it.",
        ),
        (
            "hypothetical",
            "If a later customer asks for a readable price, they might request a registered page.",
        ),
    ):
        assert not reply_is_current(
            frame.model_copy(update={"semantic_kind": kind, "wording": text}), order, clock()
        )
    assert not reply_is_current(
        frame.model_copy(update={"aggregate_revision": order.revision - 1}), order, clock()
    )
    assert not reply_is_current(
        frame.model_copy(update={"question_id": "earlier-question"}), order, clock()
    )
    clock.advance(121)
    assert not reply_is_current(frame, order, clock())
