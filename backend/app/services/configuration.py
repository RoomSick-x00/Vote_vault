"""Public, versioned configuration snapshot; no eligibility roster or voter IDs."""
import json
from eth_utils import keccak
from sqlalchemy import select
from app.models import Candidate
from app.services.ids import uuid_to_bytes32_hex


def freeze_configuration(db, election):
    candidates = db.scalars(select(Candidate).where(Candidate.election_id == election.id).order_by(Candidate.chain_index)).all()
    snapshot = {
        "version": "VV_CONFIG_1", "election_id": uuid_to_bytes32_hex(election.id),
        "title": election.title,
        "candidates": [{"candidate_id": str(c.id), "chain_index": c.chain_index, "name": c.name} for c in candidates],
        "rules": {"selection": "single_candidate", "max_ballots_per_voter": 1,
                  "opens_at": election.opens_at.isoformat(timespec="microseconds") + "Z" if election.opens_at else None,
                  "closes_at": election.closes_at.isoformat(timespec="microseconds") + "Z" if election.closes_at else None},
    }
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return {"configuration": snapshot, "canonical_json": canonical,
            "config_hash": "0x" + keccak(b"VV_CONFIG_1\x00" + canonical.encode("utf-8")).hex()}
