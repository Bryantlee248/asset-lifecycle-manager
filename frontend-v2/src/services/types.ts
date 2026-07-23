// Shared API/domain types (shapes mirror what the backend returns; field names
// are not invented — they come from `frontend/index.html` and DESIGN-SPEC.md).

export interface Role {
  code: string
  name?: string
  [key: string]: any
}

export interface User {
  id: number | string
  username?: string
  name?: string
  permissions: string[]
  roles: Role[]
  [key: string]: any
}

export interface LoginResult {
  token: string
  user: User
}

export interface Stats {
  total_assets: number
  by_stage: Record<string, number>
  by_category: Record<string, number>
  warranty_expired: number
  p1_p2_unresolved: number
}

export type Severity = '严重' | '中等'

export interface ValidationCheck {
  check_name: string
  severity: Severity
  description: string
  count: number
  details: string[]
}

export interface Validation {
  total_assets: number
  total_errors: number
  total_warnings: number
  checks: ValidationCheck[]
}

export interface Dropdowns {
  categories: any[]
  lifecycle_stages: any[]
  warranty_statuses: any[]
  [key: string]: any
}

// Paginated list envelope returned by every lifecycle list endpoint.
// Mirrors the legacy `data.items` / `data.total` shape from frontend/index.html.
export interface Paged<T = Record<string, any>> {
  items: T[]
  total: number
}

// Shared query params understood by the lifecycle list endpoints.
export interface ListParams {
  page?: number | string
  page_size?: number | string
  search?: string
  asset_code?: string
  receive_type?: string
  outbound_category?: string
  category?: string
  stage?: string
  warranty_status?: string
}

export interface DistinctValues {
  [key: string]: any
}
