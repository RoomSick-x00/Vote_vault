# Draft API contract — for team agreement

**Proposed only.** No endpoints or behavior are implemented. Paths, field names, status codes, permissions, and lifecycle rules require team agreement. This draft covers milestone 1 only: identified eligible test voters, duplicate rejection, local-chain commitments, a demo backend tally, and receipt checks. It does not offer anonymous eligibility, encrypted ballots, or independent tally verification.

## Shared conventions (proposed)

- Prefix: `/api/v1`; JSON bodies and responses.
- Bearer token: Supabase Auth access token. Backend validates identity and organizer/election access; never trust a voter ID supplied in a ballot request.
- IDs: opaque strings; timestamps: UTC ISO 8601 strings.
- One candidate selection per ballot is a proposal to confirm.
- Error shape: `{ "error": { "code": "DUPLICATE_VOTE", "message": "A ballot has already been submitted." } }`.
- Candidate and voter IDs below are illustrative test data, not credentials.

## 1. Create election

`POST /api/v1/elections` — organizer only.

Request:
```json
{ "title": "Club election", "candidates": [{ "name": "Candidate A" }, { "name": "Candidate B" }], "eligible_test_voter_ids": ["user-1", "user-2"] }
```

Response `201`:
```json
{ "election_id": "election-1", "title": "Club election", "status": "open", "candidates": [{ "candidate_id": "candidate-1", "name": "Candidate A" }, { "candidate_id": "candidate-2", "name": "Candidate B" }], "eligible_test_voter_count": 2 }
```

Decision: immediate opening versus a separate draft/open lifecycle.

## 2. List eligible test voters

`GET /api/v1/elections/{election_id}/eligible-test-voters` — owning organizer only.

Request: no body.

Response `200`:
```json
{ "election_id": "election-1", "eligible_test_voters": [{ "user_id": "user-1" }, { "user_id": "user-2" }] }
```

Decision: provisioning source and pagination. Do not expose the roster to other voters.

## 3. Submit ballot

`POST /api/v1/elections/{election_id}/ballots` — authenticated eligible test voter; identity derived from the token.

Request:
```json
{ "candidate_id": "candidate-1" }
```

Response `202` (accepted for processing; not proof of chain recording):
```json
{ "election_id": "election-1", "receipt_id": "receipt-1", "status": "pending" }
```

Proposed errors: `403 NOT_ELIGIBLE`, `409 DUPLICATE_VOTE`, `409 ELECTION_CLOSED`, `422 INVALID_CANDIDATE`.

Decision: atomic duplicate prevention, retry behavior, commitment encoding, and recovery across database writes and chain transactions. The backend receives the selection for milestone 1; it is not an encrypted ballot.

## 4. Receipt status

`GET /api/v1/elections/{election_id}/receipts/{receipt_id}` — submitting voter only (organizer access to be agreed).

Request: no body.

Response `200`:
```json
{ "election_id": "election-1", "receipt_id": "receipt-1", "status": "recorded", "commitment": "0x<commitment>", "transaction_hash": "0x<transaction-hash>", "block_number": 12 }
```

Proposed statuses: `pending`, `recorded`, `failed`. Chain fields are `null` until available. A receipt checks whether a commitment was recorded on the local chain; it does not independently verify the tally or prove how a voter voted.

Decision: confirmation rule, failure details, receipt access, and exact check semantics.

## 5. Close election

`POST /api/v1/elections/{election_id}/close` — owning organizer only.

Request: empty object `{}`.

Response `200`:
```json
{ "election_id": "election-1", "status": "closed", "closed_at": "2026-10-30T12:00:00Z" }
```

Proposal: repeated closure returns the same closed state. Decision: handling in-flight ballots and chain failures before finalizing results.

## 6. Results

`GET /api/v1/elections/{election_id}/results` — owning organizer after closure.

Request: no body.

Response `200`:
```json
{ "election_id": "election-1", "status": "closed", "tally_type": "demo_backend", "total_ballots": 1, "counts": [{ "candidate_id": "candidate-1", "votes": 1 }, { "candidate_id": "candidate-2", "votes": 0 }] }
```

Proposed error: `409 ELECTION_NOT_CLOSED`. Decision: which ballot states count, tie handling, reconciliation, and whether results later become visible to voters. This is a backend-computed demo tally, not an independently verified tally.

## Common errors (proposed)

`401 UNAUTHENTICATED`, `403 FORBIDDEN`, `404 NOT_FOUND`, and `422 VALIDATION_ERROR`, using the shared error shape. Agree resource visibility and error details before implementation.
