"""Create re-hashed altered copies of the real synthetic Belenios archive.

These are attack fixtures only. They never overwrite the source archive.
Members keep the original order and the original V7-style tar header layout.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import tarfile
from pathlib import Path


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _compact(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _load(path: Path):
    """Return (header_bytes, seq), preserving original member order.

    Items are ["data", digest, raw] or ["event", event_dict, original_raw].
    """
    with tarfile.open(path, "r:") as tar:
        items = [(m.name, tar.extractfile(m).read()) for m in tar.getmembers()]
    if not items or items[0][0] != "BELENIOS":
        raise ValueError("not a Belenios archive")
    seq = []
    for name, raw in items[1:]:
        if name.endswith(".data.json"):
            seq.append(["data", name[: -len(".data.json")], raw])
        elif name.endswith(".event.json"):
            seq.append(["event", json.loads(raw), raw])
        else:
            raise ValueError(f"unexpected member: {name}")
    return items[0][1], seq


def _tar_bytes(members: list[tuple[str, bytes]], template: bytes) -> bytes:
    """Write Belenios V7-style tar members, without end-of-archive blocks."""
    out = bytearray()
    for name, raw in members:
        h = bytearray(template)
        h[0:100] = name.encode().ljust(100, b"\0")
        h[124:136] = f"{len(raw):011o}".encode() + template[135:136]
        h[148:156] = b"        "
        h[148:156] = f"{sum(h):06o}".encode() + b"\0 "
        out += h + raw + b"\0" * (-len(raw) % 512)
    return bytes(out)


def _emit(path: Path, header: bytes, seq: list, template: bytes) -> None:
    members: list[tuple[str, bytes]] = [("BELENIOS", header)]
    parent = None
    height = 0
    for kind, value, raw in seq:
        if kind == "data":
            members.append((value + ".data.json", raw))
            continue
        event = value
        event["height"] = height
        if parent is None:
            event.pop("parent", None)
        else:
            event["parent"] = parent
        if raw is None or json.loads(raw) != event:
            raw = _compact(event)
        parent = _digest(raw)
        members.append((parent + ".event.json", raw))
        height += 1
    path.write_bytes(_tar_bytes(members, template))


def _first_event(seq: list, event_type: str) -> int:
    return next(i for i, item in enumerate(seq) if item[0] == "event" and item[1]["type"] == event_type)


def _data_index(seq: list, digest: str) -> int:
    return next(i for i, item in enumerate(seq) if item[0] == "data" and item[1] == digest)


def _replace_payload_data(seq: list, event: dict, mutate) -> None:
    i = _data_index(seq, event["payload"])
    changed = _compact(mutate(json.loads(seq[i][2])))
    new = _digest(changed)
    seq[i][1], seq[i][2] = new, changed
    event["payload"] = new


def create_copies(source: Path, output: Path) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output}")
    created = []
    template = source.read_bytes()[:512]

    # Unauthorized insertion: extra ballot with an unissued credential.
    header, seq = _load(source)
    ballot_event = seq[_first_event(seq, "Ballot")][1]
    ballot = json.loads(seq[_data_index(seq, ballot_event["payload"])][2])
    ballot["credential"] = "00" * 32
    raw = _compact(ballot)
    digest = _digest(raw)
    new_event = copy.deepcopy(ballot_event)
    new_event["payload"] = digest
    at = _first_event(seq, "EndBallots")
    seq[at:at] = [["data", digest, raw], ["event", new_event, None]]
    target = output / "unauthorized-insertion.bel"
    _emit(target, header, seq, template)
    created.append(target)

    # Ballot deletion.
    header, seq = _load(source)
    i = _first_event(seq, "Ballot")
    payload = seq[i][1]["payload"]
    del seq[i]
    del seq[_data_index(seq, payload)]
    target = output / "ballot-deletion.bel"
    _emit(target, header, seq, template)
    created.append(target)

    # Ballot modification.
    header, seq = _load(source)
    ballot_event = seq[_first_event(seq, "Ballot")][1]

    def modify_ballot(value):
        alpha = value["answers"][0]["choices"][0]["alpha"]
        value["answers"][0]["choices"][0]["alpha"] = ("0" if alpha[0] != "0" else "1") + alpha[1:]
        return value

    _replace_payload_data(seq, ballot_event, modify_ballot)
    target = output / "ballot-modification.bel"
    _emit(target, header, seq, template)
    created.append(target)

    # Manipulated result with a newly computed matching member/event hash.
    header, seq = _load(source)
    result_event = seq[_first_event(seq, "Result")][1]

    def falsify_result(value):
        value["result"] = [[0, 1]]
        return value

    _replace_payload_data(seq, result_event, falsify_result)
    target = output / "manipulated-result-rehashed.bel"
    _emit(target, header, seq, template)
    created.append(target)

    # Duplicate credential: the same ballot appears twice in the raw archive.
    header, seq = _load(source)
    dup = copy.deepcopy(seq[_first_event(seq, "Ballot")][1])
    seq.insert(_first_event(seq, "EndBallots"), ["event", dup, None])
    target = output / "duplicate-credential.bel"
    _emit(target, header, seq, template)
    created.append(target)
    return created


def selftest(source: Path) -> None:
    raw = source.read_bytes()
    header, seq = _load(source)
    out = source.with_suffix(".roundtrip.bel")
    _emit(out, header, seq, raw[:512])
    new = out.read_bytes()
    print("ROUNDTRIP IDENTICAL" if new == raw else "ROUNDTRIP DIFFERS")
    if new != raw:
        print(len(raw), len(new))
        i = next((k for k in range(min(len(raw), len(new))) if raw[k] != new[k]), None)
        print("first differing byte:", i, "(block", None if i is None else i // 512, ")")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("output_directory", nargs="?")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest(Path(args.source))
        return
    if not args.output_directory:
        parser.error("output_directory is required unless --selftest is used")
    for path in create_copies(Path(args.source), Path(args.output_directory)):
        print(path)


if __name__ == "__main__":
    main()
