"""Three dispute-decision arms evaluated on identical decision-time views.

static     a competent fixed checklist written against aggregate-brokerage-v1
memory     nearest train-only contrastive cases vote on the action (functional memory)
evolving   procedures induced from train, revised for at most two retain-or-revert
           cycles on a train-only validation slice, then frozen

Arms receive only `view` (agreement, verified checks, received messages, counters) and
train-only memory. They never read labels, scenario metadata or evals/expected. All arms
are offline and deterministic: zero model calls and zero spend.
"""

import random
import re
from collections import Counter, defaultdict

from common import ABSTAIN, ACTIONS, POLICY_MAP, TfIdf, sim_view, view_text

HUMAN = re.compile(
    r"\b(resell|resale|redistribut\w*|sublicen\w*|licen[cs]e|delet\w*|erase|gdpr|ccpa|"
    r"privacy|personal data|lawyer|legal action|attorney|chargeback)\b",
    re.I,
)
SCOPE = re.compile(
    r"\b(add|also (include|send|get)|additional|extra|expand\w*|extend\w*|more fields|"
    r"another (city|region|county|state)|other cities|oakland|east bay|beyond)\b",
    re.I,
)
AMBIGUOUS = re.compile(
    r"\b(meant|mean[st]?|definition|defined|define|interpret\w*|thousands|gross|net|gaap|"
    r"counts? as|does (it|that|this) (include|cover)|supposed to include)\b",
    re.I,
)
RETRACT = re.compile(
    r"(never ?mind|our (mistake|bad|filter)|we found (it|them)|disregard|"
    r"my (mistake|bad)|it'?s there after all|had a filter)",
    re.I,
)
SOURCE = re.compile(r"\b(scann\w*|password|encrypt\w*|unreadable|illegible)\b", re.I)


def decision(actions, verdict, view, *, cite=None, rationale=""):
    checks = view["checks"]
    if cite is None:
        cite = (
            [c["requirement"] for c in checks if c["status"] != "PASS"]
            if "free_correction" in actions
            else []
        )
    return {
        "actions": list(actions),
        "verdict": verdict,
        "citations": cite,
        "financial_action": None,
        "rationale": rationale,
        "model_calls": 0,
        "model_usd": 0.0,
    }


def text_of(view):
    return " ".join(m["text"] for m in view["messages"])


class Static:
    name = "static"

    def fit(self, train_views, train_labels):
        return self

    def decide(self, view):
        text = text_of(view)
        checks = view["checks"]
        fails = [c for c in checks if c["status"] == "FAIL"]
        uncertain = [c for c in checks if c["status"] in ("UNKNOWN", "CONFLICT")]
        target = view.get("complaint_target")
        if view.get("agreement") is None:
            return decision(
                ("ask_question",),
                "undetermined",
                view,
                cite=[],
                rationale="no accepted agreement establishes an obligation",
            )
        if HUMAN.search(text):
            return decision(
                ("human_review",), "undetermined", view, rationale="license/privacy/legal"
            )
        if uncertain:
            action = (
                "ask_question"
                if view["questions_asked"] < view.get("max_questions", 2)
                else "human_review"
            )
            return decision(
                (action,),
                "undetermined",
                view,
                cite=[c["requirement"] for c in uncertain],
                rationale="evidence is UNKNOWN or CONFLICT",
            )
        if fails:
            fams = {c["family"] for c in fails}
            if fams == {"timeliness"}:
                return decision(
                    ("human_review",),
                    "supported",
                    view,
                    cite=[c["requirement"] for c in fails],
                    rationale="late delivery; no credit is permitted",
                )
            if view.get("source_ok") is False:
                return decision(
                    ("human_review",),
                    "undetermined",
                    view,
                    cite=[c["requirement"] for c in fails],
                    rationale="source defect alone is not provider fault",
                )
            if SOURCE.search(text):
                return decision(
                    ("human_review",),
                    "undetermined",
                    view,
                    cite=[c["requirement"] for c in fails],
                    rationale="unreadable source",
                )
            if view.get("correction_used"):
                return decision(
                    ("human_review",),
                    "supported",
                    view,
                    cite=[c["requirement"] for c in fails],
                    rationale="free correction already used",
                )
            actions = (
                ("free_correction", "offer_separate_work")
                if SCOPE.search(text)
                else ("free_correction",)
            )
            return decision(actions, "supported", view, rationale="failing mandatory check")
        cite = [target] if target else []
        if RETRACT.search(text):
            return decision(
                ("reject_unsupported",), "unsupported", view, cite=cite, rationale="buyer retracted"
            )
        if SCOPE.search(text):
            return decision(
                ("offer_separate_work",),
                "out_of_scope",
                view,
                cite=cite,
                rationale="outside agreement",
            )
        if AMBIGUOUS.search(text):
            return decision(
                ("ask_question",), "undetermined", view, cite=cite, rationale="definition unclear"
            )
        return decision(
            ("reject_unsupported",), "unsupported", view, cite=cite, rationale="all checks pass"
        )


