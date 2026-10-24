import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.contracts.jobflow import Agreement, Amendment, Evidence, Issue, Message, OrderView
from app.investigation.documents import (
    DocumentError,
    cite,
    cite_field,
    extract_document,
    validate_citation,
)
from app.investigation.jobflow import (
    Interpretation,
    ModelResponseError,
    ModelUnavailable,
    assess,
    effective_fields,
    investigate,
    scoped_sources,
    validate_interpretation,
)

NOW = datetime(2026, 10, 24, 2, tzinfo=UTC)


def source(id, text, kind="agreement", authority="ACCEPTED_AGREEMENT"):
    return Evidence(
        id=id,
        sha256=hashlib.sha256(text.encode()).hexdigest(),
        filename=id + ".txt",
        media_type="text/plain",
        kind=kind,
        authority=authority,
        text=text,
        created_at=NOW,
        origin_actor_id="provider",
    )


def order(included=False, claim=True):
    fields = ["invoice_number", "amount", "currency"] + (["due_date"] if included else [])
    agreement = source("agreement", "Accepted fields: " + ", ".join(fields))
    messages = []
    evidence = [agreement]
    if claim:
        message = source(
            "kickoff",
            "We discussed including due_date in the kickoff.",
            "message",
            "PARTY_ASSERTION",
        )
        evidence.append(message)
        messages.append(
            Message(
                id="message-1",
                issue_id="issue-1",
                author_id="customer",
                author_name="Northwind",
                text=message.text,
                timestamp=NOW,
                source_id=message.id,
            )
        )
    return OrderView(
        id="order-1",
        case_id="case-1",
        revision=1,
        customer_id="northwind",
        customer_name="Northwind",
        title="Invoices",
        created_at=NOW,
        agreement=Agreement(fields=fields, document_count=100, source_id=agreement.id),
        jobs=[],
        evidence=evidence,
        issues=[
            Issue(id="issue-1", field="due_date", title="Due date", job_ids=[], messages=messages)
        ],
    )


def test_included_field_has_exact_current_source_proof():
    current = order(included=True)
    outcome = assess(current, "issue-1", now=NOW)
    assert outcome.recommendations == ["INCLUDED_FIELD"]
    assert not outcome.questions
    validate_citation(current.evidence, outcome.findings[0].citations[0])


def test_kickoff_request_is_not_accepted_amendment():
    outcome = assess(order(), "issue-1", now=NOW)
    assert outcome.recommendations == ["HUMAN_REVIEW"]
    assert outcome.findings[0].status == "CONFLICTING"
    assert len(outcome.questions) == 1
    assert "accepted" in outcome.questions[0].text


def test_clear_addition_does_not_force_a_fake_question():
    outcome = assess(order(claim=False), "issue-1", now=NOW)
    assert outcome.recommendations == ["QUOTE"]
    assert not outcome.questions


def test_question_id_stable_on_repeated_investigation():
    current = order()
    assert assess(current, "issue-1").questions == assess(current, "issue-1").questions


def test_missing_accepted_evidence_requires_specific_request():
    current = order()
    current.evidence = current.evidence[1:]
    result = assess(current, "issue-1")
    assert result.findings[0].status == "INSUFFICIENT"
    assert "accepted field list" in result.questions[0].text


def test_party_upload_cannot_replace_authoritative_agreement():
    current = order(included=True)
    current.evidence[0].authority = "PARTY_ASSERTION"
    assert assess(current, "issue-1").recommendations == ["HUMAN_REVIEW"]


def test_negated_field_mention_does_not_prove_inclusion():
    current = order(included=True)
    current.evidence[0] = source("agreement", "due_date is not included.")
    assert assess(current, "issue-1").recommendations == ["HUMAN_REVIEW"]


def test_negated_new_scope_answer_does_not_become_acceptance():
    current = order()
    current.issues[0].messages.append(
        Message(
            id="answer",
            issue_id="issue-1",
            author_id="customer",
            author_name="Northwind",
            text="This is not additional scope.",
            timestamp=NOW,
            question_id="question",
        )
    )
    assert assess(current, "issue-1").recommendations == ["HUMAN_REVIEW"]


def test_answer_acknowledging_extra_scope_can_prepare_quote_only():
    current = order()
    current.issues[0].messages.append(
        Message(
            id="answer",
            issue_id="issue-1",
            author_id="customer",
            author_name="Northwind",
            text="Due date is additional scope.",
            timestamp=NOW,
            question_id="question",
        )
    )
    assert assess(current, "issue-1").recommendations == ["QUOTE"]
    assert current.finance.received_minor == 0


def test_current_time_changes_scope_without_revision_change():
    current = order()
    current.evidence.append(source("amendment", "Fields: due_date", "amendment"))
    current.agreement.amendments.append(
        Amendment(
            id="amend-1",
            fields=["due_date"],
            effective_at=NOW + timedelta(minutes=2),
            accepted_by_customer="customer",
            accepted_by_provider="provider",
            source_id="amendment",
        )
    )
    assert "due_date" not in effective_fields(current, NOW)
    assert assess(current, "issue-1", now=NOW).recommendations == ["HUMAN_REVIEW"]
    assert assess(current, "issue-1", now=NOW + timedelta(minutes=3)).recommendations == [
        "INCLUDED_FIELD"
    ]
    assert current.revision == 1


