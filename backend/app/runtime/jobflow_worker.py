"""Application-owned durable queue worker; never holds a write transaction over I/O."""

import asyncio
import base64
import json
import time

from app.contracts.jobflow import OrderView
from app.orders.jobflow import recognize_originals
from app.payments.jobflow import post, project
from app.provider.jobflow import cite, extract, store_evidence, verify
from app.runtime.jobflow_investigations import apply_outcome, validate_outcome
from app.runtime.jobflow_policy import (
    evidence_digest,
    find,
    invalidate,
    refresh_quotes,
    scope_digest,
)
from app.storage.jobflow import DomainError, canonical


def emitter(service, db, order, operation_id, now):
    return lambda kind, **payload: service.store.event(
        db, order, "runtime", operation_id, now, kind, **payload
    )


def finish_payment(db, order, operation_id, result, now, emit):
    operation = find(order.finance.operations, operation_id, "Payment operation")
    if (
        result.get("order_id") != order.id
        or result.get("amount_minor") != operation.amount_minor
        or result.get("change_order_id") != operation.change_order_id
    ):
        raise DomainError("Provider evidence does not match the original payment intent")
    if operation.status == "CONFIRMED":
        return
    operation.status = result["status"]
    operation.provider_reference = f"local-simulator:{operation.id}"
    if operation.change_order_id:
        change = find(order.change_orders, operation.change_order_id, "Change order")
        change.status = {"CONFIRMED": "PAID", "UNKNOWN": "UNKNOWN", "FAILED": "ACCEPTED"}[
            operation.status
        ]
    if operation.status == "CONFIRMED":
        post(
            db,
            order,
            f"receipt:{operation.id}",
            operation.amount_minor,
            "cash",
            "contract_liability",
            "Simulated prepayment; not live settlement",
            now,
            emit,
        )
        if operation.change_order_id is None:
            recognize_originals(db, order, now, emit)
    emit(f"payment.{operation.status.lower()}", operation_id=operation.id, simulated=True)


def finish_delivery(
    service, db, order, operation_id, request, result, now, emit, *, reconciled=False
):
    stale = request["scope_digest"] != scope_digest(order, now)
    unknown = request["outcome"] == "UNKNOWN" and not reconciled
    artifact_ids = []
    successful = True
    for spec, produced in zip(request["specs"], result["outputs"], strict=True):
        job = find(order.jobs, spec["job_id"], "Job")
        attempt = find(job.attempts, spec["attempt_id"], "Attempt")
        if attempt.status in {"VALIDATED", "FAILED"}:
            continue
        if unknown:
            attempt.status = "UNKNOWN"
            attempt.error = "Simulated response lost; reconcile the same operation"
            job.processing = "RUNNING"
            job.owner = "executor"
            job.next_action = "Reconcile persisted provider evidence; do not repeat extraction"
            emit(
                "correction.unknown",
                job_id=job.id,
                attempt_id=attempt.id,
                operation_id=operation_id,
            )
            continue
        if produced.get("raw"):
            raw = base64.b64decode(produced["raw"], validate=True)
            source, _, _ = service.store.artifact(db, order.id, job.source_id)
            checks = verify(source, raw, job.source_id, spec["fields"])
            evidence = store_evidence(
                db,
                order,
                raw,
                filename=f"{attempt.id}.json",
                media_type="application/json",
                kind="artifact",
                authority="COMPANY_RECORD",
                actor_id="local-extractor",
                now=now,
                derived_from=[job.source_id],
            )
            for check in checks:
                check.citations = [cite(evidence)]
            attempt.output_artifact_id = evidence.id
            job.artifact_id = evidence.id
            job.checks = checks
            job.fields = spec["fields"]
            artifact_ids.append(evidence.id)
            passed = all(check.state == "PASSED" for check in checks) and not stale
            emit("artifact.created", job_id=job.id, artifact_id=evidence.id, attempt_id=attempt.id)
        else:
            passed = False
        attempt.status = "VALIDATED" if passed else "FAILED"
        attempt.error = (
            None
            if passed
            else (
                "Effective scope changed during execution; human review required"
                if stale
                else "Extraction or independent validation failed; no automatic retry"
            )
        )
        job.processing = "VALIDATED" if passed else "FAILED"
        job.obligation = "OPEN" if passed else "HANDED_OFF"
        job.recoverable = False
        job.owner = "customer" if passed else "controller"
        job.next_action = (
            "Accept the exact validated artifact" if passed else "Review failed reserved attempt"
        )
        job.financial_state = "RECOGNITION_PENDING" if passed else "REVIEW_REQUIRED"
        if result.get("executed", True):
            post(
                db,
                order,
                f"compute:{attempt.id}",
                attempt.cost_minor,
                "correction_expense",
                "compute_payable",
                "Executed correction attempt",
                now,
                emit,
            )
        emit("check.passed" if passed else "check.failed", job_id=job.id, attempt_id=attempt.id)
        successful = successful and passed
    if not unknown:
        from app.runtime.jobflow_base import after_delivery

        invalidate(order, now)
        if request.get("change_id"):
            change = find(order.change_orders, request["change_id"], "Change order")
            change.artifact_ids = artifact_ids
            if successful:
                change.status = "FULFILLED"
                emit("change_order.fulfilled", change_order_id=change.id)
        if request.get("issue_id"):
            issue = find(order.issues, request["issue_id"], "Issue")
            issue.owner = "customer" if successful else "controller"
            issue.next_action = (
                "Accept included-field delivery"
                if successful
                else "Review failed field fulfillment"
            )
            if successful:
                issue.state = "RESOLVED"
                issue.resolution = "Authorized included scope delivered and independently validated"
                for job in order.jobs:
                    if issue.id in job.issue_ids:
                        job.dispute = "RESOLVED"
                for question in issue.questions:
                    if question.status == "OPEN":
                        question.status = "CANCELLED"
                emit("dispute.remedied", issue_id=issue.id)
        after_delivery(service, db, order, request, now, emit)


