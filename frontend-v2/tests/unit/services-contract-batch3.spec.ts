import { describe, it, expect, beforeEach, vi } from 'vitest'

// ===========================================================================
// Batch-3 contract test — proves the collaboration / insights / governance /
// user-role / config services do NOT invent API URLs, methods, or body fields,
// and that they stay 1:1 with the legacy loaders in frontend/index.html.
//
// Cross-checked against legacy index.html for the endpoints it defines
// (approval-requests, approval-notifications, config dictionaries/validation/
// aggregate/stage-transitions, stats, import/export/template, reports, roles,
// auth/permissions, users). The config `toggle`/`import`/`export`/`reset` and
// the newer stats endpoints (aggregate / compare / category-composition) are
// new batch-3 backend endpoints absent from the older legacy snapshot; they are
// asserted here per the documented contract (task spec), not against legacy.
//
// Each case stubs a global fetch, invokes the service, then asserts the URL
// (pathname + searchParams) and the request method / body. Resolves every call
// with a success so api() returns without throwing.
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

// A blob-shaped response for the importexport window.fetch paths.
function blobResponse() {
  return {
    ok: true,
    status: 200,
    statusText: 'OK',
    headers: { get: () => null },
    blob: async () => ({ __blob: true } as any),
    json: async () => ({} as any),
  }
}

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

function expectListGet(pathname: string, params: Record<string, string>) {
  const { parsed, opts } = parseCall()
  expect(opts.method ?? 'GET').toBe('GET')
  expect(parsed.pathname).toBe(pathname)
  for (const [k, v] of Object.entries(params)) {
    expect(parsed.searchParams.get(k), `query param ${k}`).toBe(v)
  }
}

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

