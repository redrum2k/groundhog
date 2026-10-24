"""Integer-cent, unit-acceptance demonstration books, not the legacy mock escrow."""

from app.contracts.jobflow import Posting, PostingLine
from app.runtime.jobflow_policy import effective_fields, utcnow
from app.storage.jobflow import uid


def post(db, order, business_id, amount, debit, credit, description, now, emit):
    if not amount:
        return
    if db.execute("SELECT 1 FROM jf_postings WHERE business_event_id=?", (business_id,)).fetchone():
        return
    posting = Posting(
        id=uid("posting"),
        business_event_id=business_id,
        description=description,
        timestamp=now,
        lines=[
            PostingLine(account=debit, debit_minor=amount),
            PostingLine(account=credit, credit_minor=amount),
        ],
    )
    db.execute(
        "INSERT INTO jf_postings VALUES(?,?,?)",
        (
            business_id,
            order.id,
            posting.model_dump_json(),
        ),
    )
    emit("accounting.posted", posting_id=posting.id, business_event_id=business_id)


def project(db, order, now=None):
    postings = [
        Posting.model_validate_json(row[0])
        for row in db.execute(
            "SELECT body FROM jf_postings WHERE order_id=? ORDER BY rowid", (order.id,)
        )
    ]
    balances = dict.fromkeys(
        ["cash", "contract_liability", "revenue", "correction_expense", "compute_payable"], 0
    )
    for posting in postings:
        for line in posting.lines:
            balances[line.account] += line.debit_minor - line.credit_minor
    order.finance.postings = postings
    order.finance.received_minor = balances["cash"]
    order.finance.liability_minor = -balances["contract_liability"]
    order.finance.recognized_minor = -balances["revenue"]
    order.finance.correction_cost_minor = balances["correction_expense"]
    order.finance.unknown_minor = sum(
        op.amount_minor for op in order.finance.operations if op.status == "UNKNOWN"
    )
    order.finance.approved_additions_minor = sum(
        change.amount_minor
        for change in order.change_orders
        if change.status not in {"DRAFT", "DECLINED"}
    )
    if order.status == "HANDED_OFF":
        return
    unresolved = any(issue.state != "RESOLVED" for issue in order.issues)
    required = set(effective_fields(order, now or utcnow()))
    for job in order.jobs:
        if job.kind != "ORIGINAL":
            continue
        covered = set(job.fields) if job.accepted_artifact_id == job.artifact_id else set()
        for child in order.jobs:
            if child.parent_id == job.id and child.accepted_artifact_id:
                covered.update(child.fields)
        if not required <= covered:
            unresolved = True
    pending_actions = any(action.status in {"PROPOSED", "APPROVED"} for action in order.actions)
    pending_changes = any(
        change.status not in {"DECLINED", "RECOGNIZED"} for change in order.change_orders
    )
    open_jobs = [job for job in order.jobs if job.obligation != "FULFILLED"]
    paid_original = any(
        operation.change_order_id is None and operation.status == "CONFIRMED"
        for operation in order.finance.operations
    )
    pending_money = any(operation.status != "CONFIRMED" for operation in order.finance.operations)
    if (
        not unresolved
        and not pending_actions
        and not pending_changes
        and not open_jobs
        and paid_original
        and not pending_money
        and order.finance.liability_minor == 0
    ):
        order.status = "COMPLETE"
    elif any(job.owner == "provider" and job.obligation == "OPEN" for job in open_jobs):
        order.status = "ACTIVE"
    else:
        order.status = "WAITING"
