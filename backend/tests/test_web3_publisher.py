"""End-to-end Web3 publisher test against a real EVM (py-evm via eth-tester).

A minimal hand-assembled stub contract plays BallotRegistry: on any call it
emits the five agreed events with the call's arguments. The test then runs the
REAL production path — account signing, raw transaction submission, receipt
wait, event verification — through the public API and the publication service,
so everything except the JSON-RPC transport is production code.
"""

from __future__ import annotations

import secrets

import pytest

pytest.importorskip("eth_tester")

from eth_tester import EthereumTester  # noqa: E402
from web3 import Web3  # noqa: E402
from web3.providers import EthereumTesterProvider  # noqa: E402

from app.blockchain.publisher import Web3RegistryPublisher  # noqa: E402
from evm_stub import deploy_init as _deploy_init, stub_runtime as _stub_runtime  # noqa: E402
from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from helpers import (  # noqa: E402
    ORGANIZER,
    TEST_JWT_SECRET,
    auth,
    build_open_election,
    close_election,
    process_publications,
    vote,
)

@pytest.fixture(scope="module")
def evm_env():
    w3 = Web3(EthereumTesterProvider(EthereumTester()))
    relayer = w3.eth.account.from_key("0x" + secrets.token_hex(32))
    w3.eth.send_transaction(
        {
            "from": w3.eth.accounts[0],
            "to": relayer.address,
            "value": w3.to_wei(10, "ether"),
            "gas": 21_000,
            "gasPrice": w3.eth.gas_price,
        }
    )
    runtime = _stub_runtime()
    deploy_tx = relayer.sign_transaction(
        {
            "from": relayer.address,
            "data": _deploy_init(runtime),
            "nonce": 0,
            "gas": 200_000,
            "gasPrice": w3.eth.gas_price,
            "chainId": w3.eth.chain_id,
        }
    )
    raw = getattr(deploy_tx, "raw_transaction", None) or deploy_tx.rawTransaction
    tx_hash = w3.eth.send_raw_transaction(raw)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    assert receipt["status"] == 1, "stub contract deployment reverted"
    assert receipt["contractAddress"], "no contract address in deploy receipt"
    return w3, relayer, receipt["contractAddress"]


def _make_publisher(evm_env) -> Web3RegistryPublisher:
    w3, relayer, contract_address = evm_env
    return Web3RegistryPublisher(
        rpc_url="in-process://eth-tester",
        contract_address=contract_address,
        signer_private_key="0x" + relayer.key.hex(),
        chain_id=w3.eth.chain_id,
        w3=w3,
    )


def test_web3_publisher_publishes_and_verifies_through_full_api(
    client, database_url, sessionmaker_, evm_env
):
    w3, relayer, _ = evm_env
    settings = Settings(
        database_url=database_url,
        supabase_jwt_secret=TEST_JWT_SECRET,
        run_background_publisher=False,
    )
    app = create_app(settings=settings, publisher=_make_publisher(evm_env), run_background_publisher=False)

    from fastapi.testclient import TestClient

    api = TestClient(app)

    setup = build_open_election(api)
    election_id = setup["election_id"]
    b1 = vote(api, election_id, setup["candidates"][0]["candidate_id"], setup["token_for"]("R001"))
    b2 = vote(api, election_id, setup["candidates"][2]["candidate_id"], setup["token_for"]("R002"))
    assert b1.status_code == 202 and b2.status_code == 202
    close_election(api, election_id)

    summary = process_publications(app)
    assert summary == {"confirmed": 6, "retry_scheduled": 0, "failed": 0}, summary

    for roll_no, cast in (("R001", b1), ("R002", b2)):
        receipt = api.get(
            f"/api/v1/elections/{election_id}/receipts/{cast.json()['receipt_id']}",
            headers={"Authorization": f"Bearer {setup['token_for'](roll_no)}"},
        ).json()
        assert receipt["status"] == "confirmed"
        assert receipt["transaction_hash"].startswith("0x")
        assert receipt["block_number"] >= 1
        # transaction was actually sent by the relayer from the app's publisher
        chain_receipt = w3.eth.get_transaction_receipt(receipt["transaction_hash"])
        assert chain_receipt["from"].lower() == relayer.address.lower()
        assert chain_receipt["status"] == 1

    pubs = api.get(f"/api/v1/elections/{election_id}/publications", headers=auth(ORGANIZER)).json()
    assert pubs["summary"] == {"pending": 0, "confirmed": 6, "failed": 0}
    assert all(job["last_error"] is None for job in pubs["publications"])

    results = api.get(f"/api/v1/elections/{election_id}/results", headers=auth(ORGANIZER)).json()
    assert results["published_result_status"] == "confirmed"
    assert results["total_ballots"] == 2


def test_web3_publisher_detects_chain_id_mismatch(evm_env):
    w3, _, contract_address = evm_env
    publisher = Web3RegistryPublisher(
        rpc_url="in-process://eth-tester",
        contract_address=contract_address,
        signer_private_key="0x" + "1" * 64,
        chain_id=w3.eth.chain_id + 1,
        w3=w3,
    )
    from app.blockchain.publisher import ChainError

    with pytest.raises(ChainError, match="chain id mismatch"):
        publisher.submit("publish_ballot", {"election_id": "0x" + "0" * 64, "ballot_id": "0x" + "0" * 64, "commitment": "0x" + "0" * 64})
