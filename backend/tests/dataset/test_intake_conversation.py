"""Conversational competence cannot invent acceptance of a broader product."""

import json
from types import SimpleNamespace

import pytest

from app.agents.gateway import ClaudeGateway
from app.contracts.catalog import ClarifyCommand, RevisionCommand
from app.contracts.dataset_intake import DatasetIntakeProposal
from app.contracts.runs import RunCreate
from app.orders.runs import Runs


def compile_now(service, run):
    draft = service.get_request(run)
    return service.compile_request(
        run,
        RevisionCommand(
            expected_revision=draft.revision, idempotency_key=f"compile:{draft.revision}"
        ),
    )


def answer(service, draft, text):
    service.clarify(
        draft.request_id,
        ClarifyCommand(
            expected_revision=draft.revision,
            idempotency_key=f"answer:{draft.revision}",
            question_id=draft.question.question_id,
            text=text,
        ),
    )
    return compile_now(service, draft.request_id)


def start(service, prompt="SF adults 25–34 interested in fitness, counts by ZIP."):
    run = Runs(service).create(RunCreate(prompt=prompt), "conversation").id
    return compile_now(service, run)


@pytest.mark.parametrize(
    "response,status",
    [
        ("yes", "ready"),
        ("no", "human_review"),
        ("gym membership", "human_review"),
        ("yes, but only gym members", "human_review"),
    ],
)
def test_exact_screenshot_gets_useful_offer_not_repeated_question(
    dataset_service, response, status
):
    service, _ = dataset_service
    first = start(service)
    second = answer(service, first, "gym membership")
    assert first.question.prompt != second.question.prompt
    assert second.question.field == "category_offer_base"
    assert "OR fitness-app" in second.question.prompt and "unavailable" in second.question.prompt
    assert second.specification is None and second.questions_asked == 2
    final = answer(service, second, response)
    assert (
        final.status == status and final.deadline == first.deadline and final.prompt == first.prompt
    )
    assert final.questions_asked == 2 and len(final.answers) == 2
    if status == "ready":
        assert final.specification.terms.category == "gym_or_fitness_app"
    else:
        assert final.specification is None and "scope" in final.error.lower()


@pytest.mark.parametrize(
    "text",
    [
        "gym membership",
        "fitness apps",
        "gym members only",
        "gym members, no apps",
        "gym membership and fitness app use",
        "gym membership; fitness apps not wanted",
        "gym membership, not interested in apps",
        "fitness apps, gym membership excluded",
    ],
)
def test_narrow_requests_are_not_silently_union_products(dataset_service, text):
    service, _ = dataset_service
    draft = start(service, "SF adults 25-34, " + text)
    assert draft.status == "clarification" and draft.question.field == "category_offer_base"
    assert draft.specification is None


def test_partial_ambiguous_answer_does_not_repeat(dataset_service):
    service, _ = dataset_service
    first = start(service)
    second = answer(service, first, "I'm not sure")
    assert first.question.prompt != second.question.prompt
    assert second.question.field == "category_offer_base"


class ModelIntent:
    def __init__(
        self, scope="ambiguous", quote=None, question="Which fitness population do you mean?"
    ):
        self.calls = []
        self.scope, self.quote, self.question = scope, quote, question

    def parse(self, **kwargs):
        assert kwargs["output_format"] is DatasetIntakeProposal
        assert "NOT a supplier catalog" in kwargs["system"]
        assert kwargs["timeout"] == 20 and kwargs["max_tokens"] == 4096
        payload = json.loads(kwargs["messages"][0]["content"])
        self.calls.append(payload)
        draft = payload["draft"]
        text = draft["answers"][-1]["text"] if draft["answers"] else draft["prompt"]
        return SimpleNamespace(
            stop_reason="end_turn",
            usage={"input_tokens": 100, "output_tokens": 20},
            parsed_output=DatasetIntakeProposal(
                requested_scope=self.scope,
                evidence_quote=self.quote or text,
                clarification=self.question,
                explanation="Interpretation of the buyer's actual text.",
            ),
        )


def use_model(service, fake):
    gateway = ClaudeGateway(
        enabled=True, model="claude-opus-5-5", client=SimpleNamespace(messages=fake)
    )
    service.compiler = service.dataset_compiler = gateway


def test_model_generates_question_and_receives_actual_answers_and_history(dataset_service):
    service, _ = dataset_service
    fake = ModelIntent()
    use_model(service, fake)
    first = start(service)
    assert first.question.prompt == fake.question and len(fake.calls) == 1
    fake.scope = "gym_only"
    second = answer(
        service, first, "People buying access to the weight room, not workout software."
    )
    assert second.question.field == "category_offer_base" and second.specification is None
    assert fake.calls[-1]["draft"]["answers"][-1]["text"].startswith("People buying")
    assert fake.calls[-1]["draft"]["question_history"][0]["prompt"] == first.question.prompt
    fake.scope = "gym_or_fitness_app"
    final = answer(service, second, "yes")
    assert final.status == "ready" and final.questions_asked == 2 and len(fake.calls) == 3


