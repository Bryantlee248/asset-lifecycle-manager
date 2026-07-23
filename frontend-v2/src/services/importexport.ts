// Import / Export service — faithful 1:1 port of the legacy downloadTemplate /
// doImport / doExport loaders from frontend/index.html (lines ~3238-3338,
// ~3522-3545). The blob-download endpoints are NOT routed through api() because
// they return files; we use window.fetch with the Authorization header read
// from the same localStorage key the api layer uses (TOKEN_KEY = 'asset_token').
// No URL, credential, or endpoint is hardcoded beyond the documented /api paths.

import { TOKEN_KEY } from '@/services/api'

function getToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) || ''
  } catch {
    return ''
  }
}

function triggerDownload(blob: Blob, fallbackName: string, disposition: string | null): void {
  let filename = fallbackName
  if (disposition) {
    const match = disposition.match(/filename\*=UTF-8''(.+)/)
    if (match) filename = decodeURIComponent(match[1])
  }
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

async function fetchBlob(url: string): Promise<{ blob: Blob; disposition: string | null }> {
  const res = await window.fetch(url, {
    headers: { Authorization: 'Bearer ' + getToken() },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({} as Record<string, any>))
    throw new Error(err.detail || '下载失败')
  }
  const blob = await res.blob()
  const disposition = res.headers.get('Content-Disposition')
  return { blob, disposition }
}

/** GET /api/template/{type} -> fetch blob + trigger download, returns the blob. */
export async function downloadTemplate(type: string): Promise<Blob> {
  const { blob, disposition } = await fetchBlob(`/api/template/${type}`)
  triggerDownload(blob, `template_${type}.xlsx`, disposition)
  return blob
}

/**
 * POST /api/import/{type} (or /api/import/assets) with multipart FormData.
 * Returns the parsed JSON result (contains `success` field).
 */
export async function importFile(type: string, file: File | Blob): Promise<any> {
  const endpoint = type === 'assets' ? '/api/import/assets' : `/api/import/${type}`
  const formData = new FormData()
  formData.append('file', file as Blob)
  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) headers['Authorization'] = 'Bearer ' + token
  const res = await window.fetch(endpoint, { method: 'POST', body: formData, headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || '导入失败')
  }
  return res.json()
}

export interface ExportAssetsParams {
  category?: string
  stage?: string
  warranty_status?: string
  search?: string
}

/** GET /api/export/assets?category=&stage=&warranty_status=&search= (optional) */
export async function exportAssets(params: ExportAssetsParams = {}): Promise<Blob> {
  const p = new URLSearchParams()
  if (params.category) p.set('category', params.category)
  if (params.stage) p.set('stage', params.stage)
  if (params.warranty_status) p.set('warranty_status', params.warranty_status)
  if (params.search) p.set('search', params.search)
  const qs = p.toString()
  const { blob, disposition } = await fetchBlob(`/api/export/assets${qs ? '?' + qs : ''}`)
  triggerDownload(blob, 'export_assets.xlsx', disposition)
  return blob
}

/** GET /api/export/{type} -> blob download (type ∈ procurement|inbound|outbound|change|fault|warranty|retirement). */
export async function exportByType(type: string): Promise<Blob> {
  const { blob, disposition } = await fetchBlob(`/api/export/${type}`)
  triggerDownload(blob, `export_${type}.xlsx`, disposition)
  return blob
}

/** GET /api/stats/export -> blob download. */
export async function exportStats(): Promise<Blob> {
  const { blob, disposition } = await fetchBlob('/api/stats/export')
  triggerDownload(blob, '统计看板导出.xlsx', disposition)
  return blob
}
