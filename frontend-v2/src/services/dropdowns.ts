import { api } from './api'
import type { Dropdowns, DistinctValues } from './types'

/** GET /api/config/dropdowns — dropdown option sources. */
export async function getDropdowns(): Promise<Dropdowns> {
  return api<Dropdowns>('/api/config/dropdowns')
}

/** GET /api/distinct-values — search-time distinct values (encapsulated, batch-2 ready). */
export async function getDistinctValues(): Promise<DistinctValues> {
  return api<DistinctValues>('/api/distinct-values')
}
