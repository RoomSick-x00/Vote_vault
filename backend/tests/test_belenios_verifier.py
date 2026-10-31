import json
from pathlib import Path
from types import SimpleNamespace
import os
import tempfile
import shutil
import hashlib

import pytest

from scripts.verify_belenios_election import verify
from scripts.make_belenios_tamper_copies import create_copies
from app.services.belenios_archive import inspect_archive


@pytest.fixture(scope="module")
def public_artifacts():
    override = os.environ.get("VOTEVAULT_BELENIOS_ARTIFACTS")
    path = Path(override) if override else Path(__file__).resolve().parents[2] / "docs" / "belenios-real-synthetic"
    if not path.is_dir():
        pytest.skip("real synthetic Belenios archive is unavailable")
    return path


def args(archive, **overrides):
    values = dict(
        archive=str(archive), belenios_tool="does-not-exist", wsl_distro=None,
        expected_result=None, receipt=None, rpc=None, chain_id=None,
        contract=None, code_hash=None, election_id=None, timeout=1,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def statuses(checks):
    return {item["id"]: item["status"] for item in checks}


def result_file(value):
    path = Path(__file__).resolve().parents[2] / ".local"
    path.mkdir(exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="belenios-expected-", suffix=".json", dir=path)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump({"result": value}, handle)
    return Path(name)


def test_real_archive_fails_closed_without_proofs_or_pinned_chain(public_artifacts):
    expected = result_file([[1, 0]])
    receipt = (public_artifacts / "receipt.txt").read_text().strip()
    try:
        checks = verify(args(public_artifacts / "election.bel", expected_result=str(expected), receipt=receipt))
    finally:
        expected.unlink(missing_ok=True)
    actual = statuses(checks)
    assert actual["archive.structure"] == "PASS"
    assert actual["receipt.inclusion"] == "PASS"
    assert actual["result.announced"] == "PASS"
    assert actual["belenios.proofs"] == "INCOMPLETE"
    assert actual["chain.anchor"] == "INCOMPLETE"


def test_missing_tally_never_passes(public_artifacts):
    checks = verify(args(public_artifacts / "missing-tally.bel"))
    assert statuses(checks) == {"archive.structure": "INCOMPLETE"}


def test_repeated_real_credential_is_rejected(public_artifacts):
    checks = verify(args(public_artifacts / "duplicate-credential.bel"))
    assert statuses(checks) == {"archive.structure": "FAIL"}


def test_changed_result_fails_against_announced_result(public_artifacts):
    expected = result_file([[0, 1]])
    try:
        checks = verify(args(public_artifacts / "election.bel", expected_result=str(expected)))
    finally:
        expected.unlink(missing_ok=True)
    assert statuses(checks)["result.announced"] == "FAIL"


def test_tamper_fixtures_rehash_archive_structure_without_touching_source(public_artifacts):
    temp_root = Path(__file__).resolve().parents[2] / ".local"
    temp_root.mkdir(exist_ok=True)
    source_hash = hashlib.sha256((public_artifacts / "election.bel").read_bytes()).hexdigest()
    output = Path(tempfile.mkdtemp(prefix="belenios-tamper-fixtures-", dir=temp_root))
    try:
        paths = create_copies(public_artifacts / "election.bel", output)
        assert len(paths) == 5
        assert len(inspect_archive(paths[0].read_bytes()).ballots) == 2
        assert len(inspect_archive(paths[1].read_bytes()).ballots) == 0
        assert len(inspect_archive(paths[2].read_bytes()).ballots) == 1
        result = json.loads(inspect_archive(paths[3].read_bytes()).result)
        assert result["result"] == [[0, 1]]
        duplicate_checks = verify(args(paths[4]))
        assert statuses(duplicate_checks) == {"archive.structure": "FAIL"}

        expected = result_file([[1, 0]])
        receipt = (public_artifacts / "receipt.txt").read_text().strip()
        try:
            deletion = statuses(verify(args(paths[1], expected_result=str(expected), receipt=receipt)))
            modification = statuses(verify(args(paths[2], expected_result=str(expected), receipt=receipt)))
            manipulated_result = statuses(verify(args(paths[3], expected_result=str(expected), receipt=receipt)))
            insertion_checks = verify(args(paths[0], expected_result=str(expected), receipt=receipt))
        finally:
            expected.unlink(missing_ok=True)
        assert deletion["receipt.inclusion"] == "FAIL"
        assert modification["receipt.inclusion"] == "FAIL"
        assert manipulated_result["result.announced"] == "FAIL"
        insertion = statuses(insertion_checks)
        assert insertion["archive.structure"] == "PASS"
        assert insertion["belenios.proofs"] == "INCOMPLETE"
        assert insertion["chain.anchor"] == "INCOMPLETE"
        proof_reason = next(c["reason"] for c in insertion_checks if c["id"] == "belenios.proofs")
        assert "tar.header_of_bytes" not in proof_reason.lower()
        assert "all checks passed" in (public_artifacts / "official-verifier-rerun.txt").read_text().lower()
        assert hashlib.sha256((public_artifacts / "election.bel").read_bytes()).hexdigest() == source_hash
    finally:
        shutil.rmtree(output)

