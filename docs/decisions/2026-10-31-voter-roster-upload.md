# Decision: voter roster upload replaces Supabase-based voter eligibility

- Date: 2026-10-31
- Status: **Accepted** (Member 2, backend; aligns with Member 1's built UI)
- Scope: milestone 1, voter identity. Organizer auth (Supabase) and the chain
  interface are unchanged.

## Decision

Voters are NOT Supabase accounts. The organizer configures a per-election
`voterSchema` and **uploads the voter roster** (CSV or XLSX). Voters vote
through a public, code-based flow:

```
election code -> identify (name and/or rollNo) -> OTP to the roster contact
              -> voter session token (2 h) -> one ballot -> receipt
```

## Rules

- `voterSchema = {identityColumns: ["name"|"rollNo", …], otpChannels: ["email"|"phone", …]}`;
  the channel's column is mandatory in the roster, identity columns are
  mandatory at identify time.
- OTP codes are 6 digits, stored **hashed**, 10-minute TTL, max 5 attempts,
  30-second resend cooldown, single use. The contact given at OTP request must
  match the roster (else `403 CONTACT_MISMATCH`).
- **Dev OTP delivery:** with `APP_ENV != production` the code is returned in
  the OTP response (`devCode`) and logged, because no mail/SMS provider is
  wired. Production must integrate a sender; `devCode` is never emitted there.
- Voter sessions are backend-issued HS256 JWTs (`scope: "voter"`, 2 h TTL,
  secret: `VOTER_SESSION_SECRET` falling back to `SUPABASE_JWT_SECRET`).
  Scope separation is strict: voter tokens fail at organizer endpoints (no
  `sub`), Supabase tokens fail at voter endpoints (no voter scope).
- One ballot per voter is still enforced by `uq_ballots_election_voter`;
  `ballots.voter_id` now references the roster (`voters.id`).
- `hasVoted` is never stored — it derives from the ballots table.
- The roster is private organizer data; deletion only in draft; uploads
  blocked once the election closes.

## Chain interface impact: NONE

`ballotId` is still the ballot row's UUID (bytes32-padded), commitments and
the result hash encoding are unchanged, and no voter identity ever reaches the
chain. Member 3's `ElectionRegistry` needs no changes.

## API (camelCase, matching the frontend types)

- Organizer: `POST /elections/{id}/voters/upload` (multipart file) →
  `{imported, skipped, errors:[{row,message}]}`; `GET /elections/{id}/voters`;
  `DELETE /elections/{id}/voters/{voter_id}`.
- Elections gain `code` (shareable 8-char), `description`, `voter_schema`;
  candidates gain `description`.
- Voter: `GET /vote/{code}` (public preview), `POST /vote/{code}/identify`,
  `POST /vote/otp/request`, `POST /vote/otp/verify` (→ token + session),
  `GET /vote/session`, `POST /vote/ballot` (`{candidateId}`), `GET /vote/receipt`.
- `POST /elections/{id}/ballots` and `GET /elections/{id}/receipts/{id}` now
  authenticate with the voter session token (not Supabase).
- Supabase-based `eligible_test_voters` endpoints and table are removed.
