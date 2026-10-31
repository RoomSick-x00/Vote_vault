"""Voter-flow schemas — camelCase wire shapes matching the frontend types
(types/index.ts): PublicElection, IdentifyResponse, OtpRequestResponse,
VerifiedVoter, VoterSessionInfo, BallotReceipt, VoterRecord, VoterImportReport."""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import APIModel


class VoterSchemaOut(APIModel):
    identityColumns: list[str]
    otpChannels: list[str]


class PublicElectionOut(APIModel):
    id: str
    code: str
    title: str
    description: str
    status: str
    voterSchema: VoterSchemaOut


class CandidateFlowOut(APIModel):
    id: str
    name: str
    description: str


class IdentifyIn(APIModel):
    name: str | None = Field(default=None, max_length=200)
    rollNo: str | None = Field(default=None, max_length=64)


class IdentifyOut(APIModel):
    identifyToken: str
    channels: list[str]


class OtpRequestIn(APIModel):
    identifyToken: str
    channel: str
    contact: str = Field(min_length=3, max_length=254)


class OtpRequestOut(APIModel):
    resendAfter: int
    expiresIn: int
    channel: str
    # Dev delivery only (APP_ENV != production): no mail/SMS provider is wired,
    # so the code returns here and in the log. Never present in production.
    devCode: str | None = None


class OtpVerifyIn(APIModel):
    identifyToken: str
    otp: str = Field(min_length=4, max_length=8)


class VoterSessionOut(APIModel):
    election: PublicElectionOut
    candidates: list[CandidateFlowOut]
    voterName: str
    hasVoted: bool
    receiptId: str | None = None


class VerifiedVoterOut(APIModel):
    token: str
    session: VoterSessionOut


class BallotVoteIn(APIModel):
    candidateId: str


class BallotReceiptOut(APIModel):
    receiptId: str
    electionId: str
    candidateId: str | None = None
    commitment: str
    status: str
    txHash: str | None = None
    blockNumber: int | None = None
    createdAt: str
    confirmedAt: str | None = None


# --- organizer roster shapes --------------------------------------------------


class VoterRecordOut(APIModel):
    id: str
    name: str | None = None
    rollNo: str | None = None
    email: str | None = None
    phone: str | None = None
    hasVoted: bool
    addedAt: str


class VoterListOut(APIModel):
    voters: list[VoterRecordOut]
    voterCount: int


class VoterImportReportOut(APIModel):
    imported: int
    skipped: int
    errors: list[dict]
    columns: list[str] = Field(default_factory=list)
