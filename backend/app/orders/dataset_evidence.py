"""Request-bound transport of frozen, public-safe evidence; no assessment semantics."""

import json
import re

from app.contracts.runs import RunEvidenceRequest
from app.datasets import public_bytes, reference
from app.orders.service import DomainError
from app.runtime.dataset_policy import cutoff


def evidence_unavailable(text):
    """Route an explicit inability to answer to a human; never decide the complaint.

    Match a whole first-person statement, not quotations, conditions or mixed claims.
    This is an early end to questioning, with no change to factual or payment authority.
    """
    words = " ".join(text.lower().replace("’", "'").strip().rstrip(".! ").split())
    evidence = r"(?:source )?(?:documentation or evidence|documentation|evidence|documents)"
    return bool(
        re.fullmatch(
            r"(?:i have no|i (?:do not|don't) have (?:any|any more|additional|more)) "
            r"(?:(?:additional|more|further) )?"
            + evidence
            + r"(?: to resolve this (?:authenticity )?concern)?",
            words,
        )
        or re.fullmatch(
            r"i (?:cannot|can't) provide (?:(?:this|the requested|any more) )?" + evidence, words
        )
    )


def resolve_current_reference(order, ref, store):
    sources = order.snapshot.quote.sources
    source_match = any(
        (s.source_id, s.version, s.artifact.artifact_id, s.artifact.sha256)
        == (ref.source_id, ref.version, ref.artifact_id, ref.sha256)
        for s in sources
    )
    delivery = order.deliveries[-1] if order.deliveries else None
    delivery_match = (
        delivery
        and ref.source_id == "delivery"
        and ref.version == delivery.version
        and any(
            (a.artifact_id, a.sha256) == (ref.artifact_id, ref.sha256)
            for a in (delivery.csv, delivery.preview)
        )
    )
    if not source_match and not delivery_match:
        raise DomainError(
            422, "answer reference must identify frozen source or current delivery evidence"
        )
    try:
        return store.resolve(ref, order.artifacts)
    except ValueError:
        raise DomainError(422, "answer reference does not resolve to its frozen evidence") from None


def evidence_request(order, store, now):
    if now >= cutoff(order):
        return None
    case = order.cases[-1] if order.cases else None
    pending = next((r for r in order.evidence_requests if not r.answered), None)
    if case and case.status == "open" and case.question and now < case.deadline:
        request = RunEvidenceRequest(
            request_id=f"{case.case_id}:question:{case.questions_asked}",
            case_id=case.case_id,
            prompt=case.question,
            deadline=case.deadline,
            references_required=False,
        )
    elif pending and now < pending.deadline:
        request = RunEvidenceRequest(
            request_id=pending.request_id,
            case_id=case.case_id if case and case.status == "open" else None,
            prompt=pending.prompt,
            deadline=pending.deadline,
            references_required=True,
        )
    else:
        return None
    choices = []
    for source in order.snapshot.quote.sources:
        try:
            data = json.loads(public_bytes(source.artifact, store))
        except (DomainError, ValueError):
            continue
        for column in (
            "definition",
            "yoga_is_gym",
            "yoga_category",
            "authority_record",
            "geography",
            "age_min",
            "age_max",
            "category",
            "count_unit",
        ):
            if column not in data:
                continue
            value = data[column]
            ref = reference(
                source.artifact,
                source.source_id,
                column=column,
                version=source.version,
                value=None
                if value is None
                else str(value).lower()
                if isinstance(value, bool)
                else str(value),
            )
            try:
                resolve_current_reference(order, ref, store)
            except DomainError:
                # A schema-valid but misidentified source is not a resolving choice.
                continue
            choices.append(ref)
    return request.model_copy(update={"allowed_references": tuple(choices[:32])})


def answer_references(order, store):
    """At most two current-case answers, eight citations each, re-resolved after restart."""
    case = order.cases[-1]
    refs = []
    for answer in order.evidence_answers:
        if (
            answer.case_id == case.case_id
            and answer.original_binding.snapshot_id == order.binding.snapshot_id
            and answer.original_binding.delivery_version == order.binding.delivery_version
            and answer.original_binding.evidence_revision < order.binding.evidence_revision
        ):
            for ref in answer.references:
                resolve_current_reference(order, ref, store)
                if ref not in refs:
                    refs.append(ref)
    return tuple(refs[:16])
