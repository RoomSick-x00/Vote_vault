"""Ballot commitment scheme — fixed encoding, documented and agreed.

    nonce       = 32 random bytes
    preimage    = "VV1" || 0x00 || electionId(32) || 0x00
                  || uint256(candidateChainIndex)(32) || 0x00 || nonce(32)
    commitment  = keccak256(preimage)   -> nonzero bytes32

`electionId` is the left-padded UUID bytes32 from `app.services.ids`;
`candidateChainIndex` is the candidate's immutable 0-based chain index. The
commitment commits the backend to the voter's choice without revealing it on
chain. It is NOT encryption and does not provide an independently verifiable
tally; see the decision record for the milestone-1 scope.
"""

from __future__ import annotations

import uuid
from secrets import token_bytes

from eth_utils import keccak

from app.services.ids import uuid_to_bytes32

VERSION_TAG = b"VV1"
SEPARATOR = b"\x00"


def make_ballot_commitment(
    election_id: uuid.UUID,
    candidate_chain_index: int,
    nonce: bytes | None = None,
) -> tuple[str, str]:
    """Return (commitment_hex, nonce_hex) — both lowercase hex, commitment 0x-prefixed."""
    if nonce is None:
        nonce = token_bytes(32)
    if len(nonce) != 32:
        raise ValueError("nonce must be exactly 32 bytes")
    preimage = (
        VERSION_TAG
        + SEPARATOR
        + uuid_to_bytes32(election_id)
        + SEPARATOR
        + candidate_chain_index.to_bytes(32, "big")
        + SEPARATOR
        + nonce
    )
    commitment = keccak(preimage)
    return "0x" + commitment.hex(), nonce.hex()


def commitment_preimage(
    election_id: uuid.UUID, candidate_chain_index: int, nonce: bytes
) -> bytes:
    """The exact preimage bytes; exposed for verification tooling and tests."""
    return (
        VERSION_TAG
        + SEPARATOR
        + uuid_to_bytes32(election_id)
        + SEPARATOR
        + candidate_chain_index.to_bytes(32, "big")
        + SEPARATOR
        + nonce
    )
