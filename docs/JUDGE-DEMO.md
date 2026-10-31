# Local judge demo (PowerShell)

Use a fresh disposable database and a fresh Hardhat chain. Never run the roster migration on a retained database: migration 0004 deletes legacy ballot and eligibility data. The explorer checks record integrity and inclusion; it does not establish ballot secrecy, eligibility, or tally correctness. The backend stores voter identity and candidate choice together.

Prerequisites: Node dependencies installed in `blockchain` and `frontend`, Python dependencies installed in `.venv`, and a Supabase project configured for organizer signup/login. Configure `backend/.env` using `backend/.env.example`: set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, JWT verification (`SUPABASE_JWKS_URL` or `SUPABASE_JWT_SECRET`), and a random `VOTER_SESSION_SECRET`. Do not commit this file. Supabase signup may require email confirmation depending on the project. Development OTP is displayed on screen; no real email/SMS is sent.

From the repository root, in a first terminal:

```powershell
cd blockchain
npm run node
```

In a second terminal:

```powershell
cd blockchain
npm run deploy:local
```

Set `BLOCKCHAIN_RPC_URL=http://127.0.0.1:8545`, `BLOCKCHAIN_CHAIN_ID=31337`, and `BLOCKCHAIN_DEPLOYMENT_FILE=../blockchain/deployments/localhost.json` in `backend/.env`. Set `LOCAL_CHAIN_SIGNER_PRIVATE_KEY` to the local Hardhat account #1 private key printed by the node. This key is public and must only be used on a disposable development chain. Keep `APP_ENV=development` and `RUN_BACKGROUND_PUBLISHER=true`.

In a third terminal, from the repository root:

```powershell
cd backend
$env:DATABASE_URL='sqlite:///./judge-demo-disposable.db'
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Choose a new filename each time; do not point this at retained data. In a fourth terminal:

```powershell
cd frontend
npm run dev
```

Open the printed URL. Sign up or sign in as an organizer, create an election and candidates, upload `docs/demo-roster.csv`, select roll number and email verification, and open voting. Share the election code. In a voter tab identify as DEMO001, use `asha@example.com`, enter the displayed development OTP, select a candidate, and wait for a confirmed receipt. Repeat in another tab with DEMO002 and `rahul@example.com`. Close the election on the organizer page and wait for `closed` and result publication. Open Audit Explorer from the navigation and enter the election UUID shown on the manage page. Inspect the checks and expanded public records. In Tamper Lab try changing a ballot commitment and changing result data; compare the altered checks with the unchanged control. A missing transaction or unavailable chain produces INCOMPLETE, not a pass.

The explorer talks to the backend's configured RPC and deployment manifest. A chain restart discards the local chain; start with a fresh database and deploy again. Organizer authentication requires a working Supabase project; there is no local organizer auth provider. The browser workflow and chain-backed Tamper Lab were exercised on 2026-10-31 using disposable SQLite, Hardhat, synthetic organizer authentication, and development OTP. Real Supabase authentication and real OTP delivery were not tested.

## Verification commands and observed results

On 2026-10-31, `npm test` in `blockchain` passed 9 tests; `npm run build` in `frontend` passed (large bundle warning). The following backend run passed 68 tests with 3 skipped on disposable SQLite; it does not prove PostgreSQL concurrency behavior:

```powershell
cd backend
$env:VOTEVAULT_TEST_DATABASE_URL='sqlite:///./fresh-test-disposable.db'
..\.venv\Scripts\python.exe -m pytest -q
```

With the disposable node and freshly deployed contract running, the real-chain synthetic verification smoke test passed its control and three mutations:

```powershell
cd backend
$env:PYTHONPATH='.'
..\.venv\Scripts\python.exe scripts/audit_chain_check.py
```

This smoke test writes synthetic transactions to the local chain. It does not run the browser or authenticate to Supabase.

Browser acceptance on 2026-10-31: synthetic signup, election and candidates, roster upload and verification setup, two OTP votes and confirmed receipts, closure, backend tally 1–1, result publication, all public audit checks passing, and ballot/result mutation failures with an unchanged passing control. The synthetic authentication adapter was in-memory and is not a Supabase integration test.
