# VoteVault — Frontend

React + TypeScript + Vite + Tailwind frontend for the VoteVault election platform. It talks only to the FastAPI backend; there is no mock server or demo data in this repo.

## Run

```bash
npm install
cp .env.example .env     # set VITE_BACKEND_URL if FastAPI is not on :8000
npm run dev              # http://localhost:5173  (proxies /api -> FastAPI)
npm run build            # type-check + production build into dist/
```

For production, serve `dist/` behind the same origin as the API (reverse-proxy `/api`), or set `VITE_API_BASE_URL` at build time. Camera QR scanning requires HTTPS (or localhost).

## Flows

**Organiser** — `/signup` (mandatory) → `/organizer` → `/organizer/create` → `/organizer/elections/:id`
1. Create an election, choose identity columns (name / roll no.) and OTP channels (email / phone). These become the mandatory voter-list columns.
2. Add voters by **CSV / Excel upload** or **manual entry**.
3. Share the election **code + QR**, open voting, close and publish results.

**Voter** — `/voter` (Voter Hub) → `/vote/:code`
1. Enter the code or scan the QR (QR encodes `https://<host>/vote/<CODE>`).
2. Enter name / roll no. → backend matches against the voter list.
3. Enter registered email or phone → OTP → verify → cast ballot → receipt.

## Backend contract (FastAPI, all under `/api`)

Errors may be `{ "detail": "..." }` (FastAPI default) or `{ "error": "CODE", "message": "..." }`; both are handled.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/register` `{name,email,password,organization?}` | – | → `{user, token}` |
| POST | `/auth/login` `{email,password}` | – | → `{user, token}` |
| GET | `/auth/me` | organiser | current organiser |
| POST | `/auth/logout` | organiser | |
| GET / POST | `/elections` | organiser | list own / create `{title,description,candidates[],voterSchema}` → `Election` incl. `code` |
| GET | `/elections/{id}` | organiser | |
| PATCH | `/elections/{id}/status` `{status:"open"\|"closed"}` | organiser | |
| GET / POST | `/elections/{id}/voters` | organiser | list / add `{name?,rollNo?,email?,phone?}` |
| DELETE | `/elections/{id}/voters/{voterId}` | organiser | |
| POST | `/elections/{id}/voters/upload` (multipart `file`) | organiser | → `{imported, skipped, errors:[{row,message}]}`; headers `name, roll_no, email, phone` |
| GET | `/elections/{id}/results` | public (closed) | tally + chain reference |
| GET | `/elections/{id}/verify-receipt?code=` | public | receipt lookup |
| GET | `/receipts/{receiptId}` | public | |
| GET | `/vote/{code}` | public | `PublicElection` (`id, code, title, description, status, voterSchema`) |
| POST | `/vote/{code}/identify` `{name?,rollNo?}` | public | match against list → `{identifyToken, channels}` |
| POST | `/vote/otp/request` `{identifyToken, channel, contact}` | public | contact must match the matched voter; → `{resendAfter, expiresIn, channel}` |
| POST | `/vote/otp/verify` `{identifyToken, otp}` | public | → `{token, session}` (voter token) |
| GET | `/vote/session` | voter token | `{election, candidates, voterName, hasVoted, receiptId?}` |
| POST | `/vote/ballot` `{candidateId}` | voter token | → `BallotReceipt` |

Authentication uses `Authorization: Bearer <token>`. The organiser token is kept in `localStorage`; the voter token in `sessionStorage` and is discarded after voting. Types live in `src/types/index.ts`.

Backend notes: return identical errors for "not in list" cases where possible, rate-limit `identify` and OTP endpoints, and keep CORS/proxy configured for the frontend origin.
