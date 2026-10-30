"""EVM event log matching, independent of web3 contract-event decoding.

Topics of the agreed BallotRegistry events (all non-anonymous):
    topic0 = keccak256("<EventName>(<types>)")
    topic1 = electionId, topic2 = ballotId (publish_ballot only),
    final topic = relayer address (not verified here), data = commitment/resultHash.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from eth_utils import keccak

# Solidity event signatures from docs/decisions/2026-10-30-blockchain-interface.md
EVENT_SIGNATURES: dict[str, str] = {
    "register_election": "ElectionRegistered(bytes32,bytes32,address)",
    "open_election": "ElectionOpened(bytes32,address)",
    "publish_ballot": "BallotPublished(bytes32,bytes32,bytes32,address)",
    "close_election": "ElectionClosed(bytes32,address)",
    "publish_result": "ResultPublished(bytes32,bytes32,address)",
}


@dataclass
class ChainLog:
    topics: list[bytes] = field(default_factory=list)
    data: bytes = b""


def event_topic0(signature: str) -> bytes:
    return keccak(text=signature)


def find_matching_event_log(
    logs: list[ChainLog],
    signature: str,
    expected_topics_after_signature: list[bytes],
    expected_data_word: bytes | None,
) -> ChainLog | None:
    """Find a log whose topics/data match the expected event arguments.

    `expected_topics_after_signature` are matched against the topics that
    follow topic0; `expected_data_word`, when given, must be the first
    32-byte word of the data field.
    """
    topic0 = event_topic0(signature)
    for log in logs:
        if len(log.topics) < 1 + len(expected_topics_after_signature):
            continue
        if log.topics[0] != topic0:
            continue
        if list(log.topics[1 : 1 + len(expected_topics_after_signature)]) != list(
            expected_topics_after_signature
        ):
            continue
        if expected_data_word is not None:
            if len(log.data) < 32 or log.data[:32] != expected_data_word:
                continue
        return log
    return None
