"""Disposable Hardhat verification smoke test. Requires a freshly deployed local registry."""
import copy
import json
import uuid
from eth_utils import keccak
from web3 import Web3
from app.blockchain.publisher import load_deployment
from app.config import Settings
from app.services.audit import verify_record
from app.services.ids import uuid_to_bytes32, uuid_to_bytes32_hex

settings = Settings(blockchain_rpc_url="http://127.0.0.1:8545")
manifest = load_deployment(settings.blockchain_deployment_file)
w3 = Web3(Web3.HTTPProvider(settings.blockchain_rpc_url))
contract = w3.eth.contract(address=Web3.to_checksum_address(manifest["address"]), abi=manifest["abi"])
election, candidate, ballot = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
eid, bid = uuid_to_bytes32_hex(election), uuid_to_bytes32_hex(ballot)
config = {"version": "VV_CONFIG_1", "election_id": eid, "title": "Synthetic", "candidates": [], "rules": {}}
canonical = json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
config_hash = "0x" + keccak(b"VV_CONFIG_1\x00" + canonical.encode()).hex()
commitment = "0x" + keccak(text="synthetic ballot").hex()
result_hash = "0x" + keccak(uuid_to_bytes32(election) + (1).to_bytes(32, "big") + uuid_to_bytes32(candidate) + (1).to_bytes(32, "big")).hex()
records = []
def publish(typ, name, payload, args):
    tx = getattr(contract.functions, name)(*args).transact({"from": manifest["relayer"]})
    w3.eth.wait_for_transaction_receipt(tx)
    records.append({"type": typ, "payload": payload, "tx_hash": "0x" + tx.hex()})
publish("register_election", "registerElection", {"election_id": eid, "config_hash": config_hash}, [eid, config_hash])
publish("open_election", "openElection", {"election_id": eid}, [eid])
publish("publish_ballot", "publishBallot", {"election_id": eid, "ballot_id": bid, "commitment": commitment}, [eid, bid, commitment])
publish("close_election", "closeElection", {"election_id": eid}, [eid])
publish("publish_result", "publishResult", {"election_id": eid, "result_hash": result_hash}, [eid, result_hash])
record = {"election_id": str(election), "configuration": config, "records": records, "result": {"total_ballots": 1, "counts": [{"candidate_id": str(candidate), "votes": 1}]}}
def statuses(value): return {c["id"]: c["status"] for c in verify_record(value, settings)}
control = statuses(record)
assert all(v == "PASS" for v in control.values()), control
changed = copy.deepcopy(record); changed["records"][2]["payload"]["commitment"] = "0x" + "00" * 32
assert statuses(changed)["event.2.publish_ballot"] == "FAIL"
changed = copy.deepcopy(record); changed["result"]["counts"][0]["votes"] += 1
assert statuses(changed)["result.hash"] == "FAIL"
changed = copy.deepcopy(record); changed["records"].pop(2)
assert statuses(changed)["chain.ballot_count"] == "FAIL"
assert statuses(record) == control
print("PASS: real chain control and ballot, result, removal mutations", election)
