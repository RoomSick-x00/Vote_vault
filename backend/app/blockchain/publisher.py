"""Chain publishers: submit ElectionRegistry calls and read transaction results.

Web3RegistryPublisher talks to the Hardhat local chain over HTTP, signs with the
relayer key (LOCAL_CHAIN_SIGNER_PRIVATE_KEY — backend environment only, never
committed, never sent to the frontend), and returns raw receipts. When started
from a deployment artifact (BLOCKCHAIN_DEPLOYMENT_FILE, written by
blockchain/scripts/deploy.js), it validates before first use: chain id matches,
the deployed bytecode hashes to the manifest's runtimeCodeHash, and the signer
holds RELAYER_ROLE. Event/argument verification happens in
`app.services.publication_service`, so a fake publisher in tests exercises
exactly the same verification code path.

The database and the chain never share a transaction; every method can fail and
the caller records the failure and retries later.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from eth_utils import keccak
from web3 import Web3
from web3.exceptions import Web3Exception
from web3.providers import HTTPProvider
from web3.types import TxReceipt

from app.blockchain.abi import BALLOT_REGISTRY_ABI
from app.eth_events import ChainLog

# job_type -> Solidity function name
FUNCTION_NAMES = {
    "register_election": "registerElection",
    "open_election": "openElection",
    "close_election": "closeElection",
    "publish_ballot": "publishBallot",
    "publish_result": "publishResult",
}


class ChainError(Exception):
    """Any failure submitting or reading a chain transaction."""


def load_deployment(path_value: str) -> dict:
    """Load a deploy.js artifact ({chainId, address, relayer, runtimeCodeHash, abi}).

    Relative paths resolve against the working directory, then the backend
    directory, then the repository root — so the default
    `blockchain/deployments/localhost.json` works no matter where uvicorn starts.
    """
    raw = Path(path_value)
    candidates = [raw] if raw.is_absolute() else [
        Path.cwd() / raw,
        Path(__file__).resolve().parents[2] / raw,  # backend/
        Path(__file__).resolve().parents[3] / raw,  # repo root
    ]
    for candidate in candidates:
        if candidate.is_file():
            manifest = json.loads(candidate.read_text())
            for key in ("address", "abi", "chainId"):
                if key not in manifest:
                    raise ChainError(f"deployment artifact {candidate} is missing {key!r}")
            return manifest
    raise ChainError(
        f"deployment artifact not found at {path_value} (run blockchain/scripts/deploy.js "
        "against the Hardhat node, or unset BLOCKCHAIN_DEPLOYMENT_FILE)"
    )


class ChainReceipt:
    def __init__(self, status: int, block_number: int, logs: list[ChainLog]) -> None:
        self.status = status
        self.block_number = block_number
        self.logs = logs


class ChainPublisher(Protocol):
    name: str

    def submit(self, job_type: str, payload: dict) -> str: ...

    def fetch_receipt(
        self, tx_hash: str, timeout: float, confirmations: int
    ) -> ChainReceipt: ...


class UnavailablePublisher:
    """Used when blockchain settings are absent: submissions fail honestly."""

    name = "unavailable"

    def __init__(self, reason: str = "") -> None:
        self.reason = reason or (
            "blockchain publication is not configured "
            "(set BLOCKCHAIN_RPC_URL, BALLOT_REGISTRY_CONTRACT_ADDRESS or "
            "BLOCKCHAIN_DEPLOYMENT_FILE, LOCAL_CHAIN_SIGNER_PRIVATE_KEY)"
        )

    def submit(self, job_type: str, payload: dict) -> str:
        raise ChainError(f"Cannot submit {job_type}: {self.reason}")

    def fetch_receipt(self, tx_hash: str, timeout: float, confirmations: int) -> ChainReceipt:
        raise ChainError(f"Cannot fetch receipt {tx_hash}: {self.reason}")


class Web3RegistryPublisher:
    name = "web3"

    def __init__(
        self,
        rpc_url: str,
        contract_address: str,
        signer_private_key: str,
        chain_id: int,
        w3: Web3 | None = None,
        abi: list | None = None,
        expected_code_hash: str | None = None,
        strict_deployment: bool = False,
    ) -> None:
        self._rpc_url = rpc_url
        self._contract_address = Web3.to_checksum_address(contract_address)
        self._chain_id = chain_id
        self._account = Web3().eth.account.from_key(signer_private_key)
        self._w3: Web3 | None = w3  # injected Web3 (tests); None -> HTTPProvider
        self._chain_checked = False
        self._abi = abi or BALLOT_REGISTRY_ABI
        self._expected_code_hash = expected_code_hash
        self._strict_deployment = strict_deployment

    def _ensure(self) -> Web3:
        if self._w3 is not None and self._chain_checked:
            return self._w3
        w3 = self._w3
        if w3 is None:
            w3 = Web3(HTTPProvider(self._rpc_url))
            try:
                if not w3.is_connected():
                    raise ChainError(f"cannot connect to blockchain RPC at {self._rpc_url}")
            except ChainError:
                raise
            except Exception as exc:  # connection errors of all shapes
                raise ChainError(f"cannot connect to blockchain RPC at {self._rpc_url}: {exc}") from exc
        try:
            actual = w3.eth.chain_id
            if actual != self._chain_id:
                raise ChainError(
                    f"blockchain chain id mismatch: expected {self._chain_id}, got {actual}"
                )
        except ChainError:
            raise
        except Exception as exc:
            raise ChainError(f"cannot read chain id from {self._rpc_url}: {exc}") from exc
        if self._strict_deployment:
            self._validate_deployment(w3)
        self._w3 = w3
        self._chain_checked = True
        return w3

    def _validate_deployment(self, w3: Web3) -> None:
        """Confirm the ABI is wired to the deployed contract before any call."""
        contract = self._contract(w3)
        code = w3.eth.get_code(contract.address)
        if not code:
            raise ChainError(
                f"no bytecode at {contract.address}: deploy ElectionRegistry "
                "(blockchain/scripts/deploy.js) before starting the backend"
            )
        if self._expected_code_hash:
            actual_hash = "0x" + keccak(code).hex()
            if actual_hash.lower() != self._expected_code_hash.lower():
                raise ChainError(
                    "deployed bytecode differs from the deployment manifest "
                    f"({actual_hash} != {self._expected_code_hash}): redeploy and "
                    "restart the backend so ABI and contract cannot diverge"
                )
        try:
            relayer_role = contract.functions.RELAYER_ROLE().call()
            if not contract.functions.hasRole(relayer_role, self._account.address).call():
                raise ChainError(
                    f"relayer {self._account.address} does not hold RELAYER_ROLE on "
                    f"{contract.address}; check LOCAL_CHAIN_SIGNER_PRIVATE_KEY against "
                    "the deployment manifest"
                )
        except ChainError:
            raise
        except Exception as exc:
            raise ChainError(f"cannot verify RELAYER_ROLE on the registry: {exc}") from exc

    def _contract(self, w3: Web3):
        return w3.eth.contract(address=self._contract_address, abi=self._abi)

    def submit(self, job_type: str, payload: dict) -> str:
        from app.services.publication_service import JOB_ARG_ORDER

        function_name = FUNCTION_NAMES[job_type]
        arg_keys = JOB_ARG_ORDER[job_type]
        args = [_hex_to_bytes32(payload[key]) for key in arg_keys]
        try:
            w3 = self._ensure()
            call = getattr(self._contract(w3).functions, function_name)(*args)
            tx = call.build_transaction(
                {
                    "from": self._account.address,
                    "nonce": w3.eth.get_transaction_count(self._account.address, "pending"),
                    "gas": 400_000,
                    "gasPrice": w3.eth.gas_price,
                    "chainId": self._chain_id,
                }
            )
            signed = self._account.sign_transaction(tx)
            raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
            tx_hash = w3.eth.send_raw_transaction(raw)
        except ChainError:
            raise
        except Exception as exc:
            raise ChainError(f"submitting {function_name} failed: {exc}") from exc
        return "0x" + tx_hash.hex()

    def fetch_receipt(self, tx_hash: str, timeout: float, confirmations: int) -> ChainReceipt:
        try:
            w3 = self._ensure()
            receipt: TxReceipt = w3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=timeout, poll_latency=0.2
            )
            self._wait_confirmations(w3, receipt, confirmations, timeout)
        except ChainError:
            raise
        except Exception as exc:
            raise ChainError(f"waiting for receipt {tx_hash} failed: {exc}") from exc
        return _to_chain_receipt(receipt, self._contract_address)

    def _wait_confirmations(
        self, w3: Web3, receipt: TxReceipt, confirmations: int, timeout: float
    ) -> None:
        if confirmations <= 1:
            return
        import time

        deadline = time.monotonic() + timeout
        needed = receipt["blockNumber"] + confirmations - 1
        while w3.eth.block_number < needed:
            if time.monotonic() > deadline:
                raise ChainError(
                    f"transaction {receipt['transactionHash'].hex()} not confirmed by "
                    f"{confirmations} blocks within {timeout}s"
                )
            time.sleep(0.2)


def _to_chain_receipt(receipt: TxReceipt, contract_address: str) -> ChainReceipt:
    logs: list[ChainLog] = []
    for log in receipt.get("logs", []):
        if str(log.get("address", "")).lower() != contract_address.lower():
            continue
        logs.append(
            ChainLog(topics=[bytes(t) for t in log["topics"]], data=bytes(log["data"]))
        )
    return ChainReceipt(status=int(receipt["status"]), block_number=int(receipt["blockNumber"]), logs=logs)


def _hex_to_bytes32(value: str) -> bytes:
    raw = bytes.fromhex(value[2:] if value.startswith("0x") else value)
    if len(raw) != 32:
        raise ChainError(f"expected 32 bytes for chain argument, got {len(raw)}")
    return raw
