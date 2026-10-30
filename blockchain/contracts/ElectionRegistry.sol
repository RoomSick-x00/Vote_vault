// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";

/// @notice Records backend-supplied commitments, not voter eligibility or tally correctness.
contract ElectionRegistry is AccessControl {
    bytes32 public constant RELAYER_ROLE = keccak256("RELAYER_ROLE");
    enum State { Unregistered, Registered, Open, Closed }
    struct Election {
        State state;
        bytes32 configurationCommitment;
        bytes32 resultCommitment;
        uint256 ballotCount;
    }
    mapping(bytes32 => Election) private elections;
    mapping(bytes32 => mapping(bytes32 => bytes32)) public ballotCommitments;

    error ZeroValue();
    error InvalidState(bytes32 electionId, State actual, State expected);
    error BallotAlreadyPublished(bytes32 electionId, bytes32 ballotId);
    error ResultAlreadyPublished(bytes32 electionId);

    event ElectionRegistered(bytes32 indexed electionId, bytes32 configurationCommitment);
    event ElectionOpened(bytes32 indexed electionId);
    event ElectionClosed(bytes32 indexed electionId);
    event BallotPublished(bytes32 indexed electionId, bytes32 indexed ballotId, bytes32 commitment);
    event ResultPublished(bytes32 indexed electionId, bytes32 commitment);

    constructor(address admin, address relayer) {
        if (admin == address(0) || relayer == address(0)) revert ZeroValue();
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(RELAYER_ROLE, relayer);
    }
    function registerElection(bytes32 electionId, bytes32 configurationCommitment) external onlyRole(RELAYER_ROLE) {
        nonzero(electionId); nonzero(configurationCommitment);
        requireState(electionId, State.Unregistered);
        elections[electionId] = Election(State.Registered, configurationCommitment, bytes32(0), 0);
        emit ElectionRegistered(electionId, configurationCommitment);
    }
    function openElection(bytes32 electionId) external onlyRole(RELAYER_ROLE) {
        requireState(electionId, State.Registered);
        elections[electionId].state = State.Open;
        emit ElectionOpened(electionId);
    }
    function closeElection(bytes32 electionId) external onlyRole(RELAYER_ROLE) {
        requireState(electionId, State.Open);
        elections[electionId].state = State.Closed;
        emit ElectionClosed(electionId);
    }
    function publishBallot(bytes32 electionId, bytes32 ballotId, bytes32 commitment) external onlyRole(RELAYER_ROLE) {
        requireState(electionId, State.Open);
        nonzero(ballotId); nonzero(commitment);
        if (ballotCommitments[electionId][ballotId] != bytes32(0)) revert BallotAlreadyPublished(electionId, ballotId);
        ballotCommitments[electionId][ballotId] = commitment;
        elections[electionId].ballotCount++;
        emit BallotPublished(electionId, ballotId, commitment);
    }
    function publishResult(bytes32 electionId, bytes32 commitment) external onlyRole(RELAYER_ROLE) {
        requireState(electionId, State.Closed); nonzero(commitment);
        if (elections[electionId].resultCommitment != bytes32(0)) revert ResultAlreadyPublished(electionId);
        elections[electionId].resultCommitment = commitment;
        emit ResultPublished(electionId, commitment);
    }
    function getElection(bytes32 electionId) external view returns (State state, bytes32 configurationCommitment, bytes32 resultCommitment, uint256 ballotCount) {
        Election storage e = elections[electionId];
        return (e.state, e.configurationCommitment, e.resultCommitment, e.ballotCount);
    }
    function requireState(bytes32 electionId, State expected) private view {
        State actual = elections[electionId].state;
        if (actual != expected) revert InvalidState(electionId, actual, expected);
    }
    function nonzero(bytes32 value) private pure { if (value == bytes32(0)) revert ZeroValue(); }
}
