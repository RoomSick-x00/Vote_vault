# Local blockchain handoff

Scope: ElectionRegistry records supplied commitments. It does not enforce eligibility or one vote per voter, verify a tally, encrypt ballots, or provide anonymous eligibility. Member 2 owns eligibility, atomic ballot acceptance, durable jobs, and the demo tally. The frontend/backend application checkpoint remains dependent on their implementation.

## Install and test (PowerShell, from repository root)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-chain.txt
Set-Location blockchain
npm ci
npm test
```

The lockfile pins dependencies; solc 0.8.24 comes from npm and compilation does not fetch a separate compiler. This local setup uses Hardhat 2.22.18 with the available Node 18 runtime. A move to the current Hardhat 3/Node 22 toolchain should be coordinated separately. Do not use this setup as a production deployment recipe.

## Start and deploy

Terminal 1, inside `blockchain/`:

```powershell
npm run node
```

The node listens on loopback port 8545, chain ID **31337**. Hardhat displays public development accounts/keys: these are disposable local-chain credentials only. Never use them on another network.

Terminal 2, inside `blockchain/`:

```powershell
npm run deploy:local
```

Outputs:

- `blockchain/deployments/localhost/ElectionRegistry.abi.json`: ABI for Web3.py.
- `blockchain/deployments/localhost/deployment.json`: actual address, chain ID, relayer/admin addresses, deployment transaction/block, runtime bytecode hash. The manifest contains no keys.

The first local account deploys/administers; the second receives RELAYER_ROLE. Configure the backend privately with its local relayer key, RPC URL, chain ID, and manifest contract address using the existing names in `.env.example`. That file deliberately contains names only. `Registry.from_env` reads process environment; it does not automatically load dotenv files.

## Real-chain synthetic checkpoint

With the node running and deployment complete, from `blockchain/`:

```powershell
npx hardhat run scripts/checkpoint.js --network localhost
```

This funds a fresh ephemeral local signer, grants it relayer permission, passes its key to Python via environment only, runs the Web3.py tests, then revokes that permission. It does not print or save the key. The default Python path is the root `.venv`; set `CHECKPOINT_PYTHON` to override.

The test registers/opens an election, publishes a synthetic ballot, checks the exact event and confirmed receipt, recovers a simulated lost-response retry with exactly one ballot event/count, closes, and publishes a synthetic result commitment. `docs/checkpoint-evidence.json` captures actual hashes, blocks, expected commitments, and event-checked receipt responses. This is a service integration harness, not a running FastAPI/React/Supabase demo or proof of correct tallying. Synthetic commitments test recording only.

## Member 2 integration

Import `Registry` from `app.services.chain_registry`. Load the ABI/manifest with `Registry.from_env(deployment_directory)`.

1. Authenticate/authorize the API caller and enforce one accepted ballot per voter atomically in PostgreSQL. Persist opaque bytes32 chain IDs and immutable backend-generated commitments with an outbox job.
2. Under a cross-worker signer/nonce lock, reserve a nonce and call `prepare(function_name, *args, nonce=...)`. Store the returned signed transaction and transaction hash durably before `broadcast`. These are internal job fields, not API response payloads.
3. Call `receipt_status(hash, event_name, expected_fields)`; return `pending` until a canonical successful receipt contains the exact expected registry event. Return `confirmed` only after that check. A mismatched event or revert fails. RPC errors are transient/unknown; callers should retry lookup, not blindly create another publication.
4. Before retrying a ballot job, use `reconcile_ballot(election_id, ballot_id, commitment, deployment_block)`. A confirmed match recovers the original transaction. A conflicting commitment raises an error. If absent, reconcile any known signed transaction/hash before rebroadcasting the same bytes. Never generate a new ballot ID for retry. Contract duplicate rejection remains the final guard even for racing jobs.
5. Stop accepting new ballots and drain/reconcile accepted publication jobs before closing. The contract deliberately rejects later ballots and reopening.

The adapter does not implement a durable queue, database transaction, cross-process nonce lock, HTTP authorization, or commitment hashing scheme. Member 2 must supply those before connecting an actual API worker. Receipt ownership checks belong in the API.

See `blockchain-interface.md` for the agreed chain interface and remaining application coordination. The earlier API draft still needs an explicit open route and adoption of `confirmed` instead of `recorded`.

After a node reset, redeploy and reset/reconcile test data. Reusing an address does not preserve old chain history. The adapter checks chain ID, bytecode hash, and signer permission, but Member 2 must track the deployment instance and invalidate stale jobs/receipts.

## Verified checkpoint results

- Hardhat contract suite: **8 passing**.
- Web3.py/Pytest real-chain suite: **2 passing**. The checkpoint command completed successfully, including ephemeral relayer-role revocation.
- One third-party `websockets.legacy` deprecation warning was emitted; no test failed in the final run.
- Deployed registry: `0x5FbDB2315678afecb367f032d93F642f64180aa3`, chain ID `31337`. This address/manifest describes the local chain instance, not any public deployment.
- All five lifecycle/publication operations produced confirmed receipts with exactly matching event values. Lost-response recovery returned the original ballot transaction; a duplicate publication was rejected, with one ballot event and count of one.
- The local node was left running on loopback for inspection. In this workspace its PID is stored in ignored `.local/hardhat.pid`; stop that specific process when finished. Logs in `.local/` include Hardhat’s disposable development-account output and must not be committed.

Remaining joint checkpoint: obtain Member 2’s backend branch and connect authenticated vote acceptance/outbox/receipt routes, then run the actual frontend/backend flow and compare its responses against these events. No application-level checkpoint is claimed by this report. The team also needs the final commitment preimage/serialization scheme; synthetic fixtures do not define it.

Implementation references: [Hardhat](https://v2.hardhat.org/hardhat-runner/docs/getting-started), [OpenZeppelin access control](https://docs.openzeppelin.com/contracts/5.x/access-control), [Web3.py transaction signing](https://web3py.readthedocs.io/en/stable/transactions.html).
