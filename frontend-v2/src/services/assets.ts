// Assets service — 1:1 faithful port of the legacy asset loaders in
// frontend/index.html (loadAssets ~2962, showAssetDetail ~3025, saveAsset ~2984,
// deleteAsset ~3002, onStageChange ~3014, searchAssetsForSelect ~3046).
// No invented URLs, query params, or body fields.

import { api } from '@/services/api'
import type { Paged, ListParams } from '@/services/types'

export async function getAssets(params: ListParams = {}): Promise<Paged> {
  const p = new URLSearchParams({
    page: String(params.page ?? 1),
    page_size: String(params.page_size ?? 20),
  })
  if (params.search) p.set('search', params.search)
  if (params.category) p.set('category', params.category)
  if (params.stage) p.set('stage', params.stage)
  if (params.warranty_status) p.set('warranty_status', params.warranty_status)
  return api('/api/assets?' + p.toString())
}

export async function getAssetTimeline(assetCode: string): Promise<{ timeline: any[] }> {
  return api(`/api/assets/${encodeURIComponent(assetCode)}/timeline`)
}

export async function createAsset(body: Record<string, any>): Promise<any> {
  return api('/api/assets', { method: 'POST', body: JSON.stringify(body) })
}

export async function updateAsset(id: string | number, body: Record<string, any>): Promise<any> {
  const { id: _omit, ...rest } = body
  return api(`/api/assets/${id}`, { method: 'PUT', body: JSON.stringify(rest) })
}

export async function deleteAsset(id: string | number): Promise<any> {
  return api(`/api/assets/${id}`, { method: 'DELETE' })
}

// Stage-gate pre-check (legacy onStageChange). Returns { allowed, message }.
export async function stageGate(assetCode: string, stage: string): Promise<any> {
  return api(`/api/assets/${encodeURIComponent(assetCode)}/stage-gate/${encodeURIComponent(stage)}`)
}

export async function searchAssets(query: string, pageSize = 20): Promise<Paged> {
  const p = new URLSearchParams({ search: query, page_size: String(pageSize) })
  return api('/api/assets?' + p.toString())
}
