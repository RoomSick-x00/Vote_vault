"""Read Belenios 3.3 public archives; this module does NOT verify proofs.

This deliberately exposes raw ballot events, including credentials that
Belenios's tally reader would discard as revotes. Do not use its output as an
election verification verdict without Belenios and independent chain checks.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import tarfile
from dataclasses import dataclass

_ENTRY = re.compile(r"([0-9a-f]{64})\.(data|event)\.json\Z")
_MAX_ARCHIVE = 100 * 1024 * 1024
_MAX_ENTRY = 20 * 1024 * 1024


class InvalidArchive(ValueError):
    """An archive contradicts its recorded content or event history."""


class IncompleteArchive(ValueError):
    """An archive does not contain evidence needed for a completed tally."""


@dataclass(frozen=True)
class ArchiveFacts:
    election: bytes
    credentials: bytes
    trustees: bytes
    ballots: tuple[bytes, ...]
    receipt_trackers: tuple[str, ...]
    result: bytes


def _json(raw: bytes):
    def no_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise InvalidArchive("duplicate JSON key")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=no_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise InvalidArchive("invalid JSON in archive") from exc


def _hash_ref(value):
    # Belenios 3.3.0 archives serialize event and setup hashes as lowercase
    # hexadecimal. Ballot trackers shown to voters use unpadded Base64.
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise InvalidArchive("invalid Belenios hash reference")
    return value


def inspect_archive(raw: bytes) -> ArchiveFacts:
    """Check archive structure and expose inputs for later proof/chain checks.

    This does not check ciphertext validity, signatures, decryption proofs,
    eligibility, tally correctness, chain anchoring, or election authenticity.
    """
    if len(raw) > _MAX_ARCHIVE:
        raise InvalidArchive("archive exceeds size limit")
    items = {}
    data_hashes = set()
    referenced_data = set()
    member_names = set()
    events = []
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tar:
            members = tar.getmembers()
            if not members or members[0].name != "BELENIOS":
                raise InvalidArchive("missing Belenios archive header")
            for index, member in enumerate(members):
                if member.name in member_names:
                    raise InvalidArchive("duplicate archive member")
                member_names.add(member.name)
                if not member.isfile() or member.size > _MAX_ENTRY:
                    raise InvalidArchive("invalid archive member")
                data = tar.extractfile(member).read()
                if index == 0:
                    header = _json(data)
                    if not isinstance(header, dict) or header.get("version") != 1:
                        raise InvalidArchive("unsupported Belenios archive version")
                    continue
                match = _ENTRY.fullmatch(member.name)
                if match is None:
                    raise InvalidArchive("invalid archive member name")
                digest, kind = match.groups()
                if hashlib.sha256(data).hexdigest() != digest:
                    raise InvalidArchive("archive member hash mismatch")
                previous = items.get(digest)
                if previous is not None and previous != data:
                    raise InvalidArchive("conflicting archive members")
                items[digest] = data
                if kind == "event":
                    events.append((digest, _json(data)))
                else:
                    data_hashes.add(digest)
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise IncompleteArchive("archive cannot be read completely") from exc

    def resolve(ref):
        if ref is None:
            raise IncompleteArchive("event or setup reference is missing")
        digest = _hash_ref(ref)
        if digest not in items:
            raise IncompleteArchive("referenced archive data is missing")
        referenced_data.add(digest)
        return items[digest]

    setup = None
    ballots = []
    result = None
    end_ballots = False
    tally = False
    decryptions = 0
    parent = None
    for height, (digest, event) in enumerate(events):
        if not isinstance(event, dict) or type(event.get("height")) is not int or event["height"] != height:
            raise InvalidArchive("invalid event height")
        previous = event.get("parent")
        if (None if previous is None else _hash_ref(previous)) != parent:
            raise InvalidArchive("event chain is not contiguous")
        parent = digest
        typ, payload = event.get("type"), event.get("payload")
        if typ == "Setup":
            if height != 0 or setup is not None:
                raise InvalidArchive("invalid setup event")
            setup = _json(resolve(payload))
            if not isinstance(setup, dict):
                raise InvalidArchive("invalid setup data")
        elif typ == "Ballot":
            if setup is None or end_ballots:
                raise InvalidArchive("ballot outside voting phase")
            ballots.append(resolve(payload))
        elif typ == "EndBallots":
            if setup is None or end_ballots or payload is not None:
                raise InvalidArchive("invalid end of voting")
            end_ballots = True
        elif typ == "EncryptedTally":
            if not end_ballots or tally:
                raise InvalidArchive("invalid encrypted tally event")
            sized_tally = _json(resolve(payload))
            if not isinstance(sized_tally, dict):
                raise InvalidArchive("invalid encrypted tally record")
            resolve(sized_tally.get("encrypted_tally"))
            tally = True
        elif typ == "PartialDecryption":
            if not tally or result is not None:
                raise InvalidArchive("invalid decryption event")
            owned = _json(resolve(payload))
            if not isinstance(owned, dict):
                raise InvalidArchive("invalid partial decryption record")
            resolve(owned.get("payload"))
            decryptions += 1
        elif typ == "Result":
            if not tally or result is not None:
                raise InvalidArchive("invalid result event")
            result = resolve(payload)
        elif typ in ("Shuffle", "EndShuffles"):
            raise InvalidArchive("non-homomorphic elections are not supported")
        else:
            raise InvalidArchive("unknown Belenios event")
    if setup is None or not end_ballots or not tally or not decryptions or result is None:
        raise IncompleteArchive("closed election, tally, decryptions or result missing")
    try:
        election, credentials, trustees = (resolve(setup[key]) for key in ("election", "credentials", "trustees"))
    except KeyError as exc:
        raise IncompleteArchive("setup data is missing") from exc
    if setup.get("credentials_certificate") is not None:
        resolve(setup["credentials_certificate"])
    if data_hashes != referenced_data:
        raise InvalidArchive("archive contains unreferenced data")
    seen = set()
    trackers = []
    for ballot in ballots:
        parsed = _json(ballot)
        if not isinstance(parsed, dict) or not isinstance(parsed.get("credential"), str):
            raise InvalidArchive("ballot credential missing")
        credential = parsed["credential"]
        if credential in seen:
            raise InvalidArchive("multiple raw ballots use the same credential")
        seen.add(credential)
        trackers.append(base64.b64encode(hashlib.sha256(ballot).digest()).decode().rstrip("="))
    return ArchiveFacts(election, credentials, trustees, tuple(ballots), tuple(trackers), result)
