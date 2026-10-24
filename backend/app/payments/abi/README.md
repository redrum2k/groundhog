# Pinned Commerce Payments interface

The Solidity files under `source/` are copied unchanged from
[base/commerce-payments commit b748fdd7a830a655a19a530edcf2a94b9dc7d25f](https://github.com/base/commerce-payments/tree/b748fdd7a830a655a19a530edcf2a94b9dc7d25f).
That revision's README identifies the configured escrow and collector as v1.1.0.
The upstream MIT license accompanies the copies. `provenance.json` records source
and interface SHA-256 hashes checked by offline tests.

The JSON ABIs are **minimal interface transcriptions**, checked against the pinned
Solidity declarations, not complete compiler-generated deployment artifacts. The
escrow capture argument is `uint256 feeAmount`, an absolute token quantity. This
is not v1.0's basis-point capture interface. Refund and charge are intentionally
absent from the supported interface.

`ERC3009PaymentCollector` passes an EOA's raw 65-byte `r || s || v` signature to
USDC. Its authorization recipient is the collector, value is `maxAmount`,
`validAfter` is zero, and nonce is escrow `getHash` after replacing payer with
the zero address. The actual payment hash retains the real payer.

The USDC JSON includes only read methods from Circle's token interface. Circle's
[FiatTokenV2_2](https://github.com/circlefin/stablecoin-evm/blob/master/contracts/v2/FiatTokenV2_2.sol)
uses the observed token name and EIP-712 version `2`. Offline typed-data helpers
require a supplied name; they do not establish what is deployed. Live preparation
must compare the computed domain separator against the token's actual
`DOMAIN_SEPARATOR`, verify chain, deployed bytecode/interface compatibility,
collector binding, decimals and balances before signing/submitting.

No RPC deployment verification, blockchain transaction, live receipt or balance
observation was performed as part of the phase-one frontend contract work.
