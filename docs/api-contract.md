# API contract — agreed and implemented (milestone 1)

**Status: implemented** on branch `backend/m1-skeleton` (backend owner: Member 2).
This replaces the earlier draft. Scope remains milestone 1: identified eligible
test voters, duplicate rejection, local-chain commitments, a demo backend tally,
and receipt checks. It does NOT provide anonymous eligibility, encrypted
ballots, or independent tally verification — every result response carries the
disclaimer: “backend demo tally; independent private tally verification pending.”

## Shared conventions

- Prefix: `/api/v1`; JSON bodies and responses.
- Auth: `Authorization: Bearer <Supabase access token>`; identity is always
  derived from the token (`sub` UUID) — no voter id is accepted in a body.
- IDs: opaque UUID strings; timestamps: UTC ISO 8601 with `Z`.
- Error shape (all non-2xx): `{ "error": { "code": "DUPLICATE_VOTE", "message": "..." } }`.
- On-chain encodings (election/ballot ids as bytes32, commitment, result hash,
  events): `docs/decisions/2026-10-30-blockchain-interface.md`.

## Roles and visibility

- Any authenticated user may found an organization (`POST /organizations`) and
  becomes its `owner`; `owner`/`organizer` members manage its elections.
- Draft elections are organizer-only. Open/closed elections are visible to any
  authenticated user (voting UI needs the candidate list).
- The eligible-voter roster, receipts, and all ballot data are organizer/voter
  private as noted per endpoint; ballot rows are never exposed to organizers.

## Endpoints

### 1. Organizations
- `POST /api/v1/organizations` `{ "name": "..." }` → `201`
  `{ "organization_id", "name", "role": "owner", "created_at" }`
- `GET /api/v1/organizations` → `200` `{ "organizations": [ { "organization_id", "name", "role", "created_at" } ] }`

### 2. Create election (draft)
`POST /api/v1/elections` — org organizer. Optional scheduling: `opens_at`, `closes_at`
(bound ballot acceptance while status is `open`).

```json
{ "organization_id": "<uuid>", "title": "Club election", "opens_at": null, "closes_at": null }
```
→ `201` `{ "election_id", "organization_id", "title", "status": "draft", "candidates": [], "created_at", "opens_at", "closes_at", "opened_at": null, "closed_at": null }`

A `register_election` publication job is created in the same transaction.

### 3. Candidates (draft only; chain index = immutable 0-based insertion order)
- `POST /api/v1/elections/{election_id}/candidates`
  `{ "candidates": [{ "name": "Alice" }, { "name": "Bob" }] }` → `201`
  `{ "election_id", "candidates": [ { "candidate_id", "name", "chain_index" } ], "added", "skipped" }`
  (duplicate names skipped). Errors: `409 ELECTION_NOT_DRAFT`, `403 FORBIDDEN`.
- `GET /api/v1/elections/{election_id}/candidates` → `200` (visible to anyone who can see the election)

### 4. Eligible test voters
- `POST /api/v1/elections/{election_id}/eligible-test-voters`
  `{ "user_ids": ["<supabase user uuid>", ...] }` → `201`
  `{ "election_id", "eligible_test_voters": [ { "user_id" } ], "added", "skipped" }`
  (idempotent; rejected after close: `409 ELECTION_CLOSED`).
- `GET /api/v1/elections/{election_id}/eligible-test-voters` → organizer only → `200` same roster shape.

### 5. Open election
`POST /api/v1/elections/{election_id}/open` — organizer. Requires ≥1 candidate
(`409 ELECTION_HAS_NO_CANDIDATES`) and ≥1 eligible voter (`409 ELECTION_HAS_NO_VOTERS`).
`draft → open`; reopening → `409 ELECTION_NOT_DRAFT`. → `200`
`{ "election_id", "status": "open", "opened_at" }`. Queues an `open_election` job.

### 6. Submit ballot
`POST /api/v1/elections/{election_id}/ballots` — authenticated eligible voter;
`{ "candidate_id": "<uuid>" }` → `202` (accepted for processing; NOT proof of chain recording):

```json
{ "election_id", "receipt_id", "status": "pending", "candidate_id", "submitted_at", "idempotent_retry": false }
```

- `receipt_id` == ballot id; ballot + `publish_ballot` job are written atomically.
- Identical retry (same candidate) → same receipt, `idempotent_retry: true` —
  also after close. Different choice → `409 DUPLICATE_VOTE` (original stands).
- Errors: `403 NOT_ELIGIBLE`, `409 ELECTION_NOT_OPEN`, `409 ELECTION_CLOSED`
  (window or status), `422 INVALID_CANDIDATE`, `404 NOT_FOUND`.

### 7. Receipt (publication status)
`GET /api/v1/elections/{election_id}/receipts/{receipt_id}` — submitting voter only.

```json
{ "election_id", "receipt_id", "status": "confirmed", "ballot_accepted": true, "candidate_id",
  "commitment": "0x…", "nonce": "0x…", "transaction_hash": "0x…", "block_number": 12,
  "submitted_at", "confirmed_at", "error": null }
```

- `status` is exactly `pending` | `confirmed` | `failed`:
  `confirmed` = receipt status 1 AND the matching `BallotPublished` event args
  on chain id 31337; `failed` = reverted/absent event with retries exhausted.
- `nonce` lets the voter recompute the commitment later. Chain fields are
  `null` until available; `error` holds the last publication error.

### 8. Publications (organizer)
- `GET /api/v1/elections/{election_id}/publications` → `200`
  `{ "election_id", "publications": [ { "job_id", "job_type", "receipt_id", "status", "attempts", "max_attempts", "transaction_hash", "block_number", "next_attempt_at", "last_error", "created_at", "confirmed_at" } ], "summary": { "pending": n, "confirmed": n, "failed": n } }`
  Job types: `register_election`, `open_election`, `publish_ballot`, `close_election`, `publish_result`.
- `POST /api/v1/elections/{election_id}/publications/retry` → `200`
  `{ "election_id", "requeued", "processed": { "confirmed": n, "retry_scheduled": n, "failed": n } }`
  Operator retry with a fresh attempt budget; safe because contract functions
  are idempotent and every attempt is receipt-verified.

### 9. Close election
`POST /api/v1/elections/{election_id}/close` — organizer; empty body `{}`.
Idempotent: repeated close returns the same `closed_at`. → `200`
`{ "election_id", "status": "closed", "closed_at" }`.
Closing computes the demo tally, anchors its `resultHash` and queues
`close_election` + `publish_result` jobs — all in one DB transaction.

### 10. Results (backend demo tally)
`GET /api/v1/elections/{election_id}/results` — organizer, after close
(`409 ELECTION_NOT_CLOSED` before).

```json
{ "election_id", "status": "closed", "tally_type": "demo_backend", "total_ballots": 2,
  "counts": [ { "candidate_id", "name", "chain_index", "votes" } ],
  "publications": { "pending": 0, "confirmed": 6, "failed": 0 },
  "published_result_status": "confirmed",
  "disclaimer": "backend demo tally; independent private tally verification pending." }
```

`published_result_status`: `not_published` | `pending` | `confirmed` | `failed`.
The tally is computed from accepted ballots in the database and is NOT an
independently verified result; the `disclaimer` field must be shown as-is in the UI.

## Common errors

`401 UNAUTHENTICATED`, `403 FORBIDDEN` / `NOT_ELIGIBLE`, `404 NOT_FOUND`,
`409 <lifecycle codes above>`, `422 VALIDATION_ERROR` / `INVALID_CANDIDATE` —
all in the shared error shape.
