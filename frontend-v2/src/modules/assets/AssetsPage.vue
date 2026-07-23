<script setup lang="ts">
// Assets (资产台账) — C2 high-density ledger.
// Requirements (DESIGN-SPEC §5.2 / IMPLEMENTATION-PLAN 批次二):
//  - fixed filter region + search + column visibility + pagination/total
//  - batch-operation entry + row actions
//  - row shows 编号/名称/类型/生命周期/位置/责任人/维保状态/操作
//  - detail is a right-side drawer (AssetDetailWorkbench), not a plain popup
// No backend/API changes — uses the legacy /api/assets + timeline endpoints.

import { ref, reactive, computed, onMounted } from 'vue'
import { RefreshCw, Eye, Pencil, Download, Trash2, Columns3 } from 'lucide-vue-next'
import DataGrid from '@/components/common/DataGrid.vue'
import type { GridColumn } from '@/components/common/DataGrid.vue'
import FilterBar from '@/components/common/FilterBar.vue'
import DetailDrawer from '@/components/common/DetailDrawer.vue'
import PermissionGate from '@/components/common/PermissionGate.vue'
import StageTag from '@/components/common/StageTag.vue'
import RiskBadge from '@/components/common/RiskBadge.vue'
import AssetDetailWorkbench from './AssetDetailWorkbench.vue'
import type { FieldDef } from '@/components/assets/field'
import { getAssets, updateAsset, deleteAsset } from '@/services/assets'
import type { Paged, ListParams } from '@/services/types'
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()
const pageSize = 20
const page = ref(1)
const search = ref('')
const category = ref('')
const stage = ref('')
const warrantyStatus = ref('')
const rows = ref<any[]>([])
const total = ref(0)
const loading = ref(false)

const baseColumns: GridColumn[] = [
  { key: 'asset_code', label: '资产编号', width: '120px' },
  { key: 'device_name', label: '设备名称', width: '160px' },
  { key: 'asset_category', label: '分类', width: '90px' },
  { key: 'lifecycle_stage', label: '生命周期', slot: true, width: '90px' },
  { key: 'room', label: '位置', width: '110px' },
  { key: 'responsible_person', label: '责任人', width: '100px' },
  { key: 'warranty_status', label: '维保状态', slot: true, width: '100px' },
]
const selCol: GridColumn = { key: '__sel', label: '', width: '36px', slot: true }

const visible = reactive<Record<string, boolean>>(
  Object.fromEntries(baseColumns.map((c) => [c.key, true])),
)
const gridColumns = computed<GridColumn[]>(() => [
  selCol,
  ...baseColumns.filter((c) => visible[c.key] !== false),
])

// selection / batch ops
const selected = ref<Set<string>>(new Set())
function toggleSelect(code: string, e: Event) {
  const checked = (e.target as HTMLInputElement).checked
  if (checked) selected.value.add(code)
  else selected.value.delete(code)
  selected.value = new Set(selected.value)
}
const allVisibleSelected = computed(
  () =>
    rows.value.length > 0 &&
    rows.value.every((r) => selected.value.has(r.asset_code)),
)
function toggleSelectAll(e: Event) {
  const checked = (e.target as HTMLInputElement).checked
  const next = new Set(selected.value)
  for (const r of rows.value) {
    if (checked) next.add(r.asset_code)
    else next.delete(r.asset_code)
  }
  selected.value = next
}

// detail / edit drawer
const currentAsset = ref<any | null>(null)
const drawerOpen = ref(false)
const editing = ref(false)
const saving = ref(false)
const form = reactive<Record<string, any>>({})

const assetEditSchema: FieldDef[] = [
  { key: 'device_name', label: '设备名称' },
  { key: 'asset_category', label: '分类' },
  { key: 'lifecycle_stage', label: '生命周期', type: 'select', options: ['规划', '在途', '上架', '运行', '维修', '待报废', '已报废'] },
  { key: 'brand', label: '品牌' },
  { key: 'model', label: '型号' },
  { key: 'sn', label: 'SN序列号' },
  { key: 'room', label: '机房/位置' },
  { key: 'cabinet', label: '机柜' },
  { key: 'u_position', label: 'U位' },
  { key: 'ownership', label: '产权归属' },
  { key: 'responsible_person', label: '责任人' },
  { key: 'warranty_status', label: '维保状态', type: 'select', options: ['在保', '临保', '已过保'] },
  { key: 'config_summary', label: '配置摘要', type: 'textarea', col: 2 },
  { key: 'remarks', label: '备注', type: 'textarea', col: 2 },
]

