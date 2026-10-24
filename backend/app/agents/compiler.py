"""Jeff owns compiler semantics; the runtime persists revisions, budgets and deadlines."""

import re
from decimal import Decimal
from typing import Protocol

from app.contracts.catalog import Clarification, CompilerOutput, PrecontractContext, Terms


class ContractCompiler(Protocol):
    def compile(self, context: PrecontractContext) -> CompilerOutput: ...


class OfflineCompiler:
    """Deterministic, disclosed substitute for the bounded storage-catalog demo language."""

    def compile(self, context: PrecontractContext) -> CompilerOutput:
        draft = context.draft
        text = (draft.prompt + " " + " ".join(a.text for a in draft.answers)).lower()
        limitations = (
            "Synthetic provider-owned catalog PDFs; no web acquisition or unrestricted uploads.",
            (
                "USD unit prices only; source authority and unreadable "
                "values are checked before delivery."
            ),
        )

        def ask(field, prompt):
            return CompilerOutput(
                terms=None,
                question=Clarification(question_id=f"clarify-{field}", field=field, prompt=prompt),
                summary="A material requirement needs clarification.",
                limitations=limitations,
            )

        if "storage" not in text:
            return ask("category", "This demo supports storage products. Is storage your category?")
        if "net" not in text and "shipping" not in text:
            return ask(
                "weight_concept", "Does the weight limit mean net unit weight or shipping weight?"
            )
        if "net" in text and "shipping" in text:
            answer = draft.answers[-1].text.lower() if draft.answers else ""
            if ("net" in answer) == ("shipping" in answer):
                return ask(
                    "weight_concept", "Choose exactly one: net unit weight or shipping weight."
                )
            concept = "net_unit" if "net" in answer else "shipping"
        else:
            concept = "net_unit" if "net" in text else "shipping"
        weight = re.search(
            r"(below|under|less than|at most|no more than|<=|<)\s*(\d+(?:\.\d+)?)\s*(kg|g)\b", text
        )
        price = re.search(
            r"(below|under|less than|at most|no more than|<=|<)\s*(?:usd|\$)\s*(\d+(?:\.\d+)?)",
            text,
        )
        if not weight:
            return ask(
                "weight", "Specify a weight limit and operator, e.g. below 2 kg or at most 2 kg."
            )
        if not price or "unit" not in text:
            return ask(
                "price", "Specify USD unit price and operator, e.g. unit price no more than USD 40."
            )
        exclusive = {"below", "under", "less than", "<"}
        terms = Terms(
            corpus_id=draft.corpus_id,
            weight_concept=concept,
            weight_unit=weight[3],
            weight_threshold=Decimal(weight[2]),
            weight_operator="lt" if weight[1] in exclusive else "lte",
            price_threshold=Decimal(price[2]),
            price_operator="lt" if price[1] in exclusive else "lte",
        )
        return CompilerOutput(
            terms=terms,
            question=None,
            summary="Select every qualifying storage product with exact source citations.",
            limitations=limitations,
        )
