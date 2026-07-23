<script setup lang="ts">
import { computed } from 'vue'
import EChart from '@/components/common/EChart.vue'
import SkeletonBlock from '@/components/common/SkeletonBlock.vue'

// ChartCard — wraps EChart with a title and the three required states
// (loading / error / empty) so they can be asserted by unit tests via the
// `data-state` attribute on the root element.
const props = defineProps<{
  title: string
  option?: Record<string, any> | null
  loading?: boolean
  error?: string | null
}>()

function isEmptyOption(opt?: Record<string, any> | null): boolean {
  if (!opt) return true
  if (Array.isArray(opt.series)) return opt.series.length === 0
  return Object.keys(opt).length === 0
}

const state = computed<'error' | 'loading' | 'empty' | 'ready'>(() => {
  if (props.error) return 'error'
  if (props.loading) return 'loading'
  if (isEmptyOption(props.option)) return 'empty'
  return 'ready'
})
</script>

<template>
  <div class="c2-panel p-4" :data-state="state">
    <h2 class="mb-2 text-sm font-semibold text-slate-700">{{ title }}</h2>
    <div v-if="state === 'error'" class="py-8 text-center text-sm text-[var(--risk-critical)]">
      {{ error }}
    </div>
    <div v-else-if="state === 'loading'" class="py-2">
      <SkeletonBlock height="200px" />
    </div>
    <div v-else-if="state === 'empty'" class="py-8 text-center text-sm text-slate-400">暂无数据</div>
    <EChart v-else :option="option as Record<string, any>" height="240px" />
  </div>
</template>
