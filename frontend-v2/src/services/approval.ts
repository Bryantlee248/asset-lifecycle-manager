// Approval workflow service — faithful 1:1 port of the legacy approval loaders
// from frontend/index.html (lines ~3862-4040). URLs / methods / query params /
// body fields are copied verbatim; no invented endpoints.

import { api } from '@/services/api'

/** GET /api/approval-requests/stats */
export async function getApprovalStats(): Promise<any> {
  return api('/api/approval-requests/stats')
}

/** GET /api/approval-config/dropdowns -> { approval_types, approval_statuses } */
export async function getApprovalDropdowns(): Promise<{ approval_types: any[]; approval_statuses: any[] }> {
  return api('/api/approval-config/dropdowns')
}

/** GET /api/approval-notifications/unread-count -> { unread_count } */
export async function getApprovalUnread(): Promise<{ unread_count: number }> {
  return api('/api/approval-notifications/unread-count')
}

/** GET /api/approval-requests/my-applications?page={page}&page_size=20 */
export async function getMyApplications(page = 1): Promise<any> {
  return api(`/api/approval-requests/my-applications?page=${page}&page_size=20`)
}

/** GET /api/approval-requests/my-pending?page={page}&page_size=20 */
export async function getMyPending(page = 1): Promise<any> {
  return api(`/api/approval-requests/my-pending?page=${page}&page_size=20`)
}

export interface ApprovalRequestParams {
  page?: number
  page_size?: number
  approval_type?: string
  status?: string
  asset_code?: string
}

/** GET /api/approval-requests?page=&page_size=20 (+ optional filters) */
export async function getApprovalRequests(params: ApprovalRequestParams = {}): Promise<any> {
  const p = new URLSearchParams({
    page: String(params.page ?? 1),
    page_size: String(params.page_size ?? 20),
  })
  if (params.approval_type) p.set('approval_type', params.approval_type)
  if (params.status) p.set('status', params.status)
  if (params.asset_code) p.set('asset_code', params.asset_code)
  return api('/api/approval-requests?' + p.toString())
}

/** GET /api/approval-config/types -> { types:[{type_code,current_stage,target_stage,mode}] } */
export async function getApprovalConfigTypes(): Promise<{
  types: Array<{ type_code: string; current_stage: string; target_stage: string; mode: string }>
}> {
  return api('/api/approval-config/types')
}

/** GET /api/users/by-role/{role} */
export async function getUsersByRole(role: string): Promise<any> {
  return api(`/api/users/by-role/${role}`)
}

export interface CreateApprovalPayload {
  approval_type: string
  asset_code: string
  reason: string
  approver_ids?: Array<string | number>
}

/** POST /api/approval-requests body { approval_type, asset_code, reason, attachments:[], approver_ids } */
export async function createApproval(payload: CreateApprovalPayload): Promise<any> {
  const approver_ids =
    payload.approver_ids && payload.approver_ids.length ? payload.approver_ids : null
  return api('/api/approval-requests', {
    method: 'POST',
    body: JSON.stringify({
      approval_type: payload.approval_type,
      asset_code: payload.asset_code,
      reason: payload.reason,
      attachments: [],
      approver_ids,
    }),
  })
}

/** POST /api/approval-requests/{id}/submit body { approver_ids } (null if empty) */
export async function submitApproval(id: string | number, approver_ids: Array<string | number> = []): Promise<any> {
  return api(`/api/approval-requests/${id}/submit`, {
    method: 'POST',
    body: JSON.stringify({ approver_ids: approver_ids && approver_ids.length ? approver_ids : null }),
  })
}

/** POST /api/approval-requests/{id}/cancel */
export async function cancelApproval(id: string | number): Promise<any> {
  return api(`/api/approval-requests/${id}/cancel`, { method: 'POST' })
}

/** POST /api/approval-requests/{id}/action body { action:'approve', comment } */
export async function approveApproval(id: string | number, comment = '同意'): Promise<any> {
  return api(`/api/approval-requests/${id}/action`, {
    method: 'POST',
    body: JSON.stringify({ action: 'approve', comment }),
  })
}

/** POST /api/approval-requests/{id}/action body { action:'reject', comment } */
export async function rejectApproval(id: string | number, comment: string): Promise<any> {
  return api(`/api/approval-requests/${id}/action`, {
    method: 'POST',
    body: JSON.stringify({ action: 'reject', comment }),
  })
}

/** POST /api/approval-requests/{id}/resubmit body { reason } */
export async function resubmitApproval(id: string | number, reason: string): Promise<any> {
  return api(`/api/approval-requests/${id}/resubmit`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  })
}

/** GET /api/approval-requests/{id} */
export async function getApprovalDetail(id: string | number): Promise<any> {
  return api(`/api/approval-requests/${id}`)
}
