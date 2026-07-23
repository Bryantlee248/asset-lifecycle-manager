<script setup lang="ts">
// Approval center — batch 3 collaboration page.
//  - top stats from getApprovalStats()
//  - three sub-views (我的申请 / 我的待审 / 全部) via tabs
//  - create approval dialog (type / asset_code / reason / approvers)
//  - ApprovalQueue handles select / approve / reject with local filtering
// Gate: approval:view

import { ref, reactive, computed, onMounted } from 'vue'
import { RefreshCw, Plus } from 'lucide-vue-next'
import ApprovalQueue from '@/components/collaboration/ApprovalQueue.vue'
import StatCard from '@/components/common/StatCard.vue'
import PermissionGate from '@/components/common/PermissionGate.vue'
import { useUiStore } from '@/stores/ui'
import {
  getApprovalStats,
  getMyApplications,
  getMyPending,
  getApprovalRequests,
  getApprovalDropdowns,
  getApprovalConfigTypes,
  getUsersByRole,
  createApproval,
  submitApproval,
  approveApproval,
  rejectApproval,
  getApprovalDetail,
} from '@/services/approval'

type Tab = 'myApps' | 'myPending' | 'all'
const ui = useUiStore()

const tab = ref<Tab>('myPending')
const items = ref<any[]>([])
const selectedId = ref<string | number | null>(null)
const loading = ref(false)
const stats = ref<Record<string, any> | null>(null)

const typeOptions = ref<any[]>([])
const approverOptions = ref<any[]>([])

const createOpen = ref(false)
const submitting = ref(false)
const createForm = reactive<{ approval_type: string; asset_code: string; reason: string; approver_ids: any[] }>({
  approval_type: '',
  asset_code: '',
  reason: '',
  approver_ids: [],
})

const STAT_LABELS: Record<string, string> = {
  pending: '待审批',
  approved: '已通过',
  rejected: '已驳回',
  cancelled: '已撤回',
  total: '审批总数',
  my_pending: '我的待审',
  my_applications: '我的申请',
}
const statCards = computed(() => {
  if (!stats.value) return []
  return Object.entries(stats.value)
    .filter(([, v]) => typeof v === 'number')
    .map(([k, v]) => ({ label: STAT_LABELS[k] || k, value: v as number }))
})

async function loadStats() {
  try {
    stats.value = await getApprovalStats()
  } catch (e) {
    /* non-fatal */
  }
}

async function loadTab() {
  loading.value = true
  ui.clearError()
  try {
    let data: any
    if (tab.value === 'myApps') data = await getMyApplications(1)
    else if (tab.value === 'myPending') data = await getMyPending(1)
    else data = await getApprovalRequests({ page: 1 })
    items.value = data.items || []
    if (selectedId.value != null && !items.value.some((i) => i.id === selectedId.value)) {
      selectedId.value = null
    }
  } catch (e) {
    ui.setError((e as Error).message)
  } finally {
    loading.value = false
  }
}

function onSelect(id: string | number) {
  selectedId.value = id
  // enrich the item with detail (steps / current_level) for the queue
  getApprovalDetail(id)
    .then((detail) => {
      const idx = items.value.findIndex((i) => i.id === id)
      if (idx >= 0) items.value.splice(idx, 1, { ...items.value[idx], ...detail })
      else items.value.push(detail)
    })
    .catch(() => {})
}

async function onApprove(id: string | number) {
  try {
    await approveApproval(id)
    await loadTab()
    await loadStats()
  } catch (e) {
    ui.setError((e as Error).message)
  }
}
async function onReject(id: string | number, comment: string) {
  try {
    await rejectApproval(id, comment)
    await loadTab()
    await loadStats()
  } catch (e) {
    ui.setError((e as Error).message)
  }
}

async function openCreate() {
  createForm.approval_type = ''
  createForm.asset_code = ''
  createForm.reason = ''
  createForm.approver_ids = []
  try {
    const [d, types] = await Promise.all([getApprovalDropdowns(), getApprovalConfigTypes()])
    typeOptions.value = (d.approval_types || []).map((t: any) => t.code || t)
    try {
      const users = await getUsersByRole('ops_manager')
      approverOptions.value = Array.isArray(users) ? users : users.items || []
    } catch {
      approverOptions.value = []
    }
  } catch (e) {
    ui.setError((e as Error).message)
  }
  createOpen.value = true
}

