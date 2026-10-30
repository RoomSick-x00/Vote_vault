"""Hand-assembled EVM stub contract standing in for the BallotRegistry.

On ANY call it emits all five agreed events built from the call's calldata, so
tests and the demo exercise the real publisher path (signing, raw tx, receipt,
event-argument verification) without a Solidity toolchain. Used by
tests/test_web3_publisher.py and scripts/demo.py.
"""

from __future__ import annotations

from eth_utils import keccak

from app.eth_events import EVENT_SIGNATURES, event_topic0

PUSH1, PUSH32 = b"\x60", b"\x7f"
CALLDATACOPY, MLOAD = b"\x37", b"\x51"
LOG2, LOG3, CODECOPY, RETURN, STOP = b"\xa2", b"\xa3", b"\x39", b"\xf3", b"\x00"


def _push1(n: int) -> bytes:
    return PUSH1 + bytes([n])


def _calldata_copy(dest: int, offset: int, length: int) -> bytes:
    return _push1(length) + _push1(offset) + _push1(dest) + CALLDATACOPY


def stub_runtime() -> bytes:
    """Emit all five agreed events from the call's calldata.

    mem[0:32]=electionId (cd 4:36), mem[32:64]=word1 (cd 36:68: ballotId or
    resultHash), mem[64:96]=word2 (cd 68:100: commitment).
    """
    code = _calldata_copy(0, 4, 32) + _calldata_copy(0x20, 0x24, 32) + _calldata_copy(0x40, 0x44, 32)
    # 2-topic events (ElectionRegistered/Opened/Closed): data ignored by verifier
    for signature in (
        EVENT_SIGNATURES["register_election"],
        EVENT_SIGNATURES["open_election"],
        EVENT_SIGNATURES["close_election"],
    ):
        code += _push1(0) + MLOAD  # topic1 = electionId
        code += PUSH32 + event_topic0(signature)
        code += (_push1(32) + _push1(32) if signature == EVENT_SIGNATURES["register_election"] else _push1(0) + _push1(0)) + LOG2
    # BallotPublished: topic2 = word1, data = word2 (commitment)
    code += _push1(0x20) + MLOAD  # topic2 = word1 (ballotId)
    code += _push1(0) + MLOAD + PUSH32 + event_topic0(EVENT_SIGNATURES["publish_ballot"])
    code += _push1(0x20) + _push1(0x40) + LOG3  # offset 64, size 32 -> commitment
    # ResultPublished: topic2 = relayer stand-in, data = word1 (resultHash)
    code += _push1(0x20) + MLOAD
    code += _push1(0) + MLOAD + PUSH32 + event_topic0(EVENT_SIGNATURES["publish_result"])
    code += _push1(0x20) + _push1(0x20) + LOG3  # offset 32, size 32 -> word1
    return code + STOP


def deploy_init(runtime: bytes) -> bytes:
    """Constructor that returns `runtime` as the deployed code.

    12-byte preamble, then the runtime bytes at offset 12 (where CODECOPY reads).
    """
    return (
        _push1(len(runtime)) + _push1(12) + _push1(0) + CODECOPY
        + _push1(len(runtime)) + _push1(0) + RETURN
        + runtime
    )


def keccak_topic(signature: str) -> bytes:
    return keccak(text=signature)
