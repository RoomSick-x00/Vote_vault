"""Integration checks for archives created by the real Belenios 3.3 tool."""
import os
import json
import io
import tarfile
from pathlib import Path

import pytest
from app.services.belenios_archive import IncompleteArchive, InvalidArchive, inspect_archive


@pytest.fixture(scope="module")
def public_artifacts():
    override = os.environ.get("VOTEVAULT_BELENIOS_ARTIFACTS")
    path = Path(override) if override else Path(__file__).resolve().parents[2] / "docs" / "belenios-real-synthetic"
    if not path.is_dir():
        pytest.skip("real synthetic Belenios archive is unavailable")
    return path


def test_real_tallied_archive_and_receipt(public_artifacts):
    facts = inspect_archive((public_artifacts / "election.bel").read_bytes())
    assert len(facts.ballots) == 1
    assert (public_artifacts / "receipt.txt").read_text().strip() in facts.receipt_trackers
    assert [[int(count) for count in row] for row in json.loads(facts.result)["result"]] == [[1, 0]]
    assert "all checks passed" in (public_artifacts / "official-verifier.txt").read_text().lower()


def test_real_missing_tally_is_incomplete(public_artifacts):
    assert "no result to check" in (public_artifacts / "missing-tally-official.txt").read_text().lower()
    with pytest.raises(IncompleteArchive):
        inspect_archive((public_artifacts / "missing-tally.bel").read_bytes())


def test_real_repeat_credential_is_rejected(public_artifacts):
    assert "all checks passed" in (public_artifacts / "duplicate-official.txt").read_text().lower()
    with pytest.raises(InvalidArchive, match="same credential"):
        inspect_archive((public_artifacts / "duplicate-credential.bel").read_bytes())


def test_missing_nested_real_tally_data_is_incomplete(public_artifacts):
    archive = (public_artifacts / "election.bel").read_bytes()
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as original:
        members = original.getmembers()
        contents = {member.name: original.extractfile(member).read() for member in members}
        events = [json.loads(contents[m.name]) for m in members if m.name.endswith(".event.json")]
        event = next(event for event in events if event["type"] == "EncryptedTally")
        tally = json.loads(contents[event["payload"] + ".data.json"])
        removed = tally["encrypted_tally"] + ".data.json"
        assert removed in contents
        copy = io.BytesIO()
        with tarfile.open(fileobj=copy, mode="w") as modified:
            for member in members:
                if member.name != removed:
                    modified.addfile(member, io.BytesIO(contents[member.name]))
    with pytest.raises(IncompleteArchive, match="referenced archive data is missing"):
        inspect_archive(copy.getvalue())
