"""Budget windows before immutable capture expiry; never shorten promised review."""

from datetime import timedelta

from app.contracts.dataset import BrokeragePolicy


def cutoff(order):
    policy = order.snapshot.quote.policy
    margin = policy.transaction_margin_seconds if isinstance(policy, BrokeragePolicy) else 0
    return order.authorization.expires_at - timedelta(seconds=margin)


def fits(order, now, stage):
    policy = order.snapshot.quote.policy
    if not isinstance(policy, BrokeragePolicy):
        return now < order.authorization.expires_at
    # Reserve a last-instant dispute, one permitted correction and fresh review.
    review_dispute = policy.review_seconds + policy.dispute_seconds
    remaining_correction = (
        0 if order.free_corrections_used else policy.correction_seconds + review_dispute
    )
    seconds = review_dispute + remaining_correction
    if stage == "dispatch":
        seconds += policy.fulfillment_seconds
    elif stage == "correction":
        seconds = policy.correction_seconds + review_dispute
    return now + timedelta(seconds=seconds) < cutoff(order)
