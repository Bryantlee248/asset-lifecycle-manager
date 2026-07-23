// Retirements (退役报废) service — faithful port of loadRetirements (~3129) and
// the sub-table CRUD via apiMap.retirement = 'retirements' (saveSubForm ~3067,
// deleteRecord ~3086). No invented URLs/fields.

import { api } from '@/services/api'
import type { Paged, ListParams } from '@/services/types'

export async function getRetirements(params: ListParams = {}): Promise<Paged> {
  const p = new URLSearchParams({
    page: String(params.page ?? 1),
    page_size: String(params.page_size ?? 20),
  })
  if (params.asset_code) p.set('asset_code', params.asset_code)
  return api('/api/retirements?' + p.toString())
}

export async function createRetirement(body: Record<string, any>): Promise<any> {
  return api('/api/retirements', { method: 'POST', body: JSON.stringify(body) })
}

export async function updateRetirement(id: string | number, body: Record<string, any>): Promise<any> {
  const { id: _omit, ...rest } = body
  return api(`/api/retirements/${id}`, { method: 'PUT', body: JSON.stringify(rest) })
}

export async function deleteRetirement(id: string | number): Promise<any> {
  return api(`/api/retirements/${id}`, { method: 'DELETE' })
}
