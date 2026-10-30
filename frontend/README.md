# VoteVault - Frontend

React + TypeScript + Vite + Tailwind frontend for the VoteVault election platform. It talks to the FastAPI backend; there is no mock server or demo data in this repo.

## Run

```bash
npm ci
npm run dev       # http://localhost:5173 (proxies /api to FastAPI)
npm run build     # type-check + production build into dist/
```

For production, serve `dist/` behind the same origin as the API (reverse-proxy `/api`), or set `VITE_API_BASE_URL` at build time. Camera QR scanning requires HTTPS (or localhost). `VITE_BACKEND_URL` in `.env` configures the Vite development proxy.

## Flows

**Organiser** - `/signup` -> `/organizer` -> `/organizer/create` -> `/organizer/elections/:id`
1. Create an election and choose voter identity columns (name and/or roll number) and OTP channels (email and/or phone).
2. Add candidates and upload a CSV/XLSX voter roster containing the configured identity and contact fields.
3. Open voting and share the election code or QR. Close the election and review publication and result status.

**Voter** - `/voter` -> `/vote/:code`
1. Enter the election code or scan the organiser's QR.
2. Identify using the fields requested by the organiser, then verify the registered contact with a one-time code.
3. Cast one ballot and view the publication receipt.

## Backend contract (FastAPI, all under `/api/v1`)

Errors may use FastAPI's `{ "detail": "..." }` shape or the backend's `{ "error": { "code": "...", "message": "..." } }` envelope; both are handled.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/signup` `{email,password,full_name,organization_name}` | - | Create organiser session and organisation |
| POST | `/auth/login` `{email,password}` | - | Create organiser session |
| GET | `/auth/me` | organiser | Current organiser |
| GET | `/organizations` | organiser | List memberships |
| POST | `/elections` `{organization_id,title,description?,voter_schema?}` | organiser | Create draft election with share code |
| GET | `/elections/{id}` | organiser | Get election and candidates |
| POST | `/elections/{id}/candidates` | organiser | Add candidates while draft |
| POST | `/elections/{id}/open` | organiser | Freeze configuration and open voting |
| POST | `/elections/{id}/close` | organiser | Close and queue result publication |
| GET | `/elections/{id}/voters` | organiser | List roster entries |
| POST | `/elections/{id}/voters/upload` (multipart `file`) | organiser | Import CSV/XLSX roster |
| DELETE | `/elections/{id}/voters/{voterId}` | organiser | Remove voter while draft |
| GET | `/elections/{id}/publications` | organiser | Publication jobs and transaction references |
| GET | `/elections/{id}/results` | organiser (closed) | Backend demo tally and publication status |
| GET | `/vote/{code}` | public | Public election preview |
| POST | `/vote/{code}/identify` `{name?,rollNo?}` | public | Match identity against roster |
| POST | `/vote/otp/request` `{identifyToken,channel,contact}` | public | Request OTP; `devCode` is development-only |
| POST | `/vote/otp/verify` `{identifyToken,otp}` | public | Verify OTP and issue scoped voter token |
| GET | `/vote/session` | voter token | Get voter session and candidate list |
| POST | `/vote/ballot` `{candidateId}` | voter token | Submit ballot |
| GET | `/vote/receipt` | voter token | Get latest receipt and publication status |

Organiser tokens are stored in `localStorage`. Short-lived voter tokens are stored in `sessionStorage` and remain available to load and refresh the receipt until they expire or are cleared. The frontend keeps the organiser election ID index locally because the backend does not yet expose a list-my-elections endpoint.

The receipt confirms submission and publication status. The backend demo tally is not independently verified; encrypted ballots, anonymous eligibility, and independent tally verification are not implemented.
