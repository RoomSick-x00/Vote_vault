"""Checkpoint 2: one complete election from API request through on-chain event.

Runs the REAL backend (uvicorn subprocess) against the REAL deployed
ElectionRegistry on a local Hardhat node (chain 31337), with the publisher
wired to blockchain/deployments/localhost.json (address + ABI + runtimeCodeHash
+ RELAYER_ROLE validation), then independently verifies the chain state with
web3. Signup/login need the team's Supabase project, so this run mints dev
HS256 organizer/voter tokens instead — identity verification is unchanged.

Prerequisites:
  npx hardhat node                                   # terminal 1
  npx hardhat run scripts/deploy.js --network localhost
  export LOCAL_CHAIN_SIGNER_PRIVATE_KEY=<relayer key from the manifest>

Run from backend/:  .venv/bin/python scripts/integrated_checkpoint.py
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

import httpx  # noqa: E402
import jwt as pyjwt  # noqa: E402
from eth_utils import keccak  # noqa: E402
from web3 import Web3  # noqa: E402
import json  # noqa: E402

LABEL = "backend demo tally; independent private tally verification pending."
PORT = int(os.environ.get("CHECKPOINT_PORT", "8010"))
BASE = f"http://127.0.0.1:{PORT}"
POLL_TIMEOUT = 60
REPORT_PATH = Path(os.environ.get("CHECKPOINT_REPORT", str(ROOT / "docs/checkpoint2-live-evidence.json")))
REPORT: dict = {"scope": "live HTTP API + PostgreSQL + Hardhat; synthetic dev JWT users; backend demo tally only",
                "stages": [], "result": "incomplete"}
SECRET_VALUES: list[str] = []


def _clean(value):
    """Evidence stays useful but never carries tokens, keys, or codes."""
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if k.lower() in {"nonce", "access_token", "refresh_token",
                                            "authorization", "private_key", "password",
                                            "devcode", "identifytoken", "token"}
                    else _clean(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, bytes):
        return "0x" + value.hex()
    if isinstance(value, str):
        for secret in SECRET_VALUES:
            if secret:
                value = value.replace(secret, "[REDACTED]")
    return value


def save_report() -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(_clean(REPORT), indent=2) + "\n", encoding="utf-8")


def step(text: str) -> None:
    print(f"\n--- {text}")
    REPORT["stages"].append({"stage": text, "at": datetime.now(timezone.utc).isoformat()})


def wait_for(condition, description: str, timeout: float = POLL_TIMEOUT) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.5)
    raise SystemExit(f"TIMEOUT waiting for {description}")


def mint_token(secret: str, user_id: uuid.UUID, email: str) -> str:
    now = datetime.now(timezone.utc)
    return pyjwt.encode(
        {"sub": str(user_id), "email": email, "role": "authenticated", "iat": now,
         "exp": now + timedelta(hours=1)},
        secret, algorithm="HS256",
    )


def main() -> int:
    relayer_key = os.environ.get("LOCAL_CHAIN_SIGNER_PRIVATE_KEY")
    if not relayer_key:
        raise SystemExit("set LOCAL_CHAIN_SIGNER_PRIVATE_KEY (the manifest's relayer account key)")
    SECRET_VALUES.extend([relayer_key])

    # --- database ---------------------------------------------------------
    if os.environ.get("DATABASE_URL"):
        database_url = os.environ["DATABASE_URL"]
    else:
        import pgserver

        server = pgserver.get_server(os.environ.get("VOTEVAULT_PG_DIR", "/tmp/votevault-checkpoint-pg"))
        database_url = server.get_uri().replace("postgresql://", "postgresql+psycopg://", 1)
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")

    jwt_secret = "checkpoint-hs256-secret-0123456789abcdef"
    SECRET_VALUES.append(jwt_secret)
    env = {
        **os.environ,
        "DATABASE_URL": database_url,
        "SUPABASE_JWT_SECRET": jwt_secret,
        "BLOCKCHAIN_RPC_URL": os.environ.get("BLOCKCHAIN_RPC_URL", "http://127.0.0.1:8545"),
        "BLOCKCHAIN_CHAIN_ID": "31337",
        "BLOCKCHAIN_DEPLOYMENT_FILE": os.environ.get(
            "BLOCKCHAIN_DEPLOYMENT_FILE", "blockchain/deployments/localhost.json"
        ),
        "LOCAL_CHAIN_SIGNER_PRIVATE_KEY": relayer_key,
        "RUN_BACKGROUND_PUBLISHER": "true",
        "PUBLICATION_POLL_INTERVAL_SECONDS": "1",
        "PUBLICATION_RETRY_DELAY_SECONDS": "1",
    }

    # --- start the real backend -------------------------------------------
    step("starting uvicorn (real backend, background publisher on)")
    server = subprocess.Popen(
        [str(BACKEND_DIR / ".venv" / "bin" / "uvicorn"), "app.main:app", "--port", str(PORT)],
        cwd=str(BACKEND_DIR), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        wait_for(lambda: _healthy(), "backend to come up", 30)
        boot = httpx.get(f"{BASE}/").json()
        print(f"    root: {boot}")
        assert boot["publisher"] == "web3", "publisher must be web3 (deployment-file mode)"
        print("    publisher=web3 (loaded from deployment artifact, validation passed)")

        organizer = uuid.uuid5(uuid.NAMESPACE_URL, "checkpoint:organizer")
        voter1 = uuid.uuid5(uuid.NAMESPACE_URL, "checkpoint:voter-1")
        voter2 = uuid.uuid5(uuid.NAMESPACE_URL, "checkpoint:voter-2")
        outsider = uuid.uuid5(uuid.NAMESPACE_URL, "checkpoint:outsider")
        org_hdr = {"Authorization": f"Bearer {mint_token(jwt_secret, organizer, 'organizer@checkpoint.edu')}"}
        v1_hdr = {"Authorization": f"Bearer {mint_token(jwt_secret, voter1, 'voter1@checkpoint.edu')}"}
        v2_hdr = {"Authorization": f"Bearer {mint_token(jwt_secret, voter2, 'voter2@checkpoint.edu')}"}
        out_hdr = {"Authorization": f"Bearer {mint_token(jwt_secret, outsider, 'outsider@checkpoint.edu')}"}

        # --- the flow ------------------------------------------------------
        step("organizer: organization + election + 3 candidates + uploaded voter roster")
        org = httpx.post(f"{BASE}/api/v1/organizations", json={"name": "Checkpoint Club"}, headers=org_hdr).json()
        election = httpx.post(
            f"{BASE}/api/v1/elections",
            json={"organization_id": org["organization_id"], "title": "Checkpoint Election"},
            headers=org_hdr,
        ).json()
        election_id = election["election_id"]
        election_code = election["code"]
        candidates = httpx.post(
            f"{BASE}/api/v1/elections/{election_id}/candidates",
            json={"candidates": [{"name": "Alice Alpha"}, {"name": "Bob Beta"}, {"name": "Carmen Gamma"}]},
            headers=org_hdr,
        ).json()["candidates"]
        roster_csv = (
            "name,rollNo,email\n"
            f"Vera One,v001,{voter1}@checkpoint.edu\n"
            f"Wes Two,v002,{voter2}@checkpoint.edu\n"
        )
        roster_report = httpx.post(
            f"{BASE}/api/v1/elections/{election_id}/voters/upload",
            files={"file": ("roster.csv", roster_csv.encode(), "text/csv")},
            headers=org_hdr,
        ).json()
        assert roster_report["imported"] == 2, roster_report
        print(f"    election code: {election_code}  roster imported: {roster_report['imported']}")

        def voter_headers(roll_no: str, email: str) -> dict:
            identify = httpx.post(
                f"{BASE}/api/v1/vote/{election_code}/identify", json={"rollNo": roll_no}
            ).json()
            otp = httpx.post(
                f"{BASE}/api/v1/vote/otp/request",
                json={"identifyToken": identify["identifyToken"], "channel": "email", "contact": email},
            ).json()
            verify = httpx.post(
                f"{BASE}/api/v1/vote/otp/verify",
                json={"identifyToken": identify["identifyToken"], "otp": otp["devCode"]},
            ).json()
            return {"Authorization": f"Bearer {verify['token']}"}

        step("organizer opens the election; worker publishes register (with configHash) + open")
        opened = httpx.post(f"{BASE}/api/v1/elections/{election_id}/open", json={}, headers=org_hdr)
        assert opened.status_code == 200, opened.text
        _wait_all_confirmed(election_id, {"register_election", "open_election"}, org_hdr)
        configuration = httpx.get(f"{BASE}/api/v1/elections/{election_id}/configuration", headers=org_hdr).json()
        print(f"    config_hash on chain: {configuration['config_hash'][:26]}...")
        v1_hdr = voter_headers("v001", f"{voter1}@checkpoint.edu")
        v2_hdr = voter_headers("v002", f"{voter2}@checkpoint.edu")

        step("voter 1 votes; duplicate + conflicting + outsider attempts behave")
        choice_a, choice_c = candidates[0]["candidate_id"], candidates[2]["candidate_id"]
        first = httpx.post(f"{BASE}/api/v1/elections/{election_id}/ballots",
                           json={"candidate_id": choice_a}, headers=v1_hdr)
        assert first.status_code == 202, first.text
        receipt_id = first.json()["receipt_id"]
        retry = httpx.post(f"{BASE}/api/v1/elections/{election_id}/ballots",
                           json={"candidate_id": choice_a}, headers=v1_hdr)
        assert retry.status_code == 202 and retry.json()["receipt_id"] == receipt_id
        conflict = httpx.post(f"{BASE}/api/v1/elections/{election_id}/ballots",
                              json={"candidate_id": choice_c}, headers=v1_hdr)
        assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "DUPLICATE_VOTE"
        outsider_session = {"Authorization": f"Bearer {mint_token(jwt_secret, outsider, 'o@checkpoint.edu')}"}
        outsider_try = httpx.post(f"{BASE}/api/v1/elections/{election_id}/ballots",
                                  json={"candidate_id": choice_c}, headers=outsider_session)
        assert outsider_try.status_code == 401 and outsider_try.json()["error"]["code"] == "UNAUTHENTICATED"
        print(f"    202 accepted (receipt {receipt_id[:8]}...), retry idempotent, 409 + 401 enforced")

        step("worker publishes the ballot commitment; receipt confirms with tx + block")
        _wait_all_confirmed(election_id, {"publish_ballot"}, org_hdr)
        receipt = httpx.get(f"{BASE}/api/v1/elections/{election_id}/receipts/{receipt_id}", headers=v1_hdr).json()
        assert receipt["status"] == "confirmed" and receipt["transaction_hash"], receipt
        print(f"    receipt confirmed: tx={receipt['transaction_hash'][:22]}... block={receipt['block_number']}")

        step("voter 2 votes; organizer closes (status -> closing until the chain confirms)")
        httpx.post(f"{BASE}/api/v1/elections/{election_id}/ballots",
                   json={"candidate_id": choice_c}, headers=v2_hdr)
        closed = httpx.post(f"{BASE}/api/v1/elections/{election_id}/close", json={}, headers=org_hdr)
        assert closed.status_code == 200 and closed.json()["status"] == "closing", closed.text
        _wait_all_confirmed(election_id, {"publish_ballot", "close_election", "publish_result"}, org_hdr)
        status_now = httpx.get(f"{BASE}/api/v1/elections/{election_id}", headers=org_hdr).json()["status"]
        assert status_now == "closed", f"expected closed after chain close confirmed, got {status_now}"
        print("    close confirmed on chain; election status closed")

        step("results: backend demo tally + anchored result status")
        results = httpx.get(f"{BASE}/api/v1/elections/{election_id}/results", headers=org_hdr).json()
        for row in results["counts"]:
            print(f"      {row['name']:<14} {row['votes']} {'#' * row['votes']}")
        assert results["total_ballots"] == 2 and results["published_result_status"] == "confirmed"
        assert results["disclaimer"] == LABEL

        # --- independent on-chain verification ------------------------------
        step("independent verification against the deployed contract (web3 + manifest)")
        _verify_on_chain(election_id, receipt, configuration, results)
        print("    getElection: state=Closed, configHash/resultCommitment match, 2 ballots on chain")

        REPORT["result"] = "PASSED"
        REPORT["election"] = {"election_id": election_id, "code": election_code,
                              "status": status_now, "total_ballots": results["total_ballots"],
                              "published_result_status": results["published_result_status"],
                              "disclaimer": results["disclaimer"]}
        print(f"\n{'=' * 72}\nCHECKPOINT 2 PASSED — {LABEL}\n{'=' * 72}")
        return 0
    except BaseException as exc:
        REPORT["result"] = f"FAILED: {type(exc).__name__}: {exc}"
        raise
    finally:
        save_report()
        server.send_signal(signal.SIGINT)
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


def _healthy() -> bool:
    try:
        return httpx.get(f"{BASE}/", timeout=2).status_code == 200
    except Exception:
        return False


def _wait_all_confirmed(election_id: str, job_types: set[str], headers: dict) -> None:
    def done() -> bool:
        pubs = httpx.get(f"{BASE}/api/v1/elections/{election_id}/publications", headers=headers).json()
        by_type: dict[str, list[str]] = {}
        for job in pubs["publications"]:
            by_type.setdefault(job["job_type"], []).append(job["status"])
        return all(
            all(s == "confirmed" for s in by_type.get(t, ["missing"])) and by_type.get(t)
            for t in job_types
        )
    wait_for(done, f"jobs to confirm on chain: {sorted(job_types)}")
    pubs = httpx.get(f"{BASE}/api/v1/elections/{election_id}/publications", headers=headers).json()
    for job in pubs["publications"]:
        print(f"      {job['job_type']:<18} {job['status']:<9} tx={str(job['transaction_hash'])[:22]} block={job['block_number']}")


def _verify_on_chain(election_id: str, receipt: dict, configuration: dict, results: dict) -> None:
    from app.blockchain.publisher import load_deployment

    manifest = load_deployment(os.environ.get(
        "BLOCKCHAIN_DEPLOYMENT_FILE", "blockchain/deployments/localhost.json"))
    w3 = Web3(Web3.HTTPProvider(os.environ.get("BLOCKCHAIN_RPC_URL", "http://127.0.0.1:8545")))
    contract = w3.eth.contract(address=Web3.to_checksum_address(manifest["address"]), abi=manifest["abi"])
    election_b32 = "0x" + "00" * 16 + uuid.UUID(election_id).hex

    state, config_hash, result_commitment, ballot_count = contract.functions.getElection(election_b32).call()
    assert state == 3, f"chain state {state} != 3 (Closed)"
    assert Web3.to_hex(config_hash) == configuration["config_hash"].lower()
    assert Web3.to_hex(result_commitment) == _expected_result_hash(results, election_id)
    assert ballot_count == 2

    for receipt_id, commitment in ((receipt["receipt_id"], receipt["commitment"]),):
        stored = contract.functions.ballotCommitments(
            election_b32, "0x" + "00" * 16 + uuid.UUID(receipt_id).hex
        ).call()
        assert Web3.to_hex(stored) == commitment.lower()

    logs = w3.eth.get_logs({
        "fromBlock": manifest["blockNumber"],
        "toBlock": "latest",
        "address": Web3.to_checksum_address(manifest["address"]),
        "topics": [
            "0x" + keccak(text="BallotPublished(bytes32,bytes32,bytes32,address)").hex(),
            election_b32,
        ],
    })
    assert len(logs) == 2, f"expected exactly 2 BallotPublished events, got {len(logs)}"


def _expected_result_hash(results: dict, election_id: str) -> str:
    from app.services.ids import uuid_to_bytes32

    packed = uuid_to_bytes32(uuid.UUID(election_id)) + results["total_ballots"].to_bytes(32, "big")
    for row in results["counts"]:
        packed += uuid_to_bytes32(uuid.UUID(row["candidate_id"])) + row["votes"].to_bytes(32, "big")
    return "0x" + keccak(packed).hex()


if __name__ == "__main__":
    raise SystemExit(main())
