"""Project existing order, verification and payment records without mutating them."""

from app.contracts.catalog import CatalogOrder
from app.contracts.payment_justification import PaymentJustification
from app.datasets import is_dataset
from app.money import format_money
from app.orders.service import DomainError
from app.runtime.catalog_policy import authorization_ready, capture_allowed
from app.runtime.dataset_policy import cutoff


def payment_justification(service, order_id):
    with service.repository.transaction() as db:
        order = service.repository.load(db, "order", order_id, CatalogOrder)
        if not is_dataset(order):
            raise DomainError(422, "Payment justification currently supports aggregate orders only")
        now = service.clock()
        view = service.view(order, db=db)
        payment = view.payment
        report = order.verification
        byte_check = service.current_dataset_checks(order)
        # Query the very same executor guard, using an unpersisted intent. No
        # reservation, synchronization, sweep, model dispatch or financial effect.
        eligible = bool(
            payment
            and service.payments._eligible(
                db,
                order,
                payment.payment,
                service.payments._operation(order, "capture", "read-only-eligibility"),
            )
        )
        blockers = []
        if order.ledger:
            blockers.append("Terminal booking already exists; another capture is forbidden.")
        if not authorization_ready(order.authorization):
            blockers.append("Exact funding is not currently authorized and confirmed.")
        if payment and payment.payment.state != "funded":
            blockers.append(
                f"Payment state is {payment.payment.state}; it is not available funded money."
            )
        if any(c.status in {"open", "human_review", "scope_change"} for c in order.cases):
            blockers.append("An unresolved dispute or scope decision prevents capture.")
        if any(a.status == "pending" for a in order.approvals):
            blockers.append("Required approval is still pending.")
        if (
            not report
            or report.binding != order.binding
            or not report.passed
            or report.provider_defect
        ):
            blockers.append("Current complete verification is absent, stale or failing.")
        if not byte_check:
            blockers.append(
                "Independent revalidation of actual source/delivery bytes does not pass."
            )
        delivery = order.deliveries[-1] if order.deliveries else None
        if order.customer_acceptance != order.binding and (
            not delivery or now < delivery.review_deadline
        ):
            blockers.append(
                "No current buyer acceptance and the agreed review window has not expired."
            )
        if now >= cutoff(order):
            blockers.append("The latest safe capture cutoff has passed.")
        if not eligible and not blockers:
            blockers.append(
                "The existing executor guard rejects capture: "
                "inspect binding, authority and terminal operation records."
            )
        if eligible:
            # Disagreements between a human-readable explanation and authority are
            # bugs, never an excuse to manufacture an authorization.
            assert capture_allowed(order, now) and byte_check and not blockers
        terms = order.snapshot.quote.payment_terms
        return PaymentJustification(
            observed_at=now,
            order_id=order_id,
            revision=order.revision,
            binding=order.binding,
            agreement=order.snapshot,
            exact_price=format_money(order.snapshot.quote.amount),
            amount_atomic=str(terms.amount_atomic) if terms else None,
            state=payment.payment.state if payment else order.order_state,
            capture_eligible_now=eligible,
            blockers=tuple(blockers),
            bytes_revalidated=byte_check,
            checks=report.assessments if report else (),
            source_hashes={s.source_id: s.artifact.sha256 for s in order.sources},
            delivery_hashes={
                a.artifact_id: a.sha256 for d in order.deliveries for a in (d.csv, d.preview) if a
            },
            authorization=order.authorization,
            customer_acceptance=order.customer_acceptance,
            review_deadline=delivery.review_deadline if delivery else None,
            latest_safe_capture_at=cutoff(order),
            cases=order.cases,
            decisions=order.decisions,
            bookings=order.ledger,
            payment=payment,
        )
