"""Test-owned fixtures around normal service acceptance/funding boundaries."""

import os
import socket
from contextlib import ExitStack, contextmanager
from datetime import timedelta
from unittest.mock import patch

from evals.aggregate.schema import write_json
from tools.brokerage_acceptance import Clock, accept, cmd

from app.agents.gateway import OfflineAssessor
from app.catalog.artifacts import ArtifactStore
from app.contracts.catalog import (
    CompilerOutput,
    Complaint,
    DisputeCommand,
    QuoteRequest,
    RevisionCommand,
)
from app.contracts.payments import FundingAuthorization
from app.contracts.runs import RunCreate, RunOffer
from app.datasets import canonical, make_terms, produce_dataset
from app.orders.catalog import CatalogService
from app.orders.run_events import binding
from app.orders.runs import Runs
from app.storage.catalog import CatalogRepository


def denied(*args, **kwargs):
    raise RuntimeError("offline_evaluation_forbids_network_or_provider")


@contextmanager
def offline_guards():
    """No optional paid lane. Explicit clients plus network tripwires, even in tests."""
    with ExitStack() as stack:
        stack.enter_context(
            patch.dict(
                os.environ,
                {
                    "ENABLE_PAID_MODELS": "false",
                    "ENABLE_TESTNET_BROADCAST": "false",
                    "ENABLE_DATASET_MODEL_ASSESSMENT": "false",
                    "PAYMENT_ADAPTER": "mock",
                },
                clear=True,
            )
        )
        for target in (
            "app.agents.gateway.ClaudeGateway.__init__",
            "anthropic.Anthropic.__init__",
            "anthropic.AsyncAnthropic.__init__",
            "app.payments.base.BasePaymentTransport.__init__",
        ):
            stack.enter_context(patch(target, denied))
        for name in ("connect", "connect_ex", "sendto"):
            stack.enter_context(patch.object(socket.socket, name, denied))
        stack.enter_context(patch.object(socket, "getaddrinfo", denied))
        yield


class FixtureCompiler:
    """An explicit agreed gym/app fixture, not conversational interpretation."""

    def __init__(self, store, trace):
        self.store, self.trace = store, trace

    def compile(self, context):
        self.trace.append({"boundary": "compiler", "input": context.model_dump(mode="json")})
        return CompilerOutput(
            terms=make_terms(context.sources, self.store, request_id=context.draft.request_id),
            question=None,
            summary="Explicit synthetic gym/app cohort by ZIP.",
            limitations=("Synthetic explicitly specified cohort; no live acquisition.",),
        )


class StepLimit(RuntimeError):
    pass


def execute(recipe, directory, max_steps):
    """No expectation, rationale, split or case title is accepted by this boundary."""
    with offline_guards():
        return _execute(recipe, directory, max_steps)


