import type {
  ApiError,
  AuthMe,
  AuthSession,
  BallotAccepted,
  BallotReceipt,
  CandidatesAddOut,
  CreateElectionPayload,
  Election,
  ElectionResults,
  EligibleVotersOut,
  OpenElectionOut,
  CloseElectionOut,
  OrganizationListOut,
  PublicationsOut,
  RetryOut,
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

// Organizer sessions persist across tabs; voter sessions live only for the browser tab.
// Both tokens are Supabase JWTs — the backend derives identity from them, never from bodies.
export const getOrganizerToken = () => readStorage(localStorage, ORGANIZER_TOKEN_KEY)
export const setOrganizerToken = (t: string | null) => writeStorage(localStorage, ORGANIZER_TOKEN_KEY, t)
export const getVoterToken = () => readStorage(sessionStorage, VOTER_TOKEN_KEY)
export const setVoterToken = (t: string | null) => writeStorage(sessionStorage, VOTER_TOKEN_KEY, t)

/**
 * The backend has no "list my elections" endpoint yet. Until member 2 adds one,
 * the dashboard keeps a local index of election IDs this browser has created or
 * visited and hydrates each via GET /elections/{id} (which the organizer can see).
 */
function readElectionIndex(): string[] {
  try {
    const raw = JSON.parse(localStorage.getItem(ELECTION_INDEX_KEY) || '[]')
    return Array.isArray(raw) ? raw.filter((v): v is string => typeof v === 'string') : []
  } catch {
    return []
  }
}

export const electionIndex = {
  all: readElectionIndex,
  remember(id: string) {
    const ids = readElectionIndex()
    if (!ids.includes(id)) writeStorage(localStorage, ELECTION_INDEX_KEY, JSON.stringify([...ids, id]))
  },
  forget(id: string) {
    writeStorage(localStorage, ELECTION_INDEX_KEY, JSON.stringify(readElectionIndex().filter((v) => v !== id)))
  },
}

type AuthKind = 'organizer' | 'voter' | 'none'

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
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
  return `${url.pathname}${url.search}`
}

async function request<T>(endpoint: string, opts: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, auth = 'organizer', query } = opts
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const token = auth === 'organizer' ? getOrganizerToken() : auth === 'voter' ? getVoterToken() : null
  if (token) headers.Authorization = `Bearer ${token}`

  let response: Response
  try {
    response = await fetch(buildUrl(endpoint, query), {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
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
  // ---------- Auth (organizer; voters reuse login in the voter flow) ----------

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

  /** Voter sign-in: same Supabase account system, token kept per-tab. */
  async voterLogin(email: string, password: string): Promise<AuthSession> {
    const session = await request<AuthSession>('/auth/login', {
      method: 'POST',
      body: { email, password },
      auth: 'none',
    })
    setVoterToken(session.access_token)
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

  // ---------- Elections ----------

  /**
   * Open/closed elections are visible to any authenticated user, so voters fetch
   * them with their own token (drafts stay organizer-only → 403).
   */
  getElection: (id: string, as: 'organizer' | 'voter' = 'organizer') =>
    request<Election>(`/elections/${id}`, { auth: as }),

  /** Interim dashboard list: hydrate the local ID index in parallel, pruning dead IDs. */
  async getElectionsFromIndex(): Promise<Election[]> {
    const ids = electionIndex.all()
    const results = await Promise.allSettled(ids.map((id) => api.getElection(id)))
    const alive: Election[] = []
    results.forEach((r, i) => {
      if (r.status === 'fulfilled') alive.push(r.value)
      else if (r.reason && (r.reason as ApiError).error === 'NOT_FOUND') electionIndex.forget(ids[i])
    })
    // Newest first, matching what a server-side list would return.
    return alive.sort((a, b) => b.created_at.localeCompare(a.created_at))
  },

  createElection: (payload: CreateElectionPayload) =>
    request<Election>('/elections', { method: 'POST', body: payload }),

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

  // ---------- Eligible test voters (Supabase user UUIDs) ----------

  getEligibleVoters: (electionId: string) =>
    request<EligibleVotersOut>(`/elections/${electionId}/eligible-test-voters`),

  addEligibleVoters: (electionId: string, userIds: string[]) =>
    request<EligibleVotersOut>(`/elections/${electionId}/eligible-test-voters`, {
      method: 'POST',
      body: { user_ids: userIds },
    }),

  // ---------- Ballots & receipts (voter) ----------

  submitBallot: (electionId: string, candidateId: string) =>
    request<BallotAccepted>(`/elections/${electionId}/ballots`, {
      method: 'POST',
      body: { candidate_id: candidateId },
      auth: 'voter',
    }),

  getReceipt: (electionId: string, receiptId: string) =>
    request<BallotReceipt>(`/elections/${electionId}/receipts/${receiptId}`, { auth: 'voter' }),

  // ---------- Publications (organizer chain monitor) ----------

  getPublications: (electionId: string) =>
    request<PublicationsOut>(`/elections/${electionId}/publications`),

  retryPublications: (electionId: string) =>
    request<RetryOut>(`/elections/${electionId}/publications/retry`, { method: 'POST', body: {} }),

  // ---------- Results (organizer, after close) ----------

  getResults: (electionId: string) => request<ElectionResults>(`/elections/${electionId}/results`),
}