def test_one_party_signature_is_not_an_accepted_amendment():
    current = order()
    current.evidence.append(source("amendment", "Fields: due_date", "amendment"))
    current.agreement.amendments.append(
        Amendment(
            id="amend-1",
            fields=["due_date"],
            effective_at=NOW - timedelta(minutes=2),
            accepted_by_customer="customer",
            source_id="amendment",
        )
    )
    assert assess(current, "issue-1", now=NOW).recommendations == ["HUMAN_REVIEW"]


def test_other_issue_messages_are_not_in_model_context():
    current = order()
    current.evidence.append(
        source("unrelated", "Different customer's secret", "message", "PARTY_ASSERTION")
    )
    assert "unrelated" not in {s.id for s in scoped_sources(current, "issue-1")}
    with pytest.raises(ValueError):
        scoped_sources(current, "other-issue")


def test_tampered_citation_version_hash_and_quote_rejected():
    current = order()
    evidence = current.evidence[0]
    original = cite(evidence, evidence.text)
    for changes in (
        {"version": 2},
        {"sha256": "0" * 64},
        {"quote": "invented"},
        {"locator": "text:0:999999"},
        {"source_id": "another-order"},
    ):
        with pytest.raises(DocumentError):
            validate_citation(current.evidence, original.model_copy(update=changes))


def test_model_cannot_authorize_included_field_from_party_claim():
    current = order()
    baseline = assess(current, "issue-1")
    model = Interpretation(
        summary="Included", findings=baseline.findings, recommendation="INCLUDED_FIELD"
    )
    with pytest.raises(ModelResponseError):
        validate_interpretation(current, "issue-1", model, baseline)


def test_anthropic_requires_persisted_budget_reservation():
    with pytest.raises(ModelUnavailable):
        asyncio.run(investigate(order(), "issue-1", mode="ANTHROPIC"))


def test_anthropic_uses_structured_scoped_input_with_no_financial_tools():
    current = order()
    baseline = assess(current, "issue-1")
    result = Interpretation(
        summary=baseline.summary, findings=baseline.findings, recommendation="HUMAN_REVIEW"
    )
    captured = {}

    class Messages:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                content=[
                    SimpleNamespace(
                        type="tool_use",
                        name="submit_analysis",
                        input=result.model_dump(mode="json"),
                    )
                ],
                stop_reason="tool_use",
            )

    client = SimpleNamespace(messages=Messages())
    output = asyncio.run(
        investigate(current, "issue-1", mode="ANTHROPIC", call_authorized=True, client=client)
    )
    assert output.model_mode == "ANTHROPIC"
    assert [t["name"] for t in captured["tools"]] == ["submit_analysis"]
    assert "finance" not in captured["messages"][0]["content"]
    assert current.revision == 1


@pytest.mark.parametrize(
    "filename,media,raw",
    [
        ("../secret.txt", "text/plain", b"x"),
        ("evidence.pdf", "application/pdf", b"not pdf"),
        ("empty.txt", "text/plain", b""),
        ("bad.json", "application/json", b'{"a":1,"a":2}'),
        ("bad.csv", "text/csv", b"a,a\n1,2"),
        ("bad.csv", "text/csv", b"a,b\n1"),
        ("bad.txt", "text/plain", b"\xff"),
    ],
)
def test_unsafe_or_ambiguous_document_rejected(filename, media, raw):
    with pytest.raises(DocumentError):
        extract_document(raw, filename, media)


def test_extraction_preserves_original_hash_and_cell_data():
    raw = b"invoice,amount\nN-1,1200\n"
    parsed = extract_document(raw, "invoices.csv", "text/csv")
    assert parsed["sha256"] == hashlib.sha256(raw).hexdigest()
    assert parsed["structured"]["rows"] == [["N-1", "1200"]]


def test_json_pointer_exact_field_and_escaped_key():
    evidence = source("json", '{"rows":[{"a/b":1200}]}', "source", "COMPANY_RECORD")
    evidence.media_type = "application/json"
    citation = cite_field(evidence, "json:/rows/0/a~1b")
    assert citation.quote == "1200"
    validate_citation([evidence], citation)
    for locator in ("json:", "json:/rows", "json:/rows/00/a~1b", "json:/rows/1/a~1b"):
        with pytest.raises(DocumentError):
            cite_field(evidence, locator)


def test_csv_cell_keeps_row_and_column_distinct():
    evidence = source("csv", "invoice,amount\nA,1200\nB,2400\n", "source", "COMPANY_RECORD")
    evidence.media_type = "text/csv"
    citation = cite_field(evidence, 'csv:[2,"amount"]')
    assert citation.quote == "2400"
    validate_citation([evidence], citation)
    with pytest.raises(DocumentError):
        validate_citation([evidence], citation.model_copy(update={"locator": 'csv:[1,"amount"]'}))