def _execute(recipe, directory, max_steps):
    clock, trace = Clock(), []
    store = ArtifactStore(directory / "artifacts")
    service = CatalogService(
        CatalogRepository(directory / "orders.sqlite3"),
        store.root,
        clock,
        compiler=FixtureCompiler(store, trace),
        assessor=OfflineAssessor(),
        payment_mode="mock",
        auto_mock_funding=False,
    )
    steps, observed, produced = 0, {}, []

    def step(function, *args, **kwargs):
        nonlocal steps
        steps += 1
        if steps > max_steps:
            raise StepLimit("case_step_limit")
        trace.append(
            {
                "boundary": function.__name__,
                "inputs": [a.model_dump(mode="json") for a in args if hasattr(a, "model_dump")],
            }
        )
        write_json(directory / f"input-{steps:02}.json", trace[-1])
        return function(*args, **kwargs)

    complete = service.complete_verification

    def observe(order_id, job, report, artifact=None, preview=None, semantic=None):
        observation = {
            "job": job.model_dump(mode="json"),
            "verification": report.model_dump(mode="json"),
            "semantic": semantic.model_dump(mode="json") if semantic else None,
            "output": {
                "csv": artifact.model_dump(mode="json"),
                "preview": preview.model_dump(mode="json"),
                "version": report.binding.delivery_version,
            }
            if artifact and preview
            else None,
        }
        write_json(
            directory / f"attempt-{len(list(directory.glob('attempt-*.json'))) + 1:02}.json",
            observation,
        )
        observed[order_id] = observation
        return complete(order_id, job, report, artifact, preview, semantic)

    def produce(terms, sources, artifact_store):
        trace.append(
            {
                "boundary": "producer",
                "terms": terms.model_dump(mode="json"),
                "sources": [s.model_dump(mode="json") for s in sources],
            }
        )
        csv, preview = produce_dataset(terms, sources, artifact_store)
        if recipe == "correction" and not produced:
            raw = (
                b"\n".join(
                    line
                    for line in artifact_store.read(csv).splitlines()
                    if not line.startswith(b"94110,")
                )
                + b"\n"
            )
            csv = artifact_store.put(raw, "text/csv")
        produced.append(csv.artifact_id)
        return csv, preview

    def new_order():
        run = step(
            Runs(service).create,
            RunCreate(
                prompt="San Francisco adults 25-34, gym membership or fitness app use, "
                "grouped by ZIP."
            ),
            "create",
        )
        # Register altered synthetic evidence BEFORE compilation/quote/acceptance.
        # This uses the ordinary immutable source registry, never a DB rewrite.
        if recipe in ("insufficient", "contradictory"):
            sources = service.registry.manifest("sf-aggregate-v1")
            suffix = ":authority" if recipe == "insufficient" else ":gym_or_fitness_app"
            source = next(s for s in sources if s.source_id.endswith(suffix))
            import json

            data = json.loads(store.read(source.artifact))
            data["version"] = 2
            if recipe == "insufficient":
                data["registered_publisher"] = ""
            else:
                data["edition"] = "synthetic-2025-10"
            step(
                service.registry.register,
                source.model_copy(
                    update={
                        "version": 2,
                        "artifact": store.put(canonical(data), "application/json"),
                    }
                ),
            )
        draft = service.get_request(run.id)
        draft = step(
            service.compile_request,
            run.id,
            RevisionCommand(expected_revision=draft.revision, idempotency_key="compile"),
        )
        quote = step(
            service.issue_quote,
            run.id,
            QuoteRequest(expected_revision=draft.revision, idempotency_key="quote"),
        )
        order = step(accept, service, quote, "accept")
        write_json(directory / "accepted.json", order.model_dump(mode="json"))
        return order

    def fund(order):
        prep = step(service.payments.prepare, order.snapshot.order_id, cmd(order, "prepare"))
        order = step(
            service.payments.authorize,
            order.snapshot.order_id,
            FundingAuthorization(
                **cmd(order, "authorize").model_dump(),
                funding_attempt_id=prep.funding_attempt_id,
                payment_hash=prep.terms.payment_hash,
                simulate=True,
            ),
        )
        step(service.payments.work)
        return step(service.run_one, order.snapshot.order_id)

    def save(order, name):
        order_id = order.snapshot.order_id
        view = service.current_view(order_id)
        events, cursor = [], 0
        while True:
            page = step(Runs(service).page, order.snapshot.quote.request_id, cursor)
            events.extend(e.model_dump(mode="json", by_alias=True) for e in page.events)
            if page.caught_up:
                break
            cursor = page.next_after
        data = {
            "id": name,
            "order": order.model_dump(mode="json"),
            "payment": view.payment.model_dump(mode="json"),
            "events": events,
            "attempt": observed.get(order_id),
        }
        write_json(directory / f"checkpoint-{name}.json", data)
        write_json(directory / f"runtime-inputs-{name}.json", trace)
        if order.order_state == "operational_failure" or any(
            j.status == "failed" for j in order.jobs
        ):
            raise RuntimeError("runtime_job_failed")

    with (
        patch.object(service, "complete_verification", observe),
        patch("app.orders.dataset.produce_dataset", produce),
    ):
        order = fund(new_order())
        if recipe == "conforming":
            save(order, "delivery")
            clock.now += timedelta(seconds=60)
            order = step(service.get, order.snapshot.order_id)
            save(order, "settled")
        elif recipe == "correction":
            save(order, "initial")
            order = step(service.run_one, order.snapshot.order_id)
            save(order, "corrected")
        elif recipe == "complaint":
            save(order, "delivery")
            order = step(
                service.mutate,
                order.snapshot.order_id,
                "dispute",
                DisputeCommand(
                    **cmd(order, "dispute").model_dump(),
                    complaint=Complaint(
                        artifact_id=order.deliveries[-1].csv.artifact_id,
                        requirement_id="R-CATEGORY",
                        product_id="dataset",
                        field="category",
                        text="Standalone yoga belongs in the accepted gym membership definition.",
                        intent="dispute_fact",
                    ),
                ),
            )
            order = step(service.run_one, order.snapshot.order_id)
            save(order, "complaint")
        elif recipe == "additional_scope":
            save(order, "parent")
            offer = step(
                Runs(service).offer,
                order.snapshot.quote.request_id,
                RunOffer(binding=binding(order), scope="oakland"),
                "offer",
                "provider:eval",
            )
            child = step(accept, service, offer, "accept-child")
            write_json(directory / "accepted-child.json", child.model_dump(mode="json"))
            child = fund(child)
            save(child, "child")
        else:
            save(order, "source")
    return {"steps": steps, "clock": clock().isoformat()}
