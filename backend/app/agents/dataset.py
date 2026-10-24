"""Bounded offline compiler; injectable through the existing compiler boundary."""

import re

from app.contracts.catalog import Clarification, CompilerOutput
from app.datasets import make_terms


def _clauses(text):
    return re.split(r"[.;,]|\b(?:but|however|and|or)\b", text.lower().replace("’", "'"))


def _cohort(text):
    """Positive values and explicit exclusions, not union of every token in history."""
    ages, cities, excluded_ages, excluded_cities = set(), set(), set(), set()
    for clause in _clauses(text):
        for match in re.finditer(r"\b(\d{2})\s*(?:–|-|to)\s*(\d{2})\b", clause):
            prefix = clause[: match.start()]
            negative = bool(
                re.search(
                    r"\b(?:not|exclude|excluding|except|without)\s*(?:include\s+)?"
                    r"(?:adults?\s*(?:aged?\s*)?)?$",
                    prefix,
                )
            )
            (excluded_ages if negative else ages).add(tuple(map(int, match.groups())))
        for match in re.finditer(r"\bsan francisco\b|\bsf\b|\boakland\b", clause):
            city = "oakland" if match[0] == "oakland" else "san francisco"
            negative = bool(
                re.search(
                    r"\b(?:not|exclude|excluding|except|without)\s*(?:include\s+)?$",
                    clause[: match.start()],
                )
            )
            (excluded_cities if negative else cities).add(city)
    return ages, cities, excluded_ages, excluded_cities


def _category(text):
    lower = text.lower().replace("’", "'")
    if not re.search(r"\bgym\b", lower) or not re.search(r"\b(?:app|apps)\b", lower):
        return None
    if re.search(
        r"\b(?:not|no|without|exclude)\s+(?:include\s+)?(?:gym|fitness[- ]?apps?)\b", lower
    ):
        return None
    include, exclude, ambiguous = False, False, False
    for clause in _clauses(lower):
        if not re.search(r"\byoga\b", clause):
            continue
        if re.search(
            r"\b(?:not|never|don't|do not)\s+(?:exclude|omit|without)\b|\bnot only\b", clause
        ):
            ambiguous = True
        negative = bool(
            re.search(
                r"\b(?:not|no|never|don't|exclude|excluded|excluding|without|except|omit)\b", clause
            )
        )
        positive = bool(
            re.search(r"\b(?:include|included|including|add|with|cover|count)\b", clause)
        )
        exclude |= negative
        include |= positive and not negative
        ambiguous |= not negative and not positive
    if ambiguous or include and exclude:
        return None
    return "gym_app_or_yoga" if include else "gym_or_fitness_app"


def compile_dataset(context, store):
    draft = context.draft
    expected_city = "oakland" if draft.corpus_id.startswith("oakland") else "san francisco"
    ages, cities, excluded_ages, excluded_cities = _cohort(draft.prompt)
    category = _category(draft.prompt)
    unrelated_conflict = False
    for answer in draft.answers:
        # The service has already checked exact current question identity. Preserve
        # immutable prompt/history; only replace the field that question solicited.
        field = answer.question_id.removeprefix(draft.request_id + ":").split(":")[0]
        a, c, na, nc = _cohort(answer.text)
        if field == "cohort":
            if a or na:
                ages, excluded_ages = a, na
            if c or nc:
                cities, excluded_cities = c, nc
        elif a or c or na or nc:
            unrelated_conflict |= bool(
                (a and a != ages) or (c and c != cities) or na & ages or nc & cities
            )
        proposed_category = _category(answer.text)
        if field == "category":
            category = proposed_category
        elif proposed_category and category is None:
            category = proposed_category
        elif proposed_category and proposed_category != category:
            category = None  # Contradictory unbound scope needs its own clarification.
    cohort_ok = (
        ages == {(25, 34)}
        and cities == {expected_city}
        and not ages & excluded_ages
        and not cities & excluded_cities
        and not unrelated_conflict
    )
    if not cohort_ok:
        question = (
            "Confirm the supported cohort: adults aged 25–34 in "
            + ("Oakland" if expected_city == "oakland" else "San Francisco")
            + ", grouped by ZIP."
        )
        field = "cohort"
    elif category is None:
        question = (
            "Does fitness mean gym membership or fitness-app use? State "
            "'include yoga' only if you also want standalone yoga-studio "
            "membership."
        )
        field = "category"
    else:
        terms = make_terms(context.sources, store, category=category, request_id=draft.request_id)
        return CompilerOutput(
            terms=terms,
            question=None,
            summary="Synthetic aggregate adults aged 25–34, by registered ZIP.",
            limitations=(
                "Synthetic sources and ZIP registry; no personal records or live acquisition.",
                "Suppression threshold is a demo contract check, not a general privacy guarantee.",
            ),
        )
    return CompilerOutput(
        terms=None,
        question=Clarification(
            question_id=f"{draft.request_id}:{field}:{draft.questions_asked + 1}",
            prompt=question,
            field=field,
        ),
        summary="One bounded cohort/category clarification is required.",
        limitations=("Only the synthetic registered cohort is supported.",),
    )
