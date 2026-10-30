# ElectionRegistry interface — approved for implementation

Status: interface approved by the project owner in chat ("that would work"). No separate Member 2 sign-off or backend branch was supplied. Implementation follows this interface; application API adoption still requires Member 2 coordination.

## Identifiers and commitments

- ABI type for election IDs, ballot IDs, and all commitments: `bytes32`.
- API representation: `0x` followed by exactly 64 hexadecimal characters. Reject zero values. Normalize hexadecimal output to lowercase.
- Generate election IDs and ballot IDs from 32 cryptographically random bytes; persist them before submitting any transaction. They must not encode names, student IDs, Supabase user IDs, or candidate choices. Existing application IDs may remain separate database fields with a persisted chain-ID mapping.
- A ballot ID is unique within an election. Every retry uses the original election ID, ballot ID, and commitment. Never generate a new ballot ID for a retry.
- The backend supplies commitment bytes. The contract does not hash, interpret, or verify their preimages.
- Before generating real commitments, Member 2 must specify the versioned, domain-separated canonical serialization and hash algorithm for configuration, ballots, and results. Include a secret random salt where needed to resist guessing low-entropy choices or results; retain salts and preimages off chain. A hash alone does not establish privacy.
- Synthetic integration fixtures can supply fixed nonzero 32-byte values to test recording without claiming a cryptographic protocol.

## Access and state

Use OpenZeppelin `AccessControl`: a separately specified administrator receives `DEFAULT_ADMIN_ROLE`; the backend signer receives `RELAYER_ROLE`. Only the relayer may call the five write functions below. Admin role management uses the inherited OpenZeppelin interface.

Lifecycle: `Unregistered -> Registered -> Open -> Closed`. No reopening, re-registration, or repeated close. Backend HTTP retry handling may return existing state without sending a duplicate state transition.

| Function | Required state | Effect |
| --- | --- | --- |
| `registerElection(bytes32 electionId, bytes32 configurationCommitment)` | Unregistered | Store configuration commitment; become Registered |
| `openElection(bytes32 electionId)` | Registered | Become Open |
| `closeElection(bytes32 electionId)` | Open | Become Closed |
| `publishBallot(bytes32 electionId, bytes32 ballotId, bytes32 commitment)` | Open | Store one immutable commitment for that ballot ID |
| `publishResult(bytes32 electionId, bytes32 commitment)` | Closed, result absent | Store one immutable final result commitment |

All writes reject zero IDs/commitments where applicable. Duplicate ballot IDs revert even if the commitment matches. A second result publication reverts even if the commitment matches. Missing elections and invalid transitions revert. No writes accept plaintext metadata.

Proposed read interface:

```solidity
enum State { Unregistered, Registered, Open, Closed }
function getElection(bytes32 electionId) external view returns (
    State state, bytes32 configurationCommitment,
    bytes32 resultCommitment, uint256 ballotCount
);
function ballotCommitments(bytes32 electionId, bytes32 ballotId)
    external view returns (bytes32);
```

Unknown IDs return zero/default read values. Zero commitments are prohibited so zero unambiguously means absent.

## Events

```solidity
event ElectionRegistered(bytes32 indexed electionId, bytes32 configurationCommitment);
event ElectionOpened(bytes32 indexed electionId);
event ElectionClosed(bytes32 indexed electionId);
event BallotPublished(bytes32 indexed electionId, bytes32 indexed ballotId, bytes32 commitment);
event ResultPublished(bytes32 indexed electionId, bytes32 commitment);
```

No names, student IDs, choices, ballot nonces, salts, or plaintext results appear in contract storage, function arguments, or registry events. Standard AccessControl events contain role/account information only. Blockchain observers can still see transaction timing, relayer addresses, IDs, counts, and commitments.

## Receipt semantics for the local checkpoint

- Local chain ID: `31337`; proposed RPC: `http://127.0.0.1:8545`.
- `pending`: backend has durably accepted a publication job, or submitted it, but has not verified a successful mined transaction and the exact expected registry event. A transaction hash alone is not confirmation.
- `confirmed`: receipt status is `1`, the receipt block is still canonical, and an event from the configured registry address matches the expected operation, IDs, and commitment on chain ID 31337. One mined block suffices for this local demo; this is not a production finality policy.
- `failed`: known reverted transaction, conflicting existing commitment, or terminal validation/configuration failure. RPC timeout or receipt-not-found remains pending/unknown until reconciled; it does not prove transaction failure.
- Proposed receipt response fields: `status`, `election_id`, `ballot_id`, `commitment`, `transaction_hash`, `block_number`, `block_hash`, `chain_id`, `contract_address`. Fields unavailable while pending are null. The backend keeps its private job/receipt ID separately.
- Replace draft API `recorded` with `confirmed` only after team agreement. Add an explicit open operation; creation should initially return registered state rather than claiming open before chain confirmation.

## Backend publication and retry agreement

1. Member 2 enforces authenticated eligibility and one accepted ballot per voter using an atomic database transaction/uniqueness constraint. This is not a contract responsibility.
2. Persist ballot ID, immutable commitment, and publication job in the same acceptance transaction. Serialize signer nonce allocation across workers.
3. Persist signed transaction bytes and the locally computed transaction hash before broadcasting. Retrying an ambiguous broadcast rebroadcasts the same transaction or reconciles its known hash; it must not create a new ballot identity.
4. Before resubmitting a job, reconcile receipts, contract state, and `BallotPublished` logs. A matching existing commitment/event completes the original job; a different commitment is a conflict, not success. Recover the original publication transaction from matching logs if necessary.
5. The contract rejects any second publication for the same `(electionId, ballotId)`, including racing submissions. Test a lost-response retry and verify exactly one matching event and no ballot-count increment on retry.
6. Stop accepting votes and drain/reconcile accepted jobs before closing on chain. Otherwise closure can strand accepted pending votes. Agree close behavior before implementing the endpoint.
7. Keep `LOCAL_CHAIN_SIGNER_PRIVATE_KEY` in backend environment configuration only. Never put it in frontend configuration, deployment output, committed files, logs, or API responses. Use the existing `BALLOT_REGISTRY_CONTRACT_ADDRESS` variable for this registry unless jointly renamed.
8. A local chain restart invalidates prior deployment/state assumptions. Verify chain ID and deployed bytecode, redeploy, and reset/reconcile synthetic demo jobs; an address alone is insufficient.

## Planned handoff after approval

- Solidity source, pinned OpenZeppelin/Hardhat dependencies, normal and rejection-path tests.
- Deployment script and generated ABI plus a non-secret manifest containing deployed address, chain ID, deployment transaction, and block.
- Web3.py adapter for signing/submission, event-checked receipt lookup, and retry reconciliation.
- Local startup/deploy commands and a joint checkpoint comparing backend responses with all lifecycle/ballot/result events.
- Checkpoint report distinguishing actual frontend/backend execution from any standalone synthetic integration harness.

## Member 2 application coordination remaining

Confirm ID mapping, commitment encoding ownership, lifecycle/open endpoint, event/read interface, confirmation naming, durable retry model, and close/drain behavior. Provide the backend branch or checkout and its run/test instructions for the joint checkpoint.

Blockchain records what was committed. This checkpoint does not establish that the demo tally was counted correctly, anonymous eligibility, encrypted ballots, or independent tally verification.