// ---------------------------------------------------------------------------
// approval.ts
// ---------------------------------------------------------------------------
describe('approval service contract', () => {
  it('getApprovalStats -> GET /api/approval-requests/stats', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { getApprovalStats } = await import('@/services/approval')
    await getApprovalStats()
    expectListGet('/api/approval-requests/stats', {})
  })

  it('getApprovalDropdowns -> GET /api/approval-config/dropdowns', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { getApprovalDropdowns } = await import('@/services/approval')
    await getApprovalDropdowns()
    expectListGet('/api/approval-config/dropdowns', {})
  })

  it('getApprovalUnread -> GET /api/approval-notifications/unread-count', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { unread_count: 0 }))
    const { getApprovalUnread } = await import('@/services/approval')
    await getApprovalUnread()
    expectListGet('/api/approval-notifications/unread-count', {})
  })

  it('getMyApplications(2) -> GET /api/approval-requests/my-applications?page=2&page_size=20', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { items: [], total: 0 }))
    const { getMyApplications } = await import('@/services/approval')
    await getMyApplications(2)
    expectListGet('/api/approval-requests/my-applications', { page: '2', page_size: '20' })
  })

  it('getMyPending(3) -> GET /api/approval-requests/my-pending?page=3&page_size=20', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { items: [], total: 0 }))
    const { getMyPending } = await import('@/services/approval')
    await getMyPending(3)
    expectListGet('/api/approval-requests/my-pending', { page: '3', page_size: '20' })
  })

  it('getApprovalRequests() -> GET /api/approval-requests?page=1&page_size=20', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { items: [], total: 0 }))
    const { getApprovalRequests } = await import('@/services/approval')
    await getApprovalRequests()
    expectListGet('/api/approval-requests', { page: '1', page_size: '20' })
  })

  it('getApprovalRequests({approval_type}) adds &approval_type', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { items: [], total: 0 }))
    const { getApprovalRequests } = await import('@/services/approval')
    await getApprovalRequests({ approval_type: '采购' })
    expectListGet('/api/approval-requests', { page: '1', page_size: '20', approval_type: '采购' })
  })

  it('getApprovalRequests({status, asset_code}) adds both filters', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { items: [], total: 0 }))
    const { getApprovalRequests } = await import('@/services/approval')
    await getApprovalRequests({ status: 'pending', asset_code: 'A1' })
    expectListGet('/api/approval-requests', { page: '1', page_size: '20', status: 'pending', asset_code: 'A1' })
  })

  it('getApprovalConfigTypes -> GET /api/approval-config/types', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { types: [] }))
    const { getApprovalConfigTypes } = await import('@/services/approval')
    await getApprovalConfigTypes()
    expectListGet('/api/approval-config/types', {})
  })

  it('getUsersByRole("manager") -> GET /api/users/by-role/manager', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, []))
    const { getUsersByRole } = await import('@/services/approval')
    await getUsersByRole('manager')
    expectListGet('/api/users/by-role/manager', {})
  })

  it('createApproval without approvers -> POST body has attachments:[] and approver_ids:null', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { createApproval } = await import('@/services/approval')
    await createApproval({ approval_type: '采购', asset_code: 'A1', reason: 'r' })
    expectCrud('POST', '/api/approval-requests', (b) => {
      expect(b).toEqual({ approval_type: '采购', asset_code: 'A1', reason: 'r', attachments: [], approver_ids: null })
    })
  })

  it('createApproval with approvers -> approver_ids forwarded', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { createApproval } = await import('@/services/approval')
    await createApproval({ approval_type: '采购', asset_code: 'A1', reason: 'r', approver_ids: [1, 2] })
    expectCrud('POST', '/api/approval-requests', (b) => {
      expect(b.approver_ids).toEqual([1, 2])
      expect(b.attachments).toEqual([])
    })
  })

  it('submitApproval(5) with no approvers -> POST /api/approval-requests/5/submit body approver_ids:null', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { submitApproval } = await import('@/services/approval')
    await submitApproval(5)
    expectCrud('POST', '/api/approval-requests/5/submit', (b) => expect(b).toEqual({ approver_ids: null }))
  })

  it('submitApproval(5, [9]) -> approver_ids:[9]', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { submitApproval } = await import('@/services/approval')
    await submitApproval(5, [9])
    expectCrud('POST', '/api/approval-requests/5/submit', (b) => expect(b).toEqual({ approver_ids: [9] }))
  })

  it('cancelApproval(5) -> POST /api/approval-requests/5/cancel', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { cancelApproval } = await import('@/services/approval')
    await cancelApproval(5)
    expectCrud('POST', '/api/approval-requests/5/cancel')
  })

  it('approveApproval(5, "ok") -> POST .../5/action body {action:"approve",comment:"ok"}', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { approveApproval } = await import('@/services/approval')
    await approveApproval(5, 'ok')
    expectCrud('POST', '/api/approval-requests/5/action', (b) => expect(b).toEqual({ action: 'approve', comment: 'ok' }))
  })

  it('rejectApproval(5, "no") -> POST .../5/action body {action:"reject",comment:"no"}', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { rejectApproval } = await import('@/services/approval')
    await rejectApproval(5, 'no')
    expectCrud('POST', '/api/approval-requests/5/action', (b) => expect(b).toEqual({ action: 'reject', comment: 'no' }))
  })

  it('resubmitApproval(5, "again") -> POST .../5/resubmit body {reason:"again"}', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { resubmitApproval } = await import('@/services/approval')
    await resubmitApproval(5, 'again')
    expectCrud('POST', '/api/approval-requests/5/resubmit', (b) => expect(b).toEqual({ reason: 'again' }))
  })

  it('getApprovalDetail(5) -> GET /api/approval-requests/5', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { getApprovalDetail } = await import('@/services/approval')
    await getApprovalDetail(5)
    expectListGet('/api/approval-requests/5', {})
  })
})

