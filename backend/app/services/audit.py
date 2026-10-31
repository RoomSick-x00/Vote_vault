"""Public record export and chain-backed integrity checks; no voter identities or choices."""
import json
import uuid
from eth_utils import keccak
from sqlalchemy import select
from web3 import Web3
from app.blockchain.publisher import load_deployment, _to_chain_receipt
from app.eth_events import EVENT_SIGNATURES, find_matching_event_log
from app.models import PublicationJob
from app.services.ids import uuid_to_bytes32_hex, uuid_to_bytes32
from app.services.tally_service import compute_tally


def export_record(db, election):
    jobs = list(db.scalars(select(PublicationJob).where(PublicationJob.election_id == election.id).order_by(PublicationJob.created_at)))
    register = next((j for j in jobs if j.job_type == "register_election"), None)
    return {"election_id": str(election.id), "status": election.status,
            "configuration": register.payload.get("configuration") if register else None,
            "records": [{"type": j.job_type, "payload": {k: v for k, v in j.payload.items() if k in ("election_id", "config_hash", "ballot_id", "commitment", "result_hash")}, "tx_hash": j.tx_hash} for j in jobs],
            "result": compute_tally(db, election) if election.status == "closed" else None}


def verify_record(record, settings):
    checks = []
    def add(id, status, reason): checks.append({"id": id, "status": status, "reason": reason})
    try:
        eid = uuid_to_bytes32_hex(uuid.UUID(record["election_id"]))
        records = record["records"]
        assert isinstance(records, list)
    except (ValueError, KeyError, TypeError, AssertionError):
        return [{"id": "record.format", "status": "FAIL", "reason": "Invalid election ID or records."}]
    cfg = record.get("configuration")
    reg = next((r for r in records if r.get("type") == "register_election"), None)
    if cfg and reg:
        canonical = json.dumps(cfg, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = "0x" + keccak(b"VV_CONFIG_1\x00" + canonical.encode()).hex()
        ok = digest.lower() == reg.get("payload", {}).get("config_hash", "").lower() and cfg.get("election_id") == eid
        add("config.hash", "PASS" if ok else "FAIL", "Configuration and election ID match the exported commitment." if ok else "Configuration or election ID differs from the exported commitment.")
    else: add("config.hash", "INCOMPLETE", "Frozen configuration or registration record missing.")
    result = record.get("result")
    result_job = next((r for r in records if r.get("type") == "publish_result"), None)
    if result is not None and result_job:
        try:
            packed = bytes.fromhex(eid[2:]) + int(result["total_ballots"]).to_bytes(32, "big")
            for row in result["counts"]:
                packed += uuid_to_bytes32(uuid.UUID(row["candidate_id"])) + int(row["votes"]).to_bytes(32, "big")
            digest = "0x" + keccak(packed).hex()
            ok = digest.lower() == result_job["payload"]["result_hash"].lower()
            add("result.hash", "PASS" if ok else "FAIL", "Result data matches its commitment; this does not prove correct counting." if ok else "Result data differs from its commitment.")
        except (KeyError, ValueError, TypeError, OverflowError): add("result.hash", "FAIL", "Invalid result data.")
    else: add("result.hash", "INCOMPLETE", "Result data or publication record not yet available.")
    try:
        if not settings.blockchain_rpc_url: raise ValueError("Blockchain RPC is not configured")
        manifest = load_deployment(settings.blockchain_deployment_file)
        w3 = Web3(Web3.HTTPProvider(settings.blockchain_rpc_url, request_kwargs={"timeout": 5}))
        if w3.eth.chain_id != int(manifest["chainId"]): raise ValueError("Chain ID differs from deployment")
        address = Web3.to_checksum_address(manifest["address"])
        code = w3.eth.get_code(address)
        if not code or (manifest.get("runtimeCodeHash") and ("0x" + keccak(code).hex()).lower() != manifest["runtimeCodeHash"].lower()): raise ValueError("Deployed contract code does not match manifest")
        contract = w3.eth.contract(address=address, abi=manifest["abi"])
        state, config_hash, result_hash, count = contract.functions.getElection(bytes.fromhex(eid[2:])).call()
        add("chain.election", "PASS" if state else "FAIL", "Election found on deployed contract." if state else "Election ID is not registered on the deployed contract.")
        if reg:
            ok = bytes(config_hash).hex() == reg["payload"].get("config_hash", "")[2:].lower()
            add("chain.config", "PASS" if ok else "FAIL", "Contract configuration commitment matches." if ok else "Contract configuration commitment differs.")
        ballots = [r for r in records if r.get("type") == "publish_ballot"]
        ids = [r.get("payload", {}).get("ballot_id") for r in ballots]
        ok = len(set(ids)) == len(ids) and len(ids) == count
        add("chain.ballot_count", "PASS" if ok else "FAIL", f"Export has {len(ids)} ballot records; contract has {count} unique ballots.")
        for i, row in enumerate(records):
            typ, payload, tx = row.get("type"), row.get("payload", {}), row.get("tx_hash")
            check_id = f"event.{i}.{typ}"
            if typ not in EVENT_SIGNATURES:
                add(check_id, "FAIL", "Unknown record type."); continue
            if payload.get("election_id") != eid:
                add(check_id, "FAIL", "Record election ID does not match export."); continue
            if not tx:
                add(check_id, "INCOMPLETE", "Transaction reference not yet available."); continue
            try:
                receipt = _to_chain_receipt(w3.eth.get_transaction_receipt(tx), address)
                topics = [bytes.fromhex(eid[2:])]
                if typ == "publish_ballot": topics.append(bytes.fromhex(payload["ballot_id"][2:]))
                key = {"register_election": "config_hash", "publish_ballot": "commitment", "publish_result": "result_hash"}.get(typ)
                data = bytes.fromhex(payload[key][2:]) if key else None
                ok = receipt.status == 1 and bool(find_matching_event_log(receipt.logs, EVENT_SIGNATURES[typ], topics, data))
                if typ == "publish_ballot":
                    ok = ok and contract.functions.ballotCommitments(bytes.fromhex(eid[2:]), topics[1]).call() == data
                if typ == "publish_result": ok = ok and bytes(result_hash) == data
                add(check_id, "PASS" if ok else "FAIL", "Transaction log and contract state match." if ok else "Transaction log or contract state differs from this record.")
            except Exception as exc: add(check_id, "INCOMPLETE", f"Could not read transaction or record: {exc}")
    except Exception as exc:
        add("chain.connection", "INCOMPLETE", f"Chain verification unavailable: {exc}")
    return checks
