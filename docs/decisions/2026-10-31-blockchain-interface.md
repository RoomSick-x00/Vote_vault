# Locked blockchain interface — 2026-10-31

Approved by the project owner in chat. Supersedes the 2026-10-30 proposal and the old blockchain-interface.md wherever they conflict.

## Interface

The deployed contract remains named ElectionRegistry; the Solidity class name does not affect ABI calls. All writes require OpenZeppelin RELAYER_ROLE. Admin and relayer are separate local accounts.

| Function | Event |
| --- | --- |
| registerElection(bytes32 electionId, bytes32 configHash) | ElectionRegistered(bytes32 indexed electionId, bytes32 configHash, address indexed relayer) |
| openElection(bytes32 electionId) | ElectionOpened(bytes32 indexed electionId, address indexed relayer) |
| publishBallot(bytes32 electionId, bytes32 ballotId, bytes32 commitment) | BallotPublished(bytes32 indexed electionId, bytes32 indexed ballotId, bytes32 commitment, address indexed relayer) |
| closeElection(bytes32 electionId) | ElectionClosed(bytes32 indexed electionId, address indexed relayer) |
| publishResult(bytes32 electionId, bytes32 resultHash) | ResultPublished(bytes32 indexed electionId, bytes32 resultHash, address indexed relayer) |

IDs use backend UUIDv4 left-padding to 32 bytes; zero IDs/hashes are rejected. Ballot and result hash encodings from the 2026-10-30 decision remain unchanged. Names, voter IDs, selections, and ballot nonces never enter contract calls or events.

Identical writes succeed and emit the matching event again. Conflicting configuration, ballot, or result commitments revert. Count unique (electionId, ballotId), not logs. Registration retries never reset state or counts. Open retries after closure acknowledge the historical opening without reopening. Close retries leave the election closed. Ballot calls, including retries, require Open; backend sequencing prevents closing while a ballot job remains unconfirmed. Result calls require Closed.

## Configuration commitment

Candidates are populated after creation, so registration is deferred until opening. In the same transaction that freezes the draft, persist the exact configuration snapshot, canonical JSON, and config_hash in the registration job, then enqueue opening. Draft elections are not yet anchored.

The snapshot includes version VV_CONFIG_1, padded election ID, title, candidates sorted by immutable chain_index (UUID, index, name), and rules (single_candidate, maximum one ballot per voter, optional UTC opening/closing times). No eligibility roster appears in this public snapshot.

Canonical bytes are UTF-8 of Python json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False). Times use six fractional digits and Z. Hash: keccak256(b"VV_CONFIG_1\x00" + canonical_bytes). GET /api/v1/elections/{id}/configuration publishes the exact snapshot, canonical_json, and config_hash to authenticated viewers after freezing. Recompute using canonical_json as returned; do not hash the formatted HTTP response.

## Ordered publication and incomplete closure

Dependency checks enforce register -> open -> ballots -> close -> result. Failed or pending prerequisites block dependent jobs without spending their retry budget. Close also checks that every accepted database ballot has a confirmed publication job.

The close API atomically switches to closing under the same PostgreSQL election row lock used by ballot acceptance. New votes stop immediately. closed_at stays null and results remain unavailable until the close transaction confirms. An unpublishable ballot leaves the election visibly closing/incomplete; publications expose the failed job and error. Organizer retry resumes draining. A result publication may remain pending/failed after closure and is reported separately.

Workers serialize signer use with a process lock plus a PostgreSQL session advisory lock held across per-job commits. SQLite is a local test fallback, not the multi-process deployment concurrency guarantee. Do not run other uncoordinated writers using the same signer.

## Handoff and migration

blockchain/deployments/localhost.json contains chainId, address, abi, deployment block/hash, runtime code hash, and non-secret role addresses. Never contains a key. Redeploy after a chain reset and configure the backend with the new address and an authorized local signer key in environment only.

Run Alembic upgrade head for the closing state. Existing pre-interface jobs lack config_hash: do not silently retrofit or publish those legacy jobs against this deployment. Use fresh synthetic elections/database for the checkpoint; any retained old election needs an explicit reviewed migration of its original configuration and chain records.

This records commitments to a demo backend tally. It does not prove tally correctness, anonymous eligibility, encrypted ballots, or independent tally verification.
