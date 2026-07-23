<script setup lang="ts">
// Statistics — batch 3 insights page.
// Conclusion-driven analytics board: overview metrics, lifecycle distribution
// (pie), category composition (bar), reliability, warranty buckets, aggregate
// (switchable field/metric), trend (line) and compare. Each chart is wrapped in
// a ChartCard with a short conclusion rather than a bare chart wall.
// Gate: reports:view

import { ref, computed, onMounted } from 'vue'
import { RefreshCw } from 'lucide-vue-next'
import ChartCard from '@/components/insights/ChartCard.vue'
import StatCard from '@/components/common/StatCard.vue'
import { useUiStore } from '@/stores/ui'
import {
  getOverview,
  getStageDistribution,
  getCategoryComposition,
  getReliability,
  getWarrantyBuckets,
  getAggregate,
  getStageTrend,
  getCompare,
} from '@/services/stats'

const ui = useUiStore()
const loading = ref(false)

const overview = ref<any>(null)
const stageDist = ref<any>(null)
const categoryComp = ref<any>(null)
const reliability = ref<any>(null)
const warrantyBuckets = ref<any>(null)
const aggregate = ref<any>(null)
const stageTrend = ref<any>(null)
const compare = ref<any>(null)

// aggregate controls
const aggField = ref('lifecycle_stage')
const aggMetric = ref('count')
const aggFieldOptions = ref<{ value: string; label: string }[]>([])

// trend / compare controls
const trendMonths = ref(12)
const rangeA = ref('')
const rangeB = ref('')
const compareMetric = ref('stage')

const overviewCards = computed(() => {
  const o = overview.value
  if (!o) return []
  const pick: [string, string][] = [
    ['total_assets', '资产总数'],
    ['total_original_value', '资产原值'],
    ['total_faults', '故障总数'],
    ['warranty_expiring_soon', '即将到期'],
  ]
  return pick
    .filter(([k]) => o[k] != null)
    .map(([k, label]) => ({ label, value: o[k] }))
})

const stageOption = computed<Record<string, any> | null>(() => {
  const stages = stageDist.value?.stages || []
  if (!stages.length) return null
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, type: 'scroll' },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
        label: { show: true, formatter: '{b}\n{c}' },
        data: stages.map((s: any) => ({ name: s.stage, value: s.count })),
      },
    ],
  }
})

const categoryOption = computed<Record<string, any> | null>(() => {
  const cats = categoryComp.value?.by_category || []
  if (!cats.length) return null
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 90, right: 30, top: 20, bottom: 30 },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: cats.map((c: any) => c.category), inverse: true },
    series: [
      {
        type: 'bar',
        data: cats.map((c: any) => c.count),
        itemStyle: { color: '#0052D9' },
        label: { show: true, position: 'right' },
        barWidth: '55%',
      },
    ],
  }
})

const reliabilityOption = computed<Record<string, any> | null>(() => {
  const top = reliability.value?.top_fault_assets || []
  if (!top.length) return null
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 110, right: 30, top: 20, bottom: 30 },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: top.map((t: any) => t.asset_code).reverse() },
    series: [
      {
        type: 'bar',
        data: top.map((t: any) => t.fault_count).reverse(),
        itemStyle: { color: '#E34D59' },
        label: { show: true, position: 'right' },
        barWidth: '55%',
      },
    ],
  }
})

const warrantyOption = computed<Record<string, any> | null>(() => {
  const b = warrantyBuckets.value?.buckets || {}
  const names = ['已过期', '30天内', '60天内', '90天内', '90天以上']
  const colors = ['#E34D59', '#ED7B2F', '#ED7B2F', '#ED7B2F', '#2BA471']
  const vals = [b.expired || 0, b.within_30 || 0, b.within_60 || 0, b.within_90 || 0, b.over_90 || 0]
  if (vals.every((v) => v === 0)) return null
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 60, right: 30, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: names },
    yAxis: { type: 'value' },
    series: [
      {
        type: 'bar',
        data: vals.map((v, i) => ({ value: v, itemStyle: { color: colors[i] } })),
        label: { show: true, position: 'top' },
        barWidth: '50%',
      },
    ],
  }
})

