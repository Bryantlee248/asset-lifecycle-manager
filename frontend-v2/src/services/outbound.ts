// Outbound (资产移出) service — faithful port of loadOutbound (~3148) and the
// outbound CRUD (openOutboundForm ~3189, saveOutbound ~3198, deleteOutbound ~3213).
// Endpoints use the 'asset-outbound' base (apiMap.outbound). No invented fields.

import { api } from '@/services/api'
import type { Paged, ListParams } from '@/services/types'

export async function getOutbounds(params: ListParams = {}): Promise<Paged> {
  const p = new URLSearchParams({
    page: String(params.page ?? 1),
    page_size: String(params.page_size ?? 20),
  })
  if (params.search) p.set('search', params.search)
  if (params.outbound_category) p.set('outbound_category', params.outbound_category)
  return api('/api/asset-outbound?' + p.toString())
}

export async function createOutbound(body: Record<string, any>): Promise<any> {
  return api('/api/asset-outbound', { method: 'POST', body: JSON.stringify(body) })
}

export async function updateOutbound(id: string | number, body: Record<string, any>): Promise<any> {
  const { id: _omit, ...rest } = body
  return api(`/api/asset-outbound/${id}`, { method: 'PUT', body: JSON.stringify(rest) })
}

export async function deleteOutbound(id: string | number): Promise<any> {
  return api(`/api/asset-outbound/${id}`, { method: 'DELETE' })
}
