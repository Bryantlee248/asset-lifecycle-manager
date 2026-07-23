import { describe, it, expect, beforeEach, vi } from 'vitest'

// ===========================================================================
// Batch-2 contract test — proves the 8 lifecycle services (assets, procurement,
// inbound, outbound, changes, faults, warranties, retirements) do NOT invent
// API URLs, methods, or body fields, and that the services layer matches the
// legacy behaviour in frontend/index.html (the `api()` client is the same one
// covered by services.contract.spec.ts).
//
// Each case stubs a global fetch, invokes the service, then asserts the URL
// (pathname + searchParams) and the request method / body. We resolve every
// call with `{ items: [], total: 0 }` so `api()` returns successfully.
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

// Resolve a recorded fetch call into { url, opts, parsed } where `parsed` is a
// URL object (resolved against a dummy origin) for easy pathname/searchParams checks.
function parseCall(index = 0) {
  const [url, opts] = fetchMock.mock.calls[index]
  return {
    url: String(url),
    opts: (opts ?? {}) as RequestInit,
    parsed: new URL(String(url), 'http://localhost'),
  }
}

beforeEach(() => {
  localStorage.clear()
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

// Small helper to assert a list GET endpoint's path + query params.
function expectListGet(
  pathname: string,
  params: Record<string, string>,
) {
  const { parsed, opts } = parseCall()
  expect(opts.method ?? 'GET').toBe('GET')
  expect(parsed.pathname).toBe(pathname)
  for (const [k, v] of Object.entries(params)) {
    expect(parsed.searchParams.get(k), `query param ${k}`).toBe(v)
  }
}

// Small helper to assert a CRUD base URL.
function expectCrud(
  method: 'POST' | 'PUT' | 'DELETE',
  pathname: string,
  bodyCheck?: (body: any) => void,
) {
  const { parsed, opts } = parseCall()
  expect(opts.method).toBe(method)
  expect(parsed.pathname).toBe(pathname)
  if (bodyCheck) bodyCheck(opts.body !== undefined ? JSON.parse(String(opts.body)) : undefined)
}

describe('assets service contract', () => {
  it('getAssets -> GET /api/assets with full query', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { items: [], total: 0 }))
    const { getAssets } = await import('@/services/assets')
    await getAssets({ page: 1, page_size: 20, search: 's', category: 'c', stage: 'st', warranty_status: 'w' })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expectListGet('/api/assets', {
      page: '1',
      page_size: '20',
      search: 's',
      category: 'c',
      stage: 'st',
      warranty_status: 'w',
    })
  })

  it('createAsset -> POST /api/assets with JSON body', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: 1 }))
    const { createAsset } = await import('@/services/assets')
    const body = { asset_code: 'A9', device_name: 'x' }
    await createAsset(body)
    expectCrud('POST', '/api/assets', (b) => expect(b).toEqual(body))
  })

  it('updateAsset(7, body) -> PUT /api/assets/7, body strips id', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: 1 }))
    const { updateAsset } = await import('@/services/assets')
    await updateAsset(7, { id: 7, device_name: 'y' })
    expectCrud('PUT', '/api/assets/7', (b) => {
      expect(b).toEqual({ device_name: 'y' })
      expect(b).not.toHaveProperty('id')
    })
  })

  it('deleteAsset(7) -> DELETE /api/assets/7', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: 1 }))
    const { deleteAsset } = await import('@/services/assets')
    await deleteAsset(7)
    expectCrud('DELETE', '/api/assets/7')
  })

  it('getAssetTimeline(A1) -> GET /api/assets/A1/timeline', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { timeline: [] }))
    const { getAssetTimeline } = await import('@/services/assets')
    await getAssetTimeline('A1')
    const { parsed, opts } = parseCall()
    expect(opts.method ?? 'GET').toBe('GET')
    expect(parsed.pathname).toBe('/api/assets/A1/timeline')
  })

  it('stageGate(A1, 运行) -> GET /api/assets/A1/stage-gate/运行 (encodeURIComponent)', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { allowed: true }))
    const { stageGate } = await import('@/services/assets')
    await stageGate('A1', '运行')
    const { parsed, opts } = parseCall()
    expect(opts.method ?? 'GET').toBe('GET')
    // NOTE: URL.pathname preserves percent-encoding — the legacy contract
    // URL-encodes the stage (frontend/index.html:3017; src/services/assets.ts:40),
    // so the encoded form is the correct expected value here.
    expect(parsed.pathname).toBe('/api/assets/A1/stage-gate/' + encodeURIComponent('运行'))
  })

  it('searchAssets(q) -> GET /api/assets?search=q&page_size=20', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { items: [], total: 0 }))
    const { searchAssets } = await import('@/services/assets')
    await searchAssets('q')
    expectListGet('/api/assets', { search: 'q', page_size: '20' })
  })
})

