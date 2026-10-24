"""Versioned aggregate adapter to Jeff's bounded semantic assessor interface."""

import hashlib
import json
import os
import re
from time import monotonic

from app.agents.bounded_client import BoundedClient
from app.agents.gateway import ClaudeGateway, EvidencePassage, OfflineAssessor
from app.contracts.catalog import Assessment, Obligation, Provenance
from app.contracts.semantic import DatasetSemanticAttempt
from app.datasets import reference
from app.orders.dataset_evidence import answer_references


def investigate_dataset(order, report, store, assessor, *, audit=None, candidate_sink=None):
    case = order.cases[-1]
    terms = order.snapshot.quote.specification.terms
    authority = next(s for s in order.sources if s.source_id.endswith(":authority"))
    raw = json.loads(store.read(authority.artifact))
    refs = (
        reference(
            authority.artifact,
            authority.source_id,
            column="definition",
            value=raw.get("definition"),
            version=authority.version,
        ),
        reference(
            authority.artifact,
            authority.source_id,
            column="yoga_is_gym",
            value=str(raw["yoga_is_gym"]).lower() if raw.get("yoga_is_gym") is not None else None,
            version=authority.version,
        ),
    )
    for ref in refs:
        store.resolve(ref, order.artifacts)
    obligation = Obligation(
        obligation_id=f"{case.case_id}:claim",
        requirement_id=case.complaint.requirement_id,
        subject=case.complaint.product_id,
        field=case.complaint.field,
        check="dataset_semantic_claim",
        mandatory=False,
        decision_effect="remedy",
    )
    result, explanation = (
        "UNKNOWN",
        "The accepted definition and source meaning do not establish this claim.",
    )
    if isinstance(assessor, OfflineAssessor):
        if (
            case.complaint.field in ("coverage", "completeness")
            and case.complaint.product_id in terms.coverage.expected_keys
            and report.passed
        ):
            result, explanation = (
                "FAIL",
                "The exact disputed ZIP is present in the independently checked delivery.",
            )
            refs = (
                reference(
                    order.deliveries[-1].csv,
                    "delivery",
                    row=case.complaint.product_id,
                    column="zip",
                    value=case.complaint.product_id,
                    version=order.deliveries[-1].version,
                ),
            )
        elif "yoga" in case.complaint.text.lower() and case.complaint.field == "category":
            if terms.category == "gym_app_or_yoga" and report.passed:
                result, explanation = (
                    "FAIL",
                    (
                        "Yoga is already included in the accepted definition and verified "
                        "source; no expansion fee is owed."
                    ),
                )
            elif raw.get("yoga_is_gym") is False:
                result, explanation = (
                    "FAIL",
                    (
                        "Accepted fitness means gyms/apps; the frozen taxonomy excludes "
                        "standalone yoga. Extra yoga work needs a separate offer and "
                        "buyer acceptance."
                    ),
                )
            elif raw.get("yoga_is_gym") is True:
                result, explanation = (
                    "PASS",
                    (
                        "The frozen authority states yoga satisfies gym membership; it is "
                        "already owed, not billable expansion."
                    ),
                )
        return Assessment(
            obligation_id=obligation.obligation_id,
            result=result,
            citations=refs,
            missing_facts=(
                "Registered evidence establishing yoga's meaning under the accepted definition.",
            )
            if result == "UNKNOWN"
            else (),
            reason_code="DATASET_SEMANTIC_" + result,
            explanation=explanation,
            requested_evidence=(
                "Which frozen authority record establishes whether yoga "
                "membership satisfies the accepted gym/app definition?"
            )
            if result == "UNKNOWN"
            else None,
            provenance=Provenance(
                kind="deterministic", assessor="offline-dataset-semantics", version="1"
            ),
        )
    refs = tuple(dict.fromkeys((*refs, *answer_references(order, store))))
    proof = independent_claim(order, report, store)
    if proof:
        refs = tuple(dict.fromkeys((*refs, *proof[1])))
    relevant = {
        o.obligation_id
        for o in report.obligations
        if o.requirement_id == case.complaint.requirement_id
    }
    refs = tuple(
        dict.fromkeys(
            (
                *refs,
                *(
                    r
                    for a in report.assessments
                    if a.obligation_id in relevant
                    for r in a.citations
                ),
            )
        )
    )[:32]
    passages = tuple(
        EvidencePassage(citation=r, text=store.resolve(r, order.artifacts) or "Unknown")
        for r in refs
    )
    claim = (
        f"Accepted definition: {terms.category_meaning}. Claim: {case.complaint.text}. "
        f"Customer testimony: {case.answers}. Testimony is not source authority. "
        "PASS supports THIS complaint; FAIL contradicts it; missing contractual meaning "
        "is UNKNOWN, not contradiction. Supporting a claim does not prove provider fault. "
        "Distinguish contractual inclusion from taxonomic membership: a contract may "
        "exclude standalone yoga without establishing whether yoga qualifies as gym "
        "membership. For a taxonomy claim (counts as/qualifies as/satisfies gym membership), "
        "require the registered yoga_is_gym value. A null/Unknown value is missing authority, "
        "not false; return UNKNOWN rather than infer taxonomy from the accepted product label "
        "or its exclusion wording. Explicit inclusion/exclusion claims can instead be checked "
        "against accepted scope and the verified category. Never invent a missing value. "
        + json.dumps(
            {
                "binding": order.binding.model_dump(mode="json"),
                "case_id": case.case_id,
                "order_id": order.snapshot.order_id,
                "accepted_terms": terms.model_dump(mode="json"),
                "accepted_requirement": next(
                    r.model_dump(mode="json")
                    for r in order.snapshot.quote.specification.requirements
                    if r.requirement_id == case.complaint.requirement_id
                ),
                "deterministic_checks": [
                    a.model_dump(mode="json")
                    for a in report.assessments
                    if a.obligation_id in relevant
                ],
            },
            sort_keys=True,
        )
    )
    if audit:
        audit(
            {
                "obligation": obligation.model_dump(mode="json"),
                "claim": claim,
                "passages": [p.model_dump(mode="json") for p in passages],
            }
        )
    finding = assessor.assess_obligation(obligation, claim, passages)
    if candidate_sink:
        candidate_sink(finding)
    if finding.obligation_id != obligation.obligation_id or any(
        r not in refs for r in (*finding.citations, *finding.conflicting_evidence)
    ):
        raise ValueError("semantic result is outside the bounded cited evidence")
    return finding