def test_wrong_model_union_cannot_override_explicit_narrow_answer(dataset_service):
    service, _ = dataset_service
    fake = ModelIntent("gym_or_fitness_app")
    use_model(service, fake)
    draft = start(service, "SF adults 25-34, gym membership only; no apps.")
    assert draft.specification is None and draft.question.field == "category_offer_base"


def test_model_proposes_expanded_paraphrase_but_needs_explicit_consent(dataset_service):
    service, _ = dataset_service
    use_model(service, ModelIntent("gym_app_or_yoga"))
    draft = start(
        service,
        "SF adults 25-34: weight-room members, workout software subscribers, "
        "plus people attending standalone yoga studios.",
    )
    assert draft.question.field == "category_offer_yoga" and draft.specification is None
    assert "OR standalone yoga" in draft.question.prompt
    final = answer(service, draft, "yes")
    assert final.status == "ready" and final.specification.terms.category == "gym_app_or_yoga"


def test_model_can_identify_ambiguity_beyond_offline_keywords(dataset_service):
    service, _ = dataset_service
    fake = ModelIntent(
        question="Do you mean anyone in the combined group, or only active subscribers?"
    )
    use_model(service, fake)
    first = start(service, "SF adults 25-34, gym or fitness app users with current subscriptions.")
    assert first.question.prompt == fake.question and first.specification is None


@pytest.mark.parametrize(
    "scope,quote,question",
    [
        ("unsupported", None, None),
        ("ambiguous", "fabricated words", "What scope?"),
    ],
)
def test_unsupported_or_invalid_model_proposal_cannot_create_terms(
    dataset_service, scope, quote, question
):
    service, _ = dataset_service
    use_model(service, ModelIntent(scope, quote, question))
    draft = start(service)
    assert draft.status == "human_review" and draft.specification is None


def test_model_cannot_repeat_question_after_meaningful_answer(dataset_service):
    service, _ = dataset_service
    use_model(service, ModelIntent())
    first = start(service)
    final = answer(service, first, "People who train regularly")
    assert final.status == "human_review" and final.questions_asked == 1
    assert "repeat" in final.error


@pytest.mark.parametrize(
    "correction,category",
    [
        ("Exclude yoga.", "gym_or_fitness_app"),
        ("Include yoga.", "gym_app_or_yoga"),
    ],
)
def test_bound_yoga_correction_resolves_conflict(dataset_service, correction, category):
    service, _ = dataset_service
    first = start(
        service, "SF adults 25-34, gym or fitness app use. Include yoga but exclude yoga."
    )
    assert first.question.field == "category"
    final = answer(service, first, correction)
    assert final.status == "ready" and final.specification.terms.category == category
    assert final.prompt == first.prompt and final.deadline == first.deadline


def test_yoga_correction_cannot_erase_original_app_exclusion(dataset_service):
    service, _ = dataset_service
    first = start(service, "SF adults 25-34, gym only, no apps. Include yoga but exclude yoga.")
    second = answer(service, first, "Exclude yoga.")
    assert second.specification is None and second.question.field == "category_offer_base"


def test_cohort_answer_cannot_silently_narrow_category(dataset_service):
    service, _ = dataset_service
    first = start(service, "SF adults 18-24, gym membership or fitness app use.")
    second = answer(service, first, "Use SF adults 25-34, no apps.")
    assert second.specification is None and second.question.field == "category_offer_base"


def test_unsupported_cohort_never_becomes_supported_by_repetition(dataset_service):
    service, _ = dataset_service
    first = start(service, "Oakland adults 18-24, gym membership or fitness app use.")
    second = answer(service, first, "Keep Oakland adults 18-24.")
    assert first.question.prompt != second.question.prompt
    final = answer(service, second, "Keep Oakland adults 18-24.")
    assert final.status == "human_review" and final.specification is None


def test_restart_preserves_offer_and_consent_history(dataset_service):
    from app.orders.catalog import CatalogService
    from app.storage.catalog import CatalogRepository

    service, clock = dataset_service
    first = start(service)
    offer = answer(service, first, "gym membership")
    restarted = CatalogService(
        CatalogRepository(service.repository.path), service.store.root, clock
    )
    final = answer(restarted, offer, "Yes, the combined product is fine.")
    assert final.status == "ready" and len(final.question_history) == 2
    assert final.question_history[-1] == offer.question and final.deadline == first.deadline


