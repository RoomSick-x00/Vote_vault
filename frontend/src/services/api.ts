import type {
  ApiError,
  ElectionListOut,
  VoterSchema,
  AuthMe,
  AuthSession,
  CandidatesAddOut,
  CreateElectionPayload,
  Election,
  ElectionResults,
  IdentifyResponse,
  OpenElectionOut,
  CloseElectionOut,
  OtpRequestResponse,
  OrganizationListOut,
  PublicElection,
  PublicationsOut,
  RetryOut,
  VoterImportReport,
  VoterListOut,
  VoterReceipt,
  VoterSession,
} from '../types'

/**
 * API client for the implemented backend contract (docs/api-contract.md):
 * prefix /api/v1, JSON bodies, Bearer Supabase JWTs, and the shared error
 * envelope { error: { code, message } }.
 */

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') || '/api/v1'

const ORGANIZER_TOKEN_KEY = 'votevault_organizer_token'
const VOTER_TOKEN_KEY = 'votevault_voter_token'
const ELECTION_INDEX_KEY = 'votevault_election_ids'

function readStorage(store: Storage, key: string): string | null {
  try {
    return store.getItem(key)
  } catch {
    return null
  }
}

function writeStorage(store: Storage, key: string, value: string | null): void {
  try {
    if (value) store.setItem(key, value)
    else store.removeItem(key)
  } catch {
    /* storage unavailable */
  }
}

// Organizer sessions persist across tabs; short-lived voter sessions stay per tab.
export const getOrganizerToken = () => readStorage(localStorage, ORGANIZER_TOKEN_KEY)
export const setOrganizerToken = (t: string | null) => writeStorage(localStorage, ORGANIZER_TOKEN_KEY, t)
export const getVoterToken = () => readStorage(sessionStorage, VOTER_TOKEN_KEY)
export const setVoterToken = (t: string | null) => writeStorage(sessionStorage, VOTER_TOKEN_KEY, t)

type AuthKind = 'organizer' | 'voter' | 'none'

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
  auth?: AuthKind
  /** Query params; undefined/null values are skipped. */
  query?: Record<string, string | undefined | null>
}

function buildUrl(endpoint: string, query?: Record<string, string | undefined | null>): string {
  const url = new URL(`${API_BASE}${endpoint}`, window.location.origin)
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null) url.searchParams.set(key, value)
    }
  }
  return url.toString()
}

async function request<T>(endpoint: string, opts: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, auth = 'organizer', query } = opts
  const headers: Record<string, string> = { Accept: 'application/json' }
  const isForm = typeof FormData !== 'undefined' && body instanceof FormData
  if (body !== undefined && !isForm) headers['Content-Type'] = 'application/json'

  const token = auth === 'organizer' ? getOrganizerToken() : auth === 'voter' ? getVoterToken() : null
  if (token) headers.Authorization = `Bearer ${token}`

  let response: Response
  try {
    response = await fetch(buildUrl(endpoint, query), {
      method,
      headers,
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    })
  } catch {
    throw {
      error: 'NETWORK_FAILURE',
      message: 'Unable to reach the VoteVault server. Check your connection and try again.',
    } as ApiError
  }

  let data: unknown = null
  try {
    data = await response.json()
  } catch {
    /* empty or non-JSON body */
  }

  if (!response.ok) {
    if (response.status === 401) {
      if (auth === 'organizer' && token) {
        setOrganizerToken(null)
        window.dispatchEvent(new CustomEvent('votevault:session-expired'))
      }
      if (auth === 'voter' && token) {
        setVoterToken(null)
      }
    }
    throw parseError(data, response.status)
  }

  return data as T
}

/** Normalizes the contract envelope { error: { code, message } } into a flat ApiError. */
function parseError(data: unknown, status: number): ApiError {
  const raw = data as { error?: unknown; detail?: unknown; message?: unknown } | null
  let code: string | undefined
  let message: string | undefined

  if (raw && typeof raw.error === 'object' && raw.error !== null) {
    const inner = raw.error as { code?: unknown; message?: unknown }
    code = typeof inner.code === 'string' ? inner.code : undefined
    message = typeof inner.message === 'string' ? inner.message : undefined
  } else if (typeof raw?.error === 'string') {
    code = raw.error
    message = typeof raw?.message === 'string' ? raw.message : undefined
  }

  // Fallbacks for framework-shaped errors (should not normally occur).
  if (!message && typeof raw?.detail === 'string') message = raw.detail
  if (!message && Array.isArray(raw?.detail) && raw.detail.length > 0) {
    const first = raw.detail[0] as { loc?: unknown[]; msg?: string }
    const field = Array.isArray(first.loc) ? String(first.loc[first.loc.length - 1]) : ''
    message = field ? `${field}: ${first.msg}` : first.msg
    code = code || 'VALIDATION_ERROR'
  }

  return {
    error: code || `HTTP_${status}`,
    message: message || `Request failed (${status})`,
  }
}

// Receipt ids this browser has seen, keyed by election (session-scoped: receipts
// are visible only to the submitting voter, and voter tokens live per tab).
const RECEIPT_PREFIX = 'votevault_receipt_'

export function rememberReceipt(electionId: string, receiptId: string): void {
  writeStorage(sessionStorage, RECEIPT_PREFIX + electionId, receiptId)
}

export function getRememberedReceipt(electionId: string): string | null {
  return readStorage(sessionStorage, RECEIPT_PREFIX + electionId)
}

