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


def _yoga_policy(text):
    lower = text.lower().replace("’", "'")
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
    return include, exclude, ambiguous or include and exclude


def _category(text):
    lower = text.lower().replace("’", "'")
    if not re.search(
        r"\bgym\b[^.;]*\bor\b[^.;]*\bapps?\b|\bapps?\b[^.;]*\bor\b[^.;]*\bgym\b",
        lower,
    ):
        return None
    if re.search(r"\bonly\b", lower) or re.search(
        r"\b(?:gym|(?:fitness[- ]?)?apps?)\b[^.;,]*(?:excluded|not included|not wanted)", lower
    ):
        return None
    if re.search(
        r"\b(?:not|no|without|exclude|excluding)\s+(?:include\s+)?"
        r"(?:gym|(?:fitness[- ]?)?apps?)\b",
        lower,
    ):
        return None
    if re.search(r"\bgym\b[^.;]*\band\b[^.;]*\bapps?\b", lower):
        return None  # Intersection-only is not the available union product.
    include, _, ambiguous = _yoga_policy(lower)
    if ambiguous:
        return None
    return "gym_app_or_yoga" if include else "gym_or_fitness_app"


def _affirmative(text):
    return " ".join(re.findall(r"[a-z]+", text.lower())) in {
        "yes",
        "yes please",
        "i accept",
        "i agree",
        "yes i accept",
        "yes the combined product is fine",
        "the broader product is fine",
        "i accept the broader product",
        "yes include both",
        "both are fine",
        "either is fine",
    }


def compile_dataset(context, store, *, proposal=None):
    draft = context.draft
    if proposal and proposal.requested_scope == "unsupported":
        raise ValueError("Unsupported dataset request: " + proposal.explanation)
    expected_city = "oakland" if draft.corpus_id.startswith("oakland") else "san francisco"
    ages, cities, excluded_ages, excluded_cities = _cohort(draft.prompt)
    category = _category(draft.prompt)
    category_text = draft.prompt
    unrelated_age_conflict = unrelated_city_conflict = False
    for answer in draft.answers:
        # The service has already checked exact current question identity. Preserve
        # immutable prompt/history; only replace the field that question solicited.
        field = answer.question_id.removeprefix(draft.request_id + ":").split(":")[0]
        a, c, na, nc = _cohort(answer.text)
        if field == "cohort":
            if a or na:
                ages, excluded_ages = a, na
                unrelated_age_conflict = False
            if c or nc:
                cities, excluded_cities = c, nc
                unrelated_city_conflict = False
        elif a or c or na or nc:
            unrelated_age_conflict |= bool((a and a != ages) or na & ages)
            unrelated_city_conflict |= bool((c and c != cities) or nc & cities)
        proposed_category = _category(answer.text)
        if field.startswith("category_offer"):
            if re.match(
                r"\s*(?:no\b|decline\b|i (?:decline|do not accept)\b)", answer.text.lower()
            ):
                raise ValueError(
                    "Unsupported narrower scope: the available broader product was declined."
                )
            offered = "gym_app_or_yoga" if field.endswith("yoga") else "gym_or_fitness_app"
            if _affirmative(answer.text):
                proposed_category = offered
            if proposed_category is None:
                raise ValueError(
                    "The narrower product is unavailable and broader scope was not accepted."
                )
            category, category_text = proposed_category, answer.text
        elif field == "category":
            # A question-bound yoga correction preserves an already named base
            # population; it does not merge all contradictory conversation text.
            if (
                _category(re.sub(r"[^.;]*\byoga\b[^.;]*", "", category_text, flags=re.I))
                == "gym_or_fitness_app"
                and re.search(r"\byoga\b", answer.text.lower())
                and not re.search(r"\bgym\b|\bapps?\b", answer.text.lower())
            ):
                proposed_category = _category("gym membership or fitness app use. " + answer.text)
            category = proposed_category
            category_text = answer.text
        elif proposed_category and category is None:
            category = proposed_category
        elif proposed_category and proposed_category != category:
            category = None  # Contradictory unbound scope needs its own clarification.
            category_text = answer.text
        elif proposed_category is None and re.search(
            r"\bgym\b|\bapps?\b|\byoga\b", answer.text.lower()
        ):
            category, category_text = None, answer.text
    if proposal and proposal.requested_scope in {"gym_only", "app_only", "yoga_only"}:
        category = None  # Model-detected narrowing must also require explicit consent.
    if proposal and proposal.requested_scope in {"gym_or_fitness_app", "gym_app_or_yoga"}:
        if category != proposal.requested_scope:
            category = None  # A changed interpreted product must be offered, never imposed.
    if (
        proposal
        and proposal.requested_scope == "ambiguous"
        and proposal.clarification_field == "category"
        and proposal.clarification
    ):
        category = None
    cohort_ok = (
        ages == {(25, 34)}
        and cities == {expected_city}
        and not ages & excluded_ages
        and not cities & excluded_cities
        and not unrelated_age_conflict
        and not unrelated_city_conflict
    )
    if not cohort_ok:
        question = (
            "Confirm the supported cohort: adults aged 25–34 in "
            + ("Oakland" if expected_city == "oakland" else "San Francisco")
            + ", grouped by ZIP."
        )
        field = "cohort"
        if any(a.question_id.startswith(draft.request_id + ":cohort:") for a in draft.answers):
            question = (
                "Your correction still names an unsupported or conflicting cohort. " + question
            )
        if proposal and proposal.clarification_field == "cohort" and proposal.clarification:
            question = proposal.clarification
    elif category is None:
        # A partial answer is evidence of a narrower request, not union-product consent.
        partial = bool(
            re.search(r"\b(?:gym|apps?|yoga|membership|subscribers?)\b", category_text.lower())
        )
        included, excluded, ambiguous_yoga = _yoga_policy(category_text)
        if ambiguous_yoga and (
            not proposal or proposal.requested_scope != "gym_app_or_yoga" or excluded
        ):
            field = "category"
            question = (
                "Your yoga instructions are conflicting or unclear. Should standalone "
                "yoga be included in, or excluded from, the gym-or-fitness-app population?"
            )
        elif (
            proposal
            and proposal.requested_scope == "ambiguous"
            and proposal.clarification
            and _category(category_text) is not None
        ):
            field, question = "category", proposal.clarification
        elif partial or proposal and proposal.requested_scope != "ambiguous":
            expanded = included or bool(
                proposal and proposal.requested_scope == "gym_app_or_yoga" and not excluded
            )
            field = "category_offer_yoga" if expanded else "category_offer_base"
            product = "gym membership OR fitness-app use" + (
                " OR standalone yoga" if expanded else " (standalone yoga excluded)"
            )
            question = (
                "The available product combines " + product + ". "
                "Separate gym-only, app-only and intersection-only counts are unavailable. "
                "Do you accept this broader combined product? Please answer yes or no."
            )
        else:
            question = (
                proposal.clarification
                if proposal and proposal.clarification
                else (
                    "Does fitness mean gym membership or fitness-app use? State "
                    "'include yoga' only if you also want standalone yoga-studio membership."
                )
            )
            field = "category"
            if draft.answers and not proposal:
                question = (
                    "The requested fitness definition is still unclear. Would the combined "
                    "gym-membership OR fitness-app product, excluding standalone yoga, "
                    "meet your need?"
                )
                field = "category_offer_base"
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
    if any(
        " ".join(q.prompt.lower().split()) == " ".join(question.lower().split())
        for q in draft.question_history
    ):
        raise ValueError("Scope remains unresolved; refusing to repeat the same clarification.")
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
