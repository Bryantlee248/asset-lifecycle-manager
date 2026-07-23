// Warranties (质保续保) service — faithful port of loadWarranties (~3121) and the
// sub-table CRUD via apiMap.warranty = 'warranties' (saveSubForm ~3067,
// deleteRecord ~3086). No invented URLs/fields.

import { api } from '@/services/api'
import type { Paged, ListParams } from '@/services/types'

export async function getWarranties(params: ListParams = {}): Promise<Paged> {
  const p = new URLSearchParams({
    page: String(params.page ?? 1),
    page_size: String(params.page_size ?? 20),
  })
  if (params.asset_code) p.set('asset_code', params.asset_code)
  return api('/api/warranties?' + p.toString())
}

export async function createWarranty(body: Record<string, any>): Promise<any> {
  return api('/api/warranties', { method: 'POST', body: JSON.stringify(body) })
}

export async function updateWarranty(id: string | number, body: Record<string, any>): Promise<any> {
  const { id: _omit, ...rest } = body
  return api(`/api/warranties/${id}`, { method: 'PUT', body: JSON.stringify(rest) })
}

export async function deleteWarranty(id: string | number): Promise<any> {
  return api(`/api/warranties/${id}`, { method: 'DELETE' })
}
