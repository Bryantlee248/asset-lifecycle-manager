<script setup lang="ts">
import RiskBadge from '@/components/common/RiskBadge.vue'

// ReportCard — a conclusion-first report block: title + risk/trend header on
// top, the prose `summary` conclusion in the middle, and an optional `#chart`
// slot (details / chart) at the bottom. Drives the "conclusion + chart +
// drill-down" layout used by the reports/stats pages (no chart walls).
const props = defineProps<{
  title: string
  summary: string
  trend?: string
  risk?: 'critical' | 'warning' | 'caution' | 'ok'
}>()
</script>

<template>
  <div class="c2-panel p-4">
    <div class="flex items-start justify-between gap-3">
      <h3 class="text-sm font-semibold text-slate-800">{{ title }}</h3>
      <div class="flex shrink-0 items-center gap-2">
        <RiskBadge v-if="risk" :level="risk" />
        <span v-if="trend" class="text-xs text-slate-400">{{ trend }}</span>
      </div>
    </div>
    <p class="mt-2 text-sm leading-relaxed text-slate-600">{{ summary }}</p>
    <div class="mt-3">
      <slot name="chart" />
    </div>
  </div>
</template>
