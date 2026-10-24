"""Shared evaluator helpers for the dispute dataset. Never imported by backend/app.

The simulated bundle (Northbeam Data) uses its own contract and remedies. Everything
here translates it into aggregate-brokerage-v1 actions before any arm or memory sees it,
and builds decision-time views that carry only what a runtime agent could observe.
"""

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
EXPECTED = REPO / "evals" / "expected" / "disputes"
CASES = REPO / "evals" / "cases" / "disputes"

# aggregate-brokerage-v1 dispute actions. The agent has no payment authority, so none of
# these moves money; settlement follows the lifecycle gates in HACK.md.
ACTIONS = (
    "free_correction",  # established provider-output defect; one durable free correction
    "reject_unsupported",  # evidence contradicts the complaint; no complaint fee
    "ask_question",  # bounded evidence question (at most two, one at a time)
    "offer_separate_work",  # extra scope needs a provider offer, acceptance and funding
    "human_review",  # Maya reviews; also the only path for non-permitted remedies
)
VERDICTS = ("supported", "unsupported", "out_of_scope", "undetermined")
SETTLEMENT = {
    "free_correction": "blocked_pending_correction",
    "reject_unsupported": "eligible_on_acceptance_or_expiry",
    "ask_question": "blocked_pending_answer",
    "offer_separate_work": "base_unchanged_child_offer",
    "human_review": "blocked_human_review",
}
ABSTAIN = {"ask_question", "human_review"}

# Northbeam family -> (aggregate actions, verdict, note). Credits, refunds, SLA credits and
# agent settlements up to $500 are not permitted under aggregate-brokerage-v1.
POLICY_MAP = {
    "seller_funded_redelivery": (("free_correction",), "supported", "permitted"),
    "seller_funded_fix": (("free_correction",), "supported", "permitted"),
    "accuracy_credit": (
        ("free_correction",),
        "supported",
        "credit component not permitted; correction only",
    ),
    "paid_addition": (
        ("offer_separate_work",),
        "out_of_scope",
        "permitted; no fee unless accepted",
    ),
    "split_correction_and_addition": (
        ("free_correction", "offer_separate_work"),
        "supported",
        "permitted as correction plus a separate offer",
    ),
    "deny_with_evidence": (("reject_unsupported",), "unsupported", "permitted; no complaint fee"),
    "amend_and_resume": (
        ("ask_question",),
        "undetermined",
        "clarify first; a substantive change needs a child agreement",
    ),
    "replace_source": (("ask_question",), "undetermined", "evidence request for the source"),
    "exclude_with_credit": (
        ("human_review",),
        "undetermined",
        "pro-rata credit not permitted; a bad source alone is not provider fault",
    ),
    "sla_credit": (("human_review",), "supported", "late-delivery credit not permitted"),
    "escalate_human": (("human_review",), "undetermined", "permitted"),
}
NOT_PERMITTED_FAMILIES = {"exclude_with_credit", "sla_credit"}
MONEY_WORDS = re.compile(
    r"\b(credit|refund|discount|pro-rata|absorb|settle[sd]?|compensat\w*|\$\d)", re.I
)

# Northbeam requirement -> aggregate check family, so memory keys are domain-neutral.
CHECK_FAMILY = {
    "R-COUNT": "coverage",
    "R-COMPLETE": "coverage",
    "R-UNIQUE": "coverage",
    "R-SCHEMA": "schema",
    "R-FORMAT": "schema",
    "R-ACC": "artifact",
    "R-DELIV": "timeliness",
}

# Fields that reveal the scenario template, the answer or the future. Never shown to arms.
LEAKY_CASE_FIELDS = (
    "dispute",
    "resolution",
    "rejected_alternative",
    "outcome",
    "recheck",
    "amendment",
    "split",
)


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha256_json(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


class Dataset:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        sim = self.root / "data" / "sim"
        if not (sim / "cases.jsonl").exists():
            raise SystemExit(f"{self.root} is not an extracted dispute-dataset directory")
        self.cases = read_jsonl(sim / "cases.jsonl")
        self.train = [c for c in self.cases if c["split"] == "train"]
        # The team has already inspected and debugged against these; they are development
        # tests for wording generalization, never the final untouched holdout.
        self.dev = [c for c in self.cases if c["split"] == "test"]
        real = self.root / "data" / "real" / "hf_data_disputes.jsonl"
        self.hf = read_jsonl(real) if real.exists() else []
        self.fingerprint = {
            "cases.jsonl": sha256_file(sim / "cases.jsonl"),
            "hf_data_disputes.jsonl": sha256_file(real) if real.exists() else None,
        }


def failing_checks(checks):
    return [c for c in checks if str(c.get("status", "")).lower() not in ("pass",)]


def sim_view(case):
    """Decision-time view: accepted agreement, verified checks, messages actually received.

    Only the opening buyer message is received before the first decision; later turns,
    amendments, rechecks, labels and outcomes are future or grading data.
    """
    contract = case["contract"]
    return {
        "case_id": case["case_id"],
        "domain": "northbeam-sim",
        "agreement": {
            "product_name": contract["product_name"],
            "units": contract["units"],
            "unit": contract["unit"],
            "row_schema": contract["row_schema"],
            "requirements": contract["requirements"],
            "deadline": contract["delivery"]["deadline"],
        },
        "delivery": case["delivery"],
        "checks": [
            {
                "requirement": c["requirement"],
                "family": CHECK_FAMILY.get(c["requirement"], "other"),
                "status": c["status"].upper(),
                "evidence": c.get("evidence"),
            }
            for c in case["checks"]
        ],
        "messages": [{"actor": "buyer", "text": case["thread"][0]["text"]}],
        "correction_used": False,
        "questions_asked": 0,
    }


def sim_label(case):
    actions, verdict, note = POLICY_MAP[case["resolution"]["family"]]
    failing = [c["requirement"] for c in failing_checks(case["checks"])]
    return {
        "case_id": case["case_id"],
        "family": case["resolution"]["family"],
        "verdict": verdict,
        "acceptable_actions": list(actions),
        "primary_action": actions[0],
        "required_citations": failing if verdict == "supported" else [],
        "settlement": SETTLEMENT[actions[0]],
        "policy_note": note,
    }


def assert_safe_view(view):
    blob = json.dumps(view)
    for key in LEAKY_CASE_FIELDS + ("variant", "issue_type", "root_cause", "mechanism"):
        if f'"{key}"' in blob:
            raise AssertionError(f"decision view leaks {key!r}")


TOKEN = re.compile(r"[a-z][a-z0-9_.-]*")


def tokens(text):
    return TOKEN.findall((text or "").lower())


class TfIdf:
    def __init__(self, docs):
        self.df = Counter(t for d in docs for t in set(tokens(d)))
        self.n = len(docs)
        self.vecs = [self.vec(d) for d in docs]

    def vec(self, text):
        tf = Counter(tokens(text))
        v = {
            t: (1 + math.log(c)) * math.log((self.n + 1) / (self.df.get(t, 0) + 1))
            for t, c in tf.items()
        }
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {t: x / norm for t, x in v.items()}

    def nearest(self, text, k):
        q = self.vec(text)
        scored = [(sum(q.get(t, 0) * x for t, x in v.items()), i) for i, v in enumerate(self.vecs)]
        return sorted(scored, reverse=True)[:k]


def view_text(view, with_checks=True):
    text = " ".join(m["text"] for m in view["messages"])
    if with_checks:
        text += " " + " ".join(
            f"check_{c['family']}_{c['status'].lower()} {c.get('evidence') or ''}"
            for c in view["checks"]
            if c["status"] != "PASS"
        )
    return text
