import { describe, it, expect, beforeEach, vi } from 'vitest'

// ===========================================================================
// Contract test — proves the services layer does NOT invent API URLs, methods,
// or body fields, and that api() error handling matches the legacy behaviour
// (frontend/index.html ~lines 2336-2344):
//   401 -> '登录已过期，请重新登录'
//   403 -> err.detail || '权限不足'
//   !ok  -> err.detail || res.statusText
// ===========================================================================

const fetchMock = vi.fn()

function statusTextOf(status: number): string {
  switch (status) {
    case 200: return 'OK'
    case 401: return 'Unauthorized'
    case 403: return 'Forbidden'
    case 500: return 'Internal Server Error'
    default: return 'Error'
  }
}

function jsonResponse(status: number, body: Record<string, any>, ok = status >= 200 && status < 300) {
  return {
    status,
    ok,
    statusText: statusTextOf(status),
    json: async () => body,
  }
}

beforeEach(() => {
  localStorage.clear()
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

describe('api() error contract', () => {
  it('throws login-expired message on 401', async () => {
    fetchMock.mockResolvedValue(jsonResponse(401, {}))
    const { api } = await import('@/services/api')
    await expect(api('/api/whatever')).rejects.toThrow('登录已过期，请重新登录')
  })

  it('throws "权限不足" when 403 has no detail', async () => {
    fetchMock.mockResolvedValue(jsonResponse(403, {}))
    const { api } = await import('@/services/api')
    await expect(api('/x')).rejects.toThrow('权限不足')
  })

  it('throws err.detail when 403 provides one', async () => {
    fetchMock.mockResolvedValue(jsonResponse(403, { detail: '无权限访问' }))
    const { api } = await import('@/services/api')
    await expect(api('/x')).rejects.toThrow('无权限访问')
  })

  it('throws err.detail on generic error when present', async () => {
    fetchMock.mockResolvedValue(jsonResponse(500, { detail: '服务异常' }))
    const { api } = await import('@/services/api')
    await expect(api('/x')).rejects.toThrow('服务异常')
  })

  it('falls back to statusText when error has no detail', async () => {
    fetchMock.mockResolvedValue(jsonResponse(500, {}, false))
    const { api } = await import('@/services/api')
    await expect(api('/x')).rejects.toThrow('Internal Server Error')
  })

  it('returns parsed JSON on success', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: 1 }))
    const { api } = await import('@/services/api')
    await expect(api('/x')).resolves.toEqual({ ok: 1 })
  })
})

describe('service endpoints (URL / method / body contract)', () => {
  it('auth.login -> POST /api/auth/login with {username,password}', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(200, { token: 'T', user: { id: 1, permissions: [], roles: [] } }),
    )
    const auth = await import('@/services/auth')
    await auth.login('alice', 'secret')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, opts] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/auth/login')
    expect(opts.method).toBe('POST')
    expect(JSON.parse(opts.body)).toMatchObject({ username: 'alice', password: 'secret' })
    // token persisted under the legacy key
    expect(localStorage.getItem('asset_token')).toBe('T')
  })

  it('stats.getStats -> GET /api/stats', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(200, { total_assets: 10, by_stage: {}, by_category: {}, warranty_expired: 0, p1_p2_unresolved: 0 }),
    )
    const { getStats } = await import('@/services/stats')
    const data = await getStats()
    const [url, opts] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/stats')
    expect(opts?.method ?? 'GET').toBe('GET')
    expect(data.total_assets).toBe(10)
  })

  it('validation.getValidation -> GET /api/validation', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(200, { total_assets: 10, total_errors: 0, total_warnings: 0, checks: [] }),
    )
    const { getValidation } = await import('@/services/validation')
    const data = await getValidation()
    const [url] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/validation')
    expect(data.total_errors).toBe(0)
  })

  it('auth.fetchMe -> GET /api/auth/me', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { id: 2, permissions: [], roles: [] }))
    const auth = await import('@/services/auth')
    await auth.fetchMe()
    expect(fetchMock.mock.calls[0][0]).toBe('/api/auth/me')
  })
})

describe('hasPerm helper', () => {
  it('treats admin role as having every permission', async () => {
    const auth = await import('@/services/auth')
    expect(auth.hasPerm({ permissions: [], roles: [{ code: 'admin' }] }, 'anything')).toBe(true)
  })
  it('respects explicit permissions', async () => {
    const auth = await import('@/services/auth')
    expect(auth.hasPerm({ permissions: ['asset.view'], roles: [] }, 'asset.view')).toBe(true)
    expect(auth.hasPerm({ permissions: ['asset.view'], roles: [] }, 'asset.delete')).toBe(false)
  })
})