// ---------------------------------------------------------------------------
// notifications.ts
// ---------------------------------------------------------------------------
describe('notifications service contract', () => {
  it('getNotificationUnreadCount -> GET /api/approval-notifications/unread-count', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { unread_count: 0 }))
    const { getNotificationUnreadCount } = await import('@/services/notifications')
    await getNotificationUnreadCount()
    expectListGet('/api/approval-notifications/unread-count', {})
  })

  it('getNotifications(2) -> GET /api/approval-notifications?page=2&page_size=20', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { items: [], total: 0 }))
    const { getNotifications } = await import('@/services/notifications')
    await getNotifications(2)
    expectListGet('/api/approval-notifications', { page: '2', page_size: '20' })
  })

  it('markNotificationRead(5) -> PUT /api/approval-notifications/5/read', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { markNotificationRead } = await import('@/services/notifications')
    await markNotificationRead(5)
    expectCrud('PUT', '/api/approval-notifications/5/read')
  })

  it('markAllNotificationsRead -> PUT /api/approval-notifications/read-all', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { markAllNotificationsRead } = await import('@/services/notifications')
    await markAllNotificationsRead()
    expectCrud('PUT', '/api/approval-notifications/read-all')
  })
})

// ---------------------------------------------------------------------------
// importexport.ts — these hit window.fetch (not api()), stub global fetch.
// ---------------------------------------------------------------------------
describe('importexport service contract', () => {
  function stubDownloadUrl() {
    const c = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:x' as any)
    const r = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    return () => { c.mockRestore(); r.mockRestore() }
  }

  it('downloadTemplate("assets") -> GET /api/template/assets', async () => {
    fetchMock.mockResolvedValue(blobResponse())
    const restore = stubDownloadUrl()
    try {
      const { downloadTemplate } = await import('@/services/importexport')
      const blob = await downloadTemplate('assets')
      expect(blob).toBeTruthy()
      const { parsed, opts } = parseCall()
      expect(opts.method ?? 'GET').toBe('GET')
      expect(parsed.pathname).toBe('/api/template/assets')
    } finally { restore() }
  })

  it('importFile("assets", file) -> POST /api/import/assets with FormData file', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { success: true }))
    const { importFile } = await import('@/services/importexport')
    const file = new Blob(['x']) as any
    const res = await importFile('assets', file)
    expect(res.success).toBe(true)
    const { parsed, opts } = parseCall()
    expect(opts.method).toBe('POST')
    expect(parsed.pathname).toBe('/api/import/assets')
    expect(opts.body).toBeInstanceOf(FormData)
    expect((opts.body as FormData).get('file')).toBeTruthy()
  })

  it('importFile("users", file) -> POST /api/import/users with FormData file', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { success: true }))
    const { importFile } = await import('@/services/importexport')
    const file = new Blob(['x']) as any
    await importFile('users', file)
    const { parsed, opts } = parseCall()
    expect(opts.method).toBe('POST')
    expect(parsed.pathname).toBe('/api/import/users')
    expect(opts.body).toBeInstanceOf(FormData)
  })

  it('exportAssets({category:"c"}) -> GET /api/export/assets?category=c', async () => {
    fetchMock.mockResolvedValue(blobResponse())
    const restore = stubDownloadUrl()
    try {
      const { exportAssets } = await import('@/services/importexport')
      await exportAssets({ category: 'c' })
      const { parsed, opts } = parseCall()
      expect(opts.method ?? 'GET').toBe('GET')
      expect(parsed.pathname).toBe('/api/export/assets')
      expect(parsed.searchParams.get('category')).toBe('c')
    } finally { restore() }
  })

  it('exportAssets({}) -> GET /api/export/assets (no query)', async () => {
    fetchMock.mockResolvedValue(blobResponse())
    const restore = stubDownloadUrl()
    try {
      const { exportAssets } = await import('@/services/importexport')
      await exportAssets({})
      const { parsed, opts } = parseCall()
      expect(opts.method ?? 'GET').toBe('GET')
      expect(parsed.pathname).toBe('/api/export/assets')
      expect(parsed.search).toBe('')
    } finally { restore() }
  })

  it('exportByType("procurement") -> GET /api/export/procurement', async () => {
    fetchMock.mockResolvedValue(blobResponse())
    const restore = stubDownloadUrl()
    try {
      const { exportByType } = await import('@/services/importexport')
      await exportByType('procurement')
      const { parsed, opts } = parseCall()
      expect(opts.method ?? 'GET').toBe('GET')
      expect(parsed.pathname).toBe('/api/export/procurement')
    } finally { restore() }
  })

  it('exportStats() -> GET /api/stats/export', async () => {
    fetchMock.mockResolvedValue(blobResponse())
    const restore = stubDownloadUrl()
    try {
      const { exportStats } = await import('@/services/importexport')
      await exportStats()
      const { parsed, opts } = parseCall()
      expect(opts.method ?? 'GET').toBe('GET')
      expect(parsed.pathname).toBe('/api/stats/export')
    } finally { restore() }
  })
})

