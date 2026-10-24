"""Isolated catalog application-command probes using ordinary visible source inputs.

This module contains development examples, never final evaluator truth. The final
runner supplies fresh visible cases and grades them in a separate offline process.
"""

import base64
import json
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from pydantic import Field

from app.catalog.acquisition import acquire_registered, registered_repair
from app.catalog.documents import pdf_document, produce
from app.contracts.catalog import (
    AcceptQuoteCommand,
    OrderCommand,
    RequestCommand,
    RevisionCommand,
    Source,
    UploadCommand,
)
from app.contracts.models import Contract, Text
from app.contracts.payments import FundingAuthorization
from app.improvement.catalog import BASE, COMPANY, CatalogProcedures, product
from app.improvement.catalog_reply import current_reply_frame, reply_is_current
from app.improvement.probes import implementation_digest
from app.orders.catalog import CatalogService
from app.storage.catalog import CatalogRepository
from app.storage.jobflow import digest


class VisiblePublication(Contract):
    source_id: Text
    version: int
    supplier_id: Text
    edition: Text
    effective_date: date
    authority: str
    authority_record: str | None
    selectable: bool
    pdf_base64: Text


class VisibleCatalogCase(Contract):
    id: Text
    corpus_id: Text
    prompt: Text
    publications: tuple[VisiblePublication, ...]
    provider_output_base64: str | None = None
    historical_procedure: bool = False
    observation_seconds: int = Field(default=121, ge=0, le=3600)


class ProbeClock:
    def __init__(self):
        self.now = datetime(2026, 10, 24, 12, tzinfo=UTC)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


def command(order, key, model=OrderCommand, **extra):
    return model(
        expected_revision=order.revision,
        expected_binding=order.binding.model_dump(),
        idempotency_key=key,
        **extra,
    )


def catalog_page(
    *, supplier="supplier-probe", edition="2026-A", price="UNREADABLE", known_price="25", net="1.00"
):
    return pdf_document(
        "Supplier catalog",
        [
            f"Supplier: {supplier} / Edition: {edition} / Effective: 2026-10-01",
            "Records: S01, S02, S03",
            "S01 | storage | Small storage box",
            f"net={net} kg | shipping=1.80 kg | unit=USD {price}",
            "S02 | storage | Medium storage box",
            f"net=1.50 kg | shipping=2.20 kg | unit=USD {known_price}",
            "S03 | storage | Large storage box",
            "net=3.00 kg | shipping=4.00 kg | unit=USD 20",
        ],
    )


def publication(
    raw,
    version=1,
    *,
    selectable=True,
    authority="registered_supplier_publication",
    edition="2026-A",
):
    return VisiblePublication(
        source_id="supplier-probe",
        version=version,
        supplier_id="supplier-probe",
        edition=edition,
        effective_date=date(2026, 10, 1),
        authority=authority,
        authority_record="synthetic-registry:development" if authority != "unverified" else None,
        selectable=selectable,
        pdf_base64=base64.b64encode(raw).decode(),
    )


def development_cases(corpus_id):
    # Inputs are deliberately visible. No expected verdict or oracle is returned.
    initial = publication(catalog_page())
    repair = publication(catalog_page(price="30"), 2, selectable=False)
    unverified = publication(catalog_page(price="30"), 2, selectable=False, authority="unverified")
    changed = publication(catalog_page(price="30", known_price="37"), 2, selectable=False)
    complete = publication(catalog_page(price="30"))
    malformed_delivery = base64.b64encode(
        pdf_document(
            "Cited product shortlist",
            [
                "SELECT S01 | Small storage box | supplier-probe",
                "net_unit=1.000 kg | unit=USD 1.00",
                "source=supplier-probe@1 p1 sha=000000000000",
            ],
        )
    ).decode()
    prompt = (
        "Select storage products with net unit weight below 2 kg and unit price at most USD 40."
    )
    inputs = [
        (corpus_id, (initial, repair), None, False),
        (corpus_id, (initial, unverified), None, False),
        (corpus_id, (initial, changed), None, False),
        (corpus_id + "-other", (initial, repair), None, False),
        (corpus_id, (complete,), malformed_delivery, False),
        (corpus_id, (initial, repair), None, True),
    ]
    return tuple(
        VisibleCatalogCase(
            id=f"dev-{i + 1:03d}",
            corpus_id=scope,
            prompt=prompt,
            publications=pubs,
            provider_output_base64=output,
            historical_procedure=old,
        )
        for i, (scope, pubs, output, old) in enumerate(inputs)
    )


