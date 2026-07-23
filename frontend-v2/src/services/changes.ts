// Changes (变更迁移) service — faithful port of loadChanges (~3105) and the
// sub-table CRUD via apiMap.change = 'changes' (saveSubForm ~3067,
// deleteRecord ~3086). No invented URLs/fields.

import { api } from '@/services/api'
import type { Paged, ListParams } from '@/services/types'

export async function getChanges(params: ListParams = {}): Promise<Paged> {
  const p = new URLSearchParams({
    page: String(params.page ?? 1),
    page_size: String(params.page_size ?? 20),
  })
  if (params.asset_code) p.set('asset_code', params.asset_code)
  return api('/api/changes?' + p.toString())
}

export async function createChange(body: Record<string, any>): Promise<any> {
  return api('/api/changes', { method: 'POST', body: JSON.stringify(body) })
}

export async function updateChange(id: string | number, body: Record<string, any>): Promise<any> {
  const { id: _omit, ...rest } = body
  return api(`/api/changes/${id}`, { method: 'PUT', body: JSON.stringify(rest) })
}

export async function deleteChange(id: string | number): Promise<any> {
  return api(`/api/changes/${id}`, { method: 'DELETE' })
}