// ---------------------------------------------------------------------------
// reports.ts
// ---------------------------------------------------------------------------
describe('reports service contract', () => {
  it('getComprehensiveReport -> GET /api/reports/comprehensive', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { getComprehensiveReport } = await import('@/services/reports')
    await getComprehensiveReport()
    expectListGet('/api/reports/comprehensive', {})
  })

  it('getWarrantyExpiryReport(90) -> GET /api/reports/warranty-expiry?days=90', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { getWarrantyExpiryReport } = await import('@/services/reports')
    await getWarrantyExpiryReport(90)
    expectListGet('/api/reports/warranty-expiry', { days: '90' })
  })

  it('getWarrantyExpiryReport(30) -> GET /api/reports/warranty-expiry?days=30', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { getWarrantyExpiryReport } = await import('@/services/reports')
    await getWarrantyExpiryReport(30)
    expectListGet('/api/reports/warranty-expiry', { days: '30' })
  })
})

// ---------------------------------------------------------------------------
// stats.ts (extended)
// ---------------------------------------------------------------------------
describe('stats service contract (extended)', () => {
  it('getStats -> GET /api/stats', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { getStats } = await import('@/services/stats')
    await getStats()
    expectListGet('/api/stats', {})
  })
  it('getOverview -> GET /api/stats/overview', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { getOverview } = await import('@/services/stats')
    await getOverview()
    expectListGet('/api/stats/overview', {})
  })
  it('getStageDistribution -> GET /api/stats/stage-distribution', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { getStageDistribution } = await import('@/services/stats')
    await getStageDistribution()
    expectListGet('/api/stats/stage-distribution', {})
  })
  it('getCategoryComposition() -> GET /api/stats/category-composition?include_code=true', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { getCategoryComposition } = await import('@/services/stats')
    await getCategoryComposition()
    expectListGet('/api/stats/category-composition', { include_code: 'true' })
  })
  it('getReliability() -> GET /api/stats/reliability?top_n=10', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { getReliability } = await import('@/services/stats')
    await getReliability()
    expectListGet('/api/stats/reliability', { top_n: '10' })
  })
  it('getWarrantyBuckets -> GET /api/stats/warranty-buckets', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { getWarrantyBuckets } = await import('@/services/stats')
    await getWarrantyBuckets()
    expectListGet('/api/stats/warranty-buckets', {})
  })
  it('getAggregate("category","count") -> GET /api/stats/aggregate?field=category&metric=count', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { getAggregate } = await import('@/services/stats')
    await getAggregate('category', 'count')
    expectListGet('/api/stats/aggregate', { field: 'category', metric: 'count' })
  })
  it('getStageTrend() -> GET /api/stats/stage-trend?months=12', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { getStageTrend } = await import('@/services/stats')
    await getStageTrend()
    expectListGet('/api/stats/stage-trend', { months: '12' })
  })
  it('getCompare("2024","2025","stage") -> GET /api/stats/compare?range_a=2024&range_b=2025&metric=stage', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { getCompare } = await import('@/services/stats')
    await getCompare('2024', '2025', 'stage')
    expectListGet('/api/stats/compare', { range_a: '2024', range_b: '2025', metric: 'stage' })
  })
})

