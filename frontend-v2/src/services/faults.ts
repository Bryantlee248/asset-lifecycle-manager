// Faults (故障维修) service — faithful port of loadFaults (~3113) and the
// sub-table CRUD via apiMap.fault = 'faults' (saveSubForm ~3067,
// deleteRecord ~3086). No invented URLs/fields.

import { api } from '@/services/api'
import type { Paged, ListParams } from '@/services/types'

export async function getFaults(params: ListParams = {}): Promise<Paged> {
  const p = new URLSearchParams({
    page: String(params.page ?? 1),
    page_size: String(params.page_size ?? 20),
  })
  if (params.asset_code) p.set('asset_code', params.asset_code)
  return api('/api/faults?' + p.toString())
}

export async function createFault(body: Record<string, any>): Promise<any> {
  return api('/api/faults', { method: 'POST', body: JSON.stringify(body) })
}

export async function updateFault(id: string | number, body: Record<string, any>): Promise<any> {
  const { id: _omit, ...rest } = body
  return api(`/api/faults/${id}`, { method: 'PUT', body: JSON.stringify(rest) })
}

export async function deleteFault(id: string | number): Promise<any> {
  return api(`/api/faults/${id}`, { method: 'DELETE' })
}
