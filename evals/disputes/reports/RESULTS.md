# Dispute arm comparison

On the sealed holdout, action accuracy is static 98.2%, memory 34.9%, evolving 56.9%; best arm: static. A learning claim needs the evolving arm to beat the static checklist here without more unsupported or financial-policy violations.

## Sealed aggregate holdout

109 cases across 20 aggregate-brokerage mechanisms built from actual source and delivery bytes; checks are the real verify_dataset output. Labels sealed until predictions froze.

| metric | static | memory | evolving |
| --- | --- | --- | --- |
| n | 109 | 109 | 109 |
| action_accuracy | 0.9817 | 0.3486 | 0.5688 |
| verdict_accuracy | 0.9266 | 0.3945 | 0.5505 |
| settlement_correct | 0.9266 | 0.3486 | 0.5138 |
| unsupported_actions | 0 | 40 | 0 |
| forbidden_actions | 2 | 20 | 4 |
| correct_abstentions | 24/24 | 6/24 | 20/24 |
| over_abstentions | 5 | 23 | 33 |
| citation_recall | 1.0 | 0.5312 | 0.1719 |
| ungrounded_citations | 0 | 0 | 0 |
| financial_policy_violations | 2 | 0 | 0 |
| human_interventions | 13 | 14 | 0 |
| model_calls | 0 | 0 | 0 |
| model_usd | 0.0 | 0.0 | 0.0 |

## Development (221 simulated test cases)

Wording generalization only: same 26 templates as train, remedies translated to aggregate-brokerage-v1. Development tests, not a holdout.

| metric | static | memory | evolving |
| --- | --- | --- | --- |
| n | 221 | 221 | 221 |
| action_accuracy | 0.6335 | 0.8688 | 0.6697 |
| verdict_accuracy | 0.6335 | 0.8597 | 0.6923 |
| settlement_correct | 0.6335 | 0.8688 | 0.6697 |
| unsupported_actions | 0 | 21 | 0 |
| forbidden_actions | 0 | 0 | 0 |
| correct_abstentions | 2/60 | 60/60 | 40/60 |
| over_abstentions | 13 | 13 | 45 |
| citation_recall | 1.0 | 0.8807 | 0.7615 |
| ungrounded_citations | 0 | 0 | 0 |
| financial_policy_violations | 0 | 0 | 0 |
| human_interventions | 15 | 39 | 13 |
| model_calls | 0 | 0 | 0 |
| model_usd | 0.0 | 0.0 | 0.0 |

## Real-language stress (Hugging Face)

156 real threads, no accepted contract or verified checks. Scored only on independently reviewed rows; keyword-assigned remedies are not ground truth.

| metric | static | memory | evolving |
| --- | --- | --- | --- |
| n | 48 | 48 | 48 |
| action_accuracy | 0.2292 | 0.25 | 0.1458 |
| verdict_accuracy | 0.2083 | 0.2917 | 0.1875 |
| settlement_correct | 0.2292 | 0.25 | 0.1458 |
| unsupported_actions | 0 | 16 | 0 |
| forbidden_actions | 0 | 0 | 0 |
| correct_abstentions | 10/10 | 5/10 | 0/10 |
| over_abstentions | 38 | 15 | 0 |
| citation_recall | None | None | None |
| ungrounded_citations | 0 | 0 | 0 |
| financial_policy_violations | 0 | 0 | 0 |
| human_interventions | 0 | 17 | 0 |
| model_calls | 0 | 0 | 0 |
| model_usd | 0.0 | 0.0 | 0.0 |

## Frozen inputs

```json
{
  "dataset_fingerprint": {
    "cases.jsonl": "ec3ac12e5d506deeb19471b0230ce96e7ffc3f887a2554b04e83d7dc87056ba8",
    "hf_data_disputes.jsonl": "7981eb9e7baf2e89137738ca34267ee2aa41d5c0251da309e67c5f8d23d699a6"
  },
  "memory_sha256": "cc2f6e127ecef06722eec5b9547c3de589d37a18a30f49e30df825758cb841be",
  "procedures_sha256": "1a4406a784665ccfe5720d2625c0acd5c49810f371886fce4e83006400e164d3",
  "evolving_history": [
    {
      "cycle": 0,
      "validation_accuracy": 0.6797,
      "exceptions": 0,
      "retained": true
    },
    {
      "cycle": 1,
      "proposed": 3,
      "validation_accuracy": 0.7773,
      "retained": true
    },
    {
      "cycle": 2,
      "proposed": 2,
      "validation_accuracy": 0.875,
      "retained": true
    }
  ],
  "predictions_sha256": {
    "development": "9d19efd485ec5ea548bd90f50c4b47185e79d3f3052be3c5338d98e3c6ef20db",
    "hf_real": "c7fa82c3c771b5ad3f4236999b1dc8865c1d14df9fa22cd946e853a0262399ad",
    "holdout": "6e86013804a57d7569227a1a827371b043d638f8199783e5c32765def3a47dfe"
  },
  "holdout_scored_runs": 4
}
```
