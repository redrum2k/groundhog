"""Explicit Base Sepolia configuration. Importing this module reads no environment."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from eth_account import Account
from eth_utils import is_address, to_checksum_address

BASE_CHAIN_ID = 84532
BASE_USDC_ADDRESS = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
BASE_ESCROW_ADDRESS = "0xf96815976523E00e65Be8f34cA5e64b4f41EB19c"
BASE_COLLECTOR_ADDRESS = "0x8612dfdc421f80336cd14E8EF9cb1E765dB5ab88"
SOURCE_COMMIT = "b748fdd7a830a655a19a530edcf2a94b9dc7d25f"
DEPLOYMENT_VERSION = "v1.1.0"


@dataclass(frozen=True)
class BasePaymentConfig:
    rpc_url: str = field(default="", repr=False)
    chain_id: int = BASE_CHAIN_ID
    usdc_address: str = BASE_USDC_ADDRESS
    escrow_address: str = BASE_ESCROW_ADDRESS
    collector_address: str = BASE_COLLECTOR_ADDRESS
    provider_address: str | None = None
    operator_private_key: str | None = field(default=None, repr=False)
    confirmations: int = 2
    enable_testnet_broadcast: bool = False
    journal_path: str = "artifacts/payment-journal.sqlite3"

    def __post_init__(self):
        if self.chain_id != BASE_CHAIN_ID:
            raise ValueError("only Base Sepolia chain 84532 is supported")
        for name, expected in (
            ("usdc_address", BASE_USDC_ADDRESS),
            ("escrow_address", BASE_ESCROW_ADDRESS),
            ("collector_address", BASE_COLLECTOR_ADDRESS),
        ):
            value = getattr(self, name)
            if not is_address(value) or value.lower() != expected.lower():
                raise ValueError(f"{name} must match the pinned Base Sepolia deployment")
            object.__setattr__(self, name, to_checksum_address(value))
        if self.provider_address:
            if not is_address(self.provider_address) or int(self.provider_address, 16) == 0:
                raise ValueError("BASE_PROVIDER_ADDRESS must be a nonzero address")
            object.__setattr__(self, "provider_address", to_checksum_address(self.provider_address))
        if self.confirmations < 2:
            raise ValueError("PAYMENT_CONFIRMATIONS must be at least 2")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "BasePaymentConfig":
        values = os.environ if env is None else env
        flag = values.get("ENABLE_TESTNET_BROADCAST", "false").lower()
        if flag not in {"true", "false"}:
            raise ValueError("ENABLE_TESTNET_BROADCAST must be true or false")
        return cls(
            rpc_url=values.get("BASE_SEPOLIA_RPC_URL", ""),
            chain_id=int(values.get("BASE_CHAIN_ID", str(BASE_CHAIN_ID))),
            usdc_address=values.get("BASE_USDC_ADDRESS", BASE_USDC_ADDRESS),
            escrow_address=values.get("BASE_ESCROW_ADDRESS", BASE_ESCROW_ADDRESS),
            collector_address=values.get("BASE_ERC3009_COLLECTOR_ADDRESS", BASE_COLLECTOR_ADDRESS),
            provider_address=values.get("BASE_PROVIDER_ADDRESS") or None,
            operator_private_key=values.get("BASE_OPERATOR_PRIVATE_KEY") or None,
            confirmations=int(values.get("PAYMENT_CONFIRMATIONS", "2")),
            enable_testnet_broadcast=flag == "true",
            journal_path=values.get("PAYMENT_JOURNAL_PATH", "artifacts/payment-journal.sqlite3"),
        )

    @property
    def operator_address(self) -> str | None:
        if not self.operator_private_key:
            return None
        try:
            return Account.from_key(self.operator_private_key).address
        except Exception:
            raise ValueError("BASE_OPERATOR_PRIVATE_KEY is not a valid dedicated EOA key") from None
