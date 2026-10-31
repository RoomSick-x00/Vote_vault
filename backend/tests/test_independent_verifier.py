import copy
import json
import uuid
from types import SimpleNamespace

import pytest
from eth_utils import keccak
from scripts.verify_election import verify, word


class Call:
    def __init__(self, value): self.value = value
    def call(self): return self.value


def sample():
    election, candidate, ballot = (str(uuid.uuid4()) for _ in range(3))
    eid = word(election)
    config = {"version": "VV_CONFIG_1", "election_id": "0x" + eid.hex(), "candidates": [
        {"candidate_id": candidate, "chain_index": 0, "name": "Synthetic"}]}
    config_hash = keccak(b"VV_CONFIG_1\x00" + json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())
    nonce = bytes(range(32))
    commitment = keccak(b"VV1\x00" + eid + b"\x00" + bytes(32) + b"\x00" + nonce)
    result_hash = keccak(eid + (1).to_bytes(32, "big") + word(candidate) + (1).to_bytes(32, "big"))
    record = {"election_id": election, "configuration": config, "ballot_openings": [
        {"ballot_id": ballot, "candidate_chain_index": 0, "nonce": nonce.hex()}],
        "result": {"total_ballots": 1, "counts": [{"candidate_id": candidate, "votes": 1}]}}
    functions = SimpleNamespace(getElection=lambda _: Call((3, config_hash, result_hash, 1)),
        ballotCommitments=lambda _, bid: Call(commitment if bid == word(ballot) else bytes(32)))
    return record, SimpleNamespace(functions=functions), ballot


def test_recount_and_attacks():
    record, chain, receipt = sample()
    assert verify(record, chain, receipt)["receipt_found"]
    deletion = copy.deepcopy(record); deletion["ballot_openings"].clear()
    insertion = copy.deepcopy(record); insertion["ballot_openings"].append(copy.deepcopy(insertion["ballot_openings"][0]))
    modification = copy.deepcopy(record); modification["ballot_openings"][0]["nonce"] = "ff" * 32
    substitution = copy.deepcopy(record); substitution["ballot_openings"][0]["ballot_id"] = str(uuid.uuid4())
    tally = copy.deepcopy(record); tally["result"]["counts"][0]["votes"] = 2
    configuration = copy.deepcopy(record); configuration["configuration"]["candidates"][0]["name"] = "Changed"
    for altered in (deletion, insertion, modification, substitution, tally, configuration):
        with pytest.raises(ValueError): verify(altered, chain)
    with pytest.raises(ValueError): verify(record, chain, str(uuid.uuid4()))

    # Even an operator who anchors the hash of a false result cannot make
    # that result match the independently opened, already-anchored ballots.
    state, config_hash, _, count = chain.functions.getElection(None).call()
    candidate = record["configuration"]["candidates"][0]["candidate_id"]
    false_hash = keccak(word(record["election_id"]) + (2).to_bytes(32, "big") + word(candidate) + (2).to_bytes(32, "big"))
    dishonest_chain = SimpleNamespace(functions=SimpleNamespace(
        getElection=lambda _: Call((state, config_hash, false_hash, count)),
        ballotCommitments=chain.functions.ballotCommitments))
    tally["result"]["total_ballots"] = 2
    with pytest.raises(ValueError, match="recount"): verify(tally, dishonest_chain)
