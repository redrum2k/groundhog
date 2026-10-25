"""Conservative exact-scope memory selection within the existing SQLite transaction."""

import hashlib

from app.contracts.reviewer_memory import GuidanceConsulted, ReviewerMemory
from app.datasets import canonical, is_dataset, parse_csv, public_bytes, reference
from app.orders.service import DomainError

MAX_MEMORIES = 3


def applicability(order):
    quote = order.snapshot.quote
    case = order.cases[-1]
    requirement = next(
        r
        for r in quote.specification.requirements
        if r.requirement_id == case.complaint.requirement_id
    )
    return {
        "customer": order.snapshot.customer_actor,
        "provider": quote.provider_actor,
        # Only intake provenance varies between otherwise identical accepted requests.
        "accepted_scope": quote.specification.terms.model_dump(mode="json", exclude={"provenance"}),
        "requirement": requirement.model_dump(mode="json"),
        "field": case.complaint.field,
        "source_authority": [s.model_dump(mode="json") for s in quote.sources],
    }


def compatibility_key(scope):
    return hashlib.sha256(canonical(scope)).hexdigest()


def capture(db, service, order, command, cited, decision_id, actor, now):
    from app.orders.dataset_evidence import resolve_current_reference

    if not command.guidance:
        return None
    if not is_dataset(order) or not order.cases or not command.evidence_ids:
        raise DomainError(422, "guidance requires a dataset case and explicitly selected evidence")
    if not command.guidance.strip() or not 1 <= len(cited) <= 8:
        raise DomainError(422, "guidance needs text and one to eight selected references")
    for ref in cited:
        resolve_current_reference(order, ref, service.store)
        if ref.expected_key is not None:
            raise DomainError(422, "guidance requires present cells, not historical absence claims")
    scope = applicability(order)
    memory = ReviewerMemory(
        memory_id=decision_id + ":guidance",
        decision_id=decision_id,
        actor=actor,
        originating_order=order.snapshot.order_id,
        originating_case=order.cases[-1].case_id,
        originating_run=order.snapshot.quote.request_id,
        binding=order.binding,
        recorded_at=now,
        explanation=command.reason,
        guidance=command.guidance.strip(),
        applicability=scope,
        compatibility_key=compatibility_key(scope),
        cited_evidence=tuple(cited),
    )
    service.repository.put(db, "reviewer_memory", memory.memory_id, memory)
    return memory.memory_id


def current_reference(order, previous, store):
    """Reuse a cell locator, never an old delivery value, version or hash."""
    from app.orders.dataset_evidence import resolve_current_reference

    if previous.source_id != "delivery":
        # Exact source identity/hash/authority compatibility is checked before this.
        resolve_current_reference(order, previous, store)
        return previous
    delivery = order.deliveries[-1]
    rows = [r.model_dump() for r in parse_csv(public_bytes(delivery.csv, store))]
    matches = [r for r in rows if r["zip"] == previous.row]
    if len(matches) != 1 or previous.column not in matches[0]:
        raise ValueError("current supporting cell is missing or ambiguous")
    value = matches[0][previous.column]
    ref = reference(
        delivery.csv,
        "delivery",
        row=previous.row,
        column=previous.column,
        version=delivery.version,
        value=None if value is None else str(value),
    )
    resolve_current_reference(order, ref, store)
    return ref


def retrieve(db, order, store, report):
    if not is_dataset(order) or not order.cases or not report.passed:
        return ()
    # Repairs/authority changes cannot inherit compatibility from the old snapshot.
    if order.sources != order.snapshot.quote.sources:
        return ()
    scope = applicability(order)
    rows = db.execute(
        "SELECT data FROM catalog_records WHERE kind='reviewer_memory' "
        "AND json_extract(data,'$.compatibility_key')=? "
        "AND json_extract(data,'$.originating_order')!=? "
        "ORDER BY json_extract(data,'$.recorded_at') DESC,id DESC LIMIT 12",
        (compatibility_key(scope), order.snapshot.order_id),
    ).fetchall()
    selected = []
    for (data,) in rows:
        memory = ReviewerMemory.model_validate_json(data)
        if memory.applicability != scope:
            continue
        try:
            # Reopen all frozen authority bytes, not just the selected citations.
            for source in order.sources:
                public_bytes(source.artifact, store)
            refs = tuple(current_reference(order, r, store) for r in memory.cited_evidence)
        except (DomainError, ValueError, KeyError, OSError):
            continue
        selected.append(
            GuidanceConsulted(
                memory_id=memory.memory_id,
                actor=memory.actor,
                originating_order=memory.originating_order,
                originating_case=memory.originating_case,
                explanation=memory.explanation,
                guidance=memory.guidance,
                applicability={
                    "compatibility_key": memory.compatibility_key,
                    "customer": scope["customer"],
                    "provider": scope["provider"],
                    "requirement": scope["requirement"],
                    "field": scope["field"],
                    "geography": scope["accepted_scope"]["geography"],
                    "category": scope["accepted_scope"]["category"],
                },
                current_citations=refs,
            )
        )
        if len(selected) == MAX_MEMORIES:
            break
    return tuple(selected)