class Memory:
    name = "memory"

    def __init__(self, k=7):
        self.k = k

    def fit(self, train_views, train_labels):
        self.labels = train_labels
        self.index = TfIdf([view_text(v) for v in train_views])
        return self

    def decide(self, view):
        votes, verdicts = Counter(), Counter()
        for score, i in self.index.nearest(view_text(view), self.k):
            votes[tuple(self.labels[i]["actions"])] += score
            verdicts[self.labels[i]["verdict"]] += score
        if not votes or votes.most_common(1)[0][1] <= 0:
            return decision(
                ("ask_question",), "undetermined", view, rationale="no similar past case"
            )
        actions = votes.most_common(1)[0][0]
        return decision(
            actions, verdicts.most_common(1)[0][0], view, rationale="nearest past cases"
        )


def signature(view):
    bad = sorted({c["family"] for c in view["checks"] if c["status"] != "PASS"})
    uncertain = any(c["status"] in ("UNKNOWN", "CONFLICT") for c in view["checks"])
    return ("uncertain:" if uncertain else "") + (",".join(bad) or "none")


def words(view):
    return set(re.findall(r"[a-z]{3,}", text_of(view).lower()))


class Evolving:
    """Signature procedures plus learned keyword exceptions, kept only when they help."""

    name = "evolving"

    def __init__(self, cycles=2, seed=7):
        self.cycles, self.seed = cycles, seed
        self.history = []

    def fit(self, train_views, train_labels):
        idx = list(range(len(train_views)))
        random.Random(self.seed).shuffle(idx)
        cut = int(len(idx) * 0.8)
        fit_i, val_i = idx[:cut], idx[cut:]
        self.views, self.labels = train_views, train_labels
        self.ws = [words(v) for v in train_views]
        base = defaultdict(Counter)
        for i in fit_i:
            base[signature(train_views[i])][tuple(train_labels[i]["actions"])] += 1
        self.base = {s: c.most_common(1)[0][0] for s, c in base.items()}
        self.verdict = {}
        for i in fit_i:
            self.verdict.setdefault(tuple(train_labels[i]["actions"]), Counter())[
                train_labels[i]["verdict"]
            ] += 1
        self.exceptions = []
        score = self.score(val_i)
        self.history.append(
            {"cycle": 0, "validation_accuracy": score, "exceptions": 0, "retained": True}
        )
        for cycle in range(1, self.cycles + 1):
            proposal = self.propose(fit_i)
            if not proposal:
                self.history.append({"cycle": cycle, "proposed": 0, "retained": False})
                break
            previous = self.exceptions
            self.exceptions = previous + proposal
            new = self.score(val_i)
            retained = new > score
            self.history.append(
                {
                    "cycle": cycle,
                    "proposed": len(proposal),
                    "validation_accuracy": new,
                    "retained": retained,
                }
            )
            if retained:
                score = new
            else:
                self.exceptions = previous
        return self

    def propose(self, fit_i):
        """Per signature, the single word that best splits the base procedure's errors."""
        rules = []
        by_sig = defaultdict(list)
        for i in fit_i:
            by_sig[signature(self.views[i])].append(i)
        for sig, members in by_sig.items():
            current = {i: self.apply(self.views[i]) for i in members}
            wrong = [i for i in members if tuple(self.labels[i]["actions"]) != current[i]]
            if len(wrong) < 5:
                continue
            best = None
            for target in sorted(Counter(tuple(self.labels[i]["actions"]) for i in wrong)):
                df = Counter(w for i in members for w in self.ws[i])
                for w, n in sorted(df.items()):  # sorted: set order varies per process
                    if n < 5:
                        continue
                    hit = [i for i in members if w in self.ws[i]]
                    gain = sum(tuple(self.labels[i]["actions"]) == target for i in hit) - sum(
                        tuple(self.labels[i]["actions"]) == current[i] for i in hit
                    )
                    if best is None or gain > best[0]:
                        best = (gain, w, target)
            if best and best[0] > 0:
                rules.append({"signature": sig, "word": best[1], "actions": list(best[2])})
        return rules

    def apply(self, view):
        sig = signature(view)
        ws = words(view)
        for rule in self.exceptions:
            if rule["signature"] == sig and rule["word"] in ws:
                return tuple(rule["actions"])
        return self.base.get(sig)

    def score(self, idx):
        return round(
            sum(self.apply(self.views[i]) == tuple(self.labels[i]["actions"]) for i in idx)
            / len(idx),
            4,
        )

    def decide(self, view):
        actions = self.apply(view)
        if actions is None:
            return decision(
                ("ask_question",), "undetermined", view, rationale="no procedure for this evidence"
            )
        verdict = self.verdict.get(actions, Counter({"undetermined": 1})).most_common(1)[0][0]
        return decision(actions, verdict, view, rationale="learned procedure")

    def procedures(self):
        return {
            "base": {k: list(v) for k, v in sorted(self.base.items())},
            "exceptions": self.exceptions,
            "history": self.history,
        }


def train_set(ds):
    views = [sim_view(c) for c in ds.train]
    labels = []
    for c in ds.train:
        actions, verdict, _ = POLICY_MAP[c["resolution"]["family"]]
        labels.append({"actions": list(actions), "verdict": verdict})
    return views, labels


def make_arms(ds):
    views, labels = train_set(ds)
    arms = [Static(), Memory(), Evolving()]
    for arm in arms:
        arm.fit(views, labels)
    assert all(a in ACTIONS for arm in arms[1:] for lab in labels for a in lab["actions"])
    assert ABSTAIN <= set(ACTIONS)
    return arms