const aggregateOption = computed<Record<string, any> | null>(() => {
  const rows = aggregate.value?.rows || []
  if (!rows.length) return null
  const isVal = aggMetric.value === 'original_value'
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 80, right: 30, top: 20, bottom: 70 },
    xAxis: { type: 'category', data: rows.map((r: any) => r.value), axisLabel: { rotate: 30, interval: 0 } },
    yAxis: { type: 'value', name: isVal ? '原值(元)' : '数量' },
    series: [
      {
        type: 'bar',
        data: rows.map((r: any) => (isVal ? r.original_value : r.count)),
        itemStyle: { color: '#0052D9' },
        label: { show: true, position: 'top' },
        barWidth: '55%',
      },
    ],
  }
})

const trendOption = computed<Record<string, any> | null>(() => {
  const t = stageTrend.value
  if (!t || !t.months || !t.months.length) return null
  const months = t.months
  const stages = t.stages || []
  const matrix = t.matrix || []
  const series = stages.map((s: string, i: number) => ({
    name: s,
    type: 'line',
    smooth: true,
    data: matrix[i] || [],
  }))
  return {
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, type: 'scroll' },
    grid: { left: 50, right: 20, top: 30, bottom: 50 },
    xAxis: { type: 'category', data: months, axisLabel: { rotate: 30, interval: 0 } },
    yAxis: { type: 'value' },
    series,
  }
})

const compareOption = computed<Record<string, any> | null>(() => {
  const c = compare.value
  if (!c || typeof c !== 'object') return null
  const arr = Object.values(c).find((v) => Array.isArray(v) && v.length && typeof v[0] === 'object') as any[]
  if (!arr) return null
  const keys = Object.keys(arr[0])
  const labelKey = keys.find((k) => typeof arr[0][k] === 'string') || keys[0]
  const valueKey = keys.find((k) => typeof arr[0][k] === 'number') || keys[1]
  if (!valueKey) return null
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 70, right: 24, top: 20, bottom: 40 },
    xAxis: { type: 'category', data: arr.map((r) => r[labelKey]) },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', data: arr.map((r) => r[valueKey]), itemStyle: { color: '#2BA471' }, barWidth: '55%' }],
  }
})

const compareSummary = computed(() => {
  if (!compare.value) return '请选择两个时间段进行对比。'
  return '时间段对比结果见下图，可据此评估运营趋势与配置调整效果。'
})

async function loadAll() {
  loading.value = true
  ui.clearError()
  try {
    const [ov, sd, cc, rl, wb, ag, tr] = await Promise.all([
      getOverview(),
      getStageDistribution(),
      getCategoryComposition(true),
      getReliability(10),
      getWarrantyBuckets(),
      getAggregate(aggField.value, aggMetric.value),
      getStageTrend(trendMonths.value),
    ])
    overview.value = ov
    stageDist.value = sd
    categoryComp.value = cc
    reliability.value = rl
    warrantyBuckets.value = wb
    aggregate.value = ag
    stageTrend.value = tr
    if (rangeA.value && rangeB.value) {
      compare.value = await getCompare(rangeA.value, rangeB.value, compareMetric.value)
    }
  } catch (e) {
    ui.setError((e as Error).message)
  } finally {
    loading.value = false
  }
}

async function reloadAggregate() {
  try {
    aggregate.value = await getAggregate(aggField.value, aggMetric.value)
  } catch (e) {
    ui.setError((e as Error).message)
  }
}
async function reloadTrend() {
  try {
    stageTrend.value = await getStageTrend(trendMonths.value)
  } catch (e) {
    ui.setError((e as Error).message)
  }
}
async function reloadCompare() {
  if (!rangeA.value || !rangeB.value) {
    compare.value = null
    return
  }
  try {
    compare.value = await getCompare(rangeA.value, rangeB.value, compareMetric.value)
  } catch (e) {
    ui.setError((e as Error).message)
  }
}

onMounted(loadAll)
</script>