async function load() {
  loading.value = true
  ui.clearError()
  const params: ListParams = {
    page: page.value,
    page_size: pageSize,
    search: search.value || undefined,
    category: category.value || undefined,
    stage: stage.value || undefined,
    warranty_status: warrantyStatus.value || undefined,
  }
  try {
    const data: Paged = await getAssets(params)
    rows.value = data.items || []
    total.value = data.total || 0
  } catch (e) {
    ui.setError((e as Error).message)
  } finally {
    loading.value = false
  }
}

function applyFilter() {
  page.value = 1
  load()
}
function prevPage() {
  if (page.value > 1) {
    page.value--
    load()
  }
}
function nextPage() {
  if (page.value * pageSize < total.value) {
    page.value++
    load()
  }
}

function openDetail(row: any) {
  currentAsset.value = row
  editing.value = false
  drawerOpen.value = true
}
function startEdit() {
  for (const k of Object.keys(form)) delete form[k]
  for (const f of assetEditSchema) form[f.key] = currentAsset.value?.[f.key] ?? ''
  editing.value = true
}
function cancelEdit() {
  editing.value = false
}
async function saveAsset() {
  if (!currentAsset.value) return
  saving.value = true
  try {
    await updateAsset(currentAsset.value.id, { ...form })
    editing.value = false
    drawerOpen.value = false
    load()
  } catch (e) {
    ui.setError((e as Error).message)
  } finally {
    saving.value = false
  }
}

