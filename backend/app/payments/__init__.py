import os
from dataclasses import dataclass, replace
from pathlib import Path

from app.contracts.http import Capabilities
from app.payments.base import BasePaymentTransport
from app.payments.base_config import BasePaymentConfig
from app.payments.mock import MockPaymentAdapter


def configured_payment_mode(mode=None) -> str:
    mode = mode if mode is not None else os.getenv("PAYMENT_ADAPTER", "mock")
    if mode not in ("mock", "base_sepolia"):
        raise ValueError("PAYMENT_ADAPTER must be mock or base_sepolia")
    return mode


@dataclass(frozen=True)
class CatalogPaymentSetup:
    mode: str
    config: BasePaymentConfig | None
    transport: BasePaymentTransport | None
    capabilities: Capabilities


def catalog_payment_setup(*, mode=None, config=None, transport=None):
    """Explicit lifespan initialization, never called by import or schema export.

    Read-only preflight gates automatic signing. Unavailable Base stays Base; restart
    after repairing configuration/preflight to enable submission. Receipt inspection
    remains possible with an available transport even when submission is disabled.
    """
    mode = configured_payment_mode(mode)
    if mode == "mock":
        if config is not None or transport is not None:
            raise ValueError("Base injection requires explicit payment_mode=base_sepolia")
        return CatalogPaymentSetup(mode, None, None, Capabilities(live_adapter="disabled"))
    config = config if config is not None else BasePaymentConfig.from_env()
    signer_ready = bool(
        config.operator_address and config.provider_address and config.operator_private_key
    )
    ready = False
    try:
        transport = transport if transport is not None else BasePaymentTransport(config)
        transport.preflight()
        ready = signer_ready
    except Exception:
        # RPC URLs and upstream exceptions can contain credentials. Public health is
        # categorical; per-operation guards still recheck the exact accepted terms.
        pass
    enabled = ready and config.enable_testnet_broadcast
    return CatalogPaymentSetup(
        mode,
        replace(config, enable_testnet_broadcast=enabled),
        transport,
        Capabilities(
            payment_mode=mode,
            live_adapter="ready" if ready else "unavailable",
            live_settlement_enabled=enabled,
        ),
    )


def get_payment_adapter(journal_path: Path | None = None) -> MockPaymentAdapter:
    # Legacy invoice adapters never become catalog Base transports.
    if configured_payment_mode() != "mock":
        raise ValueError("legacy payment adapter supports mock only; use catalog Base setup")
    path = (
        journal_path
        if journal_path is not None
        else Path(os.getenv("MOCK_PAYMENT_DB_PATH", "artifacts/mock-payments.sqlite3"))
    )
    return MockPaymentAdapter(path)
