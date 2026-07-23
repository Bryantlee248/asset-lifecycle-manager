<script setup lang="ts">
// Presentational read-only view of a record, rendered from a FieldDef schema.
// Keys map 1:1 to backend fields; unknown/empty values render as a dash.
import type { FieldDef } from './field'

const props = defineProps<{
  schema: FieldDef[]
  record: Record<string, any>
}>()

function display(key: string): string {
  const v = props.record?.[key]
  if (v === null || v === undefined || v === '') return '—'
  return String(v)
}
</script>

<template>
  <dl class="grid grid-cols-1 gap-x-4 gap-y-0 sm:grid-cols-2">
    <div
      v-for="f in schema"
      :key="f.key"
      class="flex flex-col border-b border-[var(--border)] py-2"
      :class="f.col === 2 ? 'sm:col-span-2' : ''"
    >
      <dt class="text-xs text-slate-400">{{ f.label }}</dt>
      <dd class="mt-0.5 text-sm text-slate-700">{{ display(f.key) }}</dd>
    </div>
    <div v-if="!schema.length" class="sm:col-span-2 py-6 text-center text-sm text-slate-400">
      无字段定义
    </div>
  </dl>
</template>
