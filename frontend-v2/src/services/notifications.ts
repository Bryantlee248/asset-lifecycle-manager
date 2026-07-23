// Approval notification service — faithful 1:1 port of the legacy notification
// loaders from frontend/index.html (lines ~3874, ~4062-4073).

import { api } from '@/services/api'

/** GET /api/approval-notifications/unread-count -> { unread_count } */
export async function getNotificationUnreadCount(): Promise<{ unread_count: number }> {
  return api('/api/approval-notifications/unread-count')
}

/** GET /api/approval-notifications?page={page}&page_size=20 */
export async function getNotifications(page = 1): Promise<any> {
  return api(`/api/approval-notifications?page=${page}&page_size=20`)
}

/** PUT /api/approval-notifications/{id}/read */
export async function markNotificationRead(id: string | number): Promise<any> {
  return api(`/api/approval-notifications/${id}/read`, { method: 'PUT' })
}

/** PUT /api/approval-notifications/read-all */
export async function markAllNotificationsRead(): Promise<any> {
  return api('/api/approval-notifications/read-all', { method: 'PUT' })
}
