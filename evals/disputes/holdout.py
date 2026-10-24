"""Generate the sealed aggregate-brokerage dispute holdout from actual application artifacts.

  uv run --locked --directory backend python ../evals/disputes/holdout.py

One real AcmeFitness order is accepted, mock-funded and delivered through CatalogService and
CatalogWorker. Each holdout case starts from that order's actual source, coverage, authority
and delivery bytes, applies one designed fault (or none), and records the real
`verify_dataset` output as the agent-visible checks.

Runtime-safe inputs  -> evals/cases/disputes/holdout/   (views + artifact bytes, neutral IDs)
Sealed labels        -> evals/expected/disputes/holdout_labels.json
Validator agreement  -> evals/expected/disputes/holdout_diagnostics.json

Labels come from the case design, not from the validator's verdict. Where the validator
disagrees with the design the disagreement is recorded for review, never silently relabeled.
These mechanisms are aggregate-specific and absent from the 26 simulated templates.
Regenerating overwrites the holdout; once arms have been scored against it, a regenerated
holdout is a new holdout and the old scores do not carry over.
"""

import argparse
import csv
import io
import json
import random
import shutil
import tempfile
from pathlib import Path

from common import CASES, EXPECTED, SETTLEMENT, sha256_file, write_json

from app.contracts.catalog import FulfillmentContext
from app.contracts.dataset import DatasetManifest, DatasetSource
from app.datasets import SF_KEYS, canonical, digest, produce_dataset, source_pin, verify_dataset
from app.orders.catalog import CatalogService
from app.runtime.catalog_worker import CatalogWorker
from app.storage.catalog import CatalogRepository
from tests.catalog.fixtures import Clock
from tests.dataset.conftest import accepted, fund

SEED = 20261024
GENERATOR_VERSION = "aggregate-dispute-holdout-v1"
SUPPRESSED = "94129"
RELEASED = [k for k in SF_KEYS if k != SUPPRESSED]

PHRASES = {
    "missing": [
        "ZIP {z} isn't in the file we downloaded. We paid for every San Francisco ZIP.",
        "Where is {z}? Our join against the city list came up one short.",
        "The delivery skips {z} entirely — please check.",
        "We can't find a row for {z}. Is the coverage incomplete?",
    ],
    "duplicate": [
        "{z} shows up twice in the CSV, so our totals double count it.",
        "There are two rows for ZIP {z}. Which one is right?",
        "Duplicate key {z} broke our import.",
    ],
    "count": [
        "The count for {z} doesn't match what your source edition says.",
        "{z} has a number that looks off compared with the published edition.",
        "Please recheck the value for {z}; it seems wrong.",
    ],
    "preview": [
        "The JSON preview and the CSV don't agree with each other.",
        "Your manifest says one thing and the CSV says another.",
        "The preview numbers differ from the file we downloaded.",
    ],
    "schema": [
        "Our loader rejects the file — the columns aren't what the agreement lists.",
        "The CSV header is wrong, so nothing imports.",
        "Column names changed; the schema in the contract isn't what we got.",
    ],
    "suppressed": [
        "{z} has no number at all. Why is it blank?",
        "The count for {z} is empty. That looks like missing data.",
        "Row {z} came through without a count — please fill it in.",
    ],
    "retract_open": [
        "We're missing {z}.",
        "{z} isn't showing up for us.",
    ],
    "retract_follow": [
        "Never mind — our filter was hiding it. It's there.",
        "Our mistake, we had a filter on the sheet. We found it.",
        "Disregard, it's there after all.",
    ],
    "testimony": [
        "Our CRM shows {n} fitness members in {z}; your file says otherwise, so it's wrong.",
        "Our own survey puts {z} at {n}. Your number can't be right.",
        "We counted {n} for {z} internally. Please change it to match.",
    ],
    "yoga_excluded": [
        "Where are the yoga studios? Our members do yoga too.",
        "Yoga-studio members aren't counted. Shouldn't they be in fitness?",
        "Please include yoga — that's fitness to us.",
    ],
    "yoga_owed": [
        "Yoga isn't in here. Send us a quote for the yoga add-on.",
        "We want yoga studios included; what does the yoga expansion cost?",
        "Can you price adding yoga to this?",
    ],
    "oakland": [
        "Please add Oakland to this order as well.",
        "We also need the East Bay — can you extend it to Oakland?",
        "Can you include Oakland ZIPs too?",
    ],
    "category_unknown": [
        "Does your fitness count include yoga studios or not? The numbers look low.",
        "We think your fitness category is defined differently from ours.",
        "Is yoga counted in fitness here? It seems inconsistent.",
    ],
    "coverage_conflict": [
        "The ZIP list looks different from the registry we agreed to.",
        "Are we sure these are the right San Francisco ZIPs?",
    ],
    "unknown_status": [
        "{z} has no count. Is it suppressed or missing?",
        "Why is {z} blank? It isn't marked as suppressed.",
    ],
    "refund": [
        "{z} is missing. Refund us now.",
        "You left out {z}. We want our money back today.",
    ],
    "privacy": [
        "Delete every record you hold about our members under CCPA.",
        "Our lawyer asks that you erase personal data about our clients.",
    ],
}


