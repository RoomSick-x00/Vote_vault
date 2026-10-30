# Local chain and backend run guide

The current agreement is [2026-10-31-blockchain-interface.md](decisions/2026-10-31-blockchain-interface.md). Older no-ordering/idempotency proposals are superseded.

## Setup (PowerShell, repository root)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ./backend -r backend/requirements-chain.txt
Set-Location blockchain
npm ci
npx hardhat test
```

Hardhat 2 and solc 0.8.24 are pinned in the npm lockfile. Python package discovery includes only app. The optional eth-tester emulator is not needed for Hardhat integration.

## Node and deployment

Terminal 1, inside blockchain:

```powershell
npm run node
```

Terminal 2, inside blockchain:

```powershell
npm run deploy:local
```

Use **blockchain/deployments/localhost.json**: it contains `chainId`, `address`, `abi`, non-secret role addresses, deployment block/transaction, and bytecode hash. Separate legacy ABI/manifest files are also generated for the older adapter. Contract name ElectionRegistry is compatible with backend ABI calls; no rename is necessary.

RPC is http://127.0.0.1:8545 and chain ID is 31337. Put the manifest address in `BALLOT_REGISTRY_CONTRACT_ADDRESS` and the authorized local relayer key in `LOCAL_CHAIN_SIGNER_PRIVATE_KEY` in the backend environment. Configure `BLOCKCHAIN_RPC_URL` and `BLOCKCHAIN_CHAIN_ID`. Keys must never be committed or exposed to the frontend. Hardhat accounts are disposable local development accounts only.

## Database and API

From backend, with DATABASE_URL and authentication settings privately configured:

```powershell
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Migration 0002 enables `closing`. Draft creation does not publish until candidates/rules are frozen at opening. The `/configuration` endpoint returns the exact canonical JSON and config_hash for recomputation. The publisher orders registration, opening, ballot publications, closure, and result publication.

POST close immediately stops new votes and returns `closing` with null closed_at. Poll election/publications; only a confirmed close changes it to `closed`. A failed ballot keeps closure blocked, its error visible, and results unavailable. Organizer publications/retry can resume work. Once closed, the demo tally is available; result publication status remains separately visible.

Use fresh synthetic elections for this changed interface. Existing old jobs without config_hash must not be silently published or retrofitted. Retained legacy data needs a reviewed migration. A chain reset also requires redeployment and explicit reconciliation/reset of demo jobs, not just reuse of an address.

## Reproduce the real Hardhat checkpoint

Inside blockchain:

```powershell
$env:VOTEVAULT_TEST_DB = 'sqlite'
npx hardhat run scripts/checkpoint.js --network localhost
```

The launcher creates/funds an ephemeral relayer, passes its key only in the child environment, runs Pytest, then revokes its role. It uses root .venv by default; CHECKPOINT_PYTHON can override. Omit the SQLite override and provide VOTEVAULT_TEST_DATABASE_URL for a dedicated PostgreSQL test database. Tests migrate and delete test data: never point them at shared or production data.

The integrated test uses actual FastAPI routes through TestClient, a migrated test database, synthetic JWT users, and the real Web3 publisher against Hardhat. It verifies A:2/B:1/C:0, duplicate/ineligible requests, ordered publication, exact event values, and a retry producing four ballot logs but **three unique ballot IDs**. No UI or live Supabase Auth interaction is exercised.

Evidence is written to `docs/integrated-chain-evidence.json`; the older low-level harness writes `docs/synthetic-chain-evidence.json`. Existing `docs/checkpoint-evidence.json` is retained unchanged by this work. Evidence is historical: addresses/transactions require the matching node instance.

The node remains on loopback for inspection. This workspace's ignored `.local/hardhat.pid` identifies its background process. Do not commit `.local` logs, which may contain disposable Hardhat account output.

This checkpoint records commitments; it does not prove tally correctness, encrypted ballots, anonymous eligibility, or independent tally verification.

## Validation on 2026-10-31

- Hardhat: 8 contract tests passed.
- Backend/API/real-Hardhat run: 54 passed, 1 skipped (optional eth-tester emulator module unavailable on this Windows setup).
- Test database: migrated SQLite. PostgreSQL row/advisory locks and a live Supabase deployment still need validation against a dedicated PostgreSQL test database.
- Direct events matched backend config_hash, three ballot commitments, and result_hash. Repeated ballot acknowledgement produced four events, three unique ballot IDs, and on-chain ballotCount=3.
- Failed ballot publication blocked close/result; operator recovery completed the sequence. Identical lifecycle retries preserved closed state.
- No frontend was exercised in this validation; the teammate’s frontend arrived separately.
