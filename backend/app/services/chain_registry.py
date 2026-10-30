"""Local ElectionRegistry adapter. Persistence/nonce locking belongs to the job worker.

No voter authorization, database acceptance, or commitment construction occurs here.
"""
import json
import os
import re
from pathlib import Path
from hexbytes import HexBytes
from web3 import Web3
from web3.exceptions import TransactionNotFound
from web3.logs import DISCARD


def bytes32(value):
    if not isinstance(value, str) or not re.fullmatch(r"0x[0-9a-fA-F]{64}", value) or int(value, 16) == 0:
        raise ValueError("Expected nonzero 0x-prefixed bytes32")
    return value.lower()


class Registry:
    def __init__(self, rpc_url, address, abi, private_key, expected_code_hash, chain_id=31337):
        if chain_id != 31337:
            raise ValueError("This adapter is restricted to the local checkpoint")
        self.w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 10}))
        if self.w3.eth.chain_id != chain_id:
            raise ValueError("Unexpected chain ID")
        self.chain_id = chain_id
        self.account = self.w3.eth.account.from_key(private_key)
        self.contract = self.w3.eth.contract(address=Web3.to_checksum_address(address), abi=abi)
        code = self.w3.eth.get_code(self.contract.address)
        if not code or Web3.to_hex(Web3.keccak(code)).lower() != expected_code_hash.lower():
            raise ValueError("Registry bytecode differs from deployment manifest")
        role = self.contract.functions.RELAYER_ROLE().call()
        if not self.contract.functions.hasRole(role, self.account.address).call():
            raise ValueError("Signer does not have RELAYER_ROLE")

    @classmethod
    def from_env(cls, deployment_dir):
        folder = Path(deployment_dir)
        manifest = json.loads((folder / "deployment.json").read_text())
        address = os.environ["BALLOT_REGISTRY_CONTRACT_ADDRESS"]
        if address.lower() != manifest["address"].lower():
            raise ValueError("Address does not match deployment manifest")
        return cls(os.environ["BLOCKCHAIN_RPC_URL"], address,
                   json.loads((folder / "ElectionRegistry.abi.json").read_text()),
                   os.environ["LOCAL_CHAIN_SIGNER_PRIVATE_KEY"], manifest["runtimeCodeHash"],
                   int(os.environ["BLOCKCHAIN_CHAIN_ID"]))

    def prepare(self, function_name, *args, nonce):
        """Caller holds a cross-worker signer lock and reserves/persists nonce.

        Persist returned hash/raw bytes BEFORE broadcast. Raw bytes are private job
        data, never API response fields. Never log the signer key or signed payload.
        """
        arity = {"registerElection": 2, "openElection": 1, "closeElection": 1,
                 "publishBallot": 3, "publishResult": 2}
        if function_name not in arity or len(args) != arity[function_name]:
            raise ValueError("Unsupported registry operation")
        fn = getattr(self.contract.functions, function_name)(*[bytes32(arg) for arg in args])
        tx = fn.build_transaction({"from": self.account.address, "nonce": nonce,
                                   "chainId": self.chain_id, "gasPrice": self.w3.eth.gas_price})
        signed = self.account.sign_transaction(tx)
        return {"transaction_hash": Web3.to_hex(signed.hash),
                "raw_transaction": Web3.to_hex(signed.raw_transaction)}

    def broadcast(self, prepared):
        raw = HexBytes(prepared["raw_transaction"])
        if Web3.to_hex(Web3.keccak(raw)) != prepared["transaction_hash"]:
            raise ValueError("Signed transaction hash mismatch")
        # Broadcast errors/timeouts are ambiguous. Reconcile known hash before retry.
        return Web3.to_hex(self.w3.eth.send_raw_transaction(raw))

    def receipt_status(self, tx_hash, event_name, expected):
        """Confirm only exact event arguments from this registry in a canonical receipt."""
        schemas = {"ElectionRegistered": {"electionId", "configHash"},
                   "ElectionOpened": {"electionId"}, "ElectionClosed": {"electionId"},
                   "BallotPublished": {"electionId", "ballotId", "commitment"},
                   "ResultPublished": {"electionId", "resultHash"}}
        if event_name not in schemas or set(expected) != schemas[event_name]:
            raise ValueError("Exact event fields required")
        expected = {k: bytes32(v) for k, v in expected.items()}
        base = {"transaction_hash": Web3.to_hex(HexBytes(tx_hash)), "chain_id": self.chain_id,
                "contract_address": self.contract.address, "block_number": None, "block_hash": None}
        try:
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
        except TransactionNotFound:
            return dict(base, status="pending")
        if self.w3.eth.get_block(receipt.blockNumber).hash != receipt.blockHash:
            return dict(base, status="pending")
        base.update(block_number=receipt.blockNumber, block_hash=Web3.to_hex(receipt.blockHash))
        if receipt.status != 1:
            return dict(base, status="failed", reason="transaction_reverted")
        event = getattr(self.contract.events, event_name)()
        logs = event.process_receipt(receipt, errors=DISCARD)
        matches = [log for log in logs if log.address.lower() == self.contract.address.lower()
                   and all(Web3.to_hex(log.args[k]).lower() == v for k, v in expected.items())]
        if len(matches) != 1:
            return dict(base, status="failed", reason="expected_event_missing")
        return dict(base, status="confirmed", **{k: v for k, v in expected.items()})

    def reconcile_ballot(self, election_id, ballot_id, commitment, from_block=0):
        """Recover a lost response without publishing again, even after closure."""
        election_id, ballot_id, commitment = map(bytes32, (election_id, ballot_id, commitment))
        stored = Web3.to_hex(self.contract.functions.ballotCommitments(election_id, ballot_id).call())
        if int(stored, 16) == 0:
            return {"status": "pending"}
        if stored.lower() != commitment:
            raise ValueError("Ballot ID already has a different commitment")
        logs = self.contract.events.BallotPublished().get_logs(
            from_block=from_block, to_block="latest",
            argument_filters={"electionId": election_id, "ballotId": ballot_id})
        if not logs or any(Web3.to_hex(log.args.commitment).lower() != commitment for log in logs):
            raise ValueError("Cannot reconcile consistent ballot publication events")
        return self.receipt_status(logs[0].transactionHash, "BallotPublished",
                                   {"electionId": election_id, "ballotId": ballot_id, "commitment": commitment})
