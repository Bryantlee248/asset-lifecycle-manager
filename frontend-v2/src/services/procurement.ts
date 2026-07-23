// Procurement service — faithful port of loadProcurements (~3097) and the
// sub-table CRUD via apiMap.procurement = 'procurements' (saveSubForm ~3067,
// deleteRecord ~3086). No invented URLs/fields.

import { api } from '@/services/api'
import type { Paged, ListParams } from '@/services/types'

export async function getProcurements(params: ListParams = {}): Promise<Paged> {
  const p = new URLSearchParams({
    page: String(params.page ?? 1),
    page_size: String(params.page_size ?? 20),
  })
  if (params.asset_code) p.set('asset_code', params.asset_code)
  return api('/api/procurements?' + p.toString())
}

export async function createProcurement(body: Record<string, any>): Promise<any> {
  return api('/api/procurements', { method: 'POST', body: JSON.stringify(body) })
}

export async function updateProcurement(id: string | number, body: Record<string, any>): Promise<any> {
  const { id: _omit, ...rest } = body
  return api(`/api/procurements/${id}`, { method: 'PUT', body: JSON.stringify(rest) })
}

export async function deleteProcurement(id: string | number): Promise<any> {
  return api(`/api/procurements/${id}`, { method: 'DELETE' })
}