<template>
  <section>
    <div class="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <nav class="mb-1 text-xs text-slate-400">洞察报告 / 统计分析</nav>
        <h1 class="text-xl font-semibold text-slate-800">统计分析</h1>
        <p class="mt-1 text-sm text-slate-500">全生命周期运营分析：分布、可靠性、维保、聚合、趋势与对比，结论驱动决策。</p>
      </div>
      <button class="c2-btn c2-btn-ghost" type="button" :disabled="loading" @click="loadAll">
        <RefreshCw :size="15" /> 刷新
      </button>
    </div>

    <!-- Overview -->
    <div class="mb-3 grid grid-cols-2 gap-3 lg:grid-cols-4">
      <template v-if="loading && !overviewCards.length">
        <div v-for="i in 4" :key="i" class="c2-panel p-4"><div class="h-10 w-24 animate-pulse rounded bg-[var(--canvas)]"></div></div>
      </template>
      <StatCard v-for="c in overviewCards" :key="c.label" :label="c.label" :value="c.value" />
    </div>

    <div class="grid grid-cols-1 gap-3 lg:grid-cols-2">
      <ChartCard title="生命周期分布" :option="stageOption" :loading="loading" />
      <ChartCard title="分类构成（Top）" :option="categoryOption" :loading="loading" />
      <ChartCard title="可靠性 · 故障 Top" :option="reliabilityOption" :loading="loading" />
      <ChartCard title="维保到期分布" :option="warrantyOption" :loading="loading" />

      <!-- Aggregate with controls -->
      <div class="c2-panel p-4">
        <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h2 class="text-sm font-semibold text-slate-700">自定义聚合</h2>
          <div class="flex items-center gap-2 text-xs">
            <select v-model="aggField" class="c2-input w-auto" @change="reloadAggregate">
              <option value="lifecycle_stage">生命周期阶段</option>
              <option value="asset_category">资产分类</option>
              <option value="room">机房</option>
              <option value="cabinet">机柜</option>
              <option value="department">部门</option>
              <option value="ownership">产权归属</option>
              <option value="brand">品牌</option>
              <option value="model">型号</option>
              <option value="responsible_person">责任人</option>
              <option value="warranty_status">维保状态</option>
            </select>
            <select v-model="aggMetric" class="c2-input w-auto" @change="reloadAggregate">
              <option value="count">数量</option>
              <option value="original_value">原值</option>
            </select>
          </div>
        </div>
        <ChartCard title="聚合结果" :option="aggregateOption" :loading="loading" />
      </div>

      <!-- Trend with controls -->
      <div class="c2-panel p-4">
        <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h2 class="text-sm font-semibold text-slate-700">生命周期趋势</h2>
          <div class="flex items-center gap-2 text-xs">
            <span class="text-slate-400">近</span>
            <input v-model.number="trendMonths" type="number" min="1" max="60" class="c2-input w-16" @change="reloadTrend" />
            <span class="text-slate-400">月</span>
          </div>
        </div>
        <ChartCard title="趋势" :option="trendOption" :loading="loading" />
      </div>
    </div>

    <!-- Compare -->
    <div class="mt-3 c2-panel p-4">
      <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 class="text-sm font-semibold text-slate-700">时间段对比</h2>
        <div class="flex flex-wrap items-center gap-2 text-xs">
          <input v-model="rangeA" placeholder="区间A (如 2024-01)" class="c2-input w-36" />
          <span class="text-slate-400">vs</span>
          <input v-model="rangeB" placeholder="区间B (如 2024-06)" class="c2-input w-36" />
          <select v-model="compareMetric" class="c2-input w-auto">
            <option value="stage">生命周期</option>
            <option value="category">分类</option>
            <option value="count">数量</option>
          </select>
          <button class="c2-btn c2-btn-ghost px-2 py-1" type="button" :disabled="loading" @click="reloadCompare">对比</button>
        </div>
      </div>
      <p class="mb-2 text-xs text-slate-500">{{ compareSummary }}</p>
      <ChartCard title="对比结果" :option="compareOption" :loading="loading" />
    </div>
  </section>
</template>
