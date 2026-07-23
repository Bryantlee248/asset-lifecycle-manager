/**
 * Low-level API client — 1:1 faithful port of the legacy `api(url, opts)`
 * function from `frontend/index.html` (lines ~2336-2344). Do NOT invent URLs,
 * query params, or body fields; the services layer builds exact requests on top.
 *
 * Behaviour contract (must stay byte-for-byte equivalent in effect):
 *  - API base is '' (empty) under the Vite dev proxy, so requests hit relative
 *    `/api/*` and are proxied to the backend by Vite (no CORS, no backend edit).
 *  - Request headers: `Content-Type: application/json`, plus
 *    `Authorization: Bearer <token>` when a token is present.
 *  - 401 -> clear stored session, dispatch `auth:logout`, throw '登录已过期，请重新登录'.
 *  - 403 -> throw `err.detail || '权限不足'`.
 *  - !res.ok -> throw `err.detail || res.statusText`.
 *  - otherwise -> return `res.json()`.
 */

export const TOKEN_KEY = 'asset_token'
export const USER_KEY = 'asset_user'

const API = ''

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function getToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) || ''
  } catch {
    return ''
  }
}

function clearSession() {
  try {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  } catch {
    /* ignore */
  }
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('auth:logout'))
  }
}

export async function api<T = any>(url: string, opts: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(opts.headers as Record<string, string> | undefined),
  }
  if (token) {
    headers['Authorization'] = 'Bearer ' + token
  }

  const res = await fetch(API + url, { headers, ...opts })

  if (res.status === 401) {
    clearSession()
    throw new Error('登录已过期，请重新登录')
  }
  if (res.status === 403) {
    const err = await res.json().catch(() => ({} as Record<string, any>))
    throw new Error(err.detail || '权限不足')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({} as Record<string, any>))
    throw new Error(err.detail || res.statusText)
  }
  return (await res.json()) as T
}
