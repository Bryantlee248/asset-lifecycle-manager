import { api, TOKEN_KEY, USER_KEY } from './api'
import type { User, LoginResult, Role } from './types'

/**
 * Auth service — faithful to the legacy `doLogin` / `doLogout` / `hasPerm`.
 * Every exported function builds its request through `api()` with the exact
 * URL / method / body the backend expects.
 */

export async function login(username: string, password: string): Promise<LoginResult> {
  const data = await api<LoginResult>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  // Persist exactly like the legacy app (localStorage keys are part of contract).
  try {
    localStorage.setItem(TOKEN_KEY, data.token)
    localStorage.setItem(USER_KEY, JSON.stringify(data.user))
  } catch {
    /* ignore storage failures */
  }
  return data
}

export function logout(): void {
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

export async function fetchMe(): Promise<User> {
  return api<User>('/api/auth/me')
}

export async function getPermissions(): Promise<string[]> {
  return api<string[]>('/api/auth/permissions')
}

/** Pure permission check — `admin` role implies every permission. */
export function hasPerm(user: Pick<User, 'permissions' | 'roles'> | null | undefined, perm: string): boolean {
  if (!user) return false
  const permissions: string[] = user.permissions || []
  if (permissions.includes(perm)) return true
  const roles: Role[] = user.roles || []
  return roles.some((r) => r.code === 'admin')
}
