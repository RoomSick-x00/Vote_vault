import copy
import json
import uuid
from eth_utils import keccak
from app.config import Settings
from app.services.audit import verify_record
from app.services.ids import uuid_to_bytes32, uuid_to_bytes32_hex


def test_copy_mutations_use_same_verifier_and_preserve_control():
    election = uuid.uuid4()
    candidate = uuid.uuid4()
    eid = uuid_to_bytes32_hex(election)
    config = {"version": "VV_CONFIG_1", "election_id": eid, "title": "Demo", "candidates": [], "rules": {}}
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    config_hash = "0x" + keccak(b"VV_CONFIG_1\x00" + canonical.encode()).hex()
    result_hash = "0x" + keccak(uuid_to_bytes32(election) + (1).to_bytes(32, "big") + uuid_to_bytes32(candidate) + (1).to_bytes(32, "big")).hex()
    record = {"election_id": str(election), "configuration": config, "records": [
        {"type": "register_election", "payload": {"election_id": eid, "config_hash": config_hash}, "tx_hash": None},
        {"type": "publish_result", "payload": {"election_id": eid, "result_hash": result_hash}, "tx_hash": None}],
        "result": {"total_ballots": 1, "counts": [{"candidate_id": str(candidate), "votes": 1}]}}
    settings = Settings(blockchain_rpc_url="")
    def statuses(data): return {c["id"]: c["status"] for c in verify_record(data, settings)}
    assert statuses(record) == {"config.hash": "PASS", "result.hash": "PASS", "chain.connection": "INCOMPLETE"}
    altered = copy.deepcopy(record)
    altered["result"]["counts"][0]["votes"] = 2
    assert statuses(altered)["result.hash"] == "FAIL"
    altered = copy.deepcopy(record)
    altered["election_id"] = str(uuid.uuid4())
    assert statuses(altered)["config.hash"] == "FAIL"
    assert statuses(record)["result.hash"] == "PASS"
