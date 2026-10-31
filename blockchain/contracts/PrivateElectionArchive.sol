// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";

/// @notice Anchor for a future verifiable election archive, NOT a ballot verifier.
/// @dev Credentials and ciphertext validity must be checked by independent
///      election software. Never treat a successful write as proof of eligibility.
contract PrivateElectionArchive is AccessControl {
    bytes32 public constant RELAYER_ROLE = keccak256("RELAYER_ROLE");
    enum State { Unregistered, Configured, Open, Sealed }
    struct Election {
        State state;
        bytes32 configurationHash;
        bytes32 credentialsHash;
        bytes32 archiveHash;
        uint256 count;
    }
    mapping(bytes32 => Election) private elections;
    mapping(bytes32 => mapping(bytes32 => bytes32)) public ballotHashes;
    mapping(bytes32 => mapping(bytes32 => bytes32)) public ballotCredentialTags;
    mapping(bytes32 => mapping(bytes32 => bool)) public credentialUsed;

    error InvalidInput();
    error InvalidState();
    error DuplicateBallot();
    error DuplicateCredential();
    event ElectionConfigured(bytes32 indexed electionId, bytes32 configurationHash, bytes32 credentialsHash);
    event ElectionOpened(bytes32 indexed electionId);
    event BallotAnchored(bytes32 indexed electionId, bytes32 indexed ballotId, bytes32 ballotHash, bytes32 credentialTag);
    event ElectionSealed(bytes32 indexed electionId, bytes32 archiveHash, uint256 ballotCount);

    constructor(address admin, address relayer) {
        if (admin == address(0) || relayer == address(0)) revert InvalidInput();
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(RELAYER_ROLE, relayer);
    }

    /// Hashes commit to independently distributed exact bytes; no updating.
    function configure(bytes32 electionId, bytes32 configurationHash, bytes32 credentialsHash) external onlyRole(RELAYER_ROLE) {
        if (electionId == 0 || configurationHash == 0 || credentialsHash == 0) revert InvalidInput();
        Election storage e = elections[electionId];
        if (e.state != State.Unregistered) revert InvalidState();
        e.state = State.Configured;
        e.configurationHash = configurationHash;
        e.credentialsHash = credentialsHash;
        emit ElectionConfigured(electionId, configurationHash, credentialsHash);
    }

    /// The frozen commitments are observable before this separate transaction.
    function open(bytes32 electionId) external onlyRole(RELAYER_ROLE) {
        Election storage e = elections[electionId];
        if (e.state != State.Configured) revert InvalidState();
        e.state = State.Open;
        emit ElectionOpened(electionId);
    }

    /// credentialTag must be derived and verified by the selected voting system.
    /// This contract does not verify that a tag belongs to the frozen set.
    function anchorBallot(bytes32 electionId, bytes32 ballotId, bytes32 ballotHash, bytes32 credentialTag) external onlyRole(RELAYER_ROLE) {
        Election storage e = elections[electionId];
        if (e.state != State.Open) revert InvalidState();
        if (ballotId == 0 || ballotHash == 0 || credentialTag == 0) revert InvalidInput();
        if (ballotHashes[electionId][ballotId] != 0) revert DuplicateBallot();
        if (credentialUsed[electionId][credentialTag]) revert DuplicateCredential();
        ballotHashes[electionId][ballotId] = ballotHash;
        ballotCredentialTags[electionId][ballotId] = credentialTag;
        credentialUsed[electionId][credentialTag] = true;
        e.count++;
        emit BallotAnchored(electionId, ballotId, ballotHash, credentialTag);
    }

    /// expectedCount catches a publisher sealing against a stale local view.
    /// It does not prove pending application jobs have drained.
    function seal(bytes32 electionId, bytes32 archiveHash, uint256 expectedCount) external onlyRole(RELAYER_ROLE) {
        Election storage e = elections[electionId];
        if (e.state != State.Open) revert InvalidState();
        if (archiveHash == 0 || expectedCount != e.count) revert InvalidInput();
        e.archiveHash = archiveHash;
        e.state = State.Sealed;
        emit ElectionSealed(electionId, archiveHash, e.count);
    }

    function getElection(bytes32 electionId) external view returns (Election memory) {
        return elections[electionId];
    }
}
