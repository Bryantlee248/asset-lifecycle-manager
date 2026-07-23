// Stats service — extends the existing dashboard `getStats()` with the batch-3
// statistics endpoints, all 1:1 faithful to frontend/index.html (lines ~3482-3613).

import { api } from './api'
import type { Stats } from './types'

/** GET /api/stats — dashboard health/risk summary + distributions. */
export async function getStats(): Promise<Stats> {
  return api<Stats>('/api/stats')
}

/** GET /api/stats/overview */
export async function getOverview(): Promise<any> {
  return api('/api/stats/overview')
}

/** GET /api/stats/stage-distribution */
export async function getStageDistribution(): Promise<any> {
  return api('/api/stats/stage-distribution')
}

/** GET /api/stats/category-composition?include_code=true */
export async function getCategoryComposition(includeCode = true): Promise<any> {
  return api(`/api/stats/category-composition?include_code=${includeCode}`)
}

/** GET /api/stats/reliability?top_n={topN} */
export async function getReliability(topN = 10): Promise<any> {
  return api(`/api/stats/reliability?top_n=${topN}`)
}

/** GET /api/stats/warranty-buckets */
export async function getWarrantyBuckets(): Promise<any> {
  return api('/api/stats/warranty-buckets')
}

/** GET /api/stats/aggregate?field={field}&metric={metric} */
export async function getAggregate(field: string, metric = 'count'): Promise<any> {
  return api(
    `/api/stats/aggregate?field=${encodeURIComponent(field)}&metric=${encodeURIComponent(metric)}`,
  )
}

/** GET /api/stats/stage-trend?months={months} */
export async function getStageTrend(months = 12): Promise<any> {
  return api(`/api/stats/stage-trend?months=${months}`)
}

/** GET /api/stats/compare?range_a={rangeA}&range_b={rangeB}&metric={metric} */
export async function getCompare(rangeA: string, rangeB: string, metric = 'stage'): Promise<any> {
  return api(
    `/api/stats/compare?range_a=${encodeURIComponent(rangeA)}&range_b=${encodeURIComponent(
      rangeB,
    )}&metric=${encodeURIComponent(metric)}`,
  )
}
