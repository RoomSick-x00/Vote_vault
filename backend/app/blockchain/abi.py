"""ElectionRegistry ABI — the interface agreed on 2026-10-31 (see
docs/decisions/2026-10-31-blockchain-interface.md). The blockchain teammate's
Hardhat contract must match these signatures and events; this constant is what
Web3.py encodes calls and verifies logs against.
"""

BALLOT_REGISTRY_ABI: list[dict] = [
    {
        "type": "function",
        "name": "registerElection",
        "inputs": [{"name": "electionId", "type": "bytes32", "internalType": "bytes32"}, {"name": "configHash", "type": "bytes32", "internalType": "bytes32"}],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "type": "function",
        "name": "openElection",
        "inputs": [{"name": "electionId", "type": "bytes32", "internalType": "bytes32"}],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "type": "function",
        "name": "closeElection",
        "inputs": [{"name": "electionId", "type": "bytes32", "internalType": "bytes32"}],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "type": "function",
        "name": "publishBallot",
        "inputs": [
            {"name": "electionId", "type": "bytes32", "internalType": "bytes32"},
            {"name": "ballotId", "type": "bytes32", "internalType": "bytes32"},
            {"name": "commitment", "type": "bytes32", "internalType": "bytes32"},
        ],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "type": "function",
        "name": "publishResult",
        "inputs": [
            {"name": "electionId", "type": "bytes32", "internalType": "bytes32"},
            {"name": "resultHash", "type": "bytes32", "internalType": "bytes32"},
        ],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "type": "event",
        "name": "ElectionRegistered",
        "inputs": [
            {"name": "electionId", "type": "bytes32", "indexed": True, "internalType": "bytes32"},
            {"name": "configHash", "type": "bytes32", "indexed": False, "internalType": "bytes32"},
            {"name": "relayer", "type": "address", "indexed": True, "internalType": "address"},
        ],
        "anonymous": False,
    },
    {
        "type": "event",
        "name": "ElectionOpened",
        "inputs": [
            {"name": "electionId", "type": "bytes32", "indexed": True, "internalType": "bytes32"},
            {"name": "relayer", "type": "address", "indexed": True, "internalType": "address"},
        ],
        "anonymous": False,
    },
    {
        "type": "event",
        "name": "ElectionClosed",
        "inputs": [
            {"name": "electionId", "type": "bytes32", "indexed": True, "internalType": "bytes32"},
            {"name": "relayer", "type": "address", "indexed": True, "internalType": "address"},
        ],
        "anonymous": False,
    },
    {
        "type": "event",
        "name": "BallotPublished",
        "inputs": [
            {"name": "electionId", "type": "bytes32", "indexed": True, "internalType": "bytes32"},
            {"name": "ballotId", "type": "bytes32", "indexed": True, "internalType": "bytes32"},
            {"name": "commitment", "type": "bytes32", "indexed": False, "internalType": "bytes32"},
            {"name": "relayer", "type": "address", "indexed": True, "internalType": "address"},
        ],
        "anonymous": False,
    },
    {
        "type": "event",
        "name": "ResultPublished",
        "inputs": [
            {"name": "electionId", "type": "bytes32", "indexed": True, "internalType": "bytes32"},
            {"name": "resultHash", "type": "bytes32", "indexed": False, "internalType": "bytes32"},
            {"name": "relayer", "type": "address", "indexed": True, "internalType": "address"},
        ],
        "anonymous": False,
    },
]
