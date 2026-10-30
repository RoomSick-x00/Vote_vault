# VoteVault

VoteVault is a campus/club election prototype built by three teammates. The initial scaffold is now extended with Member 3’s local ElectionRegistry contract, Hardhat tests/deployment tooling, and Web3.py service adapter. See [the local chain guide](docs/local-chain.md). Frontend, FastAPI endpoints, authentication, database acceptance, and a full application checkpoint are still unimplemented in this checkout.

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

Unimplemented areas retain `.gitkeep` placeholders. Blockchain implementation and service integration files live alongside those original placeholders; existing frontend files remain untouched.

## Environment template

`.env.example` is an inventory of proposed variable names only, not a loadable environment configuration. Values, exact naming, and per-service configuration will be agreed during implementation. Never put real credentials in this template. Browser configuration may use only public Supabase settings; database credentials and the local signer key belong exclusively to backend/integration processes.

## Team decisions before implementation

- Agree the draft API shapes, election lifecycle, candidate rules, and organizer authorization.
- Agree how Supabase users map to eligible test voters and how eligibility is provisioned.
- Agree duplicate handling and database/chain consistency, including retries and chain failures.
- Define commitment encoding and receipt semantics without claiming anonymity, encryption, or independent tally verification.
- Agree results visibility, tie handling, local-chain signer ownership, and final environment variable names.

See [the draft API contract](docs/api-contract.md). These are proposals, not implemented behavior.
