<script setup lang="ts">
import { ref, computed } from 'vue'
import SkeletonBlock from './SkeletonBlock.vue'
import EmptyState from './EmptyState.vue'

export interface GridColumn {
  key: string
  label: string
  sortable?: boolean
  align?: 'left' | 'right' | 'center'
  width?: string
  // when true, the parent provides a #cell-{key} slot for custom rendering
  slot?: boolean
}

const props = defineProps<{
  columns: GridColumn[]
  rows: Record<string, any>[]
  loading?: boolean
  emptyText?: string
  rowKey?: string
}>()

const sortKey = ref<string>('')
const sortDir = ref<'asc' | 'desc'>('asc')

function toggleSort(col: GridColumn) {
  if (!col.sortable) return
  if (sortKey.value === col.key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = col.key
    sortDir.value = 'asc'
  }
}

const sortedRows = computed(() => {
  if (!sortKey.value) return props.rows
  const col = sortKey.value
  const dir = sortDir.value === 'asc' ? 1 : -1
  return [...props.rows].sort((a, b) => {
    const av = a[col]
    const bv = b[col]
    if (av == null) return 1
    if (bv == null) return -1
    if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * dir
    return String(av).localeCompare(String(bv), 'zh-CN') * dir
  })
})

const alignClass = (a?: string) =>
  a === 'right' ? 'text-right' : a === 'center' ? 'text-center' : 'text-left'
</script>

<template>
  <div class="c2-panel overflow-hidden">
    <div class="scroll-thin overflow-x-auto">
      <table class="w-full border-collapse text-sm">
        <thead>
          <tr class="border-b border-[var(--border)] bg-[var(--canvas)] text-slate-500">
            <th
              v-for="col in columns"
              :key="col.key"
              class="px-3 py-2 font-medium"
              :class="alignClass(col.align)"
              :style="{ width: col.width }"
            >
              <button
                v-if="col.sortable"
                type="button"
                class="inline-flex items-center gap-1 hover:text-[var(--brand)]"
                :aria-label="`按 ${col.label} 排序`"
                @click="toggleSort(col)"
              >
                {{ col.label }}
                <span v-if="sortKey === col.key">{{ sortDir === 'asc' ? '▲' : '▼' }}</span>
              </button>
              <span v-else>{{ col.label }}</span>
            </th>
            <th v-if="$slots.actions" class="px-3 py-2 text-right font-medium">操作</th>
          </tr>
        </thead>
        <tbody v-if="loading">
          <tr v-for="n in 4" :key="n" class="border-b border-[var(--border)]">
            <td v-for="col in columns" :key="col.key" class="px-3 py-2.5">
              <SkeletonBlock height="12px" />
            </td>
          </tr>
        </tbody>
        <tbody v-else>
          <tr
            v-for="row in sortedRows"
            :key="row[rowKey || 'id'] ?? JSON.stringify(row)"
            class="border-b border-[var(--border)] transition-colors hover:bg-[var(--canvas)]"
          >
            <td
              v-for="col in columns"
              :key="col.key"
              class="px-3 py-2.5 text-slate-700"
              :class="alignClass(col.align)"
            >
              <slot v-if="col.slot" :name="`cell-${col.key}`" :row="row" :value="row[col.key]" />
              <template v-else>{{ row[col.key] }}</template>
            </td>
            <td v-if="$slots.actions" class="px-3 py-2.5 text-right">
              <slot name="actions" :row="row" />
            </td>
          </tr>
          <tr v-if="!sortedRows.length">
            <td :colspan="columns.length + ($slots.actions ? 1 : 0)">
              <EmptyState :title="emptyText || '暂无数据'" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="$slots.footer" class="flex items-center justify-between border-t border-[var(--border)] px-3 py-2">
      <slot name="footer" />
    </div>
  </div>
</template>
