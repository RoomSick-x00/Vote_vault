"""Real local Hardhat integration; requires deployed registry and signer env.

This is a synthetic service harness, not a FastAPI/frontend/database checkpoint.
"""
import json
import os
import secrets
from pathlib import Path
import pytest
from web3 import Web3
from app.services.chain_registry import Registry, bytes32

ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "blockchain/deployments/localhost"


def _chain_ready() -> bool:
    """The checkpoint needs a live Hardhat node plus the deployment env vars;
    in environments without them, skip instead of failing the whole suite."""
    try:
        Registry.from_env(DEPLOYMENT)
        return True
    except Exception:
        return False


@pytest.mark.skipif(
    not _chain_ready(),
    reason="requires a running Hardhat node with the deployed ElectionRegistry "
    "and BALLOT_REGISTRY_CONTRACT_ADDRESS / BLOCKCHAIN_RPC_URL / "
    "LOCAL_CHAIN_SIGNER_PRIVATE_KEY / BLOCKCHAIN_CHAIN_ID set (start the node, "
    "then run: pytest tests/test_chain_checkpoint.py -v)",
)
def test_real_chain_checkpoint():
    registry = Registry.from_env(DEPLOYMENT)
    manifest = json.loads((DEPLOYMENT / "deployment.json").read_text())
    new_id = lambda: "0x" + secrets.token_hex(32)
    election, ballot, config, commitment, result = [new_id() for _ in range(5)]
    evidence = []

    def publish(fn, args, event, expected):
        # Sequential harness only. Real workers need durable jobs and nonce locking.
        prepared = registry.prepare(fn, *args, nonce=registry.w3.eth.get_transaction_count(registry.account.address, "pending"))
        assert registry.receipt_status(prepared["transaction_hash"], event, expected)["status"] == "pending"
        registry.broadcast(prepared)
        registry.w3.eth.wait_for_transaction_receipt(prepared["transaction_hash"], timeout=30)
        status = registry.receipt_status(prepared["transaction_hash"], event, expected)
        assert status["status"] == "confirmed"
        evidence.append({"operation": fn, "expected": expected, "receipt": status})
        return prepared, status

    publish("registerElection", [election, config], "ElectionRegistered", {"electionId": election, "configurationCommitment": config})
    publish("openElection", [election], "ElectionOpened", {"electionId": election})
    job, confirmed = publish("publishBallot", [election, ballot, commitment], "BallotPublished",
                             {"electionId": election, "ballotId": ballot, "commitment": commitment})
    # Simulate worker crash after broadcast but before saving success; reconcile retry.
    recovered = registry.reconcile_ballot(election, ballot, commitment, manifest["blockNumber"])
    assert recovered == confirmed
    assert registry.contract.functions.getElection(election).call()[3] == 1
    assert len(registry.contract.events.BallotPublished().get_logs(from_block=manifest["blockNumber"],
               argument_filters={"electionId": election, "ballotId": ballot})) == 1
    with pytest.raises(ValueError, match="different commitment"):
        registry.reconcile_ballot(election, ballot, result)
    # Even a new transaction with same ballot ID cannot publish twice.
    with pytest.raises(Exception, match="revert"):
        registry.prepare("publishBallot", election, ballot, commitment,
                         nonce=registry.w3.eth.get_transaction_count(registry.account.address, "pending"))
    wrong = registry.receipt_status(job["transaction_hash"], "BallotPublished",
                                   {"electionId": election, "ballotId": ballot, "commitment": result})
    assert wrong["status"] == "failed" and wrong["reason"] == "expected_event_missing"
    publish("closeElection", [election], "ElectionClosed", {"electionId": election})
    assert registry.reconcile_ballot(election, ballot, commitment)["status"] == "confirmed"
    publish("publishResult", [election, result], "ResultPublished", {"electionId": election, "commitment": result})
    state, stored_config, stored_result, count = registry.contract.functions.getElection(election).call()
    assert [state, Web3.to_hex(stored_config), Web3.to_hex(stored_result), count] == [3, config, result, 1]
    report = {"scope": "synthetic Web3.py service harness against real Hardhat; no HTTP/frontend/DB", "chainId": 31337,
              "contractAddress": manifest["address"], "lostResponseRetry": "reconciled; one ballot event and count=1", "steps": evidence}
    output = ROOT / "docs/checkpoint-evidence.json"
    output.write_text(json.dumps(report, indent=2) + "\n")


def test_bytes32_validation():
    for bad in ["0x" + "00" * 32, "1", "0x12", None, "0x" + "zz" * 32]:
        with pytest.raises(ValueError): bytes32(bad)
    assert bytes32("0x" + "AB" * 32) == "0x" + "ab" * 32
