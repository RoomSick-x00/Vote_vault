> Historical proposal. Superseded by docs/decisions/2026-10-31-blockchain-interface.md (project-owner approved).

# Decision: on-chain interface for milestone 1 — Member 2 response to Member 3

- Date: 2026-10-30
- Status: **Approved with requested changes** (Member 2, backend/database)
- Counterparty: Member 3 (blockchain/integration)
- Scope: Milestone 1 skeleton only. None of this claims anonymity, encrypted ballots, or independent tally verification.

## Verdict

Member 3's proposal is approved in structure:

- `electionId` / `ballotId` as opaque **nonzero bytes32** values persisted by the backend — **agreed**, exact encoding below.
- Commitments as **nonzero bytes32** hashes, opaque to the contract — **agreed**, backend-side encoding below.
- Relayer functions `registerElection`, `openElection`, `closeElection`, `publishBallot`, `publishResult` — **agreed**, exact signatures below.
- Events carrying only IDs/commitments (no voter identity, no candidate choice, no titles) — **agreed**, exact shapes below.
- Status semantics: `pending` = accepted or submitted, awaiting a successful receipt; `confirmed` = receipt `status == 1` **and** the matching event in the receipt logs, on chain ID 31337 — **agreed with one addition** (event-args must match; see below).

Four requested changes before the contract is final. None change the shape of the proposal; three are one-line guarantees.

## Requested changes

1. **All five relayer functions must be idempotent (re-submittable without revert).**
   `publishBallot(electionId, ballotId, commitment)` called twice with the *same* arguments must succeed (re-emitting `BallotPublished` is fine, returning quietly is fine). Only a *different* commitment for an already-recorded `(electionId, ballotId)` may revert.
   Reason: the backend publishes with at-least-once retry out of Postgres (`publication_jobs`). If a transaction is sent but the receipt times out or is lost, the backend re-sends a fresh transaction; a revert-on-duplicate would turn a successful publication into a false `failed`. Same guarantee for the other four functions.

2. **No cross-function ordering gates in milestone 1.**
   `publishBallot` must not revert merely because `registerElection`/`openElection` have not confirmed yet. Election lifecycle rules (draft → open → closed, eligibility, one ballot per voter) are enforced by the backend in Postgres; the chain record is an append-only anchor. If a gate is kept anyway, it must itself be idempotent and Member 3 must say so explicitly, because the backend then has to sequence job types.

3. **Confirmation requires the matching event, not just `status == 1`.**
   A job is `confirmed` only when: receipt `status == 1`, on chain ID 31337 (backend checks `eth_chainId` at startup), **and** the expected event is present in that receipt's logs with args equal to the submitted `electionId`/`ballotId`/`commitment`. Anything else (reverted receipt, missing/non-matching event) is a failure and goes to retry; after `PUBLICATION_MAX_ATTEMPTS` (default 5) the job is shown as `failed`. This is Member 3's rule plus an event-args equality check.

4. **Ship the ABI + deployed address as data, not prose.**
   Deliver the contract ABI and the localhost deployment address as JSON the backend can consume (e.g. `blockchain/deployments/localhost.json` with `address` and `abi`, or pasted into this doc). The backend env var is `BALLOT_REGISTRY_CONTRACT_ADDRESS` (already in the root `.env.example`), so the contract should be named **`BallotRegistry`**. Also confirm whether functions are restricted to the relayer address (`onlyRelayer` preferred, plain local chain acceptable for milestone 1).

## Agreed exact interface

Contract `BallotRegistry`. The relayer is the holder of `LOCAL_CHAIN_SIGNER_PRIVATE_KEY` (backend-side env var only; never in the repo or frontend).

### ID encoding (backend-defined, fixed)

All UUIDs are UUIDv4, 16 big-endian bytes, **left-padded with 16 zero bytes** to bytes32 — identical to `bytes32(uint256(uint128(bytes16(uuid))))`:

```
electionId = 0x || 16 zero bytes || elections.id (16 bytes)
ballotId   = 0x || 16 zero bytes || ballots.id (16 bytes)      // ballot id == receipt id
candidateId (inside resultHash only) = same padding of candidates.id
```

Nonzero is guaranteed (random UUIDs). Supabase Auth user IDs never appear on chain in any form.

### Commitment encoding (backend-defined, fixed, opaque to the contract)

```
nonce       = 32 random bytes (secrets.token_bytes(32))
preimage    = "VV1" || 0x00 || electionId(32) || 0x00 || uint256(candidateChainIndex) || 0x00 || nonce(32)
commitment  = keccak256(preimage)          // nonzero bytes32
```

`candidateChainIndex` is the 0-based immutable index the backend assigns to each candidate at creation (insertion order). The contract treats `commitment` as opaque. The nonce is returned to the voter in the receipt so the commitment can be recomputed later; this does not by itself prove the tally.

### Functions and events

| Function | Event emitted |
| --- | --- |
| `registerElection(bytes32 electionId)` | `ElectionRegistered(bytes32 indexed electionId, address indexed relayer)` |
| `openElection(bytes32 electionId)` | `ElectionOpened(bytes32 indexed electionId, address indexed relayer)` |
| `publishBallot(bytes32 electionId, bytes32 ballotId, bytes32 commitment)` | `BallotPublished(bytes32 indexed electionId, bytes32 indexed ballotId, bytes32 commitment, address indexed relayer)` |
| `closeElection(bytes32 electionId)` | `ElectionClosed(bytes32 indexed electionId, address indexed relayer)` |
| `publishResult(bytes32 electionId, bytes32 resultHash)` | `ResultPublished(bytes32 indexed electionId, bytes32 resultHash, address indexed relayer)` |

`ballotId` is indexed so the backend can query its log by receipt. `commitment` and `resultHash` live in the data field, not topics.

### resultHash encoding (backend-defined; anchors the demo tally only)

```
resultHash = keccak256(abi.encodePacked(
    electionId,
    totalBallots,                                   // uint256, accepted ballots
    for each candidate in candidateChainIndex order: candidateId(bytes32), votes(uint256)
))
```

`publishResult` anchors the backend demo tally. It is not an independent verification of anything; the results API will carry the disclaimer "backend demo tally; independent private tally verification pending."

### Job/status model on the backend (for information)

Each on-chain call is a row in `publication_jobs` (job type, payload, attempts, tx hash, block number, status) written in the same Postgres transaction as the state change it anchors. Publication is a separate best-effort operation with retry/backoff. Exposed statuses are exactly `pending` / `confirmed` / `failed`. The database and the chain never share a transaction and the API does not pretend otherwise.

## Backend work location

- Code: `backend/` on branch `backend/m1-skeleton` (FastAPI app, SQLAlchemy models, Alembic migration, Web3.py publisher, Pytest suite). Status at time of writing: starting implementation now; this interface is the input it will be coded against.
- This decision record is the coordination artifact for the contract; Member 3 does not need to wait for backend code to land before writing `BallotRegistry` — only for the four changes above to be acknowledged.