def reconcile(service, db, order, operation_id, now, emit):
    row = db.execute(
        "SELECT body FROM jf_provider_results WHERE operation_id=?", (operation_id,)
    ).fetchone()
    if row is None:
        raise DomainError("No authoritative provider result; retain UNKNOWN and hand off")
    result = json.loads(row[0])
    if any(op.id == operation_id for op in order.finance.operations):
        operation = find(order.finance.operations, operation_id, "Operation")
        if operation.status not in {"UNKNOWN", "PENDING"}:
            raise DomainError("Operation does not require reconciliation")
        finish_payment(db, order, operation_id, result, now, emit)
    else:
        work = db.execute(
            "SELECT * FROM jf_work WHERE id=? AND order_id=? AND kind='delivery'",
            (operation_id, order.id),
        ).fetchone()
        if not work or not any(
            attempt.operation_id == operation_id and attempt.status == "UNKNOWN"
            for job in order.jobs
            for attempt in job.attempts
        ):
            raise DomainError("Unknown execution intent not found")
        finish_delivery(
            service,
            db,
            order,
            operation_id,
            json.loads(work["request"]),
            result,
            now,
            emit,
            reconciled=True,
        )
    emit("operation.reconciled", operation_id=operation_id)


def claim(service):
    with service.store.connect(write=True) as db:
        work = db.execute(
            "SELECT * FROM jf_work WHERE status='QUEUED' ORDER BY rowid LIMIT 1"
        ).fetchone()
        if not work:
            return None
        work = dict(work)
        order = service.store.get(db, work["order_id"])
        order.revision += 1
        request = json.loads(work["request"])
        now = service.clock()
        emit = emitter(service, db, order, work["id"], now)
        if work["kind"] == "investigation":
            run = find(order.investigations, work["id"], "Run")
            run.status = "RUNNING"
            emit("investigation.started", run_id=run.id, issue_id=run.issue_id)
        elif work["kind"] == "delivery":
            for spec in request["specs"]:
                job = find(order.jobs, spec["job_id"], "Job")
                find(job.attempts, spec["attempt_id"], "Attempt").status = "RUNNING"
                job.processing = "RUNNING"
                emit(
                    "correction.started"
                    if request["kind"] == "correction"
                    else "fulfillment.started",
                    job_id=job.id,
                    attempt_id=spec["attempt_id"],
                    operation_id=work["id"],
                )
        db.execute(
            "UPDATE jf_work SET status='RUNNING',result=? WHERE id=?",
            (
                canonical({"claim_revision": order.revision}),
                work["id"],
            ),
        )
        service.store.save(db, order)
        work["request"] = request
        work["claim_revision"] = order.revision
        work["snapshot_current"] = (
            work["kind"] != "investigation" or request["snapshot"]["revision"] == order.revision - 1
        )
        work["scope_current"] = request.get(
            "scope_digest", scope_digest(order, now)
        ) == scope_digest(order, now)
        work["evidence_current"] = request.get(
            "evidence_digest", evidence_digest(order)
        ) == evidence_digest(order)
        if work["kind"] == "payment":
            change = find(order.change_orders, request["change_order_id"], "Change order")
            authority = change.payment_authorization
            work["payment_authorized"] = bool(
                authority
                and now < authority.expires_at
                and authority.quote_id == change.id
                and authority.amount.amount_minor == request["amount_minor"]
                and authority.authorized_by == change.accepted_by
            )
        return work