// ---------------------------------------------------------------------------
// users.ts
// ---------------------------------------------------------------------------
describe('users service contract', () => {
  it('getUsers() -> GET /api/users?page=1&page_size=20', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { items: [], total: 0 }))
    const { getUsers } = await import('@/services/users')
    await getUsers()
    expectListGet('/api/users', { page: '1', page_size: '20' })
  })
  it('getUsers({search,status}) -> adds &search &status', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { items: [], total: 0 }))
    const { getUsers } = await import('@/services/users')
    await getUsers({ search: 'x', status: 'active' })
    expectListGet('/api/users', { page: '1', page_size: '20', search: 'x', status: 'active' })
  })
  it('getAllRoles -> GET /api/roles', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { items: [] }))
    const { getAllRoles } = await import('@/services/users')
    await getAllRoles()
    expectListGet('/api/roles', {})
  })
  it('createUser({username:"u"}) -> POST /api/users body {username:"u"}', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { createUser } = await import('@/services/users')
    await createUser({ username: 'u' })
    expectCrud('POST', '/api/users', (b) => expect(b).toEqual({ username: 'u' }))
  })
  it('updateUser(5, {id, name, password:""}) -> PUT /api/users/5, strips id, drops empty password', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { updateUser } = await import('@/services/users')
    await updateUser(5, { id: 5, name: 'n', password: '' })
    expectCrud('PUT', '/api/users/5', (b) => {
      expect(b).toEqual({ name: 'n' })
      expect(b).not.toHaveProperty('id')
      expect(b).not.toHaveProperty('password')
    })
  })
  it('updateUser(5, {id, name, password:"secret"}) -> keeps non-empty password', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { updateUser } = await import('@/services/users')
    await updateUser(5, { id: 5, name: 'n', password: 'secret' })
    expectCrud('PUT', '/api/users/5', (b) => expect(b).toEqual({ name: 'n', password: 'secret' }))
  })
  it('deleteUser(5) -> DELETE /api/users/5', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { deleteUser } = await import('@/services/users')
    await deleteUser(5)
    expectCrud('DELETE', '/api/users/5')
  })
  it('resetPassword(5) -> POST /api/users/5/reset-password body {new_password:null}', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { resetPassword } = await import('@/services/users')
    await resetPassword(5)
    expectCrud('POST', '/api/users/5/reset-password', (b) => expect(b).toEqual({ new_password: null }))
  })
})

// ---------------------------------------------------------------------------
// roles.ts
// ---------------------------------------------------------------------------
describe('roles service contract', () => {
  it('getRoles -> GET /api/roles', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { items: [] }))
    const { getRoles } = await import('@/services/roles')
    await getRoles()
    expectListGet('/api/roles', {})
  })
  it('getPermissionConfig -> GET /api/auth/permissions', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { groups: [] }))
    const { getPermissionConfig } = await import('@/services/roles')
    await getPermissionConfig()
    expectListGet('/api/auth/permissions', {})
  })
  it('createRole({name,code,permissions}) -> POST /api/roles body', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { createRole } = await import('@/services/roles')
    await createRole({ name: 'r', code: 'rc', permissions: [] })
    expectCrud('POST', '/api/roles', (b) => expect(b).toEqual({ name: 'r', code: 'rc', permissions: [] }))
  })
  it('updateRole(5, {name}) -> PUT /api/roles/5 body', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { updateRole } = await import('@/services/roles')
    await updateRole(5, { name: 'r', code: 'rc', permissions: [] })
    expectCrud('PUT', '/api/roles/5', (b) => expect(b).toEqual({ name: 'r', code: 'rc', permissions: [] }))
  })
  it('deleteRole(5) -> DELETE /api/roles/5', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { deleteRole } = await import('@/services/roles')
    await deleteRole(5)
    expectCrud('DELETE', '/api/roles/5')
  })
})

