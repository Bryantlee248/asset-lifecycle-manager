// Roles service — faithful 1:1 port of the legacy role management loaders from
// frontend/index.html (lines ~3789-3843).

import { api } from '@/services/api'

/** GET /api/roles -> { items: [...] } */
export async function getRoles(): Promise<{ items: any[] }> {
  return api('/api/roles')
}

/** GET /api/auth/permissions -> { groups:[{ permissions:[...] }] } */
export async function getPermissionConfig(): Promise<{
  groups: Array<{ group?: string; name?: string; permissions: any[] }>
}> {
  return api('/api/auth/permissions')
}

export interface RoleBody {
  name: string
  code: string
  description?: string
  permissions: string[]
}

/** POST /api/roles body { name, code, description, permissions:[...] } */
export async function createRole(body: RoleBody): Promise<any> {
  return api('/api/roles', { method: 'POST', body: JSON.stringify(body) })
}

/** PUT /api/roles/{id} body { name, code, description, permissions:[...] } */
export async function updateRole(id: string | number, body: RoleBody): Promise<any> {
  return api(`/api/roles/${id}`, { method: 'PUT', body: JSON.stringify(body) })
}

/** DELETE /api/roles/{id} */
export async function deleteRole(id: string | number): Promise<any> {
  return api(`/api/roles/${id}`, { method: 'DELETE' })
}
