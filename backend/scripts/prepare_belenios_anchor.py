"""Create a public-only anchor manifest for one synthetic Belenios archive."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from eth_utils import keccak
from app.services.belenios_archive import inspect_archive


def prepare(raw: bytes) -> dict:
    facts = inspect_archive(raw)
    ballots = []
    for ballot in facts.ballots:
        parsed = json.loads(ballot)
        ballots.append({
            "ballot_id": "0x" + keccak(ballot).hex(),
            "ballot_hash": "0x" + keccak(ballot).hex(),
            "credential_tag": "0x" + keccak(parsed["credential"].encode("utf-8")).hex(),
        })
    return {
        "version": "VV_BELENIOS_ANCHOR_1",
        "election_id": "0x" + keccak(b"VV_BELENIOS_ELECTION_ID_1\x00" + facts.election).hex(),
        "configuration_hash": "0x" + keccak(b"VV_BELENIOS_CONFIG_1\x00" + facts.election + b"\x00" + facts.trustees).hex(),
        "credentials_hash": "0x" + keccak(b"VV_BELENIOS_CREDENTIALS_1\x00" + facts.credentials).hex(),
        "archive_hash": "0x" + keccak(raw).hex(),
        "ballot_count": len(facts.ballots),
        "ballots": ballots,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive")
    parser.add_argument("output")
    args = parser.parse_args()
    manifest = prepare(Path(args.archive).read_bytes())
    Path(args.output).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared public anchor manifest for {manifest['ballot_count']} ballots.")


if __name__ == "__main__":
    main()