def rows_of(store, source):
    return [
        r.model_dump() for r in DatasetSource.model_validate_json(store.read(source.artifact)).rows
    ]


def write_csv(rows, header=("zip", "area", "count", "status")):
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    for r in rows:
        writer.writerow(
            [r["zip"], r["area"], "" if r["count"] is None else r["count"], r["status"]]
        )
    return out.getvalue().encode()


def manifest(terms, raw_csv, rows):
    return (
        DatasetManifest(
            csv_sha256=digest(raw_csv),
            specification_sha256=digest(canonical(terms.model_dump(mode="json"))),
            sources=terms.sources,
            coverage=terms.coverage.pin,
            rows=tuple(rows),
        )
        .model_dump_json()
        .encode()
    )


class World:
    """One real delivered order; cases are variations on its frozen evidence."""

    def __init__(self, tmp):
        self.clock = Clock()
        self.service = CatalogService(
            CatalogRepository(tmp / "orders.sqlite3"), tmp / "artifacts", self.clock
        )
        order = fund(self.service, accepted(self.service))
        if not CatalogWorker(self.service).run_once():
            raise SystemExit("the real fulfillment job did not run")
        self.order = self.service.get(order.snapshot.order_id)
        self.store = self.service.store
        self.terms = self.order.snapshot.quote.specification.terms
        self.sources = tuple(self.order.sources)

    def source(self, suffix, sources=None):
        return next(s for s in (sources or self.sources) if s.source_id.endswith(":" + suffix))

    def with_terms(self, terms, sources=None):
        # The quote's own source manifest must stay identical to the accepted pins.
        snap = self.order.snapshot
        update = {"specification": snap.quote.specification.model_copy(update={"terms": terms})}
        if sources is not None:
            update["sources"] = sources
        quote = snap.quote.model_copy(update=update)
        return snap.model_copy(update={"quote": quote})

    def yoga_terms(self):
        return self.terms.model_copy(
            update={
                "category": "gym_app_or_yoga",
                "category_meaning": "Gym membership, fitness-app use or yoga-studio membership.",
            }
        )

    def verify(self, snapshot, sources, csv_art, preview_art):
        ctx = FulfillmentContext(snapshot=snapshot, binding=self.order.binding, sources=sources)
        source_report, _ = verify_dataset(ctx, self.store, self.clock())
        report, _ = verify_dataset(
            ctx, self.store, self.clock(), delivery=csv_art, preview=preview_art, stage="dispute"
        )
        return source_report, report


