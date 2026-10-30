> Updated interface: see [the 2026-10-31 decision](../docs/decisions/2026-10-31-blockchain-interface.md) and [run guide](../docs/local-chain.md). Registration now includes config_hash and is queued at opening; closure uses closing until all ballots and the close transaction confirm. These rules supersede any older lifecycle/no-ordering descriptions below.

# VoteVault Backend (milestone 1)

FastAPI + SQLAlchemy 2 + Alembic on Supabase PostgreSQL, Supabase Auth JWT
verification, and Web3.py publication of ballot commitments to the local
Hardhat chain (`ElectionRegistry`, chain id 31337).

**Scope label: “backend demo tally; independent private tally verification pending.”**
This is a synthetic-data skeleton: identified test voters, plaintext choices in
the database (private to the backend), commitments on chain, and a
backend-computed demo tally. It does NOT provide anonymous eligibility,
encrypted ballots, or independent verification of the tally. The ballot model
will change in milestone 2.

## Layout

```
app/
  api/routes/      endpoint handlers (elections, candidates, voters, ballots, publications, results)
  api/deps.py      auth + organizer/visibility dependencies
  auth/            Supabase JWT verification (RS256 via JWKS, or HS256 secret for dev)
  models/          SQLAlchemy models (7 tables)
  schemas/         Pydantic request/response shapes
  services/        ballot rules, commitment scheme, publication queue, tally
  blockchain/      ElectionRegistry ABI + Web3 publisher
  db/              base/session
  eth_events.py    event log verification (topics/data equality)
alembic/           migrations (the ONLY way the schema changes)
scripts/demo.py    end-to-end demo of the whole milestone flow
tests/             pytest suite (real PostgreSQL via pgserver; py-evm chain)
```

## Setup

```bash
cd backend
uv venv --python python3 .venv
uv pip install --python .venv/bin/python -e .          # runtime deps
uv pip install --python .venv/bin/python pytest pgserver "eth-tester[py-evm]"  # dev/test
cp .env.example .env                                    # fill in your values
```

Environment variables: see `.env.example`. Database and auth come from your
Supabase project; the relayer key stays in the backend environment only.

### Database migrations

Never change the schema in the Supabase dashboard. Always:

```bash
# apply (uses DATABASE_URL from .env / environment)
.venv/bin/alembic upgrade head

# create a new migration after editing app/models/
.venv/bin/alembic revision --autogenerate -m "message"
```

### Run

```bash
.venv/bin/uvicorn app.main:app --reload --port 8000
# docs at http://127.0.0.1:8000/docs
```

Without blockchain settings the API still works; publications report `pending`
and the worker records honest failures.

#### Voter flow (no accounts)

Organizers upload the voter roster (CSV/XLSX) per election; voters identify by
roll number/name, receive an OTP on their roster contact, and vote with a
short-lived session token. In dev (`APP_ENV != production`) the OTP is
returned in the API response (`devCode`) because no mail/SMS provider is
wired — production must integrate a real sender. See
`docs/decisions/2026-10-31-voter-roster-upload.md`.

#### Blockchain mode (checkpoint 2, real chain)

```bash
# 1) from blockchain/:  npx hardhat node                            # terminal 1
#    npx hardhat run scripts/deploy.js --network localhost          # writes deployments/localhost.json
# 2) backend .env:
#    BLOCKCHAIN_RPC_URL=http://127.0.0.1:8545
#    BLOCKCHAIN_CHAIN_ID=31337
#    BLOCKCHAIN_DEPLOYMENT_FILE=blockchain/deployments/localhost.json
#    LOCAL_CHAIN_SIGNER_PRIVATE_KEY=<the manifest relayer key>
.venv/bin/uvicorn app.main:app --port 8000
```

The publisher loads contract address, ABI, and bytecode hash from the
deployment artifact and refuses to run against a stale or altered deployment
(chain id, runtime code hash, and RELAYER_ROLE are validated before the first
call). Re-run `deploy.js` then restart the backend whenever the contract
changes. Full integrated checkpoint:

```bash
.venv/bin/python scripts/integrated_checkpoint.py   # node + relayer key env set
```

