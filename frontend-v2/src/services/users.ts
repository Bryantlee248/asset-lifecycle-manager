// Users service — faithful 1:1 port of the legacy user management loaders from
// frontend/index.html (lines ~3712-3786).

import { api } from '@/services/api'

export interface UserListParams {
  page?: number
  page_size?: number
  search?: string
  status?: string
}

/** GET /api/users?page=&page_size=20 (+ optional search/status) */
export async function getUsers(params: UserListParams = {}): Promise<any> {
  const p = new URLSearchParams({
    page: String(params.page ?? 1),
    page_size: String(params.page_size ?? 20),
  })
  if (params.search) p.set('search', params.search)
  if (params.status) p.set('status', params.status)
  return api('/api/users?' + p.toString())
}

/** GET /api/roles -> { items: [...] } */
export async function getAllRoles(): Promise<{ items: any[] }> {
  return api('/api/roles')
}

/** POST /api/users body { username, real_name, email, phone, department, status, password, role_ids } */
export async function createUser(body: Record<string, any>): Promise<any> {
  return api('/api/users', { method: 'POST', body: JSON.stringify(body) })
}

/** PUT /api/users/{id} — strip id from body; drop password when empty. */
export async function updateUser(id: string | number, body: Record<string, any>): Promise<any> {
  const { id: _omit, ...rest } = body
  const payload: Record<string, any> = { ...rest }
  if (!payload.password) delete payload.password
  return api(`/api/users/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
}

/** DELETE /api/users/{id} */
export async function deleteUser(id: string | number): Promise<any> {
  return api(`/api/users/${id}`, { method: 'DELETE' })
}

/** POST /api/users/{id}/reset-password body { new_password: null } */
export async function resetPassword(id: string | number): Promise<any> {
  return api(`/api/users/${id}/reset-password`, {
    method: 'POST',
    body: JSON.stringify({ new_password: null }),
  })
}
