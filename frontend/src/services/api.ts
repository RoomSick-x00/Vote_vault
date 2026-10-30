import type {
  ApiError,
  BallotReceipt,
  CreateElectionPayload,
  Election,
  ElectionResults,
  IdentifyResponse,
  OrganizerSession,
  OtpChannel,
  OtpRequestResponse,
  PublicElection,
  ReceiptLookupResult,
  VerifiedVoter,
  VoterImportReport,
  VoterInput,
  VoterRecord,
  VoterSessionInfo,
} from '../types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') || '/api'

const ORGANIZER_TOKEN_KEY = 'votevault_organizer_token'
const VOTER_TOKEN_KEY = 'votevault_voter_token'

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
export const getOrganizerToken = () => readStorage(localStorage, ORGANIZER_TOKEN_KEY)
export const setOrganizerToken = (t: string | null) => writeStorage(localStorage, ORGANIZER_TOKEN_KEY, t)
export const getVoterToken = () => readStorage(sessionStorage, VOTER_TOKEN_KEY)
export const setVoterToken = (t: string | null) => writeStorage(sessionStorage, VOTER_TOKEN_KEY, t)

type AuthKind = 'organizer' | 'voter' | 'none'

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  form?: FormData
  auth?: AuthKind
}

async function request<T>(endpoint: string, opts: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, form, auth = 'organizer' } = opts
  const headers: Record<string, string> = { Accept: 'application/json' }

  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const token = auth === 'organizer' ? getOrganizerToken() : auth === 'voter' ? getVoterToken() : null
  if (token) headers.Authorization = `Bearer ${token}`

  let response: Response
  try {
    response = await fetch(`${API_BASE}${endpoint}`, {
      method,
      headers,
      body: form ?? (body !== undefined ? JSON.stringify(body) : undefined),
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
    // FastAPI returns { detail: string | { error, message } | [...] } by default.
    const raw = data as
      | (Partial<ApiError> & { detail?: unknown })
      | null
    let message = raw?.message
    let code = raw?.error
    const detail = raw?.detail
    if (!message && typeof detail === 'string') message = detail
    if (!message && detail && typeof detail === 'object' && !Array.isArray(detail)) {
      const d = detail as Partial<ApiError>
      message = d.message
      code = code || d.error
    }
    if (!message && Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { loc?: unknown[]; msg?: string }
      const field = Array.isArray(first.loc) ? String(first.loc[first.loc.length - 1]) : ''
      message = field ? `${field}: ${first.msg}` : first.msg
      code = code || 'VALIDATION_ERROR'
    }
    throw {
      error: code || `HTTP_${response.status}`,
      message: message || `Request failed (${response.status})`,
      details: raw?.details,
    } as ApiError
  }

  return data as T
}

export const api = {
  // ---------- Organizer auth ----------
  async register(payload: {
    name: string
    email: string
    password: string
    organization?: string
  }): Promise<OrganizerSession> {
    const session = await request<OrganizerSession>('/auth/register', {
      method: 'POST',
      body: payload,
      auth: 'none',
    })
    setOrganizerToken(session.token)
    return session
  },

  async login(email: string, password: string): Promise<OrganizerSession> {
    const session = await request<OrganizerSession>('/auth/login', {
      method: 'POST',
      body: { email, password },
      auth: 'none',
    })
    setOrganizerToken(session.token)
    return session
  },

  async logout(): Promise<void> {
    try {
      await request('/auth/logout', { method: 'POST' })
    } catch {
      /* token may already be invalid */
    } finally {
      setOrganizerToken(null)
    }
  },

  async getMe(): Promise<OrganizerSession['user'] | null> {
    if (!getOrganizerToken()) return null
    try {
      return await request<OrganizerSession['user']>('/auth/me')
    } catch {
      setOrganizerToken(null)
      return null
    }
  },

  // ---------- Organizer: elections ----------
  getElections: () => request<Election[]>('/elections'),
  getElection: (id: string) => request<Election>(`/elections/${id}`),
  createElection: (payload: CreateElectionPayload) =>
    request<Election>('/elections', { method: 'POST', body: payload }),
  updateElectionStatus: (id: string, status: 'open' | 'closed') =>
    request<Election>(`/elections/${id}/status`, { method: 'PATCH', body: { status } }),

  // ---------- Organizer: voter database ----------
  getVoters: (electionId: string) => request<VoterRecord[]>(`/elections/${electionId}/voters`),
  addVoter: (electionId: string, voter: VoterInput) =>
    request<VoterRecord>(`/elections/${electionId}/voters`, { method: 'POST', body: voter }),
  removeVoter: (electionId: string, voterId: string) =>
    request<void>(`/elections/${electionId}/voters/${voterId}`, { method: 'DELETE' }),
  uploadVoters: (electionId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<VoterImportReport>(`/elections/${electionId}/voters/upload`, {
      method: 'POST',
      form,
    })
  },

  // ---------- Results & audit ----------
  getResults: (electionId: string) =>
    request<ElectionResults>(`/elections/${electionId}/results`, { auth: 'none' }),
  lookupReceipt: (electionId: string, code: string) =>
    request<ReceiptLookupResult>(
      `/elections/${electionId}/verify-receipt?code=${encodeURIComponent(code)}`,
      { auth: 'none' }
    ),
  getReceipt: (receiptId: string) =>
    request<BallotReceipt>(`/receipts/${receiptId}`, { auth: 'none' }),

  // ---------- Voter flow (code based, no account) ----------
  getPublicElection: (code: string) =>
    request<PublicElection>(`/vote/${encodeURIComponent(code)}`, { auth: 'none' }),

  identifyVoter: (code: string, identity: { name?: string; rollNo?: string }) =>
    request<IdentifyResponse>(`/vote/${encodeURIComponent(code)}/identify`, {
      method: 'POST',
      body: identity,
      auth: 'none',
    }),

  requestOtp: (identifyToken: string, channel: OtpChannel, contact: string) =>
    request<OtpRequestResponse>('/vote/otp/request', {
      method: 'POST',
      body: { identifyToken, channel, contact },
      auth: 'none',
    }),

  async verifyOtp(identifyToken: string, otp: string): Promise<VerifiedVoter> {
    const result = await request<VerifiedVoter>('/vote/otp/verify', {
      method: 'POST',
      body: { identifyToken, otp },
      auth: 'none',
    })
    setVoterToken(result.token)
    return result
  },

  getVoterSession: () => request<VoterSessionInfo>('/vote/session', { auth: 'voter' }),
  submitBallot: (candidateId: string) =>
    request<BallotReceipt>('/vote/ballot', {
      method: 'POST',
      body: { candidateId },
      auth: 'voter',
    }),
  endVoterSession: () => setVoterToken(null),
}
