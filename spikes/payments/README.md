# Isolated Base escrow laboratory — Nikita

Phase 1 provides reusable offline DTO/protocol/signature helpers and mock/fake application
boundaries. The live RPC adapter and `run.py` runner are not implemented in this phase.
No real testnet transaction has been observed. Follow [payment specification](../../docs/PAYMENT_SPIKE.md)
and [runbook](../../docs/PAYMENT_RUNBOOK.md) for current executable checks and the explicitly
marked next runner contract.

Use Base Commerce Payments on Base Sepolia with a dedicated platform operator; no x402 or
separate verification fee. Synthetic accepted terms and a fixture settlement decision let
Nikita prove payment mechanics independently of Jeff's prompts or Lucas's frontend. The later
separately authorized proof is two independent 0.10 test-USDC payments: fund/restart/capture,
and fund/void. It does not settle a USD 15 catalog order or claim an AI verdict.

This task authorizes no broadcast, deployment, token purchase or paid model call. Keep private
signers/capabilities out of reports. Capture/release remain subject to catalog gates; release
of held funds is distinct from unimplemented refunds of captured money.