// ---------------------------------------------------------------------------
// config.ts
// ---------------------------------------------------------------------------
describe('config service contract', () => {
  it('getDictionaryGroups -> GET /api/config/dictionary-groups', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { getDictionaryGroups } = await import('@/services/config')
    await getDictionaryGroups()
    expectListGet('/api/config/dictionary-groups', {})
  })
  it('getCategories -> GET /api/config/categories', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { getCategories } = await import('@/services/config')
    await getCategories()
    expectListGet('/api/config/categories', {})
  })
  it('getDictionaries("grp") -> GET /api/config/dictionaries?group_code=grp', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { getDictionaries } = await import('@/services/config')
    await getDictionaries('grp')
    expectListGet('/api/config/dictionaries', { group_code: 'grp' })
  })
  it('createDictionary({code:"c"}) -> POST /api/config/dictionaries body', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { createDictionary } = await import('@/services/config')
    await createDictionary({ code: 'c' })
    expectCrud('POST', '/api/config/dictionaries', (b) => expect(b).toEqual({ code: 'c' }))
  })
  it('updateDictionary(5, {id, code}) -> PUT /api/config/dictionaries/5 strips id', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { updateDictionary } = await import('@/services/config')
    await updateDictionary(5, { id: 5, code: 'c' })
    expectCrud('PUT', '/api/config/dictionaries/5', (b) => {
      expect(b).toEqual({ code: 'c' })
      expect(b).not.toHaveProperty('id')
    })
  })
  it('toggleDictionary(5) -> POST /api/config/dictionaries/5/toggle', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { toggleDictionary } = await import('@/services/config')
    await toggleDictionary(5)
    expectCrud('POST', '/api/config/dictionaries/5/toggle')
  })
  it('deleteDictionary(5) -> DELETE /api/config/dictionaries/5', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { deleteDictionary } = await import('@/services/config')
    await deleteDictionary(5)
    expectCrud('DELETE', '/api/config/dictionaries/5')
  })
  it('getReferences("k","v") -> GET /api/config/references?kind=k&value=v', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { getReferences } = await import('@/services/config')
    await getReferences('k', 'v')
    expectListGet('/api/config/references', { kind: 'k', value: 'v' })
  })
  it('getValidationRules -> GET /api/config/validation-rules', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { getValidationRules } = await import('@/services/config')
    await getValidationRules()
    expectListGet('/api/config/validation-rules', {})
  })
  it('toggleValidationRule(5) -> POST /api/config/validation-rules/5/toggle', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { toggleValidationRule } = await import('@/services/config')
    await toggleValidationRule(5)
    expectCrud('POST', '/api/config/validation-rules/5/toggle')
  })
  it('updateValidationRule(5, "note") -> PUT /api/config/validation-rules/5 body {remark}', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { updateValidationRule } = await import('@/services/config')
    await updateValidationRule(5, 'note')
    expectCrud('PUT', '/api/config/validation-rules/5', (b) => expect(b).toEqual({ remark: 'note' }))
  })
  it('resetValidationRules -> POST /api/config/validation-rules/reset', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { resetValidationRules } = await import('@/services/config')
    await resetValidationRules()
    expectCrud('POST', '/api/config/validation-rules/reset')
  })
  it('exportValidationRules -> GET /api/config/validation-rules/export', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { exportValidationRules } = await import('@/services/config')
    await exportValidationRules()
    expectListGet('/api/config/validation-rules/export', {})
  })
  it('importValidationRules([{x:1}]) -> POST /api/config/validation-rules/import body {rules}', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { importValidationRules } = await import('@/services/config')
    await importValidationRules([{ x: 1 }])
    expectCrud('POST', '/api/config/validation-rules/import', (b) => expect(b).toEqual({ rules: [{ x: 1 }] }))
  })
  it('getAggregateFields -> GET /api/config/aggregate-fields', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { getAggregateFields } = await import('@/services/config')
    await getAggregateFields()
    expectListGet('/api/config/aggregate-fields', {})
  })
  it('getAggregateFieldColumns -> GET /api/config/aggregate-field-columns', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { getAggregateFieldColumns } = await import('@/services/config')
    await getAggregateFieldColumns()
    expectListGet('/api/config/aggregate-field-columns', {})
  })
  it('updateAggregateField(5, {field_label,remark}) -> PUT /api/config/aggregate-fields/5', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { updateAggregateField } = await import('@/services/config')
    await updateAggregateField(5, { field_label: 'L', remark: 'r' })
    expectCrud('PUT', '/api/config/aggregate-fields/5', (b) => expect(b).toEqual({ field_label: 'L', remark: 'r' }))
  })
  it('createAggregateField({field_key,field_label}) -> POST /api/config/aggregate-fields', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { createAggregateField } = await import('@/services/config')
    await createAggregateField({ field_key: 'k', field_label: 'L' })
    expectCrud('POST', '/api/config/aggregate-fields', (b) => expect(b).toEqual({ field_key: 'k', field_label: 'L' }))
  })
  it('toggleAggregateField(5) -> POST /api/config/aggregate-fields/5/toggle', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { toggleAggregateField } = await import('@/services/config')
    await toggleAggregateField(5)
    expectCrud('POST', '/api/config/aggregate-fields/5/toggle')
  })
  it('deleteAggregateField(5) -> DELETE /api/config/aggregate-fields/5', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { deleteAggregateField } = await import('@/services/config')
    await deleteAggregateField(5)
    expectCrud('DELETE', '/api/config/aggregate-fields/5')
  })
  it('resetAggregateFields -> POST /api/config/aggregate-fields/reset', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { resetAggregateFields } = await import('@/services/config')
    await resetAggregateFields()
    expectCrud('POST', '/api/config/aggregate-fields/reset')
  })
  it('exportAggregateFields -> GET /api/config/aggregate-fields/export', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { exportAggregateFields } = await import('@/services/config')
    await exportAggregateFields()
    expectListGet('/api/config/aggregate-fields/export', {})
  })
  it('importAggregateFields([{k:1}]) -> POST /api/config/aggregate-fields/import body {fields}', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { importAggregateFields } = await import('@/services/config')
    await importAggregateFields([{ k: 1 }])
    expectCrud('POST', '/api/config/aggregate-fields/import', (b) => expect(b).toEqual({ fields: [{ k: 1 }] }))
  })
  it('getStageTransitions -> GET /api/config/stage-transitions', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { getStageTransitions } = await import('@/services/config')
    await getStageTransitions()
    expectListGet('/api/config/stage-transitions', {})
  })
  it('updateStageTransition(5, {from,to}) -> PUT /api/config/stage-transitions/5 strips id', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { updateStageTransition } = await import('@/services/config')
    await updateStageTransition(5, { id: 5, from: 'a', to: 'b' })
    expectCrud('PUT', '/api/config/stage-transitions/5', (b) => {
      expect(b).toEqual({ from: 'a', to: 'b' })
      expect(b).not.toHaveProperty('id')
    })
  })
  it('createStageTransition({from,to}) -> POST /api/config/stage-transitions body', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { createStageTransition } = await import('@/services/config')
    await createStageTransition({ from: 'a', to: 'b' })
    expectCrud('POST', '/api/config/stage-transitions', (b) => expect(b).toEqual({ from: 'a', to: 'b' }))
  })
  it('toggleStageTransition(5) -> POST /api/config/stage-transitions/5/toggle', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { toggleStageTransition } = await import('@/services/config')
    await toggleStageTransition(5)
    expectCrud('POST', '/api/config/stage-transitions/5/toggle')
  })
  it('deleteStageTransition(5) -> DELETE /api/config/stage-transitions/5', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { deleteStageTransition } = await import('@/services/config')
    await deleteStageTransition(5)
    expectCrud('DELETE', '/api/config/stage-transitions/5')
  })
  it('exportStageTransitions -> GET /api/config/stage-transitions/export', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { exportStageTransitions } = await import('@/services/config')
    await exportStageTransitions()
    expectListGet('/api/config/stage-transitions/export', {})
  })
  it('importStageTransitions([{a:1}]) -> POST /api/config/stage-transitions/import body {rules}', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { importStageTransitions } = await import('@/services/config')
    await importStageTransitions([{ a: 1 }])
    expectCrud('POST', '/api/config/stage-transitions/import', (b) => expect(b).toEqual({ rules: [{ a: 1 }] }))
  })
  it('getConfigDropdowns -> GET /api/config/dropdowns', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))
    const { getConfigDropdowns } = await import('@/services/config')
    await getConfigDropdowns()
    expectListGet('/api/config/dropdowns', {})
  })
})
