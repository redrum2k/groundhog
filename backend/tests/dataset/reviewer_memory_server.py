"""Isolated browser-test app with injected model transport; never a model-quality demo.

Run only with a fresh ORDER_DB_PATH, ARTIFACT_ROOT and mock payments. No private
configuration is loaded. Both assessor and blind reviewer use this local fixture.
The fixture reads current evidence; memory presence never chooses its verdict.
"""

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

from app.agents.gateway import ClaudeGateway
from app.contracts.catalog import Assessment, Provenance
from app.contracts.dataset import DatasetReference
from app.contracts.semantic import DatasetClaimReview, DatasetClauseReview
from app.investigation import dataset
from app.main import create_app


class InjectedClient:
    response_sink = None

    def __init__(self, **kwargs):
        self.messages = self

    def parse(self, **kwargs):
        packet = json.loads(kwargs["messages"][0]["content"])
        schema = kwargs["output_format"]
        if schema is Assessment:
            text = packet["claim"].split(". Claim: ", 1)[1].split(". Customer testimony:", 1)[0]
            passages = packet["evidence"]
        else:
            text = packet["complaint"]
            passages = packet["frozen_evidence_packet"]["passages"]
        refs = tuple(DatasetReference.model_validate(p["citation"]) for p in passages)
        result = "UNKNOWN"
        explanation = (
            "Injected offline assessor: this question needs a clearer evidence interpretation."
        )
        # Finite test-fixture interpretation, independent of run number or memory presence.
        if text == "Regenerate the delivery because ZIP 94110 is missing.":
            if any(r.source_id == "delivery" and r.row == "94110" for r in refs):
                result = "FAIL"
                explanation = (
                    "ZIP 94110 has resolving cells in the current verified delivery; "
                    "the missing-row claim does not justify regeneration."
                )
        elif text in {
            "Under our accepted scope, standalone yoga counts as gym membership.",
            "Yoga membership qualifies as gym membership.",
        }:
            taxonomy = next((r.value for r in refs if r.column == "yoga_is_gym"), None)
            if taxonomy in {"true", "false"}:
                result = "PASS" if taxonomy == "true" else "FAIL"
                explanation = (
                    "The current frozen yoga_is_gym cell is "
                    + taxonomy
                    + "; this resolves the taxonomy claim without inferring membership "
                    "from the Wellness label."
                )
        if schema is Assessment:
            parsed = Assessment(
                obligation_id=packet["requirement"]["obligation_id"],
                result=result,
                citations=refs,
                reason_code="INJECTED_OFFLINE_TEST",
                explanation=explanation,
                missing_facts=("Interpretation of the full customer question",)
                if result == "UNKNOWN"
                else (),
                provenance=Provenance(kind="model", assessor="injected-offline", version="1"),
            )
        elif schema is DatasetClaimReview:
            parsed = DatasetClaimReview(
                result=result,
                explanation=explanation,
                clauses=(
                    DatasetClauseReview(
                        text=text, result=result, citations=refs, explanation=explanation
                    ),
                ),
            )
        else:
            raise AssertionError("Unexpected model dispatch in offline browser test")
        if self.response_sink:
            self.response_sink(
                {"injected_offline_test": True, "parsed": parsed.model_dump(mode="json")}
            )
        return SimpleNamespace(stop_reason="end_turn", parsed_output=parsed)

    def close(self):
        pass


def make_app():
    assert os.environ["ENABLE_PAID_MODELS"] == "false"
    assert os.environ["ENABLE_TESTNET_BROADCAST"] == "false"
    root = Path(os.environ["ORDER_DB_PATH"])
    assert not root.exists(), "Use a fresh isolated database, never existing demo data"
    dataset.BoundedClient = InjectedClient
    os.environ["ENABLE_DATASET_MODEL_ASSESSMENT"] = "true"
    app = create_app(root, artifact_root=Path(os.environ["ARTIFACT_ROOT"]), payment_mode="mock")
    lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def injected_lifespan(app):
        async with lifespan(app):
            app.state.orders.investigator = SimpleNamespace(
                assessor=ClaudeGateway(
                    enabled=True,
                    model="injected-offline",
                    client=InjectedClient(),
                )
            )
            yield

    app.router.lifespan_context = injected_lifespan
    return app
