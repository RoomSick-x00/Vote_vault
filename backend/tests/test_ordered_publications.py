import json
import os
import uuid
from pathlib import Path
import pytest
from eth_utils import keccak
from helpers import (ORGANIZER, OUTSIDER, auth,
                     build_open_election, close_election, vote, process_publications)


def test_configuration_is_public_reproducible_and_frozen(client, app):
    setup = build_open_election(client)
    url = f"/api/v1/elections/{setup['election_id']}/configuration"
    data = client.get(url, headers=auth(ORGANIZER)).json()
    assert len(data["configuration"]["candidates"]) == 3
    assert data["config_hash"] == "0x" + keccak(b"VV_CONFIG_1\x00" + data["canonical_json"].encode()).hex()
    assert json.loads(data["canonical_json"]) == data["configuration"]
    assert "voter" not in data["configuration"]
    process_publications(app)
    assert client.get(url, headers=auth(ORGANIZER)).json() == data


def test_failed_ballot_blocks_close_and_result_until_recovered(client, app, fake_publisher):
    setup = build_open_election(client)
    assert vote(client, setup["election_id"], setup["candidates"][0]["candidate_id"], setup["token_for"]("R001")).status_code == 202
    late_voter_token = setup["token_for"]("R002")  # session minted while open
    close_election(client, setup["election_id"])
    fake_publisher.script_next("ok", times=2)
    fake_publisher.script_next("raise", "ballot publication unavailable", times=3)
    for _ in range(3): process_publications(app)
    assert not any(kind in ("close_election", "publish_result") for kind, _ in fake_publisher.submit_calls)
    url = f"/api/v1/elections/{setup['election_id']}"
    assert client.get(url, headers=auth(ORGANIZER)).json()["status"] == "closing"
    assert vote(client, setup["election_id"], setup["candidates"][0]["candidate_id"], late_voter_token).status_code == 409
    assert client.post(url + "/publications/retry", headers=auth(ORGANIZER)).status_code == 200
    process_publications(app)
    assert client.get(url, headers=auth(ORGANIZER)).json()["status"] == "closed"
    assert [kind for kind, _ in fake_publisher.submit_calls][-3:] == ["publish_ballot", "close_election", "publish_result"]


@pytest.mark.skipif(not os.environ.get("LOCAL_CHAIN_SIGNER_PRIVATE_KEY"), reason="requires real Hardhat environment")
def test_api_database_hardhat_checkpoint(client, app):
    from app.blockchain.publisher import Web3RegistryPublisher
    from app.services.ids import uuid_to_bytes32_hex
    from app.models import PublicationJob
    from sqlalchemy import select
    from web3 import Web3
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / "blockchain/deployments/localhost.json").read_text())
    publisher = Web3RegistryPublisher(os.environ["BLOCKCHAIN_RPC_URL"], manifest["address"],
                                     os.environ["LOCAL_CHAIN_SIGNER_PRIVATE_KEY"], 31337)
    app.state.publisher = publisher
    setup = build_open_election(client)
    eid = setup["election_id"]
    chain_id = uuid_to_bytes32_hex(uuid.UUID(eid))
    receipts = []
    for roll_no, index in [("R001", 0), ("R002", 0), ("R003", 1)]:
        response = vote(client, eid, setup["candidates"][index]["candidate_id"], setup["token_for"](roll_no))
        assert response.status_code == 202, response.text
        receipts.append(response.json())
    assert vote(client, eid, setup["candidates"][1]["candidate_id"], setup["token_for"]("R001")).status_code == 409
    assert vote(client, eid, setup["candidates"][0]["candidate_id"], auth(OUTSIDER)["Authorization"].split(" ", 1)[1]).status_code == 401
    assert process_publications(app)["confirmed"] == 5
    # Simulate a lost response by submitting the same durable ballot job anew.
    with app.state.sessionmaker() as db:
        ballot_job = db.scalars(select(PublicationJob).where(PublicationJob.job_type == "publish_ballot")).first()
        tx = publisher.submit(ballot_job.job_type, ballot_job.payload)
        from app.services.publication_service import _verify_receipt
        _verify_receipt(ballot_job, publisher.fetch_receipt(tx, 10, 1))
    assert close_election(client, eid)["status"] == "closing"
    assert process_publications(app)["confirmed"] == 2
    result = client.get(f"/api/v1/elections/{eid}/results", headers=auth(ORGANIZER)).json()
    assert [row["votes"] for row in result["counts"]] == [2, 1, 0]
    assert result["published_result_status"] == "confirmed"
    # Independent ABI/address read, rather than trusting API receipt status.
    w3 = Web3(Web3.HTTPProvider(os.environ["BLOCKCHAIN_RPC_URL"]))
    registry = w3.eth.contract(address=manifest["address"], abi=manifest["abi"])
    logs = registry.events.BallotPublished().get_logs(from_block=manifest["blockNumber"], argument_filters={"electionId": chain_id})
    unique = {Web3.to_hex(log.args.ballotId): Web3.to_hex(log.args.commitment) for log in logs}
    assert len(logs) == 4 and len(unique) == 3
    with app.state.sessionmaker() as db:
        jobs = db.scalars(select(PublicationJob).where(PublicationJob.election_id == uuid.UUID(eid))).all()
        for job in jobs:
            assert job.status == "confirmed"
            if job.job_type == "publish_ballot":
                assert unique[job.payload["ballot_id"]] == job.payload["commitment"]
            elif job.job_type == "register_election":
                config_events = registry.events.ElectionRegistered().get_logs(from_block=manifest["blockNumber"], argument_filters={"electionId": chain_id})
                assert len(config_events) == 1
                assert Web3.to_hex(config_events[0].args.configHash) == job.payload["config_hash"]
                assert Web3.to_hex(config_events[0].transactionHash) == job.tx_hash
            elif job.job_type == "publish_result":
                result_events = registry.events.ResultPublished().get_logs(from_block=manifest["blockNumber"], argument_filters={"electionId": chain_id})
                assert len(result_events) == 1
                assert Web3.to_hex(result_events[0].args.resultHash) == job.payload["result_hash"]
                assert Web3.to_hex(result_events[0].transactionHash) == job.tx_hash
        evidence = [{"type": j.job_type, "transaction_hash": j.tx_hash, "payload": j.payload, "status": j.status} for j in jobs]
    assert registry.functions.getElection(chain_id).call()[3] == 3
    (root / "docs/integrated-chain-evidence.json").write_text(json.dumps({
        "scope": "FastAPI TestClient + migrated test database + real Hardhat; synthetic JWTs; no UI",
        "database_dialect": app.state.sessionmaker.kw["bind"].dialect.name,
        "address": manifest["address"], "chainId": 31337, "tally": [2, 1, 0],
        "ballot_events": len(logs), "unique_ballots": len(unique), "jobs": evidence}, indent=2) + "\n")
