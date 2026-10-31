"""Verify a public Belenios archive against a pinned PrivateElectionArchive.

This script uses no VoteVault application settings, database, or admin secrets.
It requires the official Belenios CLI, a public JSON result, and an independently
pinned RPC/chain/contract/code hash. Missing inputs produce INCOMPLETE.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import shutil
import re
from pathlib import Path
import os

from eth_utils import keccak

from app.services.belenios_archive import IncompleteArchive, InvalidArchive, inspect_archive

def _configuration_hash(facts) -> bytes:
    # Domain-separated hashes of the exact Belenios election and trustee data.
    return keccak(b"VV_BELENIOS_CONFIG_1\x00" + facts.election + b"\x00" + facts.trustees)


def _credentials_hash(facts) -> bytes:
    return keccak(b"VV_BELENIOS_CREDENTIALS_1\x00" + facts.credentials)


def _wsl_path(value: str) -> str:
    match = re.fullmatch(r"([A-Za-z]):[\\/](.*)", value)
    if not match:
        raise ValueError("WSL verifier requires a Windows drive path for the temporary archive")
    return f"/mnt/{match.group(1).lower()}/{match.group(2).replace(chr(92), '/') }"


def _scratch_dir() -> Path:
    path = Path(__file__).resolve().parents[2] / ".local" / "belenios-verifier-tmp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def verify(args) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []

    def add(name: str, status: str, detail: str) -> None:
        checks.append({"id": name, "status": status, "reason": detail})

    archive_path = Path(args.archive)
    if not archive_path.is_file():
        add("archive.available", "INCOMPLETE", "Public archive file is unavailable.")
        return checks
    archive = archive_path.read_bytes()
    try:
        facts = inspect_archive(archive)
        add("archive.structure", "PASS", "Archive members, hashes, and event chain are structurally complete.")
    except IncompleteArchive as exc:
        add("archive.structure", "INCOMPLETE", str(exc))
        return checks
    except InvalidArchive as exc:
        add("archive.structure", "FAIL", str(exc))
        return checks

    if args.receipt:
        included = args.receipt in facts.receipt_trackers
        add("receipt.inclusion", "PASS" if included else "FAIL", "Receipt tracker appears in the accepted raw ballot set." if included else "Receipt tracker is absent from the accepted raw ballot set.")
    else:
        add("receipt.inclusion", "INCOMPLETE", "No voter receipt tracker was supplied.")

    if not args.expected_result:
        add("result.announced", "INCOMPLETE", "No independently published result file was supplied.")
    else:
        try:
            expected = json.loads(Path(args.expected_result).read_text(encoding="utf-8"))
            actual = json.loads(facts.result)
            expected_result = expected.get("result", expected)
            actual_result = actual.get("result")
            same = expected_result == actual_result
            add("result.announced", "PASS" if same else "FAIL", "Announced result equals the tally in the verified archive." if same else "Announced result differs from the archive tally.")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError) as exc:
            add("result.announced", "INCOMPLETE", f"Cannot read announced result: {exc}")

    tool = Path(args.belenios_tool)
    if not args.wsl_distro and not tool.is_file():
        add("belenios.proofs", "INCOMPLETE", "Official Belenios verifier executable is unavailable.")
    else:
        try:
            with tempfile.TemporaryDirectory(prefix="votevault-belenios-check-", dir=_scratch_dir()) as directory:
                Path(directory, "election.bel").write_bytes(archive)
                if args.wsl_distro:
                    wsl = shutil.which("wsl.exe") or shutil.which("wsl")
                    if not wsl:
                        raise FileNotFoundError("wsl.exe not found")
                    presence = subprocess.run([wsl, "-d", args.wsl_distro, "--", "test", "-x", args.belenios_tool],
                                              check=False, capture_output=True, text=True, timeout=args.timeout)
                    if presence.returncode != 0:
                        raise FileNotFoundError("Belenios CLI is not executable in the selected WSL distribution")
                    linux_dir = _wsl_path(directory)
                    command = [wsl, "-d", args.wsl_distro, "--", args.belenios_tool, "election", "verify", "--dir", linux_dir]
                    working_directory = None
                else:
                    command = [str(tool), "election", "verify"]
                    working_directory = directory
                completed = subprocess.run(command, cwd=working_directory,
                                           check=False, capture_output=True, text=True, timeout=args.timeout)
            output = completed.stdout + completed.stderr
            lowered = output.lower()
            if completed.returncode != 0:
                add("belenios.proofs", "FAIL", f"Official verifier exited {completed.returncode}: {output.strip()[-1000:]}")
            elif "no result to check" in lowered or "all checks passed" not in lowered:
                add("belenios.proofs", "INCOMPLETE", "Official verifier did not confirm a completed tally and all checks.")
            else:
                add("belenios.proofs", "PASS", "Official Belenios verifier reports all checks passed for the completed archive.")
        except (OSError, subprocess.TimeoutExpired) as exc:
            add("belenios.proofs", "INCOMPLETE", f"Official verifier could not complete: {exc}")

    required = (args.rpc, args.chain_id is not None, args.contract, args.code_hash, args.election_id)
    if not all(required):
        add("chain.anchor", "INCOMPLETE", "Pinned RPC, chain ID, contract, code hash, and election ID are all required.")
        return checks
    try:
        ballots = []
        for ballot in facts.ballots:
            ballot_id = "0x" + keccak(ballot).hex()
            parsed = json.loads(ballot)
            ballots.append({"ballot_id": ballot_id, "ballot_hash": ballot_id,
                            "credential_tag": "0x" + keccak(parsed["credential"].encode("utf-8")).hex()})
        chain_input = {
            "rpc": args.rpc, "chain_id": args.chain_id, "contract": args.contract,
            "code_hash": args.code_hash, "election_id": args.election_id,
            "archive_hash": "0x" + keccak(archive).hex(),
            "configuration_hash": "0x" + _configuration_hash(facts).hex(),
            "credentials_hash": "0x" + _credentials_hash(facts).hex(), "ballots": ballots,
        }
        root = Path(__file__).resolve().parents[2]
        checker = Path(args.node_checker) if args.node_checker else root / "blockchain" / "scripts" / "check_belenios_anchor.js"
        node = shutil.which("node")
        if not checker.is_file():
            add("chain.anchor", "INCOMPLETE", "Pinned-chain checker is unavailable.")
            return checks
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", prefix="vv-chain-check-", dir=_scratch_dir(), delete=False) as handle:
            json.dump(chain_input, handle)
            chain_input_path = handle.name
        try:
            if args.hardhat_project:
                project = Path(args.hardhat_project).resolve()
                hardhat = project / "node_modules" / ".bin" / "hardhat.cmd"
                if not hardhat.is_file():
                    add("chain.anchor", "INCOMPLETE", "Hardhat local provider is unavailable in the selected project.")
                    return checks
                env = os.environ.copy()
                env.update({"VV_CHAIN_INPUT": chain_input_path, "VV_USE_HARDHAT_PROVIDER": "1"})
                command = ["cmd.exe", "/c", str(hardhat), "run", str(checker), "--network", "localhost"]
                completed = subprocess.run(command, cwd=project, env=env, check=False,
                                           capture_output=True, text=True, timeout=args.timeout)
            elif node:
                completed = subprocess.run([node, str(checker), chain_input_path], cwd=root,
                                           check=False, capture_output=True, text=True, timeout=args.timeout)
            else:
                add("chain.anchor", "INCOMPLETE", "Node.js runtime is unavailable.")
                return checks
            if completed.returncode != 0:
                add("chain.anchor", "INCOMPLETE", f"Independent chain reader failed: {completed.stderr.strip()[-1000:]}")
            else:
                report_line = next((line for line in reversed(completed.stdout.splitlines()) if line.lstrip().startswith("[")), None)
                if report_line is None:
                    add("chain.anchor", "INCOMPLETE", "Independent chain reader returned no check report.")
                else:
                    try:
                        report = json.loads(report_line)
                    except json.JSONDecodeError:
                        report = None
                    if not isinstance(report, list) or any(not isinstance(row, dict) for row in report):
                        add("chain.anchor", "INCOMPLETE", "Independent chain reader returned an invalid check report.")
                    else:
                        checks.extend(report)
        finally:
            Path(chain_input_path).unlink(missing_ok=True)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        add("chain.reference", "FAIL", f"Invalid pinned chain reference or archive data: {exc}")
    except (OSError, subprocess.TimeoutExpired) as exc:
        add("chain.reference", "INCOMPLETE", f"Pinned chain could not be checked: {exc}")
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive")
    parser.add_argument("--belenios-tool", required=True)
    parser.add_argument("--wsl-distro", help="run the Linux verifier through this WSL distribution")
    parser.add_argument("--expected-result")
    parser.add_argument("--receipt", help="Belenios Base64 tracker (does not disclose the vote).")
    parser.add_argument("--rpc")
    parser.add_argument("--chain-id", type=int)
    parser.add_argument("--contract")
    parser.add_argument("--code-hash")
    parser.add_argument("--election-id")
    parser.add_argument("--node-checker", help="override the pinned-chain checker script")
    parser.add_argument("--hardhat-project", help="use a local Hardhat provider for synthetic tests only")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    checks = verify(args)
    for check in checks:
        print(f"{check['status']}: {check['id']}: {check['reason']}")
    overall = "FAIL" if any(c["status"] == "FAIL" for c in checks) else "INCOMPLETE" if any(c["status"] == "INCOMPLETE" for c in checks) else "PASS"
    print(f"{overall}: independent Belenios election verification")
    return {"PASS": 0, "FAIL": 1, "INCOMPLETE": 2}[overall]


if __name__ == "__main__":
    sys.exit(main())
