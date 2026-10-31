"""Structural tests only: these fixtures contain no cryptographic proofs."""
import hashlib
import io
import json
import tarfile

import pytest
from app.services.belenios_archive import IncompleteArchive, InvalidArchive, inspect_archive


def fixture_archive(*, duplicate=False, omit_result=False, omit_credentials=False):
    entries = [("BELENIOS", b'{"version":1,"timestamp":"0"}')]
    def add(value, kind="data"):
        raw = json.dumps(value, separators=(",", ":")).encode()
        digest = hashlib.sha256(raw).digest()
        entries.append((digest.hex() + f".{kind}.json", raw))
        return digest.hex()
    election = add({"uuid": "synthetic"})
    credentials = add(["public-credential"])
    trustees = add(["trustee"])
    setup = add({"election": election, "credentials": credentials, "trustees": trustees})
    parent = None
    height = 0
    def event(typ, payload=None):
        nonlocal parent, height
        item = {"height": height, "type": typ}
        if parent is not None: item["parent"] = parent
        if payload is not None: item["payload"] = payload
        parent = add(item, "event")
        height += 1
    event("Setup", setup)
    event("Ballot", add({"credential": "public-credential", "ciphertext": "synthetic"}))
    if duplicate:
        event("Ballot", add({"credential": "public-credential", "ciphertext": "other"}))
    event("EndBallots")
    encrypted_tally = add({"synthetic": "encrypted-tally"})
    event("EncryptedTally", add({"num_tallied": 1, "total_weight": 1, "encrypted_tally": encrypted_tally}))
    partial_decryption = add({"synthetic": "partial-decryption"})
    event("PartialDecryption", add({"owner": 1, "payload": partial_decryption}))
    if not omit_result: event("Result", add({"result": [[1]]}))
    if omit_credentials:
        entries = [(name, data) for name, data in entries if not name.startswith(credentials + ".")]
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for name, data in entries:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def test_raw_archive_structure_and_first_vote_policy():
    facts = inspect_archive(fixture_archive())
    assert len(facts.ballots) == len(facts.receipt_trackers) == 1
    assert json.loads(facts.result)["result"] == [[1]]
    with pytest.raises(InvalidArchive, match="same credential"):
        inspect_archive(fixture_archive(duplicate=True))
    with pytest.raises(IncompleteArchive, match="result missing"):
        inspect_archive(fixture_archive(omit_result=True))
    with pytest.raises(IncompleteArchive, match="referenced archive data is missing"):
        inspect_archive(fixture_archive(omit_credentials=True))


def test_member_tampering_is_rejected():
    raw = fixture_archive()
    tampered = raw.replace(b'"ciphertext":"synthetic"', b'"ciphertext":"synth3tic"', 1)
    assert tampered != raw
    with pytest.raises(InvalidArchive, match="hash mismatch"):
        inspect_archive(tampered)


def test_duplicate_member_and_unreferenced_data_are_rejected():
    raw = fixture_archive()
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as source:
        members = source.getmembers()
        contents = [(member.name, source.extractfile(member).read()) for member in members]
    duplicate = io.BytesIO()
    with tarfile.open(fileobj=duplicate, mode="w:") as target:
        for name, data in contents + [contents[1]]:
            info = tarfile.TarInfo(name); info.size = len(data)
            target.addfile(info, io.BytesIO(data))
    with pytest.raises(InvalidArchive, match="duplicate archive member"):
        inspect_archive(duplicate.getvalue())

    orphan = io.BytesIO()
    extra = b'{"orphan":true}'
    name = hashlib.sha256(extra).hexdigest() + ".data.json"
    with tarfile.open(fileobj=orphan, mode="w:") as target:
        for member_name, data in contents:
            info = tarfile.TarInfo(member_name); info.size = len(data)
            target.addfile(info, io.BytesIO(data))
        info = tarfile.TarInfo(name); info.size = len(extra)
        target.addfile(info, io.BytesIO(extra))
    with pytest.raises(InvalidArchive, match="unreferenced data"):
        inspect_archive(orphan.getvalue())