def test_model_uses_shared_reservations_and_compile_replay_is_free(dataset_service, tmp_path):
    from app.agents.bounded_client import BoundedClient
    from tests.investigation.test_model_budget import budget

    service, _ = dataset_service
    ledger = budget(tmp_path)
    fake = ModelIntent()
    client = BoundedClient(client=SimpleNamespace(messages=fake), budget=ledger)
    gateway = ClaudeGateway(enabled=True, model="claude-opus-5-5", client=client)
    service.dataset_compiler = gateway
    run = Runs(service).create(RunCreate(), "bounded-intake").id
    draft = service.get_request(run)
    command = RevisionCommand(expected_revision=draft.revision, idempotency_key="one-call")
    first = service.compile_request(run, command)
    assert first.status == "clarification"
    assert service.compile_request(run, command) == first
    assert len(fake.calls) == ledger.summary()["requests_used"] == 1
    assert ledger.summary()["active"] == 0 and ledger.summary()["known_cost_usd"] == 0.0008
    with service.repository.transaction() as db:
        saved = service.repository.load(db, "dataset_intake", f"{run}:2", DatasetIntakeProposal)
    assert saved.clarification == first.question.prompt


@pytest.mark.parametrize("denial", ["expired", "money", "concurrent"])
def test_denied_budget_never_reaches_intake_transport(dataset_service, tmp_path, denial):
    from datetime import UTC, datetime, timedelta

    from app.agents.bounded_client import BoundedClient
    from tests.investigation.test_model_budget import budget

    service, _ = dataset_service
    ledger = budget(tmp_path, maximum_usd=0.01 if denial == "money" else 45)
    if denial == "expired":
        ledger.cutoff = datetime.now(UTC) - timedelta(seconds=1)
    if denial == "concurrent":
        for n in range(2):
            ledger.reserve("occupied", "claude-opus-5-5", {"n": n}, 10)
    fake = ModelIntent()
    service.dataset_compiler = ClaudeGateway(
        enabled=True,
        model="claude-opus-5-5",
        client=BoundedClient(client=SimpleNamespace(messages=fake), budget=ledger),
    )
    final = start(service)
    assert final.status == "human_review" and final.specification is None
    assert not fake.calls and "authorization denied" in final.error


def test_expired_draft_and_stale_question_never_dispatch(dataset_service):
    from app.orders.service import DomainError

    service, clock = dataset_service
    fake = ModelIntent()
    use_model(service, fake)
    first = start(service)
    with pytest.raises(DomainError):
        service.clarify(
            first.request_id,
            ClarifyCommand(
                expected_revision=first.revision,
                idempotency_key="stale",
                question_id="other",
                text="yes",
            ),
        )
    clock.advance(301)
    with pytest.raises(DomainError):
        answer(service, first, "gym membership")
    assert len(fake.calls) == 1
    assert service.get_request(first.request_id).status == "human_review"


@pytest.mark.parametrize("model_enabled", [False, True])
def test_http_intake_questions_preserve_scope_and_no_financial_authority(tmp_path, model_enabled):
    from fastapi.testclient import TestClient

    from app.main import create_app

    fake = ModelIntent()
    gateway = (
        ClaudeGateway(enabled=True, model="claude-opus-5-5", client=SimpleNamespace(messages=fake))
        if model_enabled
        else None
    )
    with TestClient(
        create_app(
            tmp_path / "http.sqlite3",
            artifact_root=tmp_path / "artifacts",
            run_worker=False,
            compiler=gateway,
            payment_mode="mock",
            internal_token="test-worker",
            reviewer_token="test-reviewer",
        )
    ) as client:
        created = client.post(
            "/runs",
            json={"prompt": "SF adults 25-34 interested in fitness, counts by ZIP."},
            headers={"Idempotency-Key": "http-intake"},
        )
        assert created.status_code == 201
        run = created.json()["id"]
        prompts = []
        for index, text in enumerate([None, "gym membership", "yes"]):
            draft = client.get(f"/requests/{run}").json()
            if text:
                response = client.post(
                    f"/requests/{run}/answers",
                    json={
                        "expected_revision": draft["revision"],
                        "idempotency_key": f"a:{index}",
                        "question_id": draft["question"]["question_id"],
                        "text": text,
                    },
                )
                assert response.status_code == 200
                draft = response.json()
            fake.scope = ["ambiguous", "gym_only", "gym_or_fitness_app"][index]
            response = client.post(
                f"/internal/requests/{run}/compile",
                json={
                    "expected_revision": draft["revision"],
                    "idempotency_key": f"c:{index}",
                },
                headers={"X-Internal-Token": "test-worker"},
            )
            assert response.status_code == 200
            draft = response.json()
            if index < 2:
                assert draft["status"] == "clarification" and draft["specification"] is None
                prompts.append(draft["question"]["prompt"])
        assert len(set(prompts)) == 2 and draft["status"] == "ready"
        assert draft["specification"]["terms"]["category"] == "gym_or_fitness_app"
        page = client.get(f"/runs/{run}/events").json()
        questions = [
            e["message"]["text"]
            for e in page["events"]
            if e["type"] == "message" and e["message"].get("asks")
        ]
        assert questions == prompts and page["payment"] is None and page["quote"] is None
        assert not {"contract_approved", "payment_captured"} & {e["type"] for e in page["events"]}
        assert len(fake.calls) == (3 if model_enabled else 0)