def produce_delivery(service, work):
    request = work["request"]
    outputs = []
    if not work["scope_current"]:
        return {"executed": False, "outputs": [{} for _ in request["specs"]]}
    for spec in request["specs"]:
        try:
            with service.store.connect() as db:
                raw, _, _ = service.store.artifact(db, work["order_id"], spec["source_id"])
            if request["outcome"] == "FAILURE":
                outputs.append({})
            else:
                output = extract(raw, spec["source_id"], spec["fields"])
                outputs.append({"raw": base64.b64encode(output).decode()})
        except (DomainError, ValueError):
            outputs.append({})
    return {"outputs": outputs, "executed": True}


async def run_once(service):
    work = claim(service)
    if work is None:
        return False
    started = time.monotonic()
    request = work["request"]
    result = None
    error = None
    try:
        if work["kind"] == "delivery":
            result = await asyncio.to_thread(produce_delivery, service, work)
        elif work["kind"] == "payment":
            result = {
                "order_id": work["order_id"],
                "change_order_id": request["change_order_id"],
                "amount_minor": request["amount_minor"],
                "status": "FAILED"
                if request["outcome"] == "FAILURE" or not work["payment_authorized"]
                else "CONFIRMED",
            }
        else:
            if (
                not work["scope_current"]
                or not work["evidence_current"]
                or not work["snapshot_current"]
            ):
                raise DomainError("Queued investigation snapshot is stale")
            investigator = service.investigator
            if investigator is None:
                from app.investigation.jobflow import investigate

                investigator = investigate
            kwargs = {"mode": request["mode"]}
            if service.investigator is None:
                kwargs["now"] = service.clock()
            if request["mode"] == "ANTHROPIC":
                with service.store.connect() as db:
                    reserved = db.execute(
                        "SELECT 1 FROM jf_model_calls WHERE run_id=?", (work["id"],)
                    ).fetchone()
                if not reserved:
                    raise DomainError("No durable model call reservation")
                kwargs["call_authorized"] = True
            outcome = await asyncio.wait_for(
                investigator(
                    OrderView.model_validate(request["snapshot"]), request["issue_id"], **kwargs
                ),
                timeout=90,
            )
            result = outcome.model_dump(mode="json") if hasattr(outcome, "model_dump") else outcome
    except Exception as exc:
        # Never persist exception text from a transport: it can contain keys, URLs or source data.
        error = f"{type(exc).__name__}: interrupted or failed; no automatic inference retry"
    elapsed = int((time.monotonic() - started) * 1000)
    if result is not None and work["kind"] in {"delivery", "payment"}:
        with service.store.connect(write=True) as db:
            db.execute(
                "INSERT OR IGNORE INTO jf_provider_results VALUES(?,?)",
                (work["id"], canonical(result)),
            )
    with service.store.connect(write=True) as db:
        order = service.store.get(db, work["order_id"])
        current_revision = order.revision
        order.revision += 1
        now = service.clock()
        emit = emitter(service, db, order, work["id"], now)
        if work["kind"] == "investigation":
            run = find(order.investigations, work["id"], "Run")
            run.elapsed_ms = elapsed
            if (
                current_revision != work["claim_revision"]
                or not work["snapshot_current"]
                or request["evidence_digest"] != evidence_digest(order)
                or request["scope_digest"] != scope_digest(order, now)
            ):
                run.status = "STALE"
                run.error = "Evidence, scope or order changed while investigation was running"
            elif error:
                run.status = "FAILED"
                run.error = error
            else:
                try:
                    outcome = validate_outcome(
                        order, result, request, store=service.store, db=db, now=now
                    )
                except (DomainError, ValueError) as exc:
                    run.status = "FAILED"
                    run.error = (
                        f"{type(exc).__name__}: investigator output failed boundary validation"
                    )
                else:
                    apply_outcome(order, outcome, now, emit)
                    run.input_tokens = outcome.input_tokens
                    run.output_tokens = outcome.output_tokens
                    run.status = "COMPLETE"
            if run.status != "COMPLETE":
                issue = find(order.issues, run.issue_id, "Issue")
                issue.state = "WAITING_INTERNAL"
                issue.owner = "investigator"
                issue.next_action = (
                    "Review failed/stale run; explicitly request a fresh investigation"
                )
            emit(f"investigation.{run.status.lower()}", run_id=run.id, issue_id=run.issue_id)
        elif error:
            interrupt_work(order, work, emit)
        elif work["kind"] == "payment":
            visible = dict(result)
            if request["outcome"] == "UNKNOWN" and result["status"] != "FAILED":
                visible["status"] = "UNKNOWN"
            finish_payment(db, order, work["id"], visible, now, emit)
        else:
            finish_delivery(service, db, order, work["id"], request, result, now, emit)
        refresh_quotes(order, now, emit)
        from app.runtime.jobflow_base import sync_base

        sync_base(service, db, order, now)
        project(db, order, now)
        service.store.save(db, order)
        db.execute(
            "UPDATE jf_work SET status=?,result=? WHERE id=?",
            (
                "FAILED" if error else "COMPLETE",
                canonical({"error": error, "elapsed_ms": elapsed}),
                work["id"],
            ),
        )
    return True