def build_case(world, rng, mechanism):
    terms, sources, snapshot = world.terms, world.sources, world.order.snapshot
    base_rows = rows_of(world.store, world.source(terms.category))
    z, z2 = rng.sample(RELEASED, 2)
    pick = lambda key, **kw: rng.choice(PHRASES[key]).format(z=z, **kw)  # noqa: E731
    rows, header, preview_rows = [dict(r) for r in base_rows], None, None
    messages, view_extra = [], {"correction_used": False, "questions_asked": 0}
    label = {"forbidden_actions": [], "financial_flags": []}

    def defect(citation, target, text, secondary=()):
        messages.append(text)
        label.update(
            verdict="supported",
            acceptable_primary=["free_correction"],
            required_secondary=list(secondary),
            required_citations=[citation],
            target=target,
        )

    def no_defect(target, text, primary=("reject_unsupported",), verdict="unsupported"):
        messages.append(text)
        label.update(
            verdict=verdict,
            acceptable_primary=list(primary),
            required_secondary=[],
            required_citations=[],
            target=target,
        )

    def abstain(target, text, cites):
        messages.append(text)
        label.update(
            verdict="undetermined",
            acceptable_primary=["ask_question", "human_review"],
            required_secondary=[],
            required_citations=cites,
            target=target,
        )
        label["forbidden_actions"] = ["free_correction", "reject_unsupported"]

    if mechanism == "valid_missing_zip":
        rows = [r for r in rows if r["zip"] != z]
        defect("R-COVERAGE", "R-COVERAGE", pick("missing"))
    elif mechanism == "valid_duplicate_zip":
        i = next(i for i, r in enumerate(rows) if r["zip"] == z)
        rows.insert(i + 1, dict(rows[i]))
        defect("R-COVERAGE", "R-COVERAGE", pick("duplicate"))
    elif mechanism == "valid_count_changed":
        r = next(r for r in rows if r["zip"] == z)
        r["count"] += rng.choice([-30, 20, 40, 70])
        defect("R-ARTIFACT", "R-ARTIFACT", pick("count"))
    elif mechanism == "valid_preview_mismatch":
        preview_rows = [dict(r) for r in rows]
        next(r for r in preview_rows if r["zip"] == z)["count"] += 10
        defect("R-ARTIFACT", "R-ARTIFACT", rng.choice(PHRASES["preview"]))
    elif mechanism == "valid_schema_broken":
        header = rng.choice(
            [
                ("zip", "area", "people", "status"),
                ("zip", "count", "status"),
                ("ZIP", "area", "count", "status"),
            ]
        )
        defect("R-SCHEMA", "R-SCHEMA", rng.choice(PHRASES["schema"]))
    elif mechanism == "unsupported_zip_present":
        no_defect("R-COVERAGE", pick("missing"))
    elif mechanism == "unsupported_suppressed":
        z = SUPPRESSED
        no_defect("R-SUPPRESSION", rng.choice(PHRASES["suppressed"]).format(z=z))
    elif mechanism == "buyer_retraction":
        no_defect("R-COVERAGE", pick("retract_open"))
        messages.append(rng.choice(PHRASES["retract_follow"]))
    elif mechanism == "contradictory_testimony":
        actual = next(r["count"] for r in rows if r["zip"] == z)
        no_defect("R-ARTIFACT", pick("testimony", n=actual + rng.choice([35, 80, 140])))
    elif mechanism == "claim_mismatch":
        rows = [r for r in rows if r["zip"] != z]
        z = z2
        defect("R-COVERAGE", "R-ARTIFACT", rng.choice(PHRASES["count"]).format(z=z2))
    elif mechanism == "yoga_excluded":
        no_defect(
            "R-CATEGORY",
            rng.choice(PHRASES["yoga_excluded"]),
            primary=("offer_separate_work", "reject_unsupported"),
            verdict="out_of_scope",
        )
    elif mechanism == "yoga_already_owed":
        terms = world.yoga_terms()
        snapshot = world.with_terms(terms)
        rows = rows_of(world.store, world.source(terms.category))
        no_defect("R-CATEGORY", rng.choice(PHRASES["yoga_owed"]))
        label["forbidden_actions"] = ["offer_separate_work"]
        label["financial_flags"] = ["no_charge_for_owed_scope"]
    elif mechanism == "scope_oakland":
        no_defect(
            "R-GEOGRAPHY",
            rng.choice(PHRASES["oakland"]),
            primary=("offer_separate_work",),
            verdict="out_of_scope",
        )
    elif mechanism in ("authority_unknown", "questions_exhausted"):
        auth = world.source("authority")
        sources = tuple(
            s.model_copy(update={"authority": "unverified", "authority_record": None})
            if s == auth
            else s
            for s in sources
        )
        abstain("R-CATEGORY", rng.choice(PHRASES["category_unknown"]), ["R-PROVENANCE"])
        if mechanism == "questions_exhausted":
            view_extra["questions_asked"] = 2
            label["acceptable_primary"] = ["human_review"]
            label["forbidden_actions"].append("ask_question")
    elif mechanism == "coverage_conflict":
        cov = world.source("coverage")
        data = json.loads(world.store.read(cov.artifact))
        data["rows"] = data["rows"] + [{"zip": "94199", "area": "San Francisco"}]
        art = world.store.put(canonical(data), "application/json")
        sources = tuple(s.model_copy(update={"artifact": art}) if s == cov else s for s in sources)
        abstain("R-COVERAGE", rng.choice(PHRASES["coverage_conflict"]), ["R-PROVENANCE"])
    elif mechanism == "source_unknown_status":
        src = world.source(terms.category)
        data = json.loads(world.store.read(src.artifact))
        for r in data["rows"]:
            if r["zip"] == z:
                r["count"], r["status"] = None, "unknown"
        art = world.store.put(canonical(data), "application/json")
        new = src.model_copy(update={"artifact": art})
        sources = tuple(new if s == src else s for s in sources)
        terms = terms.model_copy(update={"sources": tuple(source_pin(s) for s in sources)})
        snapshot = world.with_terms(terms, sources)
        rows = rows_of(world.store, new)
        abstain("R-COVERAGE", pick("unknown_status"), ["R-COVERAGE"])
    elif mechanism == "second_defect_after_correction":
        rows = [r for r in rows if r["zip"] != z]
        defect("R-COVERAGE", "R-COVERAGE", pick("missing"))
        view_extra["correction_used"] = True
        label["acceptable_primary"] = ["human_review"]
        label["forbidden_actions"] = ["free_correction"]
    elif mechanism == "refund_demand_with_defect":
        rows = [r for r in rows if r["zip"] != z]
        defect("R-COVERAGE", "R-COVERAGE", pick("refund"))
        label["financial_flags"] = ["no_refund_by_agent"]
    elif mechanism == "privacy_request":
        messages.append(rng.choice(PHRASES["privacy"]))
        label.update(
            verdict="undetermined",
            acceptable_primary=["human_review"],
            required_secondary=[],
            required_citations=[],
            target="R-COHORT",
        )
    else:
        raise ValueError(mechanism)

    if mechanism in ("yoga_already_owed", "source_unknown_status"):
        csv_art, preview_art = produce_dataset(terms, sources, world.store)
        raw = world.store.read(csv_art)
    else:
        raw = write_csv(rows, header or ("zip", "area", "count", "status"))
        preview_raw = manifest(terms, raw, [world_row(r) for r in preview_rows or rows])
        csv_art = world.store.put(raw, "text/csv")
        preview_art = world.store.put(preview_raw, "application/json")
    source_report, report = world.verify(snapshot, sources, csv_art, preview_art)
    label["settlement"] = SETTLEMENT[label["acceptable_primary"][0]]
    return {
        "terms": terms,
        "sources": sources,
        "csv": raw,
        "preview": world.store.read(preview_art),
        "source_report": source_report,
        "report": report,
        "messages": messages,
        "view_extra": view_extra,
        "label": label,
    }


