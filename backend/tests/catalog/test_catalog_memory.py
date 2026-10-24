from app.improvement.catalog_memory import FunctionalCatalogMemory
from app.improvement.catalog_probe import development_cases, run_visible_case


class Gateway:
    model = "injected-not-real-model"

    def parse(self, schema, instruction, context):
        self.context = context
        return schema(
            action="retrieve_registered",
            rationale="Use scoped observed evidence",
            used_experience_ids=tuple(e["id"] for e in context["scoped_incident_experiences"]),
        )


def test_functional_memory_receives_actual_evidence_and_never_crosses_scope():
    for scope, expected in (("memory-demo", ["observed-one"]), ("different-scope", [])):
        gateway = Gateway()
        memory = FunctionalCatalogMemory(
            [
                {
                    "id": "observed-one",
                    "corpus_id": "memory-demo",
                    "observed_outcome": "evidence_only",
                }
            ],
            gateway=gateway,
        )
        result = run_visible_case(
            development_cases(scope)[0], arm="functional_memory", memory_decider=memory
        )
        assert result["operationally_closed"]
        assert result["company_actions"]["manual_evidence_acquisition"] == 0
        assert result["memory_decisions"][0]["decision"]["used_experience_ids"] == expected
        assert "actual_pdf_pages" in gateway.context["registered_publications_in_current_scope"][0]
        assert not (
            {"oracle", "family", "provider_output_base64", "historical_procedure"}
            & gateway.context.keys()
        )
