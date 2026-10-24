"""Bounded offline compiler; injectable through the existing compiler boundary."""

import re

from app.contracts.catalog import Clarification, CompilerOutput
from app.datasets import make_terms


def compile_dataset(context, store):
    draft = context.draft
    text = " ".join((draft.prompt, *(a.text for a in draft.answers))).lower()
    age = re.search(r"\b25\s*(?:–|-|to)\s*34\b", text)
    expected_city = "oakland" if draft.corpus_id.startswith("oakland") else "san francisco"
    city_ok = (
        expected_city in text
        or expected_city == "san francisco"
        and bool(re.search(r"\bsf\b", text))
    )
    other_city = "san francisco" if expected_city == "oakland" else "oakland"
    if other_city in text or any(
        (int(a), int(b)) != (25, 34)
        for a, b in re.findall(r"\b(\d{2})\s*(?:–|-|to)\s*(\d{2})\b", text)
    ):
        city_ok = False
    category = None
    if "gym" in text and "app" in text:
        category = "gym_app_or_yoga" if "include yoga" in text else "gym_or_fitness_app"
    if not age or not city_ok:
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
