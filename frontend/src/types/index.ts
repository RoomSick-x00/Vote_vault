/**
 * Types mirrored 1:1 from the implemented backend contract (docs/api-contract.md).
 * Field names are snake_case exactly as the API returns them — no client-side
 * renaming, so payloads stay diffable against the contract.
 */

// ---------- Auth (Supabase-backed, proxied by the backend) ----------

export interface UserRef {
  user_id: string
  email: string
  full_name: string
}

export interface OrgRef {
  organization_id: string
  name: string
  role: string
}

/** POST /auth/signup and /auth/login response. */
export interface AuthSession {
  access_token: string
  refresh_token?: string | null
  token_type?: string
  expires_in?: number
  user: UserRef
  organizations: OrgRef[]
}

/** GET /auth/me response (organizer context in the app). */
export interface AuthMe {
  user_id: string
  email: string
  full_name: string
  organizations: OrgRef[]
}

/** Organizer as the auth context sees it. */
export interface Organizer {
  user_id: string
  email: string
  full_name: string
  organizations: OrgRef[]
}

// ---------- Organizations ----------

export interface Organization {
  organization_id: string
  name: string
  role: string
  created_at: string
}

export interface OrganizationListOut {
  organizations: Organization[]
}

// ---------- Elections ----------

/** Backend statuses. `closing`: close requested, accepted ballots still draining to chain. */
export type ElectionStatus = 'draft' | 'open' | 'closing' | 'closed'
export type PublicationStatus = 'pending' | 'confirmed' | 'failed'
export type PublishedResultStatus = 'not_published' | 'pending' | 'confirmed' | 'failed'

export interface Candidate {
  candidate_id: string
  name: string
  description: string
  /** Immutable 0-based insertion order used as the on-chain index. */
  chain_index: number
}

export interface VoterSchema {
  identityColumns: Array<'name' | 'rollNo'>
  otpChannels: Array<'email' | 'phone'>
}

export interface Election {
  election_id: string
  organization_id: string
  title: string
  description: string
  code: string
  voter_schema: VoterSchema
  status: ElectionStatus
  candidates: Candidate[]
  created_at: string
  opens_at?: string | null
  closes_at?: string | null
  opened_at?: string | null
  closed_at?: string | null
}

export interface CreateElectionPayload {
  organization_id: string
  title: string
  description?: string
  voter_schema?: VoterSchema
  opens_at?: string | null
  closes_at?: string | null
}

export interface OpenElectionOut {
  election_id: string
  status: ElectionStatus
  opened_at: string
}

export interface CloseElectionOut {
  election_id: string
  status: ElectionStatus
  closed_at: string | null
}

export interface CandidatesAddPayload {
  candidates: Array<{ name: string }>
}

export interface CandidatesOut {
  election_id: string
  candidates: Candidate[]
}

export interface CandidatesAddOut extends CandidatesOut {
  added: number
  skipped: number
}

export interface VoterRecord {
  id: string
  name: string | null
  rollNo: string | null
  email: string | null
  phone: string | null
  hasVoted: boolean
  addedAt: string
}

export interface VoterListOut {
  voters: VoterRecord[]
  voterCount: number
}

export interface VoterImportReport {
  imported: number
  skipped: number
  errors: Array<{ row: number; message: string }>
}

export interface PublicElection {
  id: string
  code: string
  title: string
  description: string
  status: ElectionStatus
  voterSchema: VoterSchema
}

export interface VoterCandidate {
  id: string
  name: string
  description: string
}

export interface VoterSession {
  election: PublicElection
  candidates: VoterCandidate[]
  voterName: string
  hasVoted: boolean
  receiptId: string | null
}

export interface IdentifyResponse {
  identifyToken: string
  channels: Array<'email' | 'phone'>
}

export interface OtpRequestResponse {
  resendAfter: number
  expiresIn: number
  channel: 'email' | 'phone'
  devCode?: string | null
}

export interface VoterReceipt {
  receiptId: string
  electionId: string
  candidateId: string | null
  commitment: string
  status: PublicationStatus
  txHash: string | null
  blockNumber: number | null
  createdAt: string
  confirmedAt: string | null
}

// ---------- Publications (organizer chain-job monitor) ----------

export type PublicationJobType =
  | 'register_election'
  | 'open_election'
  | 'publish_ballot'
  | 'close_election'
  | 'publish_result'

export interface PublicationJob {
  job_id: string
  job_type: PublicationJobType | string
  receipt_id?: string | null
  status: PublicationStatus
  attempts: number
  max_attempts: number
  transaction_hash?: string | null
  block_number?: number | null
  next_attempt_at?: string | null
  last_error?: string | null
  created_at: string
  confirmed_at?: string | null
}

export interface PublicationsOut {
  election_id: string
  publications: PublicationJob[]
  summary: Record<string, number>
}

export interface RetryOut {
  election_id: string
  requeued: number
  processed: Record<string, number>
}

// ---------- Results ----------

export interface ResultCount {
  candidate_id: string
  name: string
  chain_index: number
  votes: number
}

export interface ElectionResults {
  election_id: string
  status: ElectionStatus
  tally_type: string
  total_ballots: number
  counts: ResultCount[]
  publications: Record<string, number>
  published_result_status: PublishedResultStatus
  /** Must be shown as-is in the UI (per the API contract). */
  disclaimer: string
}

// ---------- Errors ----------

/** Flattened from the backend envelope { error: { code, message } }. */
export interface ApiError {
  error: string
  message: string
}
