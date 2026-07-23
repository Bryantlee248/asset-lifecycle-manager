import { api } from './api'
import type { Validation } from './types'

/** GET /api/validation — data quality check board for the command center. */
export async function getValidation(): Promise<Validation> {
  return api<Validation>('/api/validation')
}
