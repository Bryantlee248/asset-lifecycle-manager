// Config-center service — faithful 1:1 port of the legacy configuration loaders
// from frontend/index.html (lines ~2430-2831, ~2952). Every function is a thin
// wrapper over the documented /api/config endpoints; no URL/field is invented.

import { api } from '@/services/api'

// ---- Dictionary groups / categories / dictionaries ----
export async function getDictionaryGroups(): Promise<any> {
  return api('/api/config/dictionary-groups')
}

export async function getCategories(): Promise<any> {
  return api('/api/config/categories')
}

export async function getDictionaries(groupCode: string): Promise<any> {
  return api(`/api/config/dictionaries?group_code=${encodeURIComponent(groupCode)}`)
}

export async function createDictionary(body: Record<string, any>): Promise<any> {
  return api('/api/config/dictionaries', { method: 'POST', body: JSON.stringify(body) })
}

export async function updateDictionary(id: string | number, body: Record<string, any>): Promise<any> {
  const { id: _omit, ...rest } = body
  return api(`/api/config/dictionaries/${id}`, { method: 'PUT', body: JSON.stringify(rest) })
}

export async function toggleDictionary(id: string | number): Promise<any> {
  return api(`/api/config/dictionaries/${id}/toggle`, { method: 'POST' })
}

export async function deleteDictionary(id: string | number): Promise<any> {
  return api(`/api/config/dictionaries/${id}`, { method: 'DELETE' })
}

export async function getReferences(kind: string, value: string): Promise<any> {
  return api(
    `/api/config/references?kind=${encodeURIComponent(kind)}&value=${encodeURIComponent(value)}`,
  )
}

// ---- Validation rules ----
export async function getValidationRules(): Promise<any> {
  return api('/api/config/validation-rules')
}

export async function toggleValidationRule(id: string | number): Promise<any> {
  return api(`/api/config/validation-rules/${id}/toggle`, { method: 'POST' })
}

export async function updateValidationRule(id: string | number, remark: string): Promise<any> {
  return api(`/api/config/validation-rules/${id}`, {
    method: 'PUT',
    body: JSON.stringify({ remark }),
  })
}

export async function resetValidationRules(): Promise<any> {
  return api('/api/config/validation-rules/reset', { method: 'POST' })
}

export async function exportValidationRules(): Promise<any> {
  return api('/api/config/validation-rules/export')
}

export async function importValidationRules(rules: any[]): Promise<any> {
  return api('/api/config/validation-rules/import', {
    method: 'POST',
    body: JSON.stringify({ rules }),
  })
}

// ---- Aggregate fields ----
export async function getAggregateFields(): Promise<any> {
  return api('/api/config/aggregate-fields')
}

export async function getAggregateFieldColumns(): Promise<any> {
  return api('/api/config/aggregate-field-columns')
}

export async function updateAggregateField(
  id: string | number,
  payload: { field_label: string; remark?: string | null },
): Promise<any> {
  return api(`/api/config/aggregate-fields/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function createAggregateField(payload: {
  field_key: string
  field_label: string
  metric_support?: any[]
  remark?: string | null
}): Promise<any> {
  return api('/api/config/aggregate-fields', { method: 'POST', body: JSON.stringify(payload) })
}

export async function toggleAggregateField(id: string | number): Promise<any> {
  return api(`/api/config/aggregate-fields/${id}/toggle`, { method: 'POST' })
}

export async function deleteAggregateField(id: string | number): Promise<any> {
  return api(`/api/config/aggregate-fields/${id}`, { method: 'DELETE' })
}

export async function resetAggregateFields(): Promise<any> {
  return api('/api/config/aggregate-fields/reset', { method: 'POST' })
}

export async function exportAggregateFields(): Promise<any> {
  return api('/api/config/aggregate-fields/export')
}

export async function importAggregateFields(fields: any[]): Promise<any> {
  return api('/api/config/aggregate-fields/import', {
    method: 'POST',
    body: JSON.stringify({ fields }),
  })
}

// ---- Stage transitions ----
export async function getStageTransitions(): Promise<any> {
  return api('/api/config/stage-transitions')
}

export async function updateStageTransition(id: string | number, body: Record<string, any>): Promise<any> {
  const { id: _omit, ...rest } = body
  return api(`/api/config/stage-transitions/${id}`, { method: 'PUT', body: JSON.stringify(rest) })
}

export async function createStageTransition(body: Record<string, any>): Promise<any> {
  return api('/api/config/stage-transitions', { method: 'POST', body: JSON.stringify(body) })
}

export async function toggleStageTransition(id: string | number): Promise<any> {
  return api(`/api/config/stage-transitions/${id}/toggle`, { method: 'POST' })
}

export async function deleteStageTransition(id: string | number): Promise<any> {
  return api(`/api/config/stage-transitions/${id}`, { method: 'DELETE' })
}

export async function exportStageTransitions(): Promise<any> {
  return api('/api/config/stage-transitions/export')
}

export async function importStageTransitions(rules: any[]): Promise<any> {
  return api('/api/config/stage-transitions/import', {
    method: 'POST',
    body: JSON.stringify({ rules }),
  })
}

// ---- Dropdowns ----
export async function getConfigDropdowns(): Promise<any> {
  return api('/api/config/dropdowns')
}
