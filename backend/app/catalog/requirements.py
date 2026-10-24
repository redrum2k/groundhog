from app.contracts.catalog import Requirement, Specification, Terms


def specification(terms: Terms, revision: int, summary: str, limitations: tuple[str, ...]):
    """Stable, server-owned allowlist. A compiler cannot delete global checks."""
    from app.contracts.dataset import DatasetSpecification
    from app.datasets import requirement_words

    if isinstance(terms, DatasetSpecification):
        return Specification(
            revision=revision,
            terms=terms,
            summary=summary,
            limitations=limitations,
            requirements=tuple(
                Requirement(requirement_id=f"R-{key.upper()}", wording=value, check=key)
                for key, value in requirement_words(terms).items()
            ),
        )
    words = {"lt": "below", "lte": "at most"}
    wording = {
        "category": f"Select products in category {terms.category}.",
        "weight": (
            f"{terms.weight_concept} weight {words[terms.weight_operator]} "
            f"{terms.weight_threshold} {terms.weight_unit}."
        ),
        "price": (
            f"{terms.price_basis} price {words[terms.price_operator]} "
            f"{terms.currency} {terms.price_threshold}."
        ),
        "fields": "Unique product IDs and all six required fields must be present.",
        "completeness": (
            "Include every eligible product; justify exclusions and list unresolved records."
        ),
        "provenance": (
            "Use the frozen edition and established authority; cite exact source passages."
        ),
        "pdf": "The actual delivered PDF must faithfully contain the complete cited shortlist.",
    }
    return Specification(
        revision=revision,
        terms=terms,
        summary=summary,
        limitations=limitations,
        requirements=tuple(
            Requirement(requirement_id=f"R-{key.upper()}", wording=value, check=key)
            for key, value in wording.items()
        ),
    )
