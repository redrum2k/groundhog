"""Bounded LOCAL qualification, isolated from live orders and withheld from runtime.

The oracle reopens literal source bytes and recorded owner evidence independently
of SourceKnowledge's normalized output. Fresh byte variants are frozen before use.
These engineering cases are not independent human labels or the old nine-case suite.
"""

import json
import random
import time
from pathlib import Path
from uuid import uuid4

from app.agents import source_preparation
from app.agents.source_knowledge import AuthorityHead, VendorExport
from app.catalog.preparation import PreparedSources
from app.contracts.catalog import Artifact, QuoteRequest, RequestCommand, Source
from app.contracts.dataset import DatasetSource
from app.contracts.source_learning import BundleUpload, PartitionInput
from app.datasets import canonical
from app.learning.service import CORPUS, OPERATIONS, SourceLearning, implementation_digest
from app.orders.catalog import CatalogService
from app.orders.service import DomainError
from app.storage.catalog import CatalogRepository


def verify_composition(isolated, bundle, allowed, key, oracle_rows):
    """Exercise the real adapter, then independently reopen its saved bytes/pins."""
    service = isolated.service
    draft = service.create_request(
        RequestCommand(
            prompt="SF adults 25-34, gym membership or fitness app use, counts by ZIP.",
            corpus_id=CORPUS,
            idempotency_key=key,
        )
    )
    cases = isolated.cases(draft.request_id, bundle)
    engine = isolated.engine(allowed)
    results = [engine.assess(case) for case in cases]
    draft = source_preparation.compile_composed_sources(
        engine,
        tuple(r["encounter_id"] for r in results),
        idempotency_key=key + ":compile",
    )
    with service.repository.transaction() as db:
        prepared = service.repository.load(
            db, "prepared_sources", draft.request_id, PreparedSources
        )
    prefix = f"{CORPUS}:prepared:{draft.request_id}:"
    sources = {s.source_id: s for s in prepared.sources}
    derived = sources[prefix + cases[0].scope.category]
    normalized = DatasetSource.model_validate_json(service.store.read(derived.artifact))
    actual = {row.zip: (row.area, row.count, row.status) for row in normalized.rows}
    if len(normalized.rows) != len(actual) or actual != oracle_rows:
        raise ValueError("composed rows differ from independently read source bytes")
    scope = cases[0].scope
    if (
        normalized.source_id,
        normalized.version,
        normalized.edition,
        normalized.geography,
        normalized.age_min,
        normalized.age_max,
        normalized.category,
        normalized.population,
        normalized.count_unit,
        normalized.groups_disjoint,
    ) != (
        derived.source_id,
        derived.version,
        derived.edition,
        scope.geography,
        scope.age_min,
        scope.age_max,
        scope.category,
        "synthetic_adults",
        cases[0].desired_unit,
        True,
    ):
        raise ValueError("composed source changed its authorized scope")
    expected = {
        s.source_id: s
        for s in service.registry.manifest(CORPUS)
        if s.source_id != CORPUS + ":" + scope.category
    }
    expected[derived.source_id] = derived
    for index, result in enumerate(results):
        if result["resolution_id"]:
            resolution = isolated.memory.get("source_resolution", result["resolution_id"])
            proof = Artifact.model_validate(resolution["evidence"])
            attached = sources[prefix + f"schema-resolution-{index}"]
            if attached.artifact != proof:
                raise ValueError("composition omitted or substituted owner evidence")
            service.store.read(proof)
            expected[attached.source_id] = attached
    lineage_source = sources[prefix + "schema-lineage"]
    lineage = json.loads(service.store.read(lineage_source.artifact))
    if (
        lineage["operations"] != list(OPERATIONS)
        or lineage["derived"] != derived.model_dump(mode="json")
        or lineage["components"]
        != [
            {
                "encounter_id": r["encounter_id"],
                "binding": r["binding"],
                "citations": r["citations"],
                "procedure_id": r["procedure_id"],
            }
            for r in results
        ]
    ):
        raise ValueError("composition evidence lineage differs from its assessed inputs")
    expected[lineage_source.source_id] = lineage_source
    if sources != expected or len(sources) != len(prepared.sources):
        raise ValueError("composition selected the wrong source or evidence set")
    quote = service.issue_quote(
        draft.request_id,
        QuoteRequest(
            expected_revision=draft.revision,
            idempotency_key=key + ":quote",
        ),
    )
    if quote.sources != prepared.sources:
        raise ValueError("quote lost composed source selection")
    return {
        "request_id": draft.request_id,
        "derived_sha256": derived.artifact.sha256,
        "lineage_sha256": lineage_source.artifact.sha256,
        "rows": len(actual),
        "independently_verified": True,
    }