def interrupt_work(order, work, emit):
    if work["kind"] == "investigation":
        run = find(order.investigations, work["id"], "Run")
        run.status = "FAILED"
        run.error = "Worker interrupted; automatic model retry prohibited"
        issue = find(order.issues, run.issue_id, "Issue")
        issue.state = "WAITING_INTERNAL"
        issue.owner = "investigator"
        issue.next_action = "Review interrupted run and request a fresh investigation explicitly"
    elif work["kind"] == "payment":
        operation = find(order.finance.operations, work["id"], "Operation")
        operation.status = "UNKNOWN"
        if operation.change_order_id:
            find(order.change_orders, operation.change_order_id, "Change").status = "UNKNOWN"
    else:
        for job in order.jobs:
            for attempt in job.attempts:
                if attempt.operation_id == work["id"] and attempt.status in {"QUEUED", "RUNNING"}:
                    attempt.status = "UNKNOWN"
                    attempt.error = (
                        "Interrupted execution; reconcile evidence or hand off, never resend"
                    )
                    job.processing = "RUNNING"
                    job.owner = "executor"
                    job.next_action = (
                        "Reconcile the original operation or hand off if evidence is absent"
                    )
    emit("operation.interrupted", operation_id=work["id"])


def recover(service):
    """Called once at single-worker application startup, not on every HTTP request."""
    with service.store.connect(write=True) as db:
        for row in db.execute("SELECT * FROM jf_work WHERE status='RUNNING'").fetchall():
            work = dict(row)
            order = service.store.get(db, work["order_id"])
            order.revision += 1
            now = service.clock()
            emit = emitter(service, db, order, work["id"], now)
            interrupt_work(order, work, emit)
            project(db, order, now)
            service.store.save(db, order)
            db.execute("UPDATE jf_work SET status='INTERRUPTED' WHERE id=?", (work["id"],))


async def drain(service):
    while await run_once(service):
        pass
