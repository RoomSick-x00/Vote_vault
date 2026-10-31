# Question 07 traceability

Exact requirement: “Develop a secure web-based voting system for campus elections that allows eligible students to vote only once, keeps their choices private, and detects unauthorised changes to recorded votes or election results. The system must also allow election results to be verified independently rather than relying entirely on the administrator or the main application.”

This matrix records repository evidence checked on 2026-10-31. “Last output” below is either a literal checked-in run record or the live command output reproduced in this work; a saved record is explicitly identified as such. The Belenios mode is an isolated synthetic experiment; the current browser workflow remains the older plaintext workflow.

| Clause | Mechanism | Evidence file and test | Exact command | Actual last output | Status |
|---|---|---|---|---|---|
| Eligible students only | Legacy app: voter roster plus OTP; Belenios demo: credential set. No verified registrar/roster freeze connected to Belenios. | `backend/app/services/voter_service.py`; `backend/app/services/belenios_archive.py`; `backend/tests/test_belenios_real_archive.py`; `docs/belenios-real-synthetic/README.md` | `Set-Location backend; $env:VOTEVAULT_TEST_DATABASE_URL='sqlite:///./fresh-test-disposable.db'; ..\.venv\Scripts\python.exe -m pytest tests/test_belenios_real_archive.py -v` | Saved test output: `4 passed`; these tests prove structure/duplicate rules, not eligibility. | PARTIAL |
| Vote only once | Legacy app prevents a second ballot per voter. Belenios supports replacement voting; isolated archive reader and anchor contract reject repeated credentials/tags. | `backend/app/services/ballot_service.py`; `backend/app/services/belenios_archive.py`; `backend/tests/test_belenios_real_archive.py`; `blockchain/contracts/PrivateElectionArchive.sol`; `blockchain/test/PrivateElectionArchive.js`; duplicate fixture `docs/belenios-real-synthetic/duplicate-credential.bel` | `Set-Location blockchain; .\node_modules\.bin\hardhat.cmd test` and `Set-Location backend; .\.venv\Scripts\python.exe -m pytest tests/test_belenios_real_archive.py -v` | Saved: real archive tests `4 passed`; duplicate Belenios archive rejected by our reader. Raw-vote duplicate command evidence in current run not yet produced. | PARTIAL |
| Keep choices private | Legacy database stores `voter_id` with `candidate_id`; it does not satisfy secret ballot privacy. Belenios raw ballots are encrypted and tracker is choice-independent; one-voter demo tally reveals the choice. | `docs/api-contract.md`; `docs/belenios-real-synthetic/README.md`; `backend/app/services/belenios_archive.py`; `backend/tests/test_belenios_real_archive.py` | `Set-Location backend; .\.venv\Scripts\python.exe -m pytest tests/test_belenios_real_archive.py -v` | Saved: `4 passed`. Synthetic README explicitly states “With only one voter, the published tally reveals that voter's choice.” | PARTIAL |
| Detect unauthorized changes to recorded votes | Exact archive bytes checked against a pinned archive hash (`chain.archive`); Belenios proofs independently check encrypted ballot validity. Existing tamper fixture generation currently fails the official parser due non-reproducible tar headers, so independent tamper evidence is absent. | `backend/scripts/verify_belenios_election.py`; `backend/scripts/make_belenios_tamper_copies.py`; `backend/scripts/run_belenios_tamper_tests.ps1`; `docs/belenios-real-synthetic/standalone-verifier-output.txt` | `.\.venv\Scripts\python.exe backend/scripts/make_belenios_tamper_copies.py docs/belenios-real-synthetic/election.bel --selftest` | Live: `ROUNDTRIP DIFFERS`; sizes `19456 20480`; first differing byte `1024 (block 2)`. | UNPROVEN |
| Detect unauthorized changes to election results | Announced result compared with archive result; proofs verify tally; chain seals the full archive bytes. There is no successful independent manipulated-result fixture run yet. | `backend/scripts/verify_belenios_election.py`; `docs/belenios-real-synthetic/announced-result.json`; `docs/belenios-real-synthetic/official-verifier-rerun.txt` | `bash backend/scripts/verify_saved_belenios.sh` (from WSL Ubuntu) | Saved official output: `I: no shuffles to check` / `I: all checks passed`; this is only the unmodified election. | PARTIAL |
| Independent verification, not reliant entirely on admin/main app | Standalone Python script reads public archive/result/receipt and RPC contract reference; needs official Belenios executable and pinned reference supplied out of band. The current anchor is local Hardhat, controlled by the demo operator. | `backend/scripts/verify_belenios_election.py`; `blockchain/scripts/check_belenios_anchor.js`; `docs/belenios-real-synthetic/chain-reference-19c0a74a19ab49aabb6a4f0a088a0da6.json`; `docs/belenios-real-synthetic/standalone-verifier-output.txt` | See exact invocation recorded in `standalone-verifier-output.txt` and `chain-reference-19c0a74a19ab49aabb6a4f0a088a0da6.json`; rerun after starting Hardhat on `127.0.0.1:18546`. | Saved: all six checks `PASS` and `PASS: independent Belenios election verification`. The reference says `synthetic_only: true`; independent retention not established. | PARTIAL |
| On-chain anchor required | Current Belenios anchor covers election/config hash, credential-set hash, accepted ballot hashes and sealed archive hash; result hash is reconciled via archive/result checks rather than a separate public-result commitment. Local Hardhat only. Chain proves records existed at anchor time and anchored values were not changed on that chain; it does not prove eligibility or tally correctness. | `blockchain/contracts/PrivateElectionArchive.sol`; `blockchain/scripts/check_belenios_anchor.js`; chain reference JSON above | `.\backend\scripts\run_belenios_anchor_demo.ps1` (requires local node) | Saved standalone report: `PASS: chain.anchor`; `PASS: chain.archive`; no public testnet evidence. | PARTIAL |