## Tests

```bash
.venv/bin/python -m pytest tests/        # 59 tests + 1 integration checkpoint
```

Tests run against a REAL PostgreSQL (bundled `pgserver`, no root needed; or set
`VOTEVAULT_TEST_DATABASE_URL`) and a REAL EVM (py-evm via eth-tester), so the
unique-constraint race and receipt verification are genuine. SQLite fallback:
`VOTEVAULT_TEST_DB=sqlite`. Migrations are applied with Alembic in tests — the
same schema path as production.

`tests/test_chain_checkpoint.py` (Member 3) runs against a live Hardhat node
and is skipped automatically when the node or its env vars are absent.

## Organizer signup / login

`POST /api/v1/auth/signup` (email, password, full name, organization name) and
`POST /api/v1/auth/login` relay credentials to Supabase Auth using the public
anon key (`SUPABASE_URL` + `SUPABASE_ANON_KEY`). The signup response is a
Supabase session whose access token every protected endpoint already verifies;
the backend stores only the profile (email, full name) and creates the
organization with the signer as owner. Passwords never touch this database.
For the demo, disable "Confirm email" in the Supabase dashboard, or signup
returns `403 EMAIL_CONFIRMATION_REQUIRED`.

## Demo (the milestone flow)

```bash
.venv/bin/python scripts/demo.py
```

Shows: organizer creates an election → adds three candidates and eligible test
users → opens it → one voter votes → duplicate and ineligible attempts fail →
commitments confirm on a real EVM → organizer closes → backend demo tally
appears — ending with the label:

> backend demo tally; independent private tally verification pending.

## API summary (`/api/v1`, full shapes in `docs/api-contract.md`)

| Method & path | Who | Purpose |
| --- | --- | --- |
| `POST /organizations` | any user | found org, becomes owner |
| `GET /organizations` | any user | own memberships |
| `POST /elections` | org organizer | create draft election (+ register job) |
| `GET /elections/{id}` | organizer (draft) / any user (open, closed) | election + candidates |
| `POST /elections/{id}/candidates` | organizer | add candidates (draft only) |
| `POST /elections/{id}/eligible-test-voters` | organizer | add eligible synthetic users |
| `GET /elections/{id}/eligible-test-voters` | organizer | roster (organizer-only) |
| `POST /elections/{id}/open` | organizer | draft → open (requires candidates + voters) |
| `POST /elections/{id}/ballots` | eligible voter | submit ballot; `202` accepted; idempotent retry |
| `GET /elections/{id}/receipts/{receipt_id}` | submitting voter | receipt + publication status |
| `GET /elections/{id}/publications` | organizer | all publication jobs |
| `POST /elections/{id}/publications/retry` | organizer | requeue + process now |
| `POST /elections/{id}/close` | organizer | open → closed (idempotent), queues result publication |
| `GET /elections/{id}/results` | organizer (after close) | demo tally + disclaimer |

Error shape everywhere: `{"error": {"code": "...", "message": "..."}}`.

## Guarantees implemented

- One ballot per voter per election via a **database unique constraint**
  (`uq_ballots_election_voter`) inside one transaction; concurrent duplicates
  resolve to exactly one stored ballot — identical retries return the existing
  receipt, different choices get `409 DUPLICATE_VOTE`.
- Ballot + `publish_ballot` job written **atomically**; chain submission is a
  separate retrying operation. Statuses are exactly `pending` / `confirmed` /
  `failed`; `confirmed` requires receipt status 1 **and** the matching event
  args on chain id 31337.
- Commitment encoding (fixed, see `docs/decisions/2026-10-30-blockchain-interface.md`):
  `keccak256("VV1" ‖ 0x00 ‖ electionId(bytes32) ‖ 0x00 ‖ uint256 candidateChainIndex ‖ 0x00 ‖ nonce32)`,
  with UUID ids left-padded to bytes32 (`bytes32(uint256(uint128(bytes16(uuid))))`).
- Ballot rows, eligible rosters, and receipts are never exposed to organizers
  or other voters; identity always comes from the verified JWT, never a body field.
