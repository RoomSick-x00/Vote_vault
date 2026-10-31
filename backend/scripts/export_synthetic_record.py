"""Export secret ballot openings for SYNTHETIC test elections only.

This intentionally reveals every choice. Never use with real voters.
Run from the repository root with PYTHONPATH=backend and the backend .env set.
"""
import argparse
import json
import uuid

from sqlalchemy import select
from app.config import Settings
from app.db.session import create_engine_and_sessionmaker
from app.models import Ballot, Candidate, Election
from app.services.audit import export_record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("election_id", type=uuid.UUID)
    parser.add_argument("output")
    parser.add_argument("--synthetic-only", action="store_true", required=True,
                        help="confirm that every voter and vote is synthetic")
    args = parser.parse_args()
    engine, factory = create_engine_and_sessionmaker(Settings().database_url)
    try:
        with factory() as db:
            election = db.get(Election, args.election_id)
            if election is None or election.status != "closed":
                parser.error("election must exist and be closed")
            record = export_record(db, election)
            rows = db.execute(select(Ballot, Candidate.chain_index).join(
                Candidate, Candidate.id == Ballot.candidate_id
            ).where(Ballot.election_id == election.id, Ballot.accepted.is_(True))).all()
            record["ballot_openings"] = sorted([
                {"ballot_id": str(ballot.id), "candidate_chain_index": index, "nonce": ballot.nonce}
                for ballot, index in rows
            ], key=lambda row: row["ballot_id"])
        with open(args.output, "x", encoding="utf-8") as out:
            json.dump(record, out, indent=2, ensure_ascii=False)
        print("Exported synthetic-only record; it reveals ballot choices.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
