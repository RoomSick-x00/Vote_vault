"""Checkpoint 2: existing live HTTP API -> PostgreSQL jobs -> real Hardhat.

Requires a running Hardhat node, current deployment JSON, DATABASE_URL for a
local synthetic database, and the authorized local signer in process environment.
Uses the supported HS256 development auth mode; never outputs tokens or keys.
Run with the active virtualenv: python scripts/integrated_checkpoint.py
"""
from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

import httpx
import jwt
from eth_utils import keccak
from sqlalchemy import select
from web3 import Web3
from web3.logs import DISCARD

from app.blockchain.abi import BALLOT_REGISTRY_ABI
from app.blockchain.publisher import Web3RegistryPublisher, load_deployment
from app.db.session import create_engine_and_sessionmaker
from app.models import Ballot, PublicationJob

PORT = int(os.environ.get("CHECKPOINT_PORT", "8010"))
BASE = f"http://127.0.0.1:{PORT}"
REPORT_PATH = Path(os.environ.get("CHECKPOINT_REPORT", str(ROOT / "docs/checkpoint2-live-evidence.json")))
REPORT = {"scope": "live HTTP API + PostgreSQL + Hardhat; synthetic dev JWT users; backend demo tally only",
          "started_at": datetime.now(timezone.utc).isoformat(), "api": [], "chain": [], "failure_checks": []}
SECRET_VALUES = []


def clean(value):
    if isinstance(value, dict):
        return {k: "[REDACTED]" if k.lower() in {"nonce", "access_token", "refresh_token", "authorization", "private_key", "password"}
                else clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, bytes):
        return Web3.to_hex(value)
    if isinstance(value, str):
        for secret in SECRET_VALUES:
            if secret:
                value = value.replace(secret, "[REDACTED]")
    return value


def save_report():
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(clean(REPORT), indent=2) + "\n", encoding="utf-8")


def stage(name):
    REPORT["last_stage"] = name
    print(name, flush=True)


def request(method, path, headers, body=None, expected=200, record=True):
    response = httpx.request(method, BASE + path, headers=headers, json=body, timeout=15)
    data = response.json()
    if record:
        REPORT["api"].append({"method": method, "path": path, "status": response.status_code,
                              "request": clean(body), "response": clean(data)})
    if response.status_code != expected:
        raise AssertionError(f"{method} {path}: expected {expected}, got {response.status_code}: {clean(data)}")
    return data


def wait_jobs(election_id, kinds, headers):
    deadline = time.monotonic() + 60
    latest = None
    while time.monotonic() < deadline:
        latest = request("GET", f"/api/v1/elections/{election_id}/publications", headers, record=False)
        selected = [j for j in latest["publications"] if j["job_type"] in kinds]
        if any(j["status"] == "failed" for j in selected):
            raise AssertionError(f"Publication failed: {clean(latest)}")
        if {j["job_type"] for j in selected} == kinds and all(j["status"] == "confirmed" for j in selected):
            return request("GET", f"/api/v1/elections/{election_id}/publications", headers)
        time.sleep(0.25)
    raise TimeoutError(f"Jobs did not confirm: {clean(latest)}")


def padded(identifier):
    return "0x" + "00" * 16 + uuid.UUID(str(identifier)).hex


def verify_abi(manifest):
    signatures = []
    for expected in BALLOT_REGISTRY_ABI:
        actual = next(a for a in manifest["abi"] if a.get("name") == expected["name"] and a["type"] == expected["type"])
        actual_inputs = [(a["name"], a["type"], a.get("indexed")) for a in actual["inputs"]]
        expected_inputs = [(a["name"], a["type"], a.get("indexed")) for a in expected["inputs"]]
        assert actual_inputs == expected_inputs, (actual["name"], actual_inputs, expected_inputs)
        assert actual.get("stateMutability") == expected.get("stateMutability")
        signatures.append({"kind": actual["type"], "name": actual["name"], "inputs": actual["inputs"]})
    REPORT["abi_verified"] = signatures


