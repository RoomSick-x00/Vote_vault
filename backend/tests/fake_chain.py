"""In-memory BallotRegistry stand-in with scriptable failure modes.

It emits the same event-log structure the real chain returns (topics + data),
so receipt verification in `publication_service` runs through the identical
code path in tests. Scriptable outcomes per submission:
    "ok"       -> mined, correct event emitted
    "revert"   -> mined with status 0
    "raise"    -> submission itself fails (RPC/connection error)
    "timeout"  -> submitted but receipt never arrives
    "no_event" -> mined with status 1 but no matching event
"""

from __future__ import annotations

from collections import deque

from app.blockchain.publisher import ChainError, ChainReceipt
from app.eth_events import EVENT_SIGNATURES, ChainLog, event_topic0

_RELAYER_PLACEHOLDER = b"\x00" * 12 + b"\x11" * 20


class FakeChainPublisher:
    name = "fake"

    def __init__(self) -> None:
        self.records: list[dict] = []
        self.script: deque[tuple[str, str | None]] = deque()
        self.submit_calls: list[tuple[str, dict]] = []
        self.block = 100

    # --- scripting -------------------------------------------------------
    def script_next(self, outcome: str, message: str | None = None, times: int = 1) -> None:
        for _ in range(times):
            self.script.append((outcome, message))

    # --- ChainPublisher protocol ------------------------------------------
    def submit(self, job_type: str, payload: dict) -> str:
        self.submit_calls.append((job_type, dict(payload)))
        outcome, message = self.script.popleft() if self.script else ("ok", None)
        if outcome == "raise":
            raise ChainError(message or "scripted submit failure (e.g. RPC unreachable)")
        self.block += 1
        tx_hash = f"0x{len(self.records):064x}"
        status = 0 if outcome == "revert" else 1
        self.records.append(
            {
                "tx_hash": tx_hash,
                "job_type": job_type,
                "payload": payload,
                "block": self.block,
                "status": status,
                "outcome": outcome,
            }
        )
        return tx_hash

    def fetch_receipt(self, tx_hash: str, timeout: float, confirmations: int) -> ChainReceipt:
        record = next((r for r in self.records if r["tx_hash"] == tx_hash), None)
        if record is None:
            raise ChainError(f"unknown transaction {tx_hash}")
        if record["outcome"] == "timeout":
            raise ChainError(f"transaction {tx_hash} not mined within {timeout}s")
        if record["status"] != 1:
            return ChainReceipt(status=0, block_number=record["block"], logs=[])
        if record["outcome"] == "no_event":
            return ChainReceipt(status=1, block_number=record["block"], logs=[])
        return ChainReceipt(status=1, block_number=record["block"], logs=[self._event_log(record)])

    # --- helpers -----------------------------------------------------------
    def _event_log(self, record: dict) -> ChainLog:
        job_type, payload = record["job_type"], record["payload"]
        signature = EVENT_SIGNATURES[job_type]
        topics: list[bytes] = [
            event_topic0(signature),
            _hex_to_bytes32(payload["election_id"]),
        ]
        data = b""
        if job_type == "publish_ballot":
            topics.append(_hex_to_bytes32(payload["ballot_id"]))
            topics.append(_RELAYER_PLACEHOLDER)
            data = _hex_to_bytes32(payload["commitment"])
        else:
            topics.append(_RELAYER_PLACEHOLDER)
            if job_type == "register_election":
                data = _hex_to_bytes32(payload["config_hash"])
            if job_type == "publish_result":
                data = _hex_to_bytes32(payload["result_hash"])
        return ChainLog(topics=topics, data=data)

    def confirmed_tx_hashes(self) -> list[str]:
        return [r["tx_hash"] for r in self.records if r["outcome"] == "ok"]


def _hex_to_bytes32(value: str) -> bytes:
    return bytes.fromhex(value[2:] if value.startswith("0x") else value)
