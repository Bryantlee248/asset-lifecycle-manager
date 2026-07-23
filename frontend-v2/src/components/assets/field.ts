// Shared field descriptor used by the generic detail/edit workbench so every
// lifecycle module can declare its record shape in one place (no invented
// labels — keys map 1:1 to the backend field names from frontend/index.html).

export interface FieldDef {
  key: string
  label: string
  type?: 'text' | 'number' | 'date' | 'textarea' | 'select'
  options?: string[]
  required?: boolean
  readonly?: boolean
  // grid span hint: 2 => full width on the 2-col detail layout
  col?: 1 | 2
}

// Read-only keys that must never be sent back in a PUT/POST body.
export const READONLY_KEYS = new Set([
  'id',
  'created_at',
  'updated_at',
  'created_by',
  'updated_by',
])