def verify_transaction(w3, contract, tx_hash, event_name, expected):
    receipt = w3.eth.get_transaction_receipt(tx_hash)
    assert receipt.status == 1
    assert receipt.to.lower() == contract.address.lower()
    assert receipt.blockHash == w3.eth.get_block(receipt.blockNumber).hash
    events = getattr(contract.events, event_name)().process_receipt(receipt, errors=DISCARD)
    events = [e for e in events if e.address.lower() == contract.address.lower()]
    assert len(events) == 1
    args = {k: Web3.to_hex(v) if isinstance(v, bytes) else v for k, v in events[0].args.items()}
    assert set(args) == set(expected)
    assert all(str(args[k]).lower() == str(v).lower() for k, v in expected.items()), (args, expected)
    tx = w3.eth.get_transaction(tx_hash)
    assert tx["from"].lower() == expected["relayer"].lower()
    function, submitted = contract.decode_function_input(tx["input"])
    call_values = list(submitted.values())
    expected_values = [expected["electionId"]]
    if event_name == "ElectionRegistered": expected_values.append(expected["configHash"])
    if event_name == "BallotPublished": expected_values.extend([expected["ballotId"], expected["commitment"]])
    if event_name == "ResultPublished": expected_values.append(expected["resultHash"])
    assert [Web3.to_hex(v).lower() for v in call_values] == [v.lower() for v in expected_values]
    item = {"function": function.fn_name, "submitted_arguments": clean(submitted), "transaction_hash": Web3.to_hex(receipt.transactionHash), "receipt_status": receipt.status,
            "block_number": receipt.blockNumber, "block_hash": Web3.to_hex(receipt.blockHash),
            "contract_address": contract.address, "event": event_name, "expected": expected, "actual": args}
    REPORT["chain"].append(item)
    return item


def expect_revert(w3, contract, function, signer, label, error_signature):
    # Explicit gas bypasses estimation, so rejection is proven by an actual mined receipt.
    tx = function.build_transaction({"from": signer.address, "nonce": w3.eth.get_transaction_count(signer.address, "pending"),
                                     "gas": 400000, "gasPrice": w3.eth.gas_price, "chainId": 31337})
    signed = signer.sign_transaction(tx)
    result = w3.provider.make_request("eth_sendRawTransaction", [Web3.to_hex(signed.raw_transaction)])
    receipt = w3.eth.wait_for_transaction_receipt(signed.hash, timeout=15)
    assert receipt.status == 0 and len(receipt.logs) == 0
    replay = w3.provider.make_request("eth_call", [{"from": signer.address, "to": contract.address, "data": tx["data"]}, "latest"])
    error_data = replay.get("error", {}).get("data", "")
    if isinstance(error_data, dict):
        error_data = error_data.get("data", "")
    selector = Web3.to_hex(Web3.keccak(text=error_signature)[:4])
    assert str(error_data).startswith(selector), replay.get("error", {}).get("message")
    REPORT["failure_checks"].append({"test": label, "transaction_hash": Web3.to_hex(signed.hash),
                                    "receipt_status": receipt.status, "event_count": len(receipt.logs),
                                    "expected_error": error_signature, "error_selector": selector,
                                    "rpc_message": result.get("error", {}).get("message", "reverted receipt")})


