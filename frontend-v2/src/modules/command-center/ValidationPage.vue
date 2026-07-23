<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ShieldCheck, AlertOctagon, AlertTriangle, RefreshCw, ChevronDown } from 'lucide-vue-next'
import { getValidation } from '@/services/validation'
import type { Validation, ValidationCheck } from '@/services/types'
import { useUiStore } from '@/stores/ui'
import StatCard from '@/components/common/StatCard.vue'
import SkeletonBlock from '@/components/common/SkeletonBlock.vue'
import ErrorState from '@/components/common/ErrorState.vue'
import RiskBadge from '@/components/common/RiskBadge.vue'

const ui = useUiStore()
const data = ref<Validation | null>(null)
const loading = ref(false)
const error = ref('')
const expanded = ref<Record<string, boolean>>({})

async function load() {
  loading.value = true
  error.value = ''
  ui.clearError()
  try {
    data.value = await getValidation()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

const total = computed(() => data.value?.total_assets ?? 0)
const errors = computed(() => data.value?.total_errors ?? 0)
const warnings = computed(() => data.value?.total_warnings ?? 0)

const checks = computed<ValidationCheck[]>(() => data.value?.checks || [])

function toggle(name: string) {
  expanded.value[name] = !expanded.value[name]
}

onMounted(load)
</script>

<template>
  <section>
    <div class="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <nav class="mb-1 text-xs text-slate-400">指挥台 / 数据校验</nav>
        <h1 class="text-xl font-semibold text-slate-800">数据校验看板</h1>
        <p class="mt-1 text-sm text-slate-500">资产数据质量体检：定位严重/中等异常，支撑治理闭环。</p>
      </div>
      <button class="c2-btn c2-btn-primary" type="button" :disabled="loading" @click="load">
        <RefreshCw :size="15" /> 刷新校验
      </button>
    </div>

    <!-- three summary cards -->
    <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <template v-if="loading">
        <div v-for="i in 3" :key="i" class="c2-panel p-4"><SkeletonBlock height="40px" /></div>
      </template>
      <template v-else-if="!error">
        <StatCard label="资产总数" :value="total" hint="参与校验的台账" :icon="ShieldCheck" tone="brand" />
        <StatCard label="严重问题" :value="errors" hint="需立即治理" :icon="AlertOctagon" tone="risk" />
        <StatCard label="中等问题" :value="warnings" hint="建议跟进" :icon="AlertTriangle" tone="caution" />
      </template>
    </div>

    <ErrorState v-if="error" :message="error" class="mt-3" @retry="load" />

    <!-- checks list -->
    <div v-if="!error" class="mt-3 c2-panel divide-y divide-[var(--border)]">
      <div class="px-4 py-3 text-sm font-semibold text-slate-700">数据质量检查</div>

      <div v-if="loading" class="space-y-3 p-4">
        <SkeletonBlock v-for="i in 4" :key="i" height="36px" />
      </div>

      <ul v-else>
        <li v-for="check in checks" :key="check.check_name" class="px-4 py-3">
          <div class="flex flex-wrap items-center gap-2">
            <span class="font-medium text-slate-800">{{ check.check_name }}</span>
            <RiskBadge
              :level="check.severity === '严重' ? 'critical' : 'warning'"
              :label="check.severity"
            />
            <span
              class="text-sm font-semibold"
              :class="check.count > 0 ? (check.severity === '严重' ? 'text-[var(--risk-critical)]' : 'text-[var(--risk-warning)]') : 'text-[var(--risk-ok)]'"
            >
              {{ check.count > 0 ? `问题 ${check.count} 项` : '正常' }}
            </span>
            <button
              v-if="check.details && check.details.length"
              class="ml-auto flex items-center gap-1 rounded px-2 py-1 text-xs text-slate-500 hover:bg-[var(--canvas)]"
              type="button"
              :aria-expanded="!!expanded[check.check_name]"
              @click="toggle(check.check_name)"
            >
              明细 ({{ check.details.length }})
              <ChevronDown :size="14" :class="expanded[check.check_name] ? 'rotate-180' : ''" />
            </button>
          </div>
          <p class="mt-1 text-xs text-slate-500">{{ check.description }}</p>

          <ul v-if="expanded[check.check_name]" class="mt-2 space-y-1 rounded bg-[var(--canvas)] p-3 text-xs text-slate-600">
            <li v-for="(d, i) in check.details" :key="i" class="flex gap-2">
              <span class="text-slate-400">·</span><span>{{ d }}</span>
            </li>
          </ul>
        </li>

        <li v-if="!checks.length" class="px-4 py-8 text-center text-sm text-slate-400">暂无校验项</li>
      </ul>
    </div>
  </section>
</template>