describe('procurement service contract', () => {
  it('getProcurements -> GET /api/procurements with query', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { items: [], total: 0 }))
    const { getProcurements } = await import('@/services/procurement')
    await getProcurements({ page: 1, asset_code: 'A1' })
    expectListGet('/api/procurements', { page: '1', page_size: '20', asset_code: 'A1' })
  })
  it('createProcurement -> POST /api/procurements', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: 1 }))
    const { createProcurement } = await import('@/services/procurement')
    await createProcurement({ po: 'P1' })
    expectCrud('POST', '/api/procurements', (b) => expect(b).toEqual({ po: 'P1' }))
  })
  it('updateProcurement(7, body) -> PUT /api/procurements/7 strips id', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: 1 }))
    const { updateProcurement } = await import('@/services/procurement')
    await updateProcurement(7, { id: 7, po: 'P2' })
    expectCrud('PUT', '/api/procurements/7', (b) => {
      expect(b).toEqual({ po: 'P2' })
      expect(b).not.toHaveProperty('id')
    })
  })
  it('deleteProcurement(7) -> DELETE /api/procurements/7', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: 1 }))
    const { deleteProcurement } = await import('@/services/procurement')
    await deleteProcurement(7)
    expectCrud('DELETE', '/api/procurements/7')
  })
})

describe('inbound service contract', () => {
  it('getInbounds -> GET /api/asset-inbound with query', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { items: [], total: 0 }))
    const { getInbounds } = await import('@/services/inbound')
    await getInbounds({ page: 1, search: 's', receive_type: 'r' })
    expectListGet('/api/asset-inbound', { page: '1', page_size: '20', search: 's', receive_type: 'r' })
  })
  it('createInbound -> POST /api/asset-inbound', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: 1 }))
    const { createInbound } = await import('@/services/inbound')
    await createInbound({ asset_code: 'A1' })
    expectCrud('POST', '/api/asset-inbound', (b) => expect(b).toEqual({ asset_code: 'A1' }))
  })
  it('updateInbound(7, body) -> PUT /api/asset-inbound/7 strips id', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: 1 }))
    const { updateInbound } = await import('@/services/inbound')
    await updateInbound(7, { id: 7, qty: 3 })
    expectCrud('PUT', '/api/asset-inbound/7', (b) => {
      expect(b).toEqual({ qty: 3 })
      expect(b).not.toHaveProperty('id')
    })
  })
  it('deleteInbound(7) -> DELETE /api/asset-inbound/7', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: 1 }))
    const { deleteInbound } = await import('@/services/inbound')
    await deleteInbound(7)
    expectCrud('DELETE', '/api/asset-inbound/7')
  })
})

describe('outbound service contract', () => {
  it('getOutbounds -> GET /api/asset-outbound with query', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { items: [], total: 0 }))
    const { getOutbounds } = await import('@/services/outbound')
    await getOutbounds({ page: 1, search: 's', outbound_category: 'o' })
    expectListGet('/api/asset-outbound', { page: '1', page_size: '20', search: 's', outbound_category: 'o' })
  })
  it('createOutbound -> POST /api/asset-outbound', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: 1 }))
    const { createOutbound } = await import('@/services/outbound')
    await createOutbound({ asset_code: 'A1' })
    expectCrud('POST', '/api/asset-outbound', (b) => expect(b).toEqual({ asset_code: 'A1' }))
  })
  it('updateOutbound(7, body) -> PUT /api/asset-outbound/7 strips id', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: 1 }))
    const { updateOutbound } = await import('@/services/outbound')
    await updateOutbound(7, { id: 7, qty: 2 })
    expectCrud('PUT', '/api/asset-outbound/7', (b) => {
      expect(b).toEqual({ qty: 2 })
      expect(b).not.toHaveProperty('id')
    })
  })
  it('deleteOutbound(7) -> DELETE /api/asset-outbound/7', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: 1 }))
    const { deleteOutbound } = await import('@/services/outbound')
    await deleteOutbound(7)
    expectCrud('DELETE', '/api/asset-outbound/7')
  })
})

