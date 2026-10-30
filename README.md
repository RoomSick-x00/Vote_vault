# VoteVault

VoteVault is a campus/club election prototype built by three teammates.

**Status:** the FastAPI backend and Solidity ElectionRegistry are integrated with a real local Hardhat chain. The current interface includes frozen configuration commitments, retry acknowledgements, and ordered publication with a `closing` state while accepted ballots drain. The frontend has also landed; its integration with this revised lifecycle has not yet been validated. See [the run guide](docs/local-chain.md) and [the locked interface](docs/decisions/2026-10-31-blockchain-interface.md). Results are a backend demo tally; independent tally verification is not implemented.

## Milestones

### 1. Working demo skeleton (planned)

An organizer creates an election and specifies eligible test voters. Eligible test voters submit one ballot each; duplicate submissions are rejected. Ballot commitments are recorded on a required Hardhat local blockchain. The organizer closes the election and sees a demo backend tally and receipt checks.

This milestone does not provide anonymous eligibility, encrypted ballots, or independent verification of the tally. Local blockchain records and receipt checks alone do not establish those capabilities. Treat this as a test-data prototype, not a production election system.

### 2. Privacy and independent verification (later)

Add anonymous eligibility, encrypted ballots, and independent tally verification. Their protocol and security design remain to be agreed. AI features are optional and deferred; blockchain is required.

## Agreed stack

- Frontend: React, TypeScript, Vite, Tailwind, React Router
- Backend: Python, FastAPI, Pydantic
- Database: Supabase PostgreSQL, SQLAlchemy, Alembic
- Authentication: Supabase Auth
- Blockchain: Solidity, OpenZeppelin, Hardhat local chain
- Backend-to-chain connection: Web3.py
- Testing (later): Pytest, Hardhat tests, Playwright

## Team ownership and directories

| Directory | Owner | Intended purpose |
| --- | --- | --- |
| `frontend/` | Frontend teammate | `public/` static assets; `src/pages/`, `components/`, `routes/`, `services/`, and `styles/` for the UI; `tests/e2e/` reserved for Playwright. |
| `backend/` | Backend/database teammate | `app/api/routes/` for API handlers, `models/` for SQLAlchemy models, `schemas/` for Pydantic shapes, `services/` for application logic, `db/` for database access; `alembic/versions/` for migrations; `tests/` reserved for Pytest. |
| `blockchain/` | Blockchain/integration teammate | `contracts/` for Solidity, `scripts/` for local-chain tooling, `test/` reserved for Hardhat tests. Owns Web3.py integration in coordination with the backend teammate. |
| `docs/` | Shared | Draft API agreement in `api-contract.md`; `architecture/` for future design notes; `decisions/` for team decisions. |

Empty leaf directories contain `.gitkeep` placeholders only. There are no package manifests, generated applications, migrations, contracts, or test implementations yet.

## Environment template

`.env.example` (root) is an inventory of variable names; `backend/.env.example`
is the backend's authoritative template with setup notes. Never put real
credentials in any template. Browser configuration may use only public Supabase
settings; database credentials and the local signer key belong exclusively to
backend/integration processes.

## Team decisions before implementation

- Agree the draft API shapes, election lifecycle, candidate rules, and organizer authorization.
- Agree how Supabase users map to eligible test voters and how eligibility is provisioned.
- Agree duplicate handling and database/chain consistency, including retries and chain failures.
- Define commitment encoding and receipt semantics without claiming anonymity, encryption, or independent tally verification.
- Agree results visibility, tie handling, local-chain signer ownership, and final environment variable names.

See [the draft API contract](docs/api-contract.md). These are proposals, not implemented behavior.
