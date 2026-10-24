"""Authority derives from accepted terms and the clock, never model prose."""

from datetime import UTC, datetime, timedelta

from app.contracts.jobflow import Action
from app.storage.jobflow import DomainError, digest, uid


def utcnow():
    return datetime.now(UTC)


def effective_fields(order, now):
    fields = set(order.agreement.fields)
    for amendment in order.agreement.amendments:
        if (
            amendment.accepted_by_customer
            and amendment.accepted_by_provider
            and amendment.effective_at <= now
        ):
            fields.update(amendment.fields)
    return sorted(fields)


def scope_digest(order, now):
    return digest(
        {
            "fields": effective_fields(order, now),
            "policy": order.agreement.policy_id,
            "unit": order.agreement.unit_price_minor,
            "count": order.agreement.document_count,
        }
    )


def evidence_digest(order):
    return digest([(item.id, item.version, item.sha256, item.authority) for item in order.evidence])


def action_digest(action):
    return digest(action.model_dump(mode="json", exclude={"status", "owner"}))


def proposal(order, now, *, kind, fields, job_ids, basis, issue_id=None, citations=None):
    return Action(
        id=uid("action"),
        kind=kind,
        fields=fields,
        job_ids=job_ids,
        basis=basis,
        issue_id=issue_id,
        citations=citations or [],
        revision=order.revision,
        agreement_version=order.agreement.version,
        evidence_digest=evidence_digest(order),
        scope_digest=scope_digest(order, now),
        expires_at=now + timedelta(hours=1),
        owner="controller",
        amount_minor=(
            len(fields) * len(job_ids) * order.agreement.additional_field_price_minor
            if kind == "QUOTE"
            else 0
        ),
    )


def current_action(order, action, now):
    if (
        action.expires_at <= now
        or action.agreement_version != order.agreement.version
        or action.evidence_digest != evidence_digest(order)
        or action.scope_digest != scope_digest(order, now)
    ):
        raise DomainError("Action is stale; investigate current evidence and effective terms")
    owed = set(effective_fields(order, now))
    if action.kind == "QUOTE" and (not action.fields or owed.intersection(action.fields)):
        raise DomainError("Cannot charge for fields already owed under current terms")
    if action.kind == "INCLUDED_FIELD" and not set(action.fields) <= owed:
        raise DomainError("Included work lacks an effective accepted agreement")


def invalidate(order):
    for action in order.actions:
        if action.status in {"PROPOSED", "APPROVED"}:
            action.status = "STALE"


def refresh_quotes(order, now, emit):
    """Reprice unexecuted quotes after evidence changes; never reuse an approval."""
    candidates = [
        action for action in order.actions if action.kind == "QUOTE" and action.status == "STALE"
    ]
    for old in reversed(candidates):
        fields = [field for field in old.fields if field not in effective_fields(order, now)]
        if not fields:
            continue
        if any(
            action.kind == "QUOTE"
            and action.fields == fields
            and action.job_ids == old.job_ids
            and action.status in {"PROPOSED", "APPROVED", "EXECUTED"}
            for action in order.actions
        ):
            continue
        action = proposal(
            order,
            now,
            kind="QUOTE",
            fields=fields,
            job_ids=old.job_ids,
            basis="Fresh additional-scope quote; prior approval is historical",
            issue_id=old.issue_id,
            citations=old.citations,
        )
        order.actions.append(action)
        emit("action.proposed", action_id=action.id)


def require(actor, order=None, roles=None):
    if roles is not None and actor.role not in roles:
        raise DomainError("Role is not authorized for this action", 403)
    if order and actor.role == "customer" and actor.customer_id != order.customer_id:
        raise DomainError("Order belongs to another customer", 403)


def find(items, identifier, label):
    for item in items:
        if item.id == identifier:
            return item
    raise DomainError(f"{label} not found", 404)


def select_jobs(order, identifiers):
    if not identifiers or len(identifiers) != len(set(identifiers)):
        raise DomainError("Select a nonempty set of unique job IDs", 422)
    return [find(order.jobs, identifier, "Job") for identifier in identifiers]
