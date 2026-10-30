"""UUID <-> bytes32 encoding agreed with the blockchain teammate.

Rule (docs/decisions/2026-10-30-blockchain-interface.md): a UUID's 16
big-endian bytes are LEFT-padded with 16 zero bytes to 32 bytes — identical to
`bytes32(uint256(uint128(bytes16(uuid))))` in Solidity (the 128-bit value is
zero-extended into the low half of the 32-byte word).
"""

from __future__ import annotations

import uuid


def uuid_to_bytes32(value: uuid.UUID) -> bytes:
    return b"\x00" * 16 + value.bytes


def uuid_to_bytes32_hex(value: uuid.UUID) -> str:
    """0x-prefixed 64-hex form used in publication job payloads."""
    return "0x" + uuid_to_bytes32(value).hex()
