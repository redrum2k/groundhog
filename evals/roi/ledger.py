"""Observed scripted work episodes, deliberately without human timing claims."""

from evals.roi.plan import digest

PROVIDER_ROLES = {"operator", "controller"}


class Ledger:
    def __init__(self, case, arm, input_hash):
        self.case, self.arm, self.input_hash = case, arm, input_hash
        self.events = {}

    def add(
        self, role, work_type, reference, *, source="scripted_application_command", order_id=None
    ):
        episode = digest([self.arm, self.case["case_id"], role, work_type, reference])
        event = {
            "case_id": self.case["case_id"],
            "stream_id": self.case["stream_id"],
            "category": self.case["category"],
            "order_id": order_id,
            "arm": self.arm,
            "phase": self.case["phase"],
            "event_id": episode,
            "work_episode_id": episode,
            "actor_role": role,
            "work_type": work_type,
            "event_source": source,
            "input_hash": self.input_hash,
            "procedure_version": None,
            "attention_seconds": None,
            "attention_provenance": "unmeasured_scripted_action",
            "provider_cost_usd": 0,
            "cost_provenance": "executed_offline_no_provider_dispatch",
            "machine_elapsed_seconds": None,
            "wait_seconds": None,
            "artifact_refs": [reference],
            "expected_disposition": None,
            "observed_disposition": None,
            "quality_pass": None,
            "booking_count": None,
        }
        self.events.setdefault(episode, event)
        return episode


def unique_episodes(events):
    distinct = {}
    for event in events:
        key = event["work_episode_id"]
        if key in distinct and distinct[key] != event:
            raise ValueError("Conflicting records for one work episode")
        distinct[key] = event
    return list(distinct.values())