async function submitCreate() {
  if (!createForm.approval_type || !createForm.asset_code || createForm.reason.length < 5) {
    ui.setError('请填写审批类型、资产编号，且原因至少 5 个字')
    return
  }
  submitting.value = true
  try {
    const result = await createApproval({
      approval_type: createForm.approval_type,
      asset_code: createForm.asset_code,
      reason: createForm.reason,
      approver_ids: createForm.approver_ids,
    })
    if (result && result.id) {
      await submitApproval(result.id, createForm.approver_ids)
    }
    createOpen.value = false
    await loadTab()
    await loadStats()
  } catch (e) {
    ui.setError((e as Error).message)
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  await loadStats()
  await loadTab()
})
</script>

<template>
  <section>
    <div class="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <nav class="mb-1 text-xs text-slate-400">协同中心 / 审批中心</nav>
        <h1 class="text-xl font-semibold text-slate-800">审批中心</h1>
        <p class="mt-1 text-sm text-slate-500">统一审批队列：我的申请、我的待审与全部审批，支持创建审批与同意/驳回。</p>
      </div>
      <div class="flex items-center gap-2">
        <PermissionGate perm="approval:approve">
          <button class="c2-btn c2-btn-primary" type="button" @click="openCreate">
            <Plus :size="15" /> 新建审批
          </button>
        </PermissionGate>
        <button class="c2-btn c2-btn-ghost" type="button" :disabled="loading" @click="loadTab">
          <RefreshCw :size="15" /> 刷新
        </button>
      </div>
    </div>

    <div v-if="statCards.length" class="mb-3 grid grid-cols-2 gap-3 lg:grid-cols-4">
      <StatCard v-for="s in statCards" :key="s.label" :label="s.label" :value="s.value" />
    </div>

    <div class="mb-3 flex items-center gap-1 border-b border-[var(--border)] text-sm">
      <button
        type="button"
        class="border-b-2 px-3 py-2"
        :class="tab === 'myPending' ? 'border-[var(--brand)] font-medium text-slate-800' : 'border-transparent text-slate-500'"
        @click="tab = 'myPending'; loadTab()"
      >我的待审</button>
      <button
        type="button"
        class="border-b-2 px-3 py-2"
        :class="tab === 'myApps' ? 'border-[var(--brand)] font-medium text-slate-800' : 'border-transparent text-slate-500'"
        @click="tab = 'myApps'; loadTab()"
      >我的申请</button>
      <button
        type="button"
        class="border-b-2 px-3 py-2"
        :class="tab === 'all' ? 'border-[var(--brand)] font-medium text-slate-800' : 'border-transparent text-slate-500'"
        @click="tab = 'all'; loadTab()"
      >全部</button>
    </div>

    <ApprovalQueue
      :items="items"
      :selected-id="selectedId"
      :loading="loading"
      @select="onSelect"
      @approve="onApprove"
      @reject="onReject"
      @refresh="loadTab"
    />

    <!-- Create dialog -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="createOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" @click.self="createOpen = false">
          <div class="c2-panel w-full max-w-md space-y-3 p-5 shadow-[var(--shadow)]">
            <h3 class="text-base font-semibold text-slate-800">新建审批</h3>
            <div>
              <label class="mb-1 block text-xs text-slate-400">审批类型</label>
              <select v-model="createForm.approval_type" class="c2-input w-full">
                <option value="">（请选择）</option>
                <option v-for="t in typeOptions" :key="t" :value="t">{{ t }}</option>
              </select>
            </div>
            <div>
              <label class="mb-1 block text-xs text-slate-400">资产编号</label>
              <input v-model="createForm.asset_code" class="c2-input w-full" placeholder="资产编号" />
            </div>
            <div>
              <label class="mb-1 block text-xs text-slate-400">变更原因</label>
              <textarea v-model="createForm.reason" rows="3" class="c2-input w-full" placeholder="请填写变更原因（至少 5 个字）"></textarea>
            </div>
            <div>
              <label class="mb-1 block text-xs text-slate-400">审批人（可多选）</label>
              <select v-model="createForm.approver_ids" multiple class="c2-input h-24 w-full">
                <option v-for="u in approverOptions" :key="u.id" :value="u.id">{{ u.real_name || u.username }}</option>
              </select>
            </div>
            <div class="flex justify-end gap-2">
              <button class="c2-btn c2-btn-ghost" type="button" :disabled="submitting" @click="createOpen = false">取消</button>
              <button class="c2-btn c2-btn-primary" type="button" :disabled="submitting" @click="submitCreate">提交</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </section>
</template>
