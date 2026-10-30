"""Fixed encoding vectors for the agreed commitment and ID schemes."""

from __future__ import annotations

import uuid

from eth_utils import keccak

from app.services.commitment import commitment_preimage, make_ballot_commitment
from app.services.ids import uuid_to_bytes32, uuid_to_bytes32_hex


def test_uuid_left_padded_to_bytes32():
    u = uuid.UUID("12345678-1234-4234-8234-123456781234")
    b32 = uuid_to_bytes32(u)
    assert len(b32) == 32
    assert b32[:16] == b"\x00" * 16          # left padding
    assert b32[16:] == u.bytes               # big-endian UUID bytes
    assert uuid_to_bytes32_hex(u) == "0x" + b32.hex()
    # matches Solidity bytes32(uint256(uint128(bytes16(uuid))))
    assert int.from_bytes(b32, "big") == u.int


def test_commitment_encoding_vector():
    election_id = uuid.UUID("aaaaaaaa-bbbb-4bbb-8bbb-cccccccccccc")
    nonce = bytes(range(32))
    chain_index = 2

    commitment_hex, nonce_hex = make_ballot_commitment(election_id, chain_index, nonce)

    expected_preimage = (
        b"VV1"
        + b"\x00"
        + uuid_to_bytes32(election_id)
        + b"\x00"
        + (2).to_bytes(32, "big")
        + b"\x00"
        + nonce
    )
    assert commitment_preimage(election_id, chain_index, nonce) == expected_preimage
    assert commitment_hex == "0x" + keccak(expected_preimage).hex()
    assert nonce_hex == nonce.hex()
    assert int(commitment_hex, 16) != 0  # nonzero bytes32 per the interface agreement


def test_commitment_changes_with_every_component():
    election = uuid.uuid4()
    nonce_a, nonce_b = b"\x01" * 32, b"\x02" * 32
    c1, _ = make_ballot_commitment(election, 0, nonce_a)
    c2, _ = make_ballot_commitment(election, 1, nonce_a)  # different candidate
    c3, _ = make_ballot_commitment(election, 0, nonce_b)  # different nonce
    c4, _ = make_ballot_commitment(uuid.uuid4(), 0, nonce_a)  # different election
    assert len({c1, c2, c3, c4}) == 4


def test_random_nonce_is_32_bytes_and_unique():
    election = uuid.uuid4()
    c_a, n_a = make_ballot_commitment(election, 0)
    c_b, n_b = make_ballot_commitment(election, 0)
    assert len(bytes.fromhex(n_a)) == 32
    assert n_a != n_b and c_a != c_b
