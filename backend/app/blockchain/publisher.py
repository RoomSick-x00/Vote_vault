"""Chain publishers: submit BallotRegistry calls and read transaction results.

Web3RegistryPublisher talks to the Hardhat local chain over HTTP, signs with the
relayer key (LOCAL_CHAIN_SIGNER_PRIVATE_KEY — backend environment only, never
committed, never sent to the frontend), and returns raw receipts. Event/argument
verification happens in `app.services.publication_service`, so a fake publisher
in tests exercises exactly the same verification code path.

The database and the chain never share a transaction; every method can fail and
the caller records the failure and retries later.
"""

from __future__ import annotations

from typing import Protocol

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
            "(set BLOCKCHAIN_RPC_URL, BALLOT_REGISTRY_CONTRACT_ADDRESS, "
            "LOCAL_CHAIN_SIGNER_PRIVATE_KEY)"
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
    ) -> None:
        self._rpc_url = rpc_url
        self._contract_address = Web3.to_checksum_address(contract_address)
        self._chain_id = chain_id
        self._account = Web3().eth.account.from_key(signer_private_key)
        self._w3: Web3 | None = w3  # injected Web3 (tests); None -> HTTPProvider
        self._chain_checked = False

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
        self._w3 = w3
        self._chain_checked = True
        return w3

    def _contract(self, w3: Web3):
        return w3.eth.contract(address=self._contract_address, abi=BALLOT_REGISTRY_ABI)

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
