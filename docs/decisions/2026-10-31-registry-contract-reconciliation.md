# Decision: reconciling the agreed interface with the implemented ElectionRegistry

- Date: 2026-10-31
- Status: **OPEN — team decision required** (raised by Member 2)
- Counterparty: Member 3 (blockchain/integration)
- Context: Member 3 implemented and deployed `ElectionRegistry.sol`
  (`blockchain/contracts/`, deployment manifest in
  `blockchain/deployments/localhost/`) with a Web3 adapter
  (`backend/app/services/chain_registry.py`) and an integration checkpoint
  (`backend/tests/test_chain_checkpoint.py`). The backend publisher
  (`app/blockchain/abi.py`, `app/services/publication_service.py`) was coded
  against the 2026-10-30 interface decision. The two do not interoperate as-is.

## What differs

| # | Agreed (2026-10-30 doc) | Implemented ElectionRegistry | Consequence |
| --- | --- | --- | --- |
| 1 | `registerElection(electionId)` | `registerElection(electionId, configurationCommitment)` | Backend must define and publish an election-configuration commitment (2nd bytes32). |
| 2 | No cross-function ordering gates | Strict state machine: `Unregistered→Registered→Open→Closed`; `publishBallot` only in `Open`, `publishResult` only in `Closed` | Publication jobs must respect order; an unconfirmed `open_election` job makes ballot publications revert (honest failure, but noisy). |
| 3 | All functions idempotent (re-callable with same args) | `publishBallot`/`publishResult`/`registerElection` revert on repeat (`BallotAlreadyPublished`, `ResultAlreadyPublished`) | A lost receipt (tx mined, response lost) followed by a naive re-send **reverts** — the backend would report `failed` for a publication that actually succeeded. Member 3's `reconcile_ballot` recovers this by reading the stored commitment + unique event log instead of re-sending. |
| 4 | Events carry `(…, address indexed relayer)` | Events carry only id/commitment fields (no relayer topic) | Different topic0 hashes; `app/eth_events.py` signatures must be updated to match. |

Also good (adopted from Member 3's work): `RELAYER_ROLE` access control,
code-hash pinning against the deployment manifest, block-hash reorg check, and
"pending" (not failed) on `TransactionNotFound`.

## Options

- **A (Member 2's recommendation): keep ElectionRegistry as canonical.** Member 3's
  state machine and duplicate-rejection give the chain-side stronger integrity,
  and the reconcile path covers the lost-receipt case. Backend adapts:
  1. Load `ElectionRegistry.abi.json` from the deployment manifest instead of the
     hand-written `BALLOT_REGISTRY_ABI`; drop `app/blockchain/abi.py`.
  2. Define `configurationCommitment` = `keccak256("VVCFG1" ‖ 0x00 ‖ electionId ‖ 0x00 ‖ title ‖ 0x00 ‖ uint256(count) ‖ candidateIds in chain order)` (documented, fixed) and add it to the `register_election` payload.
  3. In `publication_service`, before re-sending a `publish_ballot` job (and after any submit error), call `reconcile_ballot(electionId, ballotId, commitment)`; if it returns a confirmed receipt, mark the job confirmed without a new transaction.
  4. Gate submissions: only submit `publish_ballot` when `register_election` and `open_election` jobs are confirmed; only submit `publish_result` when `close_election` is confirmed.
  5. Update `app/eth_events.py` signatures to the implemented events.
- **B: Member 3 aligns the contract to the 2026-10-30 doc** (1-arg register, no gates, idempotent re-submit). Simpler backend, weaker chain-side integrity, contract + deployment redo.
- **C: hybrid** — keep the state machine and configuration commitment, make the three "already done" reverts idempotent no-ops when arguments match. Both sides change a little.

## Interim state (already in place)

- `tests/test_chain_checkpoint.py` now skips automatically when the Hardhat node
  or its env vars are absent, so `pytest tests/` stays green everywhere; it runs
  for real whenever the node is up.
- The backend still runs end-to-end against the py-evm stub with the 2026-10-30
  ABI until this decision lands.

Please reply in chat with A/B/C (or edits); the decision doc will be updated and
the integration work scheduled the same day.
