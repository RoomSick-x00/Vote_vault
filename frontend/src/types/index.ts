export interface Organizer {
  id: string
  name: string
  email: string
  organization?: string
}

export interface OrganizerSession {
  user: Organizer
  token: string
}

export interface Candidate {
  id: string
  name: string
  description: string
}

export type ElectionStatus = 'draft' | 'open' | 'closed'
export type PublicationStatus = 'pending' | 'confirmed' | 'failed'
export type ResultCommitmentStatus = 'uncommitted' | 'pending' | 'confirmed'

/** Voter-list columns an organizer can require. */
export type ColumnKey = 'name' | 'rollNo' | 'email' | 'phone'
export type OtpChannel = 'email' | 'phone'

export interface VoterSchema {
  /** Columns the voter must type in to be matched against the database (e.g. name, rollNo). */
  identityColumns: Array<'name' | 'rollNo'>
  /** Channels allowed for OTP delivery. The matching column becomes mandatory in the voter list. */
  otpChannels: OtpChannel[]
}

export interface BlockchainTxInfo {
  genesisTx?: string
  resultTx?: string
  blockNumber?: number
  confirmedAt?: string
}

export interface Election {
  id: string
  /** Short join code voters enter (also encoded in the QR). */
  code: string
  title: string
  description: string
  status: ElectionStatus
  publicationStatus: PublicationStatus
  candidates: Candidate[]
  voterSchema: VoterSchema
  createdAt: string
  openedAt?: string
  closedAt?: string
  voterCount: number
  ballotCount: number
  blockchainTx?: BlockchainTxInfo
  resultCommitmentStatus: ResultCommitmentStatus
}

export interface CreateElectionPayload {
  title: string
  description: string
  candidates: Array<{ name: string; description: string }>
  voterSchema: VoterSchema
}

export interface VoterRecord {
  id: string
  name?: string
  rollNo?: string
  email?: string
  phone?: string
  hasVoted: boolean
  addedAt: string
}

export interface VoterInput {
  name?: string
  rollNo?: string
  email?: string
  phone?: string
}

export interface VoterImportReport {
  imported: number
  skipped: number
  errors: Array<{ row: number; message: string }>
}

// ---- Voter session (public, code based) ----

/** Public election info shown before the voter identifies themselves. */
export interface PublicElection {
  id: string
  code: string
  title: string
  description: string
  status: ElectionStatus
  voterSchema: VoterSchema
}

export interface IdentifyResponse {
  /** Short-lived token that links identify → OTP steps. */
  identifyToken: string
  /** Channels the voter may use for OTP. */
  channels: OtpChannel[]
}

export interface OtpRequestResponse {
  /** Seconds before another OTP may be requested. */
  resendAfter: number
  /** Seconds until the OTP expires. */
  expiresIn: number
  channel: OtpChannel
}

export interface VoterSessionInfo {
  election: PublicElection
  candidates: Candidate[]
  voterName: string
  hasVoted: boolean
  receiptId?: string
}

export interface VerifiedVoter {
  token: string
  session: VoterSessionInfo
}

export interface BallotReceipt {
  receiptId: string
  electionId: string
  candidateId?: string
  commitment: string
  status: 'pending' | 'confirmed' | 'failed'
  txHash?: string
  blockNumber?: number
  createdAt: string
  confirmedAt?: string
}

export interface CandidateTally {
  candidateId: string
  candidateName: string
  count: number
  percentage: number
}

export interface ElectionResults {
  electionId: string
  title: string
  status: ElectionStatus
  totalBallots: number
  tally: CandidateTally[]
  blockchainReference: {
    resultTxHash?: string
    blockNumber?: number
    resultCommitment?: string
    commitmentStatus: ResultCommitmentStatus
  }
  note?: string
}

export interface ReceiptLookupResult {
  found: boolean
  receiptId?: string
  commitment?: string
  status?: 'pending' | 'confirmed' | 'failed'
  blockNumber?: number
  txHash?: string
  message: string
  recordedOnBlockchain: boolean
  commitmentMatched: boolean
  timestamp?: string
}

export interface ApiError {
  error: string
  message: string
  details?: Record<string, unknown>
}