def main():
    signer_key = os.environ.get("LOCAL_CHAIN_SIGNER_PRIVATE_KEY")
    database_url = os.environ.get("DATABASE_URL")
    if not signer_key or not database_url:
        raise RuntimeError("Set DATABASE_URL (isolated checkpoint DB) and LOCAL_CHAIN_SIGNER_PRIVATE_KEY in environment")
    SECRET_VALUES.extend([signer_key, database_url])
    secret = secrets.token_urlsafe(48)
    SECRET_VALUES.append(secret)
    with socket.socket() as sock:
        if sock.connect_ex(("127.0.0.1", PORT)) == 0:
            raise RuntimeError(f"Port {PORT} is already in use; choose CHECKPOINT_PORT")

    stage("Validate deployment and ABI")
    manifest_path = os.environ.get("BLOCKCHAIN_DEPLOYMENT_FILE", "blockchain/deployments/localhost.json")
    manifest = load_deployment(manifest_path)
    rpc = os.environ.get("BLOCKCHAIN_RPC_URL", "http://127.0.0.1:8545")
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 10}))
    assert w3.eth.chain_id == manifest["chainId"] == 31337
    assert Web3.to_hex(Web3.keccak(w3.eth.get_code(manifest["address"]))) == manifest["runtimeCodeHash"]
    deployment_receipt = w3.eth.get_transaction_receipt(manifest["transactionHash"])
    assert deployment_receipt.status == 1 and deployment_receipt.contractAddress.lower() == manifest["address"].lower()
    verify_abi(manifest)
    contract = w3.eth.contract(address=Web3.to_checksum_address(manifest["address"]), abi=manifest["abi"])
    signer = w3.eth.account.from_key(signer_key)
    assert signer.address.lower() == manifest["relayer"].lower()
    assert contract.functions.hasRole(contract.functions.RELAYER_ROLE().call(), signer.address).call()
    REPORT["deployment"] = {k: manifest[k] for k in ("chainId", "address", "relayer", "transactionHash", "blockNumber", "runtimeCodeHash")}
    REPORT["rpc_url"] = rpc
    REPORT["api_url"] = BASE

    stage("Apply Alembic migrations to the isolated database")
    from alembic import command
    from alembic.config import Config
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(cfg, "head")
    engine, sessions = create_engine_and_sessionmaker(database_url)
    REPORT["database"] = {"dialect": engine.dialect.name, "migrations": "upgrade head"}
    assert engine.dialect.name == "postgresql", "This checkpoint requires PostgreSQL"

    # Empty values override any .env Supabase settings so local JWTs remain local.
    env = {**os.environ, "DATABASE_URL": database_url, "SUPABASE_URL": "", "SUPABASE_JWKS_URL": "",
           "SUPABASE_ANON_KEY": "", "SUPABASE_JWT_SECRET": secret, "BLOCKCHAIN_RPC_URL": rpc,
           "BLOCKCHAIN_CHAIN_ID": "31337", "BLOCKCHAIN_DEPLOYMENT_FILE": manifest_path,
           "BALLOT_REGISTRY_CONTRACT_ADDRESS": manifest["address"], "LOCAL_CHAIN_SIGNER_PRIVATE_KEY": signer_key,
           "RUN_BACKGROUND_PUBLISHER": "true", "PUBLICATION_POLL_INTERVAL_SECONDS": "0.25",
           "PUBLICATION_RETRY_DELAY_SECONDS": "1"}
    log_dir = ROOT / ".local/checkpoint2"
    log_dir.mkdir(parents=True, exist_ok=True)
    server_command = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)]
    REPORT["backend_command"] = server_command
    stage("Start live Uvicorn API with its existing background worker")
    with (log_dir / "backend.log").open("w", encoding="utf-8") as log:
        server = subprocess.Popen(server_command, cwd=BACKEND_DIR, env=env, stdout=log, stderr=subprocess.STDOUT,
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if server.poll() is not None:
                    raise RuntimeError("Uvicorn exited during startup; inspect .local/checkpoint2/backend.log")
                try:
                    if httpx.get(BASE + "/", timeout=1).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.25)
            else:
                raise TimeoutError("Uvicorn did not start in 30 seconds")
            assert request("GET", "/", {})["publisher"] == "web3"
            def headers():
                now = datetime.now(timezone.utc)
                return {"Authorization": "Bearer " + jwt.encode({"sub": str(uuid.uuid4()), "role": "authenticated",
                        "iat": now, "exp": now + timedelta(hours=1)}, secret, algorithm="HS256")}
            org_headers, voter_headers, late_headers, outsider_headers = [headers() for _ in range(4)]
            def subject(h):
                return jwt.decode(h["Authorization"][7:], secret, algorithms=["HS256"])["sub"]
            stage("Create organization, election, candidates and eligible test voters via HTTP")
            org = request("POST", "/api/v1/organizations", org_headers, {"name": "Checkpoint 2 Club"}, 201)
            election = request("POST", "/api/v1/elections", org_headers,
                               {"organization_id": org["organization_id"], "title": "Live Chain Checkpoint"}, 201)
            eid = election["election_id"]
            base = f"/api/v1/elections/{eid}"
            candidates = request("POST", base + "/candidates", org_headers,
                                 {"candidates": [{"name": x} for x in ("Candidate A", "Candidate B", "Candidate C")]}, 201)["candidates"]
            request("POST", base + "/eligible-test-voters", org_headers,
                    {"user_ids": [subject(voter_headers), subject(late_headers)]}, 201)
            stage("Open via API; wait for worker registration and opening confirmations")
            request("POST", base + "/open", org_headers, {})
            wait_jobs(eid, {"register_election", "open_election"}, org_headers)
            configuration = request("GET", base + "/configuration", org_headers)
            assert "0x" + keccak(b"VV_CONFIG_1\x00" + configuration["canonical_json"].encode()).hex() == configuration["config_hash"]
            assert json.loads(configuration["canonical_json"]) == configuration["configuration"]

            stage("Submit one ballot and exercise duplicate/ineligible API requests")
            choice = {"candidate_id": candidates[0]["candidate_id"]}
            first = request("POST", base + "/ballots", voter_headers, choice, 202)
            retry = request("POST", base + "/ballots", voter_headers, choice, 202)
            assert retry["receipt_id"] == first["receipt_id"] and retry["idempotent_retry"]
            with ThreadPoolExecutor(max_workers=2) as pool:
                rapid = list(pool.map(lambda _: request("POST", base + "/ballots", voter_headers, choice, 202), range(2)))
            assert all(r["receipt_id"] == first["receipt_id"] and r["idempotent_retry"] for r in rapid)
            conflict = request("POST", base + "/ballots", voter_headers, {"candidate_id": candidates[1]["candidate_id"]}, 409)
            assert conflict["error"]["code"] == "DUPLICATE_VOTE"
            ineligible = request("POST", base + "/ballots", outsider_headers, choice, 403)
            assert ineligible["error"]["code"] == "NOT_ELIGIBLE"
            wait_jobs(eid, {"publish_ballot"}, org_headers)
            receipt = request("GET", base + "/receipts/" + first["receipt_id"], voter_headers)
            assert receipt["status"] == "confirmed"
            election_b32, ballot_b32 = padded(eid), padded(first["receipt_id"])
            REPORT["election_id"], REPORT["ballot_id"] = eid, first["receipt_id"]
            REPORT["chain_election_id"], REPORT["chain_ballot_id"] = election_b32, ballot_b32

            stage("Verify live on-chain identical retry, conflicting commitment and unauthorized signer")
            publisher = Web3RegistryPublisher(rpc, manifest["address"], signer_key, 31337,
                                              abi=manifest["abi"], expected_code_hash=manifest["runtimeCodeHash"], strict_deployment=True)
            tx = publisher.submit("publish_ballot", {"election_id": election_b32, "ballot_id": ballot_b32, "commitment": receipt["commitment"]})
            w3.eth.wait_for_transaction_receipt(tx, timeout=15)
            verify_transaction(w3, contract, tx, "BallotPublished", {"electionId": election_b32,
                               "ballotId": ballot_b32, "commitment": receipt["commitment"], "relayer": signer.address})
            assert contract.functions.getElection(election_b32).call()[3] == 1
            different = Web3.to_hex(keccak(text="checkpoint conflicting commitment"))
            expect_revert(w3, contract, contract.functions.publishBallot(election_b32, ballot_b32, different), signer,
                          "conflicting ballot commitment", "BallotAlreadyPublished(bytes32,bytes32)")
            stranger = w3.eth.account.create()
            # Hardhat-only funding, no signer key is written or printed.
            assert "result" in w3.provider.make_request("hardhat_setBalance", [stranger.address, hex(10**18)])
            expect_revert(w3, contract, contract.functions.openElection(election_b32), stranger,
                          "unauthorized signer", "AccessControlUnauthorizedAccount(address,bytes32)")

            stage("Close via API; wait for the worker to publish close and result")
            closing = request("POST", base + "/close", org_headers, {})
            assert closing["status"] == "closing" and closing["closed_at"] is None
            late = request("POST", base + "/ballots", late_headers, choice, 409)
            assert late["error"]["code"] == "ELECTION_CLOSED"
            publications = wait_jobs(eid, {"register_election", "open_election", "publish_ballot", "close_election", "publish_result"}, org_headers)
            final = request("GET", base, org_headers)
            assert final["status"] == "closed"
            results = request("GET", base + "/results", org_headers)
            assert [r["votes"] for r in results["counts"]] == [1, 0, 0]
            assert results["published_result_status"] == "confirmed"
            packed = bytes.fromhex(election_b32[2:]) + (1).to_bytes(32, "big")
            for row in sorted(results["counts"], key=lambda x: x["chain_index"]):
                packed += bytes.fromhex(padded(row["candidate_id"])[2:]) + row["votes"].to_bytes(32, "big")
            result_hash = Web3.to_hex(keccak(packed))

            stage("Compare database jobs with each independent transaction receipt and decoded event")
            event_names = {"register_election": "ElectionRegistered", "open_election": "ElectionOpened",
                           "publish_ballot": "BallotPublished", "close_election": "ElectionClosed", "publish_result": "ResultPublished"}
            with sessions() as db:
                ballots = db.scalars(select(Ballot).where(Ballot.election_id == uuid.UUID(eid), Ballot.accepted.is_(True))).all()
                jobs = db.scalars(select(PublicationJob).where(PublicationJob.election_id == uuid.UUID(eid)).order_by(PublicationJob.created_at)).all()
                assert len(ballots) == 1 and str(ballots[0].id) == first["receipt_id"]
                assert ballots[0].commitment == receipt["commitment"]
                assert len(jobs) == 5 and all(j.status == "confirmed" for j in jobs)
                ordered_blocks = []
                evidence_jobs = []
                for kind in ("register_election", "open_election", "publish_ballot", "close_election", "publish_result"):
                    job = next(j for j in jobs if j.job_type == kind)
                    expected = {"electionId": election_b32, "relayer": signer.address}
                    if kind == "register_election": expected["configHash"] = configuration["config_hash"]
                    if kind == "publish_ballot": expected.update(ballotId=ballot_b32, commitment=receipt["commitment"])
                    if kind == "publish_result": expected["resultHash"] = result_hash
                    assert job.payload["election_id"] == election_b32
                    if kind == "register_election": assert job.payload["config_hash"] == expected["configHash"]
                    if kind == "publish_ballot":
                        assert job.payload["ballot_id"] == ballot_b32 and job.payload["commitment"] == receipt["commitment"]
                    if kind == "publish_result": assert job.payload["result_hash"] == result_hash
                    checked = verify_transaction(w3, contract, job.tx_hash, event_names[kind], expected)
                    assert checked["block_number"] == job.block_number
                    ordered_blocks.append(job.block_number)
                    evidence_jobs.append({"job_id": str(job.id), "job_type": kind, "status": job.status,
                                          "attempts": job.attempts, "transaction_hash": job.tx_hash,
                                          "block_number": job.block_number, "payload": job.payload, "last_error": job.last_error})
                assert ordered_blocks == sorted(set(ordered_blocks))
                REPORT["database_jobs"] = evidence_jobs
                REPORT["accepted_database_ballots"] = 1
            chain_state = contract.functions.getElection(election_b32).call()
            assert chain_state[0] == 3 and chain_state[3] == 1
            assert Web3.to_hex(chain_state[1]) == configuration["config_hash"]
            assert Web3.to_hex(chain_state[2]) == result_hash
            assert Web3.to_hex(contract.functions.ballotCommitments(election_b32, ballot_b32).call()) == receipt["commitment"]
            logs = contract.events.BallotPublished().get_logs(from_block=manifest["blockNumber"], argument_filters={"electionId": election_b32})
            assert len(logs) == 2 and {Web3.to_hex(l.args.ballotId) for l in logs} == {ballot_b32}
            REPORT["getElection"] = {"state": "Closed", "state_number": 3, "configurationCommitment": Web3.to_hex(chain_state[1]),
                                     "resultCommitment": Web3.to_hex(chain_state[2]), "ballotCount": chain_state[3]}
            REPORT["result_hash_recomputed"] = result_hash
            REPORT["ballot_event_count"] = len(logs)
            REPORT["unique_ballot_ids"] = 1
            REPORT["job_summary"] = publications["summary"]
            REPORT["passed"] = True
            REPORT["completed_at"] = datetime.now(timezone.utc).isoformat()
            save_report()
            print(f"PASS: five confirmed backend jobs; one accepted ballot; evidence: {REPORT_PATH}", flush=True)
            return 0
        finally:
            # Only stop the API subprocess this script owns; keep the chain/database for inspection.
            server.terminate()
            try: server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
            engine.dispose()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        REPORT["passed"] = False
        REPORT["error"] = clean(f"{type(exc).__name__}: {exc}")
        save_report()
        print(REPORT["error"], file=sys.stderr)
        raise SystemExit(1)
