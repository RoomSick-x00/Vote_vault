"""VoteVault milestone-1 end-to-end demo.

Runs the complete agreed flow against a REAL PostgreSQL (bundled via pgserver,
or point DATABASE_URL at Supabase) and a REAL EVM chain (py-evm in-process —
the same signing/receipt/event-verification code path used for Hardhat):

    organizer creates election -> adds 3 candidates + eligible test users
    -> opens it -> one voter votes -> duplicate + ineligible attempts fail
    -> commitment confirms on the chain -> organizer closes
    -> backend demo tally appears.

Run from backend/:  .venv/bin/python scripts/demo.py
"""

from __future__ import annotations

import os
import secrets
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "tests"))

import jwt as pyjwt  # noqa: E402

LABEL = "backend demo tally; independent private tally verification pending."


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n  {text}\n{'=' * 72}")


def step(n: int, text: str) -> None:
    print(f"\n--- {n}. {text}")


def resolve_database_url() -> str:
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    import pgserver

    server = pgserver.get_server(os.environ.get("VOTEVAULT_PG_DIR", "/tmp/votevault-demo-pg"))
    return server.get_uri().replace("postgresql://", "postgresql+psycopg://", 1)


def main() -> int:
    banner("VoteVault milestone-1 demo — synthetic data only")

    # --- infrastructure ---------------------------------------------------
    database_url = resolve_database_url()
    print(f"database: {database_url.split('@')[-1]}")  # never print credentials

    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    print("running Alembic migrations to head ...")
    command.upgrade(cfg, "head")

    from eth_tester import EthereumTester
    from web3 import Web3
    from web3.providers import EthereumTesterProvider

    from evm_stub import deploy_init, stub_runtime

    w3 = Web3(EthereumTesterProvider(EthereumTester()))
    relayer = w3.eth.account.from_key("0x" + secrets.token_hex(32))
    w3.eth.send_transaction(
        {"from": w3.eth.accounts[0], "to": relayer.address, "value": w3.to_wei(10, "ether"), "gas": 21_000}
    )
    deploy = relayer.sign_transaction(
        {
            "from": relayer.address,
            "data": deploy_init(stub_runtime()),
            "nonce": 0,
            "gas": 400_000,
            "gasPrice": w3.eth.gas_price,
            "chainId": w3.eth.chain_id,
        }
    )
    receipt = w3.eth.wait_for_transaction_receipt(
        w3.eth.send_raw_transaction(getattr(deploy, "raw_transaction", None) or deploy.rawTransaction)
    )
    print(
        f"chain: EVM in-process (py-evm), chain id {w3.eth.chain_id}, "
        f"BallotRegistry stub at {receipt['contractAddress']}"
    )

    from app.blockchain.publisher import Web3RegistryPublisher
    from app.config import Settings
    from app.main import create_app

    settings = Settings(
        database_url=database_url,
        supabase_jwt_secret="demo-jwt-secret-0123456789abcdef",
        run_background_publisher=False,
    )
    publisher = Web3RegistryPublisher(
        rpc_url="in-process://",
        contract_address=receipt["contractAddress"],
        signer_private_key="0x" + relayer.key.hex(),
        chain_id=w3.eth.chain_id,
        w3=w3,
    )
    app = create_app(settings=settings, publisher=publisher, run_background_publisher=False)
    from fake_supabase import FakeSupabaseAuth

    app.state.supabase_auth = FakeSupabaseAuth(settings.supabase_jwt_secret)

    from fastapi.testclient import TestClient

    client = TestClient(app)

    # synthetic Supabase Auth users
    voter1 = uuid.uuid5(uuid.NAMESPACE_URL, "demo:voter-1")
    voter2 = uuid.uuid5(uuid.NAMESPACE_URL, "demo:voter-2")
    outsider = uuid.uuid5(uuid.NAMESPACE_URL, "demo:outsider")

    def hdr(user: uuid.UUID) -> dict:
        now = datetime.now(timezone.utc)
        token = pyjwt.encode(
            {"sub": str(user), "role": "authenticated", "iat": now, "exp": now.timestamp() + 3600},
            settings.supabase_jwt_secret,
            algorithm="HS256",
        )
        return {"Authorization": f"Bearer {token}"}

    def voter_token(code: str, roll_no: str, email: str) -> dict:
        """identify -> OTP (dev delivery) -> verify; returns bearer headers."""
        identify = client.post(f"/api/v1/vote/{code}/identify", json={"rollNo": roll_no}).json()
        otp = client.post(
            "/api/v1/vote/otp/request",
            json={"identifyToken": identify["identifyToken"], "channel": "email", "contact": email},
        ).json()
        verify = client.post(
            "/api/v1/vote/otp/verify",
            json={"identifyToken": identify["identifyToken"], "otp": otp["devCode"]},
        ).json()
        return {"Authorization": f"Bearer {verify['token']}"}

    def show_vote(resp, who: str) -> dict:
        print(f"    HTTP {resp.status_code}: {resp.text[:200]}")
        return resp.json() if resp.content else {}

    def show(resp) -> dict:
        print(f"    HTTP {resp.status_code}: {resp.text[:220]}")
        return resp.json() if resp.content else {}

    from app.services import publication_service

    def drain() -> None:
        summary = publication_service.process_due_jobs(
            app.state.sessionmaker, app.state.publisher, settings
        )
        print(f"    publication worker: {summary}")

    # --- the flow -----------------------------------------------------------
    step(1, "organizer signs up (email, password, full name, organization name)")
    session = show(
        client.post(
            "/api/v1/auth/signup",
            json={
                "email": "dana@democlub.edu",
                "password": "demo-password-123",
                "full_name": "Dana Organizer",
                "organization_name": "Demo Campus Club",
            },
        )
    )
    organizer_token = {"Authorization": f"Bearer {session['access_token']}"}
    org = {"organization_id": session["organizations"][0]["organization_id"]}

    step(2, "organizer creates a draft election")
    election = show(
        client.post(
            "/api/v1/elections",
            json={"organization_id": org["organization_id"], "title": "Demo Club President 2026"},
            headers=organizer_token,
        )
    )
    election_id = election["election_id"]

    step(3, "organizer adds three candidates (draft only; chain indexes 0,1,2)")
    candidates = show(
        client.post(
            f"/api/v1/elections/{election_id}/candidates",
            json={"candidates": [{"name": "Alice Alpha"}, {"name": "Bob Beta"}, {"name": "Carmen Gamma"}]},
            headers=organizer_token,
        )
    )

    step(4, "organizer uploads the voter roster (CSV; voters have no accounts)")
    roster_csv_text = (
        "name,rollNo,email,phone\n"
        f"Vera One,v001,{voter1}@demo.edu,5550001\n"
        f"Wes Two,v002,{voter2}@demo.edu,5550002\n"
    )
    print("    CSV:\n      " + "\n      ".join(roster_csv_text.strip().splitlines()))
    show(
        client.post(
            f"/api/v1/elections/{election_id}/voters/upload",
            files={"file": ("roster.csv", roster_csv_text.encode(), "text/csv")},
            headers=organizer_token,
        )
    )

    step(5, "organizer opens the election")
    show(client.post(f"/api/v1/elections/{election_id}/open", json={}, headers=organizer_token))
    drain()  # register_election + open_election hit the chain

    step(6, "voter 1 identifies (roll no), gets a dev OTP, and submits a ballot")
    choice = candidates["candidates"][0]["candidate_id"]
    v1 = voter_token(election["code"], "v001", f"{voter1}@demo.edu")
    accepted = show(
        client.post(
            f"/api/v1/elections/{election_id}/ballots",
            json={"candidate_id": choice},
            headers=v1,
        )
    )

    step(7, "publication worker publishes the ballot commitment (separate operation)")
    drain()
    rec = client.get(
        f"/api/v1/elections/{election_id}/receipts/{accepted['receipt_id']}", headers=v1
    ).json()
    print(
        f"    receipt: status={rec['status']} commitment={rec['commitment'][:18]}... "
        f"tx={rec['transaction_hash'][:20]}... block={rec['block_number']}"
    )

    step(8, "identical retry returns the SAME receipt (idempotent)")
    retry = client.post(
        f"/api/v1/elections/{election_id}/ballots",
        json={"candidate_id": choice},
        headers=v1,
    )
    print(
        f"    HTTP {retry.status_code}: receipt_id same={retry.json()['receipt_id'] == accepted['receipt_id']}"
        f", idempotent_retry={retry.json()['idempotent_retry']}"
    )

    step(9, "a different second choice is rejected (original ballot stands)")
    other = candidates["candidates"][1]["candidate_id"]
    show(client.post(f"/api/v1/elections/{election_id}/ballots", json={"candidate_id": other}, headers=v1))

    step(10, "a voter session from the roster only works in its own election")
    outsider_session = hdr(outsider)  # Supabase token is not a voter session
    show(client.post(f"/api/v1/elections/{election_id}/ballots", json={"candidate_id": other}, headers=outsider_session))

    step(11, "voter 2 votes; organizer closes the election")
    v2 = voter_token(election["code"], "v002", f"{voter2}@demo.edu")
    client.post(
        f"/api/v1/elections/{election_id}/ballots",
        json={"candidate_id": candidates["candidates"][2]["candidate_id"]},
        headers=v2,
    )
    show(client.post(f"/api/v1/elections/{election_id}/close", json={}, headers=organizer_token))

    step(12, "publication worker publishes close + the anchored result hash")
    drain()
    pubs = client.get(f"/api/v1/elections/{election_id}/publications", headers=organizer_token).json()
    print(f"    publications summary: {pubs['summary']}")
    for job in pubs["publications"]:
        print(
            f"      {job['job_type']:<18} {job['status']:<9} "
            f"tx={str(job['transaction_hash'])[:20]} block={job['block_number']}"
        )

    step(13, "backend demo tally (organizer, after close)")
    results = show(client.get(f"/api/v1/elections/{election_id}/results", headers=organizer_token))
    for row in results["counts"]:
        bar = "#" * row["votes"]
        print(f"      {row['name']:<14} {row['votes']} {bar}")
    print(f"    total ballots: {results['total_ballots']}  published result: {results['published_result_status']}")

    banner(f"RESULT: {LABEL}")
    print("All commitments above were mined on a real EVM; the tally itself is")
    print("backend-computed from the private ballots table and is NOT independently")
    print("verified. Milestone 2 adds anonymous eligibility, encrypted ballots, and")
    print("independent tally verification.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