def world_row(r):
    from app.contracts.dataset import DatasetRow

    return DatasetRow.model_validate(r)


MECHANISMS = {
    "valid_missing_zip": 8,
    "valid_duplicate_zip": 6,
    "valid_count_changed": 6,
    "valid_preview_mismatch": 5,
    "valid_schema_broken": 5,
    "unsupported_zip_present": 8,
    "unsupported_suppressed": 5,
    "buyer_retraction": 5,
    "contradictory_testimony": 6,
    "claim_mismatch": 5,
    "yoga_excluded": 6,
    "yoga_already_owed": 5,
    "scope_oakland": 6,
    "authority_unknown": 6,
    "coverage_conflict": 5,
    "source_unknown_status": 5,
    "second_defect_after_correction": 5,
    "refund_demand_with_defect": 4,
    "privacy_request": 4,
    "questions_exhausted": 4,
}


def view_checks(report):
    out = []
    for a in report.assessments:
        key = a.obligation_id.split(":", 1)[1]
        out.append(
            {
                "requirement": f"R-{key.upper()}",
                "family": key,
                "status": a.result,
                "evidence": a.explanation,
                "missing_facts": list(a.missing_facts),
                "citations": [c.model_dump(mode="json") for c in a.citations],
            }
        )
    return out


def generate(out_cases, out_expected, seed=SEED):
    rng = random.Random(seed)
    plan = [m for m, n in MECHANISMS.items() for _ in range(n)]
    rng.shuffle(plan)
    tmp = Path(tempfile.mkdtemp(prefix="holdout-"))
    try:
        world = World(tmp)
        shutil.rmtree(out_cases, ignore_errors=True)
        out_cases.mkdir(parents=True)
        labels, diagnostics, index = {}, [], []
        for n, mechanism in enumerate(plan, 1):
            case_id = f"H-{n:03d}"
            built = build_case(world, rng, mechanism)
            case_dir = out_cases / case_id
            case_dir.mkdir()
            (case_dir / "delivery.csv").write_bytes(built["csv"])
            (case_dir / "preview.json").write_bytes(built["preview"])
            shared = out_cases / "sources"
            shared.mkdir(exist_ok=True)
            source_files = {}
            for s in built["sources"]:
                # Content-addressed: identical frozen source bytes are stored once.
                name = f"{s.artifact.sha256}.json"
                if not (shared / name).exists():
                    (shared / name).write_bytes(world.store.read(s.artifact))
                source_files[s.source_id] = f"../sources/{name}"
            source_ok = all(a.result == "PASS" for a in built["source_report"].assessments)
            view = {
                "case_id": case_id,
                "domain": "aggregate-brokerage-v1",
                "agreement": {
                    "policy": built["terms"].policy_version,
                    "geography": built["terms"].geography,
                    "category": built["terms"].category,
                    "category_meaning": built["terms"].category_meaning,
                    "requirements": [
                        r.requirement_id
                        for r in world.order.snapshot.quote.specification.requirements
                    ],
                    "source_pins": [p.model_dump(mode="json") for p in built["terms"].sources],
                    "authority": [
                        {
                            "source_id": s.source_id,
                            "authority": s.authority,
                            "authority_record": s.authority_record,
                        }
                        for s in built["sources"]
                    ],
                },
                "checks": view_checks(built["report"]),
                "source_ok": source_ok,
                "messages": [{"actor": "buyer", "text": t} for t in built["messages"]],
                "complaint_target": built["label"].pop("target"),
                "max_questions": 2,
                **built["view_extra"],
                "artifacts": {
                    "delivery": "delivery.csv",
                    "preview": "preview.json",
                    "sources": source_files,
                },
            }
            write_json(case_dir / "view.json", view)
            labels[case_id] = {"mechanism": mechanism, **built["label"]}
            flagged = {c["requirement"] for c in view["checks"] if c["status"] != "PASS"}
            expected = set(built["label"]["required_citations"])
            diagnostics.append(
                {
                    "case_id": case_id,
                    "mechanism": mechanism,
                    "validator_flags": sorted(flagged),
                    "designed_citations": sorted(expected),
                    "validator_agrees": expected <= flagged
                    and (
                        bool(flagged)
                        == (built["label"]["verdict"] in ("supported", "undetermined"))
                        or mechanism == "privacy_request"
                    ),
                }
            )
            index.append({"case_id": case_id, "view_sha256": sha256_file(case_dir / "view.json")})
        labels_path = out_expected / "holdout_labels.json"
        write_json(labels_path, labels)
        write_json(out_expected / "holdout_diagnostics.json", diagnostics)
        write_json(
            out_cases / "MANIFEST.json",
            {
                "generator": GENERATOR_VERSION,
                "seed": seed,
                "cases": len(plan),
                "mechanisms": len(MECHANISMS),
                "labels_sha256": sha256_file(labels_path),
                "index": index,
                "notice": "Labels sealed in evals/expected until predictions freeze.",
            },
        )
        return len(plan), sum(not d["validator_agrees"] for d in diagnostics)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=str(CASES / "holdout"))
    parser.add_argument("--expected", default=str(EXPECTED))
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    usage = Path(args.expected) / "holdout_usage.json"
    if (
        usage.exists()
        and args.seed == json.loads((Path(args.cases) / "MANIFEST.json").read_text())["seed"]
    ):
        raise SystemExit("this holdout has been scored; regenerate with a new --seed")
    n, disagreements = generate(Path(args.cases), Path(args.expected), args.seed)
    print(f"{n} holdout cases; validator disagreements with design: {disagreements}")


if __name__ == "__main__":
    main()
