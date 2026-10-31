"""Independently recount a synthetic election against a pinned registry.

Only third-party dependencies are web3 and eth-utils. No application imports,
database credentials, or results API are required. See docs/SECURITY-REVIEW.md.
"""
import argparse
import json
import sys
import uuid
from collections import Counter

from eth_utils import keccak
from web3 import Web3

ABI = [
    {"type": "function", "name": "getElection", "stateMutability": "view", "inputs": [{"name": "electionId", "type": "bytes32"}], "outputs": [{"type": "uint8"}, {"type": "bytes32"}, {"type": "bytes32"}, {"type": "uint256"}]},
    {"type": "function", "name": "ballotCommitments", "stateMutability": "view", "inputs": [{"type": "bytes32"}, {"type": "bytes32"}], "outputs": [{"type": "bytes32"}]},
]


def word(value):
    return bytes(16) + uuid.UUID(value).bytes


def verify(record, registry, receipt=None):
    """Raise ValueError on inconsistency; registry is a pinned contract instance."""
    eid = word(record["election_id"])
    config = record["configuration"]
    if config["version"] != "VV_CONFIG_1" or config["election_id"] != "0x" + eid.hex():
        raise ValueError("configuration election or version mismatch")
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    state, config_hash, result_hash, count = registry.functions.getElection(eid).call()
    if state != 3 or bytes(result_hash) == bytes(32):
        raise RuntimeError("election is not closed with a published result")
    if keccak(b"VV_CONFIG_1\x00" + canonical) != bytes(config_hash):
        raise ValueError("configuration does not match chain")
    candidates = config["candidates"]
    ids = [c["candidate_id"] for c in candidates]
    indices = [c["chain_index"] for c in candidates]
    if len(set(ids)) != len(ids) or indices != list(range(len(indices))) or not ids:
        raise ValueError("invalid candidate configuration")
    ballots = record["ballot_openings"]
    if len(ballots) != count:
        raise ValueError("ballot count differs from chain")
    seen = set()
    counts = Counter()
    for ballot in ballots:
        bid = word(ballot["ballot_id"])
        if bid in seen:
            raise ValueError("duplicate ballot ID")
        seen.add(bid)
        index = ballot["candidate_chain_index"]
        if type(index) is not int or index not in indices:
            raise ValueError("invalid candidate index")
        nonce = bytes.fromhex(ballot["nonce"])
        if len(nonce) != 32:
            raise ValueError("invalid nonce")
        commitment = keccak(b"VV1\x00" + eid + b"\x00" + index.to_bytes(32, "big") + b"\x00" + nonce)
        if bytes(registry.functions.ballotCommitments(eid, bid).call()) != commitment:
            raise ValueError("ballot opening does not match chain")
        counts[index] += 1
    if receipt is not None and word(receipt) not in seen:
        raise ValueError("receipt is not in verified ballot set")
    announced = record["result"]
    expected = [(c["candidate_id"], counts[c["chain_index"]]) for c in candidates]
    rows = [(r["candidate_id"], r["votes"]) for r in announced["counts"]]
    if rows != expected or announced["total_ballots"] != len(ballots):
        raise ValueError("announced result does not match ballot recount")
    packed = eid + len(ballots).to_bytes(32, "big")
    for candidate_id, votes in expected:
        packed += word(candidate_id) + votes.to_bytes(32, "big")
    if keccak(packed) != bytes(result_hash):
        raise ValueError("recount does not match chain result commitment")
    return {"ballots": len(ballots), "counts": dict(expected), "receipt_found": receipt is not None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", help="JSON record containing synthetic ballot openings")
    parser.add_argument("--rpc", required=True, help="independently trusted RPC endpoint")
    parser.add_argument("--chain-id", required=True, type=int)
    parser.add_argument("--contract", required=True, help="independently obtained registry address")
    parser.add_argument("--code-hash", required=True, help="independently obtained runtime code keccak256")
    parser.add_argument("--receipt", help="optional ballot receipt UUID")
    args = parser.parse_args()
    try:
        with open(args.record, encoding="utf-8") as handle:
            record = json.load(handle)
        w3 = Web3(Web3.HTTPProvider(args.rpc, request_kwargs={"timeout": 10}))
        if w3.eth.chain_id != args.chain_id:
            raise RuntimeError("RPC chain ID mismatch")
        address = Web3.to_checksum_address(args.contract)
        code = w3.eth.get_code(address)
        if not code or ("0x" + keccak(code).hex()).lower() != args.code_hash.lower():
            raise RuntimeError("registry code does not match pinned hash")
        result = verify(record, w3.eth.contract(address=address, abi=ABI), args.receipt)
    except (ValueError, KeyError, TypeError, OverflowError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"INCOMPLETE: {exc}", file=sys.stderr)
        return 2
    print("PASS: " + json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
