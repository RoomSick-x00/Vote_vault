# Security review and synthetic verification

VoteVault is an educational prototype. Do not use it for an actual election without independent security auditing, validation, and a redesigned privacy protocol.

## Current assessment

* The database enforces one ballot per roster voter and election; the API also checks eligibility and election state. This does not protect against an operator changing the roster, database, application, or chain relayer. Simultaneous submissions must be tested against PostgreSQL, not just SQLite.
* Privacy fails the stated requirement: `ballots.voter_id` and `ballots.candidate_id` are stored together. The server sees the choice during submission. A database operator can identify votes. Separate tables alone would not solve timing, logs, backups, sessions, or request correlation.
* A ballot is accepted into the database before its asynchronous chain publication. Until confirmation it has no independent anchor; a missing publication is not proof of inclusion. The contract records what its authorized relayer submits, not voter eligibility or consent. A dishonest relayer can inject ballots before close. A receipt is evidence of inclusion of a commitment, not proof of eligibility, correct intent, privacy, or a correct tally.
* The existing audit endpoint checks exported commitments against chain state and hashes, but a result hash alone does not establish a correct tally. The new standalone verifier additionally recounts **synthetic openings** against the contract and compares the computed result to the published result hash. It does not turn this into a private voting system.
* A local Hardhat chain controlled by the same operator as the database is not an independently retained immutable record: it can be reset or rewritten. A meaningful demo needs a separately retained chain or signed checkpoints, with contract address, chain ID and code hash obtained independently. A malicious RPC can lie about state; use an independently trusted node and independently retained finalized chain history. Confirmations, forks, chain governance, contract admin and relayer keys are trust assumptions.
* OTP development mode exposes codes; real delivery does not by itself protect against enumeration, credential compromise, abuse, or roster manipulation. Test with synthetic data only.

## Standalone recount for synthetic elections

The record includes each ballot's candidate index and nonce. **It reveals every individual vote** and receipt holders can be linked to their choices. It is not a secret-ballot or coercion-resistant protocol. Do not export real voting data. The exporter is a local command and is deliberately not exposed as a public API.

After a synthetic election is closed and all chain jobs confirmed, from the repository root in PowerShell (configure `DATABASE_URL` as for the backend):

```powershell
$env:PYTHONPATH = 'backend'
.\.venv\Scripts\python.exe backend\scripts\export_synthetic_record.py <election-uuid> synthetic-record.json --synthetic-only
.\.venv\Scripts\python.exe backend\scripts\verify_election.py synthetic-record.json --rpc <trusted-rpc-url> --chain-id <chain-id> --contract <independently-pinned-address> --code-hash <independently-pinned-runtime-hash> --receipt <optional-receipt-uuid>
```

Omit `--receipt` if no receipt is being checked. Pin these values through a channel independent of the application's export. The verifier needs `web3` and `eth-utils`, but no application imports, database credentials, or application API. Exit codes: 0 PASS, 1 FAIL, 2 INCOMPLETE. It checks the frozen candidate configuration, closed state, exact chain ballot count, distinct ballot IDs, every commitment opening, the recount, the announced result, and the on-chain result commitment. Receipt verification confirms inclusion of the specified ID in that validated set. FAIL indicates an inconsistency; INCOMPLETE indicates that state or trusted chain access could not be established.

This detects changes, deletions and additions **relative to the independently trusted anchored set**. It cannot detect fraudulent ballots already submitted by the authorized relayer, a false roster, a coerced voter, a compromised client, a dishonest RPC, a reset chain, or a voter who accepted an unanchored receipt. A result that was maliciously published from an altered ballot set before anchoring can still verify. Individual inclusion requires the voter to retain and check their receipt.

## Work still required

Replace the identified plaintext ballot design with a reviewed privacy-preserving eligibility and verifiable tally protocol using established components; specify its trust boundaries and migration path. Establish an independently retained public record and demonstrate the full workflow against it. Test ballot eligibility and duplicate submissions on PostgreSQL, including concurrent requests and adversarial operator scenarios. Review authentication, rate limits, transport, operational key management, logs, and all UI claims. Obtain an independent audit before any real deployment.