function exportCsv() {
  const cols = baseColumns
  const lines = [cols.map((c) => c.label).join(',')]
  for (const r of rows.value) {
    if (!selected.value.has(r.asset_code)) continue
    lines.push(cols.map((c) => `"${(r[c.key] ?? '').toString().replace(/"/g, '""')}"`).join(','))
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `assets-selected-${selected.value.size}.csv`
  a.click()
  URL.revokeObjectURL(url)
}
async function batchDelete() {
  if (!selected.value.size) return
  if (!window.confirm(`确认删除选中的 ${selected.value.size} 项资产？`)) return
  try {
    await Promise.all(
      rows.value
        .filter((r) => selected.value.has(r.asset_code))
        .map((r) => deleteAsset(r.id)),
    )
    selected.value = new Set()
    load()
  } catch (e) {
    ui.setError((e as Error).message)
  }
}

const warrantyTone = (v: string): 'critical' | 'warning' | 'caution' | 'ok' =>
  v === '已过保' ? 'critical' : v === '临保' ? 'warning' : 'ok'

onMounted(load)
</script>

<template>
  <section>
    <div class="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <nav class="mb-1 text-xs text-slate-400">资产运营 / 资产台账</nav>
        <h1 class="text-xl font-semibold text-slate-800">资产台账</h1>
        <p class="mt-1 text-sm text-slate-500">高密度作业台：固定筛选、搜索、列显隐、批量操作；行呈现编号/名称/类型/生命周期/位置/责任人/维保状态。</p>
      </div>
      <button class="c2-btn c2-btn-ghost" type="button" :disabled="loading" @click="load">
        <RefreshCw :size="15" /> 刷新
      </button>
    </div>

    <!-- fixed filter region -->
    <div class="c2-panel mb-3 flex flex-wrap items-center gap-2 px-3 py-2.5">
      <div class="relative min-w-[200px] flex-1">
        <svg class="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></svg>
        <input v-model="search" class="c2-input w-full pl-8" placeholder="搜索资产编号 / 名称 / SN" aria-label="搜索" @keyup.enter="applyFilter" />
      </div>
      <select v-model="category" class="c2-input w-auto" aria-label="分类筛选" @change="applyFilter">
        <option value="">全部分类</option>
        <option v-for="c in ['服务器','网络设备','安全设备','存储设备','终端设备']" :key="c" :value="c">{{ c }}</option>
      </select>
      <select v-model="stage" class="c2-input w-auto" aria-label="生命周期筛选" @change="applyFilter">
        <option value="">全部生命周期</option>
        <option v-for="s in ['规划','在途','上架','运行','维修','待报废','已报废']" :key="s" :value="s">{{ s }}</option>
      </select>
      <select v-model="warrantyStatus" class="c2-input w-auto" aria-label="维保状态筛选" @change="applyFilter">
        <option value="">全部维保</option>
        <option v-for="w in ['在保','临保','已过保']" :key="w" :value="w">{{ w }}</option>
      </select>
      <button class="c2-btn c2-btn-ghost" type="button" @click="() => { search=''; category=''; stage=''; warrantyStatus=''; applyFilter() }">重置</button>

      <!-- column visibility -->
      <details class="relative ml-auto">
        <summary class="c2-btn c2-btn-ghost flex cursor-pointer list-none items-center gap-1">
          <Columns3 :size="15" /> 列设置
        </summary>
        <div class="absolute right-0 z-20 mt-1 w-44 rounded border border-[var(--border)] bg-[var(--surface)] p-2 shadow-[var(--shadow)]">
          <label v-for="c in baseColumns" :key="c.key" class="flex items-center gap-2 py-1 text-sm text-slate-600">
            <input type="checkbox" :checked="visible[c.key]" @change="visible[c.key] = ($event.target as HTMLInputElement).checked" />
            {{ c.label }}
          </label>
        </div>
      </details>
    </div>

    <!-- batch ops entry -->
    <div v-if="selected.size" class="mb-2 flex items-center gap-2 rounded border border-[var(--border)] bg-[var(--canvas)] px-3 py-2 text-sm">
      <span class="text-slate-600">已选 {{ selected.size }} 项</span>
      <button class="c2-btn c2-btn-ghost px-2 py-1 text-xs" type="button" @click="exportCsv"><Download :size="13" /> 导出CSV</button>
      <PermissionGate perm="assets:delete">
        <button class="c2-btn c2-btn-ghost px-2 py-1 text-xs text-[var(--risk-critical)]" type="button" @click="batchDelete"><Trash2 :size="13" /> 批量删除</button>
      </PermissionGate>
      <button class="c2-btn c2-btn-ghost px-2 py-1 text-xs" type="button" @click="selected = new Set()">清空</button>
    </div>

    <DataGrid :columns="gridColumns" :rows="rows" :loading="loading" row-key="asset_code">
      <template #cell-__sel="{ row }">
        <input type="checkbox" :checked="selected.has(row.asset_code)" :aria-label="`选择 ${row.asset_code}`" @change="toggleSelect(row.asset_code, $event)" />
      </template>
      <template #cell-lifecycle_stage="{ row }">
        <StageTag :stage="row.lifecycle_stage" size="sm" />
      </template>
      <template #cell-warranty_status="{ row }">
        <RiskBadge :level="warrantyTone(row.warranty_status)" :label="row.warranty_status || '—'" dot />
      </template>
      <template #actions="{ row }">
        <button class="c2-link" type="button" @click="openDetail(row)"><Eye :size="14" /> 详情</button>
        <PermissionGate perm="assets:edit">
          <button class="c2-link" type="button" @click="openDetail(row); startEdit()"><Pencil :size="14" /> 编辑</button>
        </PermissionGate>
      </template>
      <template #footer>
        <span class="text-xs text-slate-500">共 {{ total }} 条</span>
        <div class="flex items-center gap-1">
          <label class="mr-2 flex items-center gap-1 text-xs text-slate-500">
            <input type="checkbox" :checked="allVisibleSelected" @change="toggleSelectAll($event)" /> 全选本页
          </label>
          <button class="c2-btn c2-btn-ghost px-2 py-1 text-xs" type="button" :disabled="page <= 1" @click="prevPage">上一页</button>
          <span class="px-1 text-xs text-slate-500">第 {{ page }} 页</span>
          <button class="c2-btn c2-btn-ghost px-2 py-1 text-xs" type="button" :disabled="page * pageSize >= total" @click="nextPage">下一页</button>
        </div>
      </template>
    </DataGrid>

    <DetailDrawer :open="drawerOpen" :title="editing ? '编辑资产' : (currentAsset?.asset_code || '资产详情')" width="520px" @close="drawerOpen = false">
      <AssetDetailWorkbench v-if="!editing && currentAsset" :asset="currentAsset" @edit="startEdit" @stage="startEdit" />
      <div v-else-if="editing" class="space-y-3">
        <div v-for="f in assetEditSchema" :key="f.key" :class="f.col === 2 ? 'sm:col-span-2' : ''">
          <label class="mb-1 block text-xs text-slate-400">{{ f.label }}</label>
          <textarea v-if="f.type === 'textarea'" v-model="form[f.key]" rows="2" class="c2-input w-full"></textarea>
          <select v-else-if="f.type === 'select'" v-model="form[f.key]" class="c2-input w-full">
            <option value="">（未填）</option>
            <option v-for="o in f.options || []" :key="o" :value="o">{{ o }}</option>
          </select>
          <input v-else v-model="form[f.key]" type="text" class="c2-input w-full" />
        </div>
      </div>
      <template #footer>
        <div v-if="editing" class="flex justify-end gap-2">
          <button class="c2-btn c2-btn-ghost" type="button" :disabled="saving" @click="cancelEdit">取消</button>
          <button class="c2-btn c2-btn-primary" type="button" :disabled="saving" @click="saveAsset">保存</button>
        </div>
      </template>
    </DetailDrawer>
  </section>
</template>