export const api = {
  auditRecord: (id: string) => request<AuditRecord>(`/audit/${encodeURIComponent(id)}`, { auth: 'none' }),
  verifyAudit: (record: AuditRecord) => request<{ checks: AuditCheck[] }>('/audit/verify', { method: 'POST', body: record, auth: 'none' }),

  // ---------- Organizer auth ----------

  async signup(payload: {
    email: string
    password: string
    full_name: string
    organization_name: string
  }): Promise<AuthSession> {
    const session = await request<AuthSession>('/auth/signup', { method: 'POST', body: payload, auth: 'none' })
    setOrganizerToken(session.access_token)
    return session
  },

  async login(email: string, password: string): Promise<AuthSession> {
    const session = await request<AuthSession>('/auth/login', {
      method: 'POST',
      body: { email, password },
      auth: 'none',
    })
    setOrganizerToken(session.access_token)
    return session
  },

  /** No backend logout endpoint — the JWT is simply dropped locally. */
  logout(): void {
    setOrganizerToken(null)
  },

  endVoterSession(): void {
    setVoterToken(null)
  },

  async getMe(): Promise<AuthMe | null> {
    if (!getOrganizerToken()) return null
    try {
      return await request<AuthMe>('/auth/me')
    } catch {
      setOrganizerToken(null)
      return null
    }
  },

  getOrganizations: () => request<OrganizationListOut>('/organizations'),

  /** Found an organization; the caller becomes its owner. */
  createOrganization: (name: string) =>
    request<{ organization_id: string; name: string; role: string; created_at: string }>('/organizations', {
      method: 'POST',
      body: { name },
    }),

  // ---------- Elections ----------

  getElection: (id: string) => request<Election>(`/elections/${id}`),

  /** Server-side dashboard list: elections of organizations the user organizes. */
  getElections: () => request<ElectionListOut>('/elections'),

  createElection: (payload: CreateElectionPayload) =>
    request<Election>('/elections', { method: 'POST', body: payload }),

  /** Select verification attributes after the roster is uploaded (draft only). */
  setVoterSchema: (electionId: string, schema: VoterSchema) =>
    request<Election>(`/elections/${electionId}/voter-schema`, {
      method: 'PUT',
      body: schema,
    }),

  openElection: (id: string) =>
    request<OpenElectionOut>(`/elections/${id}/open`, { method: 'POST', body: {} }),

  /** Returns `closing` while accepted ballots drain to the chain; poll until `closed`. */
  closeElection: (id: string) =>
    request<CloseElectionOut>(`/elections/${id}/close`, { method: 'POST', body: {} }),

  // ---------- Candidates (draft only) ----------

  getCandidates: (electionId: string) =>
    request<{ election_id: string; candidates: Election['candidates'] }>(`/elections/${electionId}/candidates`),

  addCandidates: (electionId: string, names: Array<{ name: string }>) =>
    request<CandidatesAddOut>(`/elections/${electionId}/candidates`, {
      method: 'POST',
      body: { candidates: names },
    }),

  // ---------- Organizer voter roster ----------

  getVoters: (electionId: string) =>
    request<VoterListOut>(`/elections/${electionId}/voters`),

  uploadVoters: (electionId: string, file: File) => {
    const body = new FormData()
    body.append('file', file)
    return request<VoterImportReport>(`/elections/${electionId}/voters/upload`, {
      method: 'POST',
      body,
    })
  },

  deleteVoter: (electionId: string, voterId: string) =>
    request<void>(`/elections/${electionId}/voters/${voterId}`, { method: 'DELETE' }),

  // ---------- Public voter code -> identify -> OTP -> session ----------

  getPublicElection: (code: string) =>
    request<PublicElection>(`/vote/${encodeURIComponent(code)}`, { auth: 'none' }),

  identifyVoter: (code: string, identity: { name?: string; rollNo?: string }) =>
    request<IdentifyResponse>(`/vote/${encodeURIComponent(code)}/identify`, {
      method: 'POST',
      body: identity,
      auth: 'none',
    }),

  requestVoterOtp: (identifyToken: string, channel: 'email' | 'phone', contact: string) =>
    request<OtpRequestResponse>('/vote/otp/request', {
      method: 'POST',
      body: { identifyToken, channel, contact },
      auth: 'none',
    }),

  async verifyVoterOtp(identifyToken: string, otp: string) {
    const verified = await request<{ token: string; session: VoterSession }>('/vote/otp/verify', {
      method: 'POST',
      body: { identifyToken, otp },
      auth: 'none',
    })
    setVoterToken(verified.token)
    return verified.session
  },

  getVoterSession: () => request<VoterSession>('/vote/session', { auth: 'voter' }),

  submitVoterBallot: (candidateId: string) =>
    request<VoterReceipt>('/vote/ballot', {
      method: 'POST',
      body: { candidateId },
      auth: 'voter',
    }),

  getVoterReceipt: () => request<VoterReceipt>('/vote/receipt', { auth: 'voter' }),

  // ---------- Publications (organizer chain monitor) ----------

  getPublications: (electionId: string) =>
    request<PublicationsOut>(`/elections/${electionId}/publications`),

  retryPublications: (electionId: string) =>
    request<RetryOut>(`/elections/${electionId}/publications/retry`, { method: 'POST', body: {} }),

  // ---------- Results (organizer, after close) ----------

  getResults: (electionId: string) => request<ElectionResults>(`/elections/${electionId}/results`),
}

export interface AuditRecord { election_id: string; status: string; configuration: unknown; records: Array<{ type: string; payload: Record<string, string>; tx_hash: string | null }>; result: { total_ballots: number; counts: Array<{ candidate_id: string; name: string; chain_index: number; votes: number }> } | null }
export interface AuditCheck { id: string; status: 'PASS' | 'FAIL' | 'INCOMPLETE'; reason: string }