def semantic_key(order):
    payload = {
        "binding": order.binding.model_dump(mode="json"),
        "case": order.cases[-1].model_dump(mode="json"),
        "specification": order.snapshot.quote.specification.model_dump(mode="json"),
    }
    # Question counters/state are effects, not a new evidence snapshot.
    payload["case"] = {
        k: v for k, v in payload["case"].items() if k in {"case_id", "complaint", "answers"}
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def semantic_attempt(db, order):
    row = db.execute(
        "SELECT data FROM catalog_records WHERE kind='dataset_assessment' AND id=?",
        (semantic_key(order),),
    ).fetchone()
    return DatasetSemanticAttempt.model_validate_json(row[0]) if row else None


def unclear(order, reason):
    return Assessment(
        obligation_id=f"{order.cases[-1].case_id}:claim",
        result="UNKNOWN",
        reason_code="DATASET_SEMANTIC_UNRESOLVED",
        explanation=reason,
        missing_facts=(
            "Complaint-specific support from exact accepted terms and verified evidence.",
        ),
        requested_evidence="Identify the frozen source and exact cell establishing this claim.",
        provenance=Provenance(kind="deterministic", assessor="dataset-evidence-gate", version="1"),
    )


def interpret_claim(complaint):
    """Whole-clause, auditable predicates. Unknown qualifiers never disappear.

    The model does not select the predicate or its truth value. This deliberately
    bounded grammar generalizes phrases, not arbitrary natural-language entailment.
    """
    text = " ".join(complaint.text.lower().replace("’", "'").split()).rstrip(".?!")
    yoga = r"(?:standalone )?yoga(?:[- ]studio)?(?: memberships?| studios?)?"
    prefix = r"(?:(?:under|within) (?:our|the) (?:accepted|agreed) (?:scope|terms|definition),? )?"
    scope = (
        r"(?:our|the) (?:accepted|agreed) "
        r"(?:(?:fitness|gym/app) )?(?:scope|definition|category|contract)"
    )
    if complaint.field == "category":
        # Scope-first wording names the same bounded category predicate. Match the
        # whole clause so price promises, mixed scope and extra qualifiers stay unknown.
        population = r"(?:our|the) (?:accepted|agreed) (?:population|cohort)"
        yoga_only = r"(?:a person|people|adults) whose only (?:activity|membership) is " + yoga
        for asserted, verbs in (
            (True, r"counts|includes|covers"),
            (False, r"(?:does not|doesn't) (?:count|include|cover)"),
        ):
            if re.fullmatch(population + " (?:" + verbs + ") " + yoga_only, text):
                return "contract_includes_yoga", asserted
        for asserted, verbs in (
            (
                True,
                r"(?:is|are) (?:already )?(?:included|covered) (?:in|by|under)|"
                r"(?:belongs?|falls?) (?:in|under|within)",
            ),
            (
                False,
                r"(?:is not|isn't|are not|aren't) (?:included|covered) (?:in|by|under)|"
                r"(?:does not|doesn't|do not|don't) belong (?:in|under|within)",
            ),
        ):
            if re.fullmatch(prefix + yoga + " (?:" + verbs + ") " + scope, text):
                return "contract_includes_yoga", asserted
        for asserted, verbs in (
            (True, r"counts? as|qualifies? as|satisfies"),
            (False, r"(?:does not|doesn't|do not|don't) (?:count as|qualify as|satisfy)"),
        ):
            if re.fullmatch(
                prefix
                + yoga
                + " (?:"
                + verbs
                + r") (?:the |our )?(?:accepted |agreed )?gym(?: membership)?"
                r"(?: category| definition)?",
                text,
            ):
                return "taxonomy_yoga_is_gym", asserted
    if complaint.field == "coverage":
        target = r"(?:zip )?" + re.escape(complaint.product_id)
        artifact = r"(?:the |our )?(?:delivered )?(?:csv|dataset|delivery)"
        if re.fullmatch(
            target + r" (?:is missing|is absent|was omitted|is not included|does not appear)"
            r"(?: (?:from|in) " + artifact + ")?",
            text,
        ) or re.fullmatch(
            r"you (?:left|omitted) " + target + r" (?:out of|from) " + artifact, text
        ):
            return "delivery_has_zip", False
    return None


def independent_claim(order, report, store):
    """Establish a typed predicate using frozen terms AND resolving source bytes."""
    case = order.cases[-1]
    terms = order.snapshot.quote.specification.terms
    predicate = interpret_claim(case.complaint)
    if not report.passed or predicate is None:
        return None
    name, asserted = predicate
    if name == "contract_includes_yoga":
        source = next(s for s in order.sources if s.source_id.endswith(":" + terms.category))
        ref = reference(
            source.artifact,
            source.source_id,
            column="category",
            value=terms.category,
            version=source.version,
        )
        store.resolve(ref, order.artifacts)
        included = terms.category == "gym_app_or_yoga"
        return (
            "PASS" if included == asserted else "FAIL",
            (ref,),
            "The frozen accepted category and independently verified source category "
            "establish scope; no provider-output fault follows.",
        )
    if name == "taxonomy_yoga_is_gym":
        authority = next(s for s in order.sources if s.source_id.endswith(":authority"))
        data = json.loads(store.read(authority.artifact))
        actual = data.get("yoga_is_gym")
        # Conflicting taxonomy cannot silently broaden an explicitly excluding contract.
        if type(actual) is not bool or (actual and terms.category == "gym_or_fitness_app"):
            return None
        ref = reference(
            authority.artifact,
            authority.source_id,
            column="yoga_is_gym",
            value=str(data["yoga_is_gym"]).lower(),
            version=authority.version,
        )
        store.resolve(ref, order.artifacts)
        return (
            "PASS" if actual == asserted else "FAIL",
            (ref,),
            "The exact frozen yoga_is_gym cell establishes membership "
            "under the accepted gym/app definition.",
        )
    if name == "delivery_has_zip" and case.complaint.product_id in terms.coverage.expected_keys:
        ref = reference(
            order.deliveries[-1].csv,
            "delivery",
            row=case.complaint.product_id,
            column="zip",
            value=case.complaint.product_id,
            version=order.deliveries[-1].version,
        )
        store.resolve(ref, order.artifacts)
        return (
            "FAIL",
            (ref,),
            "The complained-of ZIP resolves in the independently verified delivery.",
        )
    return None


def guarded_dataset_assessment(service, order, job, report):
    """Use existing assessor and durable store. No call from polling; no uncertain retry."""
    assessor = service.investigator.assessor
    enabled = os.getenv("ENABLE_DATASET_MODEL_ASSESSMENT") == "true"
    if not enabled:
        # A global paid compiler opt-in is not activation of this optional feature.
        return investigate_dataset(
            order,
            report,
            service.store,
            OfflineAssessor() if isinstance(assessor, ClaudeGateway) else assessor,
        )
    if isinstance(assessor, OfflineAssessor):
        return investigate_dataset(order, report, service.store, assessor)
    key = semantic_key(order)
    attempt = DatasetSemanticAttempt(
        attempt_id=key,
        order_id=order.snapshot.order_id,
        case_id=order.cases[-1].case_id,
        order_revision=order.revision,
        binding=order.binding,
        accepted_specification_sha256=hashlib.sha256(
            order.snapshot.quote.specification.model_dump_json().encode()
        ).hexdigest(),
        status="DISPATCHED",
    )
    with service.repository.transaction() as db:
        existing = semantic_attempt(db, order)
        if existing:
            return existing.effective or unclear(
                order, "Uncertain prior dispatch retained; no automatic retry."
            )
        service.repository.put(db, "dataset_assessment", key, attempt)

    def persist(**updates):
        nonlocal attempt
        attempt = attempt.model_copy(update=updates)
        with service.repository.transaction() as db:
            service.repository.put(db, "dataset_assessment", key, attempt)

    own_client = None
    started = monotonic()
    candidate = None
    status = "FAILED"
    try:
        if isinstance(assessor, ClaudeGateway):
            own_client = BoundedClient(purpose="primary-dataset-dispute")
            own_client.response_sink = lambda raw: persist(raw_response=raw)
            assessor = ClaudeGateway(enabled=True, model=assessor.model, client=own_client)
        candidate = investigate_dataset(
            order,
            report,
            service.store,
            assessor,
            audit=lambda request: persist(request=request),
            candidate_sink=lambda value: persist(candidate=value),
        )
        persist(candidate=candidate)
        status = "ADVISORY"
    except Exception as error:
        status = "INVALID" if attempt.candidate is not None else "FAILED"
        persist(failure=type(error.__cause__ or error).__name__)
    finally:
        if own_client:
            own_client.close()
    try:
        proof = independent_claim(order, report, service.store)
    except (ValueError, KeyError, StopIteration, OSError):
        proof = None
    effective = unclear(
        order, "The candidate lacks independently checkable complaint-specific support."
    )
    if candidate and candidate.result in {"UNKNOWN", "CONFLICT"}:
        effective, status = candidate, "VALIDATED"
    elif candidate and proof and supports_candidate(order, service.store, candidate, proof):
        effective, status = candidate, "VALIDATED"
    elif candidate is None and proof:
        effective = Assessment(
            obligation_id=effective.obligation_id,
            result=proof[0],
            citations=proof[1],
            reason_code="DATASET_INDEPENDENT_FALLBACK",
            explanation=proof[2],
            provenance=Provenance(
                kind="deterministic", assessor="dataset-evidence-gate", version="1"
            ),
        )
    persist(effective=effective, status=status, elapsed_seconds=monotonic() - started)
    return effective


def supports_candidate(order, store, candidate, proof):
    """Two explicit proof certificates; valid-looking citations alone never suffice.

    The primary certificate is the actual verified category/CSV cell. For the
    explicitly excluding contract only, the exact authority definition AND false
    taxonomy cell are an independently checkable equivalent category certificate.
    Neither a model explanation nor a customer statement supplies these facts.
    """
    if candidate.result != proof[0]:
        return False
    if set(proof[1]) <= set(candidate.citations):
        return True
    predicate = interpret_claim(order.cases[-1].complaint)
    terms = order.snapshot.quote.specification.terms
    if (
        predicate is None
        or predicate[0] != "contract_includes_yoga"
        or terms.category != "gym_or_fitness_app"
        or terms.category_meaning
        != "Gym membership or fitness-app use; standalone yoga is excluded."
    ):
        return False
    authority = next(s for s in order.sources if s.source_id.endswith(":authority"))
    raw = json.loads(store.read(authority.artifact))
    if (
        raw.get("definition") != "Gym membership or fitness-app use."
        or raw.get("yoga_is_gym") is not False
    ):
        return False
    equivalent = (
        reference(
            authority.artifact,
            authority.source_id,
            column="definition",
            value=raw["definition"],
            version=authority.version,
        ),
        reference(
            authority.artifact,
            authority.source_id,
            column="yoga_is_gym",
            value="false",
            version=authority.version,
        ),
    )
    for ref in equivalent:
        store.resolve(ref, order.artifacts)
    return set(equivalent) <= set(candidate.citations)


def stale_semantic_attempt(service, order):
    with service.repository.transaction() as db:
        attempt = semantic_attempt(db, order)
        if attempt:
            service.repository.put(
                db,
                "dataset_assessment",
                attempt.attempt_id,
                attempt.model_copy(update={"status": "STALE"}),
            )
