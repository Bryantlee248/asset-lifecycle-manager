<script setup lang="ts">
// ApprovalQueue — dual-column approval work queue.
//  - Left: 待办列表 with local type/status filters + refresh.
//  - Right: selected request summary (asset_code / reason / type), flow
//    trajectory (steps: level + approver + status), and approve / reject
//    actions (reject requires a reason). Status is rendered via RiskBadge.
// Pure presentational: data is supplied via `items` / `selectedId` and all
// intent is emitted upward (select / approve / reject / refresh).

import { ref, computed } from 'vue'
import RiskBadge from '@/components/common/RiskBadge.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { RefreshCw, Check, X } from 'lucide-vue-next'

const props = defineProps<{
  items: any[]
  selectedId?: string | number | null
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'select', id: string | number): void
  (e: 'approve', id: string | number): void
  (e: 'reject', id: string | number, comment: string): void
  (e: 'refresh'): void
}>()

const filterType = ref('')
const filterStatus = ref('')

const typeOptions = computed(() => {
  const set = new Set<string>()
  props.items.forEach((i) => i.approval_type && set.add(i.approval_type))
  return Array.from(set)
})
const statusOptions = computed(() => {
  const set = new Set<string>()
  props.items.forEach((i) => i.status && set.add(i.status))
  return Array.from(set)
})

const filteredItems = computed(() =>
  props.items.filter((i) => {
    if (filterType.value && i.approval_type !== filterType.value) return false
    if (filterStatus.value && i.status !== filterStatus.value) return false
    return true
  }),
)

const selectedItem = computed(() => {
  if (props.selectedId == null) return null
  return props.items.find((i) => i.id === props.selectedId) || null
})

function statusLevel(s: string): 'critical' | 'warning' | 'caution' | 'ok' {
  switch (s) {
    case 'pending':
      return 'warning'
    case 'approved':
      return 'ok'
    case 'rejected':
      return 'critical'
    case 'cancelled':
    case 'draft':
    default:
      return 'caution'
  }
}
function statusLabel(s: string): string {
  const map: Record<string, string> = {
    draft: '草稿',
    pending: '待审批',
    approved: '已通过',
    rejected: '已驳回',
    cancelled: '已撤回',
  }
  return map[s] || s
}

const rejectOpen = ref(false)
const rejectComment = ref('')

function onSelect(item: any) {
  emit('select', item.id)
}
function confirmApprove() {
  if (!selectedItem.value) return
  emit('approve', selectedItem.value.id)
}
function openReject() {
  rejectComment.value = ''
  rejectOpen.value = true
}
function confirmReject() {
  if (!selectedItem.value) return
  emit('reject', selectedItem.value.id, rejectComment.value)
  rejectOpen.value = false
}
</script>

<template>
  <div class="grid grid-cols-1 gap-3 lg:grid-cols-[minmax(280px,360px)_1fr]">
    <!-- Left: todo list -->
    <div class="c2-panel flex flex-col overflow-hidden">
      <div class="flex flex-wrap items-center gap-2 border-b border-[var(--border)] px-3 py-2.5">
        <select v-model="filterType" class="c2-input w-auto text-xs" aria-label="按类型筛选">
          <option value="">全部类型</option>
          <option v-for="t in typeOptions" :key="t" :value="t">{{ t }}</option>
        </select>
        <select v-model="filterStatus" class="c2-input w-auto text-xs" aria-label="按状态筛选">
          <option value="">全部状态</option>
          <option v-for="s in statusOptions" :key="s" :value="s">{{ statusLabel(s) }}</option>
        </select>
        <button class="c2-btn c2-btn-ghost ml-auto px-2 py-1 text-xs" type="button" :disabled="loading" @click="emit('refresh')">
          <RefreshCw :size="13" /> 刷新
        </button>
      </div>
      <div class="scroll-thin max-h-[60vh] flex-1 overflow-y-auto">
        <div v-if="!filteredItems.length" class="px-3 py-10 text-center text-sm text-slate-400">暂无审批单</div>
        <button
          v-for="item in filteredItems"
          :key="item.id"
          type="button"
          class="flex w-full flex-col gap-1 border-b border-[var(--border)] px-3 py-2.5 text-left transition-colors hover:bg-[var(--canvas)]"
          :class="item.id === selectedId ? 'bg-[var(--canvas)]' : ''"
          @click="onSelect(item)"
        >
          <div class="flex items-center justify-between gap-2">
            <span class="truncate text-sm font-medium text-slate-800">{{ item.asset_code || '—' }}</span>
            <RiskBadge :level="statusLevel(item.status)" :label="statusLabel(item.status)" />
          </div>
          <span class="truncate text-xs text-slate-500">{{ item.approval_type || '—' }}</span>
          <span class="line-clamp-1 text-xs text-slate-400">{{ item.reason || '' }}</span>
        </button>
      </div>
    </div>

    <!-- Right: detail / actions -->
    <div class="c2-panel p-4">
      <EmptyState v-if="!selectedItem" title="请选择左侧审批单查看详情" />
      <template v-else>
        <div class="flex items-start justify-between gap-3">
          <div>
            <h3 class="text-base font-semibold text-slate-800">{{ selectedItem.asset_code || '—' }}</h3>
            <p class="mt-0.5 text-sm text-slate-500">{{ selectedItem.approval_type || '—' }}</p>
          </div>
          <RiskBadge :level="statusLevel(selectedItem.status)" :label="statusLabel(selectedItem.status)" />
        </div>

        <div class="mt-3 rounded border border-[var(--border)] bg-[var(--canvas)] p-3">
          <p class="text-xs text-slate-400">变更原因</p>
          <p class="mt-1 text-sm text-slate-700">{{ selectedItem.reason || '（无）' }}</p>
        </div>

        <div v-if="selectedItem.steps && selectedItem.steps.length" class="mt-3">
          <p class="mb-1 text-xs text-slate-400">流转轨迹</p>
          <div class="space-y-2">
            <div v-for="(step, idx) in selectedItem.steps" :key="idx" class="flex items-center gap-2 text-sm">
              <span class="rounded bg-[var(--canvas)] px-1.5 py-0.5 text-xs text-slate-500">第{{ step.level }}级</span>
              <span class="text-slate-600">{{ step.approver || '—' }}</span>
              <RiskBadge :level="statusLevel(step.status)" :label="statusLabel(step.status)" />
            </div>
          </div>
        </div>

        <!-- Reject reason form -->
        <div v-if="rejectOpen" class="mt-3 rounded border border-[var(--risk-critical)] p-3">
          <label class="mb-1 block text-xs text-slate-500">驳回原因（必填）</label>
          <textarea v-model="rejectComment" rows="2" class="c2-input w-full" placeholder="请填写驳回原因"></textarea>
          <div class="mt-2 flex justify-end gap-2">
            <button class="c2-btn c2-btn-ghost" type="button" @click="rejectOpen = false">取消</button>
            <button class="c2-btn bg-[var(--risk-critical)] text-white hover:bg-[#c93b46]" type="button" :disabled="!rejectComment" @click="confirmReject">确认驳回</button>
          </div>
        </div>

        <div v-if="!rejectOpen" class="mt-4 flex gap-2">
          <button class="c2-btn c2-btn-primary" type="button" @click="confirmApprove">
            <Check :size="14" /> 同意
          </button>
          <button class="c2-btn border border-[var(--risk-critical)] text-[var(--risk-critical)] hover:bg-[#fde8e8]" type="button" @click="openReject">
            <X :size="14" /> 驳回
          </button>
        </div>
      </template>
    </div>
  </div>
</template>
