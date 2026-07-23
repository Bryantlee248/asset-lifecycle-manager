// Inbound (资产移入) service — faithful port of loadInbound (~3139) and the
// inbound CRUD (openInboundForm ~3157, saveInbound ~3167, deleteInbound ~3183).
// Endpoints use the 'asset-inbound' base (apiMap.inbound). No invented fields.

import { api } from '@/services/api'
import type { Paged, ListParams } from '@/services/types'

export async function getInbounds(params: ListParams = {}): Promise<Paged> {
  const p = new URLSearchParams({
    page: String(params.page ?? 1),
    page_size: String(params.page_size ?? 20),
  })
  if (params.search) p.set('search', params.search)
  if (params.receive_type) p.set('receive_type', params.receive_type)
  return api('/api/asset-inbound?' + p.toString())
}

export async function createInbound(body: Record<string, any>): Promise<any> {
  return api('/api/asset-inbound', { method: 'POST', body: JSON.stringify(body) })
}

export async function updateInbound(id: string | number, body: Record<string, any>): Promise<any> {
  const { id: _omit, ...rest } = body
  return api(`/api/asset-inbound/${id}`, { method: 'PUT', body: JSON.stringify(rest) })
}

export async function deleteInbound(id: string | number): Promise<any> {
  return api(`/api/asset-inbound/${id}`, { method: 'DELETE' })
}