describe('changes service contract', () => {
  it('getChanges -> GET /api/changes with query', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { items: [], total: 0 }))
    const { getChanges } = await import('@/services/changes')
    await getChanges({ page: 1, asset_code: 'A1' })
    expectListGet('/api/changes', { page: '1', page_size: '20', asset_code: 'A1' })
  })
  it('createChange -> POST /api/changes', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: 1 }))
    const { createChange } = await import('@/services/changes')
    await createChange({ asset_code: 'A1' })
    expectCrud('POST', '/api/changes', (b) => expect(b).toEqual({ asset_code: 'A1' }))
  })
  it('updateChange(7, body) -> PUT /api/changes/7 strips id', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: 1 }))
    const { updateChange } = await import('@/services/changes')
    await updateChange(7, { id: 7, note: 'n' })
    expectCrud('PUT', '/api/changes/7', (b) => {
      expect(b).toEqual({ note: 'n' })
      expect(b).not.toHaveProperty('id')
    })
  })
  it('deleteChange(7) -> DELETE /api/changes/7', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: 1 }))
    const { deleteChange } = await import('@/services/changes')
    await deleteChange(7)
    expectCrud('DELETE', '/api/changes/7')
  })
})

describe('faults service contract', () => {
  it('getFaults -> GET /api/faults with query', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { items: [], total: 0 }))
    const { getFaults } = await import('@/services/faults')
    await getFaults({ page: 1, asset_code: 'A1' })
    expectListGet('/api/faults', { page: '1', page_size: '20', asset_code: 'A1' })
  })
  it('createFault -> POST /api/faults', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: 1 }))
    const { createFault } = await import('@/services/faults')
    await createFault({ asset_code: 'A1' })
    expectCrud('POST', '/api/faults', (b) => expect(b).toEqual({ asset_code: 'A1' }))
  })
  it('updateFault(7, body) -> PUT /api/faults/7 strips id', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: 1 }))
    const { updateFault } = await import('@/services/faults')
    await updateFault(7, { id: 7, desc: 'd' })
    expectCrud('PUT', '/api/faults/7', (b) => {
      expect(b).toEqual({ desc: 'd' })
      expect(b).not.toHaveProperty('id')
    })
  })
  it('deleteFault(7) -> DELETE /api/faults/7', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: 1 }))
    const { deleteFault } = await import('@/services/faults')
    await deleteFault(7)
    expectCrud('DELETE', '/api/faults/7')
  })
})

describe('warranties service contract', () => {
  it('getWarranties -> GET /api/warranties with query', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { items: [], total: 0 }))
    const { getWarranties } = await import('@/services/warranties')
    await getWarranties({ page: 1, asset_code: 'A1' })
    expectListGet('/api/warranties', { page: '1', page_size: '20', asset_code: 'A1' })
  })
  it('createWarranty -> POST /api/warranties', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: 1 }))
    const { createWarranty } = await import('@/services/warranties')
    await createWarranty({ asset_code: 'A1' })
    expectCrud('POST', '/api/warranties', (b) => expect(b).toEqual({ asset_code: 'A1' }))
  })
  it('updateWarranty(7, body) -> PUT /api/warranties/7 strips id', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: 1 }))
    const { updateWarranty } = await import('@/services/warranties')
    await updateWarranty(7, { id: 7, vendor: 'v' })
    expectCrud('PUT', '/api/warranties/7', (b) => {
      expect(b).toEqual({ vendor: 'v' })
      expect(b).not.toHaveProperty('id')
    })
  })
  it('deleteWarranty(7) -> DELETE /api/warranties/7', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: 1 }))
    const { deleteWarranty } = await import('@/services/warranties')
    await deleteWarranty(7)
    expectCrud('DELETE', '/api/warranties/7')
  })
})

describe('retirements service contract', () => {
  it('getRetirements -> GET /api/retirements with query', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { items: [], total: 0 }))
    const { getRetirements } = await import('@/services/retirements')
    await getRetirements({ page: 1, asset_code: 'A1' })
    expectListGet('/api/retirements', { page: '1', page_size: '20', asset_code: 'A1' })
  })
  it('createRetirement -> POST /api/retirements', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: 1 }))
    const { createRetirement } = await import('@/services/retirements')
    await createRetirement({ asset_code: 'A1' })
    expectCrud('POST', '/api/retirements', (b) => expect(b).toEqual({ asset_code: 'A1' }))
  })
  it('updateRetirement(7, body) -> PUT /api/retirements/7 strips id', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: 1 }))
    const { updateRetirement } = await import('@/services/retirements')
    await updateRetirement(7, { id: 7, reason: 'r' })
    expectCrud('PUT', '/api/retirements/7', (b) => {
      expect(b).toEqual({ reason: 'r' })
      expect(b).not.toHaveProperty('id')
    })
  })
  it('deleteRetirement(7) -> DELETE /api/retirements/7', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: 1 }))
    const { deleteRetirement } = await import('@/services/retirements')
    await deleteRetirement(7)
    expectCrud('DELETE', '/api/retirements/7')
  })
})
