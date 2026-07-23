<script setup lang="ts">
// Asset detail workbench — right-drawer content for a single asset.
// Differs from the generic lifecycle workbench: it shows a summary header,
// primary actions (AssetActionBar), tabbed sections (基础信息 / 生命周期 /
// 关系 / 变更维修 / 审计), a real lifecycle timeline fetched from
// /api/assets/{code}/timeline, and a stage-gate pre-check (StageGateBadge).
// No new endpoints are invented — only legacy ones are used.

import { ref, watch } from 'vue'
import { Boxes, GitBranch, Wrench, ScrollText } from 'lucide-vue-next'
import StageTag from '@/components/common/StageTag.vue'
import RiskBadge from '@/components/common/RiskBadge.vue'
import AssetActionBar from '@/components/assets/AssetActionBar.vue'
import StageGateBadge from '@/components/assets/StageGateBadge.vue'
import LifecycleTimeline from '@/components/assets/LifecycleTimeline.vue'
import LifecycleRecordWorkbench from '@/components/assets/LifecycleRecordWorkbench.vue'
import type { FieldDef } from '@/components/assets/field'
import { getAssetTimeline, stageGate } from '@/services/assets'

const props = defineProps<{ asset: Record<string, any> }>()
const emit = defineEmits<{ (e: 'edit'): void; (e: 'stage'): void }>()

const STAGES = ['规划', '在途', '上架', '运行', '维修', '待报废', '已报废']

const tabs = ['基础信息', '生命周期', '关系', '变更维修', '审计'] as const
type Tab = (typeof tabs)[number]
const activeTab = ref<Tab>('基础信息')

const timeline = ref<any[]>([])
const timelineLoading = ref(false)
const gate = ref<{ allowed: boolean; message?: string } | null>(null)

const baseSchema: FieldDef[] = [
  { key: 'asset_code', label: '资产编号', readonly: true },
  { key: 'device_name', label: '设备名称' },
  { key: 'asset_category', label: '分类' },
  { key: 'brand', label: '品牌' },
  { key: 'model', label: '型号' },
  { key: 'sn', label: 'SN序列号' },
  { key: 'room', label: '机房/位置' },
  { key: 'cabinet', label: '机柜' },
  { key: 'u_position', label: 'U位' },
  { key: 'ownership', label: '产权归属' },
  { key: 'responsible_person', label: '责任人' },
  { key: 'config_summary', label: '配置摘要', col: 2 },
  { key: 'remarks', label: '备注', col: 2 },
]

async function loadTimeline() {
  if (!props.asset?.asset_code) return
  timelineLoading.value = true
  try {
    const d = await getAssetTimeline(props.asset.asset_code)
    timeline.value = (d.timeline || []).map((t: any) => ({
      time: t.time || t.date || '',
      title: t.title || t.stage || '状态变更',
      desc: t.desc || t.description || '',
      tone: t.tone || 'neutral',
    }))
  } catch {
    timeline.value = []
  } finally {
    timelineLoading.value = false
  }
}

async function checkGate(stage: string) {
  if (!props.asset?.asset_code) return
  try {
    gate.value = await stageGate(props.asset.asset_code, stage)
  } catch (e: any) {
    gate.value = { allowed: false, message: e?.message || '门禁校验失败' }
  }
}

function onStagePick(e: Event) {
  const v = (e.target as HTMLSelectElement).value
  if (v) checkGate(v)
}

const warrantyTone = (v: string): 'critical' | 'warning' | 'caution' | 'ok' =>
  v === '已过保' ? 'critical' : v === '临保' ? 'warning' : 'ok'

watch(
  () => props.asset,
  (a) => {
    if (a) {
      gate.value = null
      loadTimeline()
    }
  },
  { immediate: true },
)
</script>

<template>
  <div class="space-y-3">
    <!-- summary header -->
    <div class="rounded border border-[var(--border)] bg-[var(--surface)] p-3">
      <div class="flex items-center gap-2">
        <Boxes :size="16" class="text-[var(--brand)]" />
        <span class="font-semibold text-slate-800">{{ asset.asset_code }}</span>
        <StageTag :stage="asset.lifecycle_stage" size="sm" />
        <RiskBadge :level="warrantyTone(asset.warranty_status)" :label="asset.warranty_status || '—'" dot />
      </div>
      <div class="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
        <span>设备：{{ asset.device_name || '—' }}</span>
        <span>位置：{{ asset.room || '—' }}</span>
        <span>责任人：{{ asset.responsible_person || '—' }}</span>
      </div>
      <div class="mt-2"><AssetActionBar :asset="asset" @edit="emit('edit')" @stage="emit('stage')" /></div>
    </div>

    <!-- tabs -->
    <div class="flex flex-wrap gap-1 border-b border-[var(--border)]">
      <button
        v-for="t in tabs"
        :key="t"
        type="button"
        class="rounded-t px-3 py-1.5 text-sm"
        :class="activeTab === t ? 'border-b-2 border-[var(--brand)] font-medium text-[var(--brand)]' : 'text-slate-500 hover:text-slate-700'"
        @click="activeTab = t"
      >
        {{ t }}
      </button>
    </div>

    <!-- 基础信息 -->
    <div v-if="activeTab === '基础信息'">
      <LifecycleRecordWorkbench :schema="baseSchema" :record="asset" />
    </div>

    <!-- 生命周期 -->
    <div v-else-if="activeTab === '生命周期'" class="space-y-3">
      <div class="flex flex-wrap items-center gap-2">
        <span class="text-sm text-slate-600">当前阶段：</span>
        <StageTag :stage="asset.lifecycle_stage" />
        <select class="c2-input w-auto" aria-label="预检目标阶段" @change="onStagePick">
          <option value="">预检流转至…</option>
          <option v-for="s in STAGES" :key="s" :value="s" :disabled="s === asset.lifecycle_stage">{{ s }}</option>
        </select>
      </div>
      <StageGateBadge v-if="gate" :allowed="gate.allowed" :message="gate.message" />
      <div v-if="timelineLoading" class="text-xs text-slate-400">时间线加载中…</div>
      <LifecycleTimeline v-else :events="timeline" />
    </div>

    <!-- 关系 -->
    <div v-else-if="activeTab === '关系'" class="space-y-2 text-sm text-slate-600">
      <p class="flex items-center gap-2"><GitBranch :size="14" /> 关联记录（移入/移出/变更/故障/维保/退役）将在批次三接入统一关系视图。</p>
      <p class="text-xs text-slate-400">当前仅展示资产编号维度的直接关联入口，避免臆造后端未提供的聚合接口。</p>
    </div>

    <!-- 变更维修 -->
    <div v-else-if="activeTab === '变更维修'" class="space-y-2 text-sm text-slate-600">
      <p class="flex items-center gap-2"><Wrench :size="14" /> 变更与维修履历由 changes / faults 模块承载，可在对应页面按资产编号筛选查看。</p>
      <p class="text-xs text-slate-400">本工作区不重复存储，避免与生命周期模块数据不一致。</p>
    </div>

    <!-- 审计 -->
    <div v-else-if="activeTab === '审计'" class="space-y-1 text-sm text-slate-600">
      <p class="flex items-center gap-2"><ScrollText :size="14" /> 创建时间：{{ asset.created_at || '—' }}</p>
      <p>更新时间：{{ asset.updated_at || '—' }}</p>
      <p class="text-xs text-slate-400">完整审计流（操作人/操作类型）将在批次三接入。</p>
    </div>
  </div>
</template>