## Five attack cases

| Attack | Chain seal (`chain.archive`) | Independent cryptographic/rule check | Current evidence/status |
|---|---|---|---|
| Duplicate voting (same credential twice) | Reanchored bytes would pass the seal only if an authorized anchor accepted them; original seal should fail. | Archive parser rejects repeated credentials; contract rejects repeated credential tags. Belenios itself allows replacement votes, so official proof check alone is insufficient. | Duplicate archive exists; reader-test output says rejected. App second-submission proof not run in this audit. PARTIAL |
| Unauthorized ballot insertion | Original sealed hash should detect byte changes. | An unissued/invalid credential must fail proof/credential rules; valid newly issued credential could pass crypto and requires roster/eligibility policy. | Fixture currently unusable because tar roundtrip is not reproducible. UNPROVEN |
| Ballot deletion | Original sealed hash should detect byte changes. | Receipt inclusion can show a voter's ballot is absent, but Belenios proof checking may accept a well-formed election with fewer ballots; no trusted expected accepted-ballot set alone proves deletion. | Fixture currently unusable. Independent detection is not established. UNPROVEN |
| Ballot ciphertext modification | Original sealed hash should detect byte changes. | Belenios proof checking should reject invalid ciphertext/proof; receipt inclusion is tracker membership, not choice disclosure. | Fixture currently unusable. UNPROVEN |
| Manipulated result with newly computed member/event hashes | Original sealed hash should detect byte changes. | Expected announced result comparison and tally proof should catch a changed tally. | Fixture currently unusable. UNPROVEN |

Current verified archive diagnostics (live): `election.bel` is 19,456 bytes (38 512-byte blocks), 17 members in tar order, all mtime `1793425925`; it ends exactly at byte 19,456 with no trailing blocks. The generator was replaced with an ordered member-sequence writer that does not append end markers. Live self-test now prints `ROUNDTRIP IDENTICAL`; the generated `.roundtrip.bel` was removed afterward.

The five fixtures were generated and the verifier reports are in `.local/belenios-tamper-c2f3815ae8214eaf84dc59d3cadfbf1d/`. Actual outcomes from that run:

| Fixture | Actual finding | Status and limitation |
|---|---|---|
| Unauthorized insertion | `archive.structure`, `receipt.inclusion`, `result.announced` PASS; `belenios.proofs` INCOMPLETE; `chain.reference` INCOMPLETE | UNPROVEN: invalid credential was not independently rejected because WSL and chain were unavailable. |
| Ballot deletion | `receipt.inclusion` FAIL; `chain.reference` INCOMPLETE | Caught by receipt inclusion; seal check unavailable. |
| Ballot modification | `receipt.inclusion` FAIL; `chain.reference` INCOMPLETE | Caught because altered ballot no longer matches the supplied tracker; seal and proof checks unavailable. |
| Rehashed manipulated result | `result.announced` FAIL; `chain.reference` INCOMPLETE | Caught by separately supplied announced result; proof check unavailable. |
| Duplicate credential | `archive.structure` FAIL: `multiple raw ballots use the same credential` | Caught by repeated-credential rule before proof/chain checks. This fixture duplicates the same ballot event; it is not a second app submission. |

The PowerShell tamper runner now sets a 120-second verifier timeout, asserts expected checks, and errors if a tar-format error is reported as a proof failure. Its execution remains incomplete here because WSL returned `Wsl/E_ACCESSDENIED` and `127.0.0.1:18546` refused the chain connection. Thus no successful `chain.archive` or official Belenios proof outcomes were observed for these attack copies.

Regression commands run after fixing the ordered tar writer and updating its tests:

```text
PYTHONPATH=backend
VOTEVAULT_TEST_DATABASE_URL=sqlite:///C:/Users/mailp/OneDrive/Desktop/VVT/.local/q07-current-test.db
python -m pytest backend/tests/test_belenios_real_archive.py backend/tests/test_belenios_verifier.py -q --basetemp .local/q07-pytest-temp
9 passed, 3 warnings in 2.55s

Set-Location blockchain; .\node_modules\.bin\hardhat.cmd test
13 passing (9s)
```

These tests cover the public archive reader, receipt/result rule checks, repeated raw credentials, and unauthorized contract writes. They do not substitute for the unavailable WSL cryptographic checks or live chain verification, and no second Belenios browser submission was exercised.

## Scope and trust that remains

The Belenios artifacts are synthetic only. The one-voter tally discloses its choice, the synthetic trustee holds the full decryption key, the roster/credential-set freeze is not integrated, and the chain is locally controlled. A registrar can add fake eligible students before roster freeze; an authorized relayer can submit arbitrary tags (denial of service); a dishonest party controlling the local chain can rewrite its entire history. The current legacy browser app stores identity and choice together. Therefore Question 07 is not proven.
