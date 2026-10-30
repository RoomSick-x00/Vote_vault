# Run VoteVault locally — step by step

Verified working order: Hardhat chain → backend → frontend. Anything already
set up once (venv, `.env`, node_modules) only needs doing again on a fresh
machine or after a `git clean`.

> **ZCode terminal note:** if you run these commands inside a ZCode terminal,
> prefix every `python`/`alembic`/`uvicorn` command with `env -u LD_LIBRARY_PATH`
> (the ZCode AppImage injects a libpython that breaks venvs). From a normal
> terminal (kitty etc.) no prefix is needed. The commands below include it.

---

## 0. One-time setup (skip if `.venv` and `node_modules` exist)

```bash
cd ~/Book/hack/Vote_vault

# Python venv (uv-managed Python 3.12; system python is shadowed by an AppImage shim)
uv venv .venv --python 3.12
uv pip install -e ./backend -p .venv/bin/python

# Blockchain deps
cd blockchain && npm ci && cd ..

# Frontend deps
cd frontend && npm install && cd ..

# Database (SQLite dev DB at backend/votevault-dev.db; Postgres optional)
cd backend && env -u LD_LIBRARY_PATH ../.venv/bin/python -m alembic upgrade head && cd ..
```

`backend/.env` must exist (gitignored). Required keys:

```ini
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_ANON_KEY=sb_publishable_...
SUPABASE_JWKS_URL=https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json
VOTER_SESSION_SECRET=<any long random hex>
```

The chain block below is added in step 2 after deploying.

---

## 1. Stop anything already running

```bash
kill $(ss -tlnp | grep -E ':(8000|8545|517[0-9])' | grep -oP 'pid=\K[0-9]+' | sort -u) 2>/dev/null
```

## 2. Start the Hardhat chain (terminal 1) and deploy

```bash
cd blockchain
npm run node            # keeps running; JSON-RPC at http://127.0.0.1:8545
```

New terminal (only on first run, or whenever the chain was restarted):

```bash
cd blockchain
npm run deploy:local
```

This rewrites `blockchain/deployments/localhost.json`. Copy the fresh values
into `backend/.env` (append or update):

```ini
BLOCKCHAIN_RPC_URL=http://127.0.0.1:8545
BLOCKCHAIN_CHAIN_ID=31337
BALLOT_REGISTRY_CONTRACT_ADDRESS=<"address" from the deploy output>
LOCAL_CHAIN_SIGNER_PRIVATE_KEY=0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d
```

The key is Hardhat account #1 — the relayer the deploy script authorizes.
It is a public disposable dev key; never use a real key here.

**Every chain restart invalidates the old contract** — redeploy and update the
address, then use "Retry failed" on the manage page for stuck jobs.

## 3. Start the backend (terminal 2)

```bash
cd backend
env -u LD_LIBRARY_PATH ../.venv/bin/python -m uvicorn app.main:app --port 8000
```

Check: `curl localhost:8000/` → `"publisher": "web3"` (means chain env loaded;
`"unavailable"` means the chain block is missing/blank in `.env`).

## 4. Start the frontend (terminal 3)

```bash
cd frontend
npm run dev
```

Open the printed URL — `http://localhost:5173` (or 5174 if 5173 is taken).

---

## 5. Demo walkthrough

**Organizer:**
1. Sign in (`member1.demo@gmail.com` / `hackathon2026`) or sign up fresh.
   New accounts with no organisation: the create page has an inline
   "name your organisation" card.
2. Create election: title, optional description/schedule, identity field
   (rollNo), OTP channel (email), at least 2 candidates.
3. On the manage page upload the roster (CSV, header row required):

   ```csv
   name,rollNo,email
   Asha Verma,CS2101,asha.verma@gmail.com
   Rahul Nair,CS2102,rahul.nair@gmail.com
   ```
4. "Open voting" → confirm. The publications monitor shows
   register/open jobs confirming within seconds.

**Voter (same browser is fine — voter session is per-tab):**
5. Open the election link from the share card (`/vote/<CODE>`), or paste the
   code in the Voter Hub.
6. Enter roll number → registered email → the OTP is displayed on screen
   (dev mode; no mail provider wired) → verify.
7. Pick a candidate → confirm → receipt page with the commitment hash.
   Status flips to "recorded on chain" once the publisher confirms.

**Back to organizer:**
8. "Close & tally" → confirm. Status goes `closing` → `closed` when the close
   publication confirms on chain (seconds with the node running).
9. Results page shows the demo tally, the mandatory disclaimer, and the
   on-chain result publication status.

## 6. Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Could not find platform dependent libraries` / weird venv errors | You're in a ZCode terminal — use the `env -u LD_LIBRARY_PATH` prefix |
| Backend won't start, `python-multipart` error | `uv pip install python-multipart -p .venv/bin/python` |
| Migration error `duplicate column name` | Half-applied migration — delete `backend/votevault-dev.db` and re-run `alembic upgrade head` |
| Login 401 `alg not allowed` / `Invalid audience` | Old backend process — restart it (fixes are in `app/auth/tokens.py`) |
| Signup 403 `EMAIL_CONFIRMATION_REQUIRED` | Supabase → Authentication → Sign In/Providers → Email → turn off "Confirm email" |
| Publications stuck `pending` / `failed` with `blockchain publication is not configured` | Chain not running or contract address stale → step 2, then "Retry failed" |
| Election stuck in `closing` | Close job needs on-chain confirmation — same fix as above |
| Dashboard shows elections from another machine | Expected: no list endpoint yet; the dashboard lists elections created in that browser |
