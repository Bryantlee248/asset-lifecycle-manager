<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Boxes, Activity, ShieldAlert, AlertTriangle, RefreshCw } from 'lucide-vue-next'
import { getStats } from '@/services/stats'
import type { Stats } from '@/services/types'
import { useUiStore } from '@/stores/ui'
import StatCard from '@/components/common/StatCard.vue'
import SkeletonBlock from '@/components/common/SkeletonBlock.vue'
import ErrorState from '@/components/common/ErrorState.vue'
import EChart from '@/components/common/EChart.vue'

const STAGE_ORDER = ['规划', '在途', '上架', '运行', '维修', '待报废', '已报废']

const ui = useUiStore()
const stats = ref<Stats | null>(null)
const loading = ref(false)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  ui.clearError()
  try {
    stats.value = await getStats()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

const running = computed(() => stats.value?.by_stage?.['运行'] ?? 0)
const total = computed(() => stats.value?.total_assets ?? 0)
const warrantyExpired = computed(() => stats.value?.warranty_expired ?? 0)
const p1p2 = computed(() => stats.value?.p1_p2_unresolved ?? 0)

const stageOption = computed(() => {
  const by = stats.value?.by_stage || {}
  const data = STAGE_ORDER.map((s) => ({ name: s, value: by[s] || 0 }))
  return {
    grid: { left: 8, right: 16, top: 24, bottom: 4, containLabel: true },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: data.map((d) => d.name), axisLine: { lineStyle: { color: '#E2E8F0' } }, axisLabel: { color: '#64748b' } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#E2E8F0' } }, axisLabel: { color: '#64748b' } },
    series: [
      {
        type: 'bar',
        data: data.map((d) => d.value),
        barWidth: '52%',
        itemStyle: { color: '#157347', borderRadius: [4, 4, 0, 0] },
      },
    ],
  }
})

const categoryOption = computed(() => {
  const by = stats.value?.by_category || {}
  const entries = Object.entries(by).sort((a, b) => (b[1] as number) - (a[1] as number)).slice(0, 8)
  return {
    grid: { left: 8, right: 24, top: 8, bottom: 4, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: { type: 'value', splitLine: { lineStyle: { color: '#E2E8F0' } }, axisLabel: { color: '#64748b' } },
    yAxis: { type: 'category', data: entries.map((e) => e[0]).reverse(), axisLine: { lineStyle: { color: '#E2E8F0' } }, axisLabel: { color: '#64748b' } },
    series: [
      {
        type: 'bar',
        data: entries.map((e) => e[1]).reverse(),
        barWidth: '56%',
        itemStyle: { color: '#0052D9', borderRadius: [0, 4, 4, 0] },
      },
    ],
  }
})

// Trend chart is intentionally deferred to batch 3 (reports/stats), where it will
// be backed by real time-series endpoints. We do NOT render illustrative/fake
// data here — see the explicit placeholder panel in the template instead.

onMounted(load)
</script>

<template>
  <section>
    <!-- Page header: title + one-line task + breadcrumb + primary action -->
    <div class="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <nav class="mb-1 text-xs text-slate-400">指挥台 / 仪表盘</nav>
        <h1 class="text-xl font-semibold text-slate-800">指挥台 · 仪表盘</h1>
        <p class="mt-1 text-sm text-slate-500">全局资产健康与风险一览，风险与异常优先于常规统计呈现。</p>
      </div>
      <button class="c2-btn c2-btn-ghost" type="button" :disabled="loading" @click="load">
        <RefreshCw :size="15" /> 刷新
      </button>
    </div>

    <!-- Risk / health summary -->
    <div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <template v-if="loading">
        <div v-for="i in 4" :key="i" class="c2-panel p-4"><SkeletonBlock height="40px" /></div>
      </template>
      <template v-else-if="!error">
        <StatCard label="资产总数" :value="total" hint="全量台账" :icon="Boxes" tone="brand" />
        <StatCard label="运行资产" :value="running" hint="生命周期=运行" :icon="Activity" />
        <StatCard label="已过保资产" :value="warrantyExpired" hint="质保已到期" :icon="ShieldAlert" tone="caution" />
        <StatCard label="P1/P2 未解决" :value="p1p2" hint="高优先级待处理" :icon="AlertTriangle" tone="risk" />
      </template>
    </div>

    <ErrorState v-if="error" :message="error" class="mt-3" @retry="load" />

    <!-- Distributions -->
    <div v-if="!error" class="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
      <div class="c2-panel p-4">
        <h2 class="mb-2 text-sm font-semibold text-slate-700">生命周期分布</h2>
        <EChart v-if="stats" :option="stageOption" height="260px" />
        <SkeletonBlock v-else height="260px" />
      </div>
      <div class="c2-panel p-4">
        <h2 class="mb-2 text-sm font-semibold text-slate-700">分类构成（Top 8）</h2>
        <EChart v-if="stats" :option="categoryOption" height="260px" />
        <SkeletonBlock v-else height="260px" />
      </div>
    </div>

    <!-- Trend: deferred to batch 3 (real time-series from reports/stats). -->
    <div v-if="!error" class="mt-3 c2-panel p-4">
      <div class="mb-2 flex items-center justify-between">
        <h2 class="text-sm font-semibold text-slate-700">资产趋势</h2>
        <span class="rounded bg-[var(--canvas)] px-2 py-0.5 text-[11px] text-slate-400">批次三接入真实时序数据</span>
      </div>
      <EmptyState
        title="真实运营趋势图将于批次三接入"
        description="数据来源为 reports / stats 模块的真实时序接口，本页不展示任何示意性假数据。"
      />
    </div>
  </section>
</template>
