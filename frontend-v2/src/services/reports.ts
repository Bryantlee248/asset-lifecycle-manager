// Reports service — faithful 1:1 port of the legacy report loaders from
// frontend/index.html (lines ~3689-3698).

import { api } from '@/services/api'

/** GET /api/reports/comprehensive */
export async function getComprehensiveReport(): Promise<any> {
  return api('/api/reports/comprehensive')
}

/** GET /api/reports/warranty-expiry?days={days} */
export async function getWarrantyExpiryReport(days = 90): Promise<any> {
  return api(`/api/reports/warranty-expiry?days=${days}`)
}