def qualify(owner, candidate):
    started = time.monotonic()
    if tuple(candidate["operations"]) != OPERATIONS:
        raise ValueError("candidate has unauthorized operations")
    bundle = owner.memory.get("source_bundle", candidate["bundle_id"])
    seed = uuid4().hex
    rng = random.Random(seed)
    columns = {}
    training_hashes = set()
    for component_id in candidate["component_ids"]:
        component = owner.memory.get("source_procedure", component_id)
        resolution = owner.memory.get("source_resolution", component["resolution_id"])
        proof = json.loads(
            owner.service.store.read(Artifact.model_validate(resolution["evidence"]))
        )
        columns[proof["source_family"]] = proof["definition"]["column"]
        training_hashes.add(proof["source_pin"]["sha256"])
    trials = []
    modes = (
        "fresh_values",
        "permuted_values",
        "current_documentation",
        "conflicting_definitions",
        "revoked_authority",
        "changed_schema",
    )
    for index, mode in enumerate(modes):
        parts = []
        for original in bundle["partitions"]:
            source = Source.model_validate(original["source"])
            authority = Source.model_validate(original["authority"])
            raw = json.loads(owner.service.store.read(source.artifact))
            head = json.loads(owner.service.store.read(authority.artifact))
            raw["version"] += 100 + index
            for row in raw["rows"]:
                if row["status"] == "released":
                    row["values"] = {column: rng.randint(70, 970) for column in raw["columns"]}
            if mode == "permuted_values":
                raw["rows"].reverse()
            if mode == "current_documentation":
                head["definitions"] = [
                    {"column": columns[raw["source_family"]], "unit": "unique_adults_per_zip"}
                ]
            elif mode == "conflicting_definitions":
                head["definitions"] = [
                    {"column": c, "unit": "unique_adults_per_zip"} for c in raw["columns"]
                ]
            elif mode == "revoked_authority":
                head["status"] = "revoked"
            elif mode == "changed_schema":
                raw["schema_version"] += 1
                head["source_version"] = raw["schema_version"]
            parts.append(
                PartitionInput(
                    export=VendorExport.model_validate(raw),
                    authority=AuthorityHead.model_validate(head),
                )
            )
        trials.append(
            {
                "mode": mode,
                "input": BundleUpload(
                    idempotency_key=seed + str(index), partitions=tuple(parts)
                ).model_dump(mode="json"),
            }
        )
    plan = {
        "lane": "LOCAL",
        "attempt": 1,
        "maximum_seconds": 60,
        "seed": seed,
        "candidate_id": candidate["id"],
        "implementation_sha256": implementation_digest(),
        "trials": trials,
        "oracle": "literal_source_bytes_and_separate_owner_evidence",
        "origin": "fresh_engineering_cases_not_independent_human_labels",
    }
    capsule = owner.service.store.put(canonical(plan), "application/json")
    root = Path(owner.service.store.root) / "learning-qualification" / capsule.sha256
    root.mkdir(parents=True, exist_ok=False)
    outcomes, violations = [], []
    totals = {arm: {"reviews": 0, "operations": 0} for arm in ("baseline", "candidate")}
    correct = 0
    for index, trial in enumerate(trials):
        if time.monotonic() - started > 60:
            violations.append("qualification_time_limit")
            break
        service = CatalogService(
            CatalogRepository(root / f"case-{index}.sqlite3"),
            owner.service.store.root,
            owner.service.clock,
        )
        isolated = SourceLearning(service, enabled=True)
        # Preserve exact registered authority versions. Re-numbering an identical
        # authority artifact in the isolated DB would spuriously invalidate a
        # component learned from dictionary v2+ even though its evidence is current.
        for part in bundle["partitions"]:
            service.registry.register(Source.model_validate(part["authority"]))
        # Immutable training history only; no evaluation labels enter the engine.
        with isolated.memory.store.connect(write=True) as db:
            for kind in ("source_encounter", "source_resolution", "source_procedure"):
                for record in owner.memory.records(kind):
                    body = {
                        k: v
                        for k, v in record.items()
                        if k not in ("id", "customer_id", "product_id")
                    }
                    copied = isolated.memory.put(kind, body, db=db)
                    if copied["id"] != record["id"]:
                        raise ValueError("qualification training provenance changed")
        command = BundleUpload.model_validate(trial["input"])
        isolated.publish(command, "qualification:synthetic-provider")
        draft = service.create_request(
            RequestCommand(
                prompt="SF adults 25-34, gym membership or fitness app use, counts by ZIP.",
                corpus_id=CORPUS,
                idempotency_key=seed + str(index),
            )
        )
        cases = isolated.cases(draft.request_id, isolated.bundle())
        if any(case.source.artifact.sha256 in training_hashes for case in cases):
            violations.append("training_bytes_reused_as_fresh")
        expected_ready = {
            "baseline": trial["mode"] == "current_documentation",
            "candidate": trial["mode"]
            in ("fresh_values", "permuted_values", "current_documentation"),
        }
        oracle_rows = {}
        for case in cases:
            # Deliberately does not call engine normalization or read its result.
            source_bytes = json.loads(service.store.read(case.source.artifact))
            for row in source_bytes["rows"]:
                if row["zip"] in oracle_rows:
                    violations.append("oracle_partition_overlap")
                oracle_rows[row["zip"]] = (
                    row["area"],
                    row["values"][columns[source_bytes["source_family"]]],
                    row["status"],
                )
        row_outcomes = {}
        valid = True
        for arm, allowed in (("baseline", ()), ("candidate", candidate["component_ids"])):
            results = [isolated.engine(allowed).assess(case) for case in cases]
            ready = all(result["internal_reviews"] == 0 for result in results)
            actual = {
                row["zip"]: (row["area"], row["count"], row["status"])
                for result in results
                for row in (result["normalized"]["rows"] if result["normalized"] else [])
            }
            verified = ready == expected_ready[arm] and (not ready or actual == oracle_rows)
            composition = None
            if ready:
                try:
                    composition = verify_composition(
                        isolated,
                        isolated.bundle(),
                        allowed,
                        f"{seed}:{index}:{arm}",
                        oracle_rows,
                    )
                except (ValueError, KeyError, DomainError) as error:
                    verified = False
                    composition = {"independently_verified": False, "error": str(error)}
            valid &= verified
            reviews = sum(r["internal_reviews"] for r in results)
            operations = sum(len(r["tool_operations"]) for r in results)
            totals[arm]["reviews"] += reviews
            totals[arm]["operations"] += operations
            row_outcomes[arm] = {
                "ready": ready,
                "independently_verified": verified,
                "reviews": reviews,
                "machine_operations": operations,
                "source_hashes": [case.source.artifact.sha256 for case in cases],
                "encounter_ids": [r["encounter_id"] for r in results],
                "composition": composition,
            }
        correct += int(valid)
        if not valid:
            violations.append("oracle_mismatch:" + trial["mode"])
        with service.repository.transaction() as db:
            if db.execute("SELECT count(*) FROM catalog_records WHERE kind='order'").fetchone()[0]:
                violations.append("qualification_created_financial_order")
        outcomes.append({"mode": trial["mode"], "arms": row_outcomes})
    if implementation_digest() != plan["implementation_sha256"]:
        violations.append("implementation_changed_during_qualification")
    passed = (
        not violations
        and correct == len(trials)
        and totals["candidate"]["reviews"] < totals["baseline"]["reviews"]
    )
    trace = owner.service.store.put(canonical(outcomes), "application/json")
    return {
        "candidate_id": candidate["id"],
        "passed": passed,
        "cases": len(trials),
        "baseline_reviews": totals["baseline"]["reviews"],
        "candidate_reviews": totals["candidate"]["reviews"],
        "baseline_operations": totals["baseline"]["operations"],
        "candidate_operations": totals["candidate"]["operations"],
        "correct_both": correct,
        "capsule_sha256": capsule.sha256,
        "capsule": capsule.model_dump(mode="json"),
        "trace": trace.model_dump(mode="json"),
        "implementation_sha256": plan["implementation_sha256"],
        "violations": violations,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "paid_calls": 0,
        "origin": plan["origin"],
        "human_minutes_measured": False,
        "operation_basis": (
            "source-assessment logical operations; excludes composition, "
            "shadow verification, HTTP and delivery"
        ),
    }
