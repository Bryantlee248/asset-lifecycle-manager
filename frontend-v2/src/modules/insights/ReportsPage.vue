<script setup lang="ts">
// Reports center — batch 3 insights page.
// Conclusion-driven: each section leads with a ReportCard (prose conclusion) and
// a ChartCard (chart / drill-down), avoiding a bare chart wall.
// Gate: reports:view

import { ref, computed, onMounted } from 'vue'
import { RefreshCw } from 'lucide-vue-next'
import ReportCard from '@/components/insights/ReportCard.vue'
import ChartCard from '@/components/insights/ChartCard.vue'
import { useUiStore } from '@/stores/ui'
import { getComprehensiveReport, getWarrantyExpiryReport } from '@/services/reports'

const ui = useUiStore()
const comprehensive = ref<any>(null)
const warranty = ref<any>(null)
const warrantyDays = ref(90)
const loading = ref(false)

async function loadComprehensive() {
  try {
    comprehensive.value = await getComprehensiveReport()
  } catch (e) {
    ui.setError((e as Error).message)
  }
}
async function loadWarranty() {
  try {
    warranty.value = await getWarrantyExpiryReport(warrantyDays.value)
  } catch (e) {
    ui.setError((e as Error).message)
  }
}

// Generic best-effort bar chart from the first array-of-objects field found in
// a report payload. Returns null when nothing chartable is present (ChartCard
// then shows the empty state).
function toBarOption(data: any): Record<string, any> | null {
  if (!data || typeof data !== 'object') return null
  const arr = Object.values(data).find((v) => Array.isArray(v) && v.length && typeof v[0] === 'object') as any[]
  if (!arr || !arr.length) return null
  const keys = Object.keys(arr[0])
  const labelKey = keys.find((k) => typeof arr[0][k] === 'string') || keys[0]
  const valueKey = keys.find((k) => typeof arr[0][k] === 'number') || keys[1]
  if (!valueKey) return null
  return {
    grid: { left: 70, right: 24, top: 20, bottom: 50 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: { type: 'category', data: arr.map((r) => r[labelKey]), axisLabel: { rotate: 30, interval: 0 } },
    yAxis: { type: 'value' },
    series: [
      {
        type: 'bar',
        data: arr.map((r) => r[valueKey]),
        itemStyle: { color: '#0052D9' },
        label: { show: true, position: 'top' },
        barWidth: '55%',
      },
    ],
  }
}

const comprehensiveSummary = computed(() => {
  const c = comprehensive.value
  if (!c) return '加载中…'
  const nums = Object.entries(c).filter(([, v]) => typeof v === 'number')
  if (!nums.length) return '暂无综合报表数据。'
  return nums.map(([k, v]) => `${k}: ${v}`).join('；')
})

const warrantySummary = computed(() => {
  const w = warranty.value
  if (!w) return '加载中…'
  const expiring =
    w.expiring_count ?? w.count ?? (Array.isArray(w.expiring_list) ? w.expiring_list.length : null)
  return `未来 ${warrantyDays.value} 天内预计到期资产 ${expiring ?? '—'} 项，请关注续保与替换计划。`
})

const comprehensiveOption = computed(() => toBarOption(comprehensive.value))
const warrantyOption = computed(() => toBarOption(warranty.value))

async function refresh() {
  loading.value = true
  ui.clearError()
  await Promise.all([loadComprehensive(), loadWarranty()])
  loading.value = false
}

onMounted(async () => {
  loading.value = true
  ui.clearError()
  await Promise.all([loadComprehensive(), loadWarranty()])
  loading.value = false
})
</script>

<template>
  <section>
    <div class="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <nav class="mb-1 text-xs text-slate-400">洞察报告 / 报表中心</nav>
        <h1 class="text-xl font-semibold text-slate-800">报表中心</h1>
        <p class="mt-1 text-sm text-slate-500">综合运营报表与维保到期预警：结论先行，图表与明细下钻支撑决策。</p>
      </div>
      <button class="c2-btn c2-btn-ghost" type="button" :disabled="loading" @click="refresh">
        <RefreshCw :size="15" /> 刷新
      </button>
    </div>

    <div class="grid grid-cols-1 gap-3 lg:grid-cols-2">
      <ReportCard title="综合运营报表" :summary="comprehensiveSummary" :loading="loading">
        <ChartCard title="综合指标分布" :option="comprehensiveOption" :loading="loading" class="mt-2" />
      </ReportCard>

      <ReportCard title="维保到期预警" :summary="warrantySummary" :loading="loading">
        <template #chart>
          <div class="mt-2 flex items-center gap-2">
            <span class="text-xs text-slate-400">未来</span>
            <input v-model.number="warrantyDays" type="number" min="1" class="c2-input w-20 text-sm" />
            <span class="text-xs text-slate-400">天</span>
            <button class="c2-btn c2-btn-ghost px-2 py-1 text-xs" type="button" :disabled="loading" @click="loadWarranty">查询</button>
          </div>
          <ChartCard title="到期资产分布" :option="warrantyOption" :loading="loading" class="mt-2" />
        </template>
      </ReportCard>
    </div>
  </section>
</template>