def install_probe_version(procedures, proposal):
    with procedures.store.connect(write=True) as db:
        version = procedures._put(
            db,
            "version",
            proposal.corpus_id,
            {
                "proposal": proposal.model_dump(mode="json"),
                "mode": "ISOLATED_PROBE_ONLY",
                "previous_version": BASE,
                "patch_id": "probe-injected-candidate",
                "implementation_sha256": implementation_digest(),
            },
            actor="system:isolated-probe",
        )
        db.execute(
            "INSERT INTO im_active VALUES(?,?,?)",
            (COMPANY, product(proposal.corpus_id), version["id"]),
        )
    return version["id"]


def run_visible_case(case, *, arm, proposal=None, memory_decider=None, output=None):
    """Same application and evidence opportunity; only per-order action selection differs."""
    if output is None:
        with tempfile.TemporaryDirectory(prefix="catalog-probe-") as path:
            return run_visible_case(
                case, arm=arm, proposal=proposal, memory_decider=memory_decider, output=Path(path)
            )
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    clock = ProbeClock()
    service = CatalogService(
        CatalogRepository(output / "orders.sqlite3"), output / "artifacts", clock
    )
    procedures = CatalogProcedures(service)
    for pub in case.publications:
        artifact = service.store.put(base64.b64decode(pub.pdf_base64))
        service.registry.register(
            Source(
                source_id=pub.source_id,
                version=pub.version,
                corpus_id=case.corpus_id,
                supplier_id=pub.supplier_id,
                edition=pub.edition,
                effective_date=pub.effective_date,
                authority=pub.authority,
                authority_record=pub.authority_record,
                artifact=artifact,
            ),
            selectable=pub.selectable,
        )
    if proposal and arm == "evolving_process" and not case.historical_procedure:
        install_probe_version(procedures, proposal)
    draft = service.create_request(
        RequestCommand(prompt=case.prompt, corpus_id=case.corpus_id, idempotency_key="incoming")
    )
    draft = service.compile_request(
        draft.request_id,
        RevisionCommand(expected_revision=draft.revision, idempotency_key="compile"),
    )
    if draft.status != "ready":
        raise ValueError(
            "Visible-case prompt must specify fixed terms; no hidden customer answer is available"
        )
    quote = service.issue_quote(
        draft.request_id, RevisionCommand(expected_revision=draft.revision, idempotency_key="quote")
    )
    order = service.accept_quote(
        AcceptQuoteCommand(
            quote_id=quote.quote_id,
            customer_actor="customer:synthetic-evaluation",
            idempotency_key="accept",
        )
    )
    if proposal and arm == "evolving_process" and case.historical_procedure:
        install_probe_version(procedures, proposal)
    accepted_snapshot = order.snapshot
    stages = [{"stage": "accepted", "state": order.order_state, "revision": order.revision}]
    preparation = service.payments.prepare(order.snapshot.order_id, command(order, "prepare"))
    order = service.payments.authorize(
        order.snapshot.order_id,
        command(
            order,
            "fund",
            FundingAuthorization,
            funding_attempt_id=preparation.funding_attempt_id,
            payment_hash=preparation.terms.payment_hash,
            simulate=True,
        ),
    )
    stages.append(
        {"stage": "funding_submitted", "state": service.view(order).payment.payment.state}
    )
    service.payments.work()
    order = service.get(order.snapshot.order_id)
    stages.append(
        {"stage": "funding_confirmed", "state": service.view(order).payment.payment.state}
    )
    actions = {
        "manual_intake_clarification": 0,
        "manual_evidence_acquisition": 0,
        "case_review_decision": 0,
        "financial_reconciliation": None,
        "improvement_review_activation": None,
        "maintenance": None,
        "upstream_artifact_registration": len(case.publications),
    }
    decisions = []
    supplied_output = False

    def fixture_producer(extracted, terms, store):
        nonlocal supplied_output
        pdf, sidecar = produce(extracted, terms, store)
        if case.provider_output_base64 and not supplied_output:
            pdf = store.put(base64.b64decode(case.provider_output_base64))
            supplied_output = True
        return pdf, sidecar

    service.producer = fixture_producer
    staff_attempts = set()
    violations = []
    for step in range(12):
        queued = any(j.status == "queued" for j in order.jobs)
        if queued:
            order = service.run_one(order.snapshot.order_id)
            stages.append(
                {
                    "stage": "work",
                    "state": order.order_state,
                    "revision": order.revision,
                    "passed": bool(order.verification and order.verification.passed),
                    "provider_defect": bool(
                        order.verification and order.verification.provider_defect
                    ),
                    "ledger_count": len(order.ledger),
                }
            )
            if order.ledger:
                violations.append("capture_before_review_trigger")
            continue
        if order.order_state == "waiting_evidence":
            request = next((r for r in reversed(order.evidence_requests) if not r.answered), None)
            if request is None or request.request_id in staff_attempts:
                break
            staff_attempts.add(request.request_id)
            choice = "staff"
            if arm == "competent_static":
                choice = "retrieve_registered"
            elif arm == "functional_memory":
                if memory_decider is None:
                    raise ValueError(
                        "Functional memory requires a real decision context, not experience IDs"
                    )
                choice, trace = memory_decider(case, order)
                decisions.append(trace)
            elif (
                arm == "evolving_process"
                and proposal
                and not case.historical_procedure
                and proposal.corpus_id == case.corpus_id
            ):
                # Auto-acquisition already ran in the real worker. Do not create a
                # second recipe authority if it found no usable evidence.
                choice = "staff"
            if choice == "retrieve_registered":
                updated = acquire_registered(service, order)
                if updated.revision != order.revision:
                    order = updated
                    continue
            # Matched synthetic staff response: act only when valid registered
            # evidence exists. An unfulfilled future task is not a completed action.
            if choice in ("staff", "retrieve_registered"):
                frame = current_reply_frame(order)
                if frame is None or not reply_is_current(frame, order, clock()):
                    break
                repair = registered_repair(service, order)
                if repair:
                    order = service.upload(
                        order.snapshot.order_id,
                        command(
                            order,
                            f"staff:{step}",
                            UploadCommand,
                            evidence_request_id=request.request_id,
                            actor="provider:synthetic-evidence-staff",
                            reason="Requested registered source copy supplied by staff",
                            relationship="replacement_page",
                            pdf_base64=base64.b64encode(
                                service.store.read(repair.artifact)
                            ).decode(),
                        ),
                    )
                    actions["manual_evidence_acquisition"] += 1
                    continue
            break
        break
    delivered_before_acceptance = bool(order.deliveries)
    if order.order_state == "delivered":
        order = service.mutate(
            order.snapshot.order_id, "accept", command(order, "customer-review-accept")
        )
    clock.advance(case.observation_seconds)
    order = service.get(order.snapshot.order_id)
    view = service.view(order)
    if order.snapshot != accepted_snapshot:
        violations.append("accepted_snapshot_changed")
    if order.ledger and (not order.verification or not order.verification.passed):
        violations.append("capture_without_current_pass")
    with service.repository.transaction() as db:
        events = [
            json.loads(r[0]) for r in db.execute("SELECT data FROM catalog_run_events ORDER BY seq")
        ]
    artifacts = {
        a.sha256: base64.b64encode(service.store.read(a)).decode() for a in order.artifacts
    }
    pending = []
    if order.order_state in ("human_review", "operational_failure"):
        pending.append({"kind": order.order_state, "owner": "provider", "reason": order.error})
    if order.order_state == "waiting_evidence":
        pending.extend(
            {"kind": "evidence_request", "id": r.request_id, "owner": "source_provider"}
            for r in order.evidence_requests
            if not r.answered and r.deadline > clock()
        )
    if order.order_state == "pending_approval":
        pending.append({"kind": "consent_or_new_offer", "owner": "provider_and_customer"})
    pending.extend(
        {"kind": "job", "id": j.job_id, "owner": "provider", "status": j.status}
        for j in order.jobs
        if j.status in ("queued", "running")
    )
    if view.payment.payment.state not in ("captured", "voided", "funded"):
        pending.append(
            {
                "kind": "payment_reconciliation",
                "owner": "operator",
                "state": view.payment.payment.state,
            }
        )
    actions["case_review_decision"] = len(order.decisions)
    return {
        "case_id": case.id,
        "arm": arm,
        "incoming": True,
        "accepted": True,
        "funded": True,
        "delivered": delivered_before_acceptance,
        "verified_compliant": bool(order.verification and order.verification.passed),
        "provider_defect_observed": any(
            report.provider_defect
            for report in (*order.verification_history, order.verification)
            if report is not None
        ),
        "repair_completed": any(a.applied_revision for a in order.amendments),
        "order_state": order.order_state,
        "payment_state": view.payment.payment.state,
        "financial_effects": [b.kind for b in order.ledger],
        "operationally_closed": order.order_state == "closed"
        and view.payment.payment.state == "captured",
        "pending_company_obligations": len(pending),
        "pending_obligation_details": pending,
        "company_actions": actions,
        "action_measurement_scope": (
            "Explicit synthetic interaction commands; null categories are unmeasured, "
            "never zero-cost claims"
        ),
        "customer_answers": len(draft.answers),
        "seller_rework_attempts": order.free_corrections_used,
        "violations": violations,
        "memory_decisions": decisions,
        "stages": stages,
        "events": events,
        "artifact_bytes_by_sha256": artifacts,
        "order": view.model_dump(mode="json"),
        "mode": "synthetic structured interaction / deterministic compiler / mock finance",
    }


def run_catalog_probe(proposal, *, cases=None):
    cases = cases or development_cases(proposal.corpus_id)
    results, violations, changed = [], [], []
    for case in cases:
        arms = {
            arm: run_visible_case(case, arm=arm, proposal=proposal)
            for arm in ("current_static", "competent_static", "evolving_process")
        }
        baseline, candidate = arms["competent_static"], arms["evolving_process"]
        for arm, result in arms.items():
            violations.extend(f"{case.id}/{arm}:{v}" for v in result["violations"])
        for field in (
            "accepted",
            "verified_compliant",
            "financial_effects",
            "operationally_closed",
            "pending_company_obligations",
        ):
            if baseline[field] != candidate[field]:
                violations.append(
                    f"{case.id}: candidate differs from competent baseline on {field}"
                )
        if (
            arms["current_static"]["company_actions"]["manual_evidence_acquisition"]
            > candidate["company_actions"]["manual_evidence_acquisition"]
        ):
            changed.append(case.id)
        results.append({"case_id": case.id, "arms": arms})
    eligible = bool(changed) and not violations
    return {
        "manifest_sha256": digest([c.model_dump(mode="json") for c in cases]),
        "visible_cases": [c.model_dump(mode="json") for c in cases],
        "outcomes": results,
        "violations": violations,
        "changed_cases": changed,
        "promotion_eligible": eligible,
        "selection": "RETAIN_TESTED_CANDIDATE" if eligible else "RETAIN_BASE",
        "comparison_claim": (
            "Development mechanism contrast, not fresh operating-benefit qualification"
        ),
        "functional_memory": "Reserved for real-model comparison; not simulated by experience IDs",
        "upstream_setup_counted": True,
        "staff_seconds_measured": False,
    }
