<script setup lang="ts">
// Generic "list + filter + detail/edit workbench" host for the lifecycle
// operation modules (procurement / inbound / outbound / changes / faults /
// warranties / retirements). The module pages supply the *differences* via
// props (columns, filters, status strip, edit schema, endpoints) while the
// shared mechanics — fixed filter bar, search, pagination/total, row actions,
// detail drawer, edit/create form, delete — live here. No API is invented; the
// fetch/CRUD functions are passed in from each module's service.

import { ref, reactive, computed, onMounted } from 'vue'
import { RefreshCw, Plus, Pencil, Trash2, Eye } from 'lucide-vue-next'
import DataGrid from '@/components/common/DataGrid.vue'
import type { GridColumn } from '@/components/common/DataGrid.vue'
import FilterBar from '@/components/common/FilterBar.vue'
import DetailDrawer from '@/components/common/DetailDrawer.vue'
import PermissionGate from '@/components/common/PermissionGate.vue'
import RiskBadge from '@/components/common/RiskBadge.vue'
import StageTag from '@/components/common/StageTag.vue'
import LifecycleRecordWorkbench from './LifecycleRecordWorkbench.vue'
import type { FieldDef } from './field'
import type { Paged, ListParams } from '@/services/types'
import { useUiStore } from '@/stores/ui'

export interface CellRenderer {
  key: string
  kind: 'stage' | 'risk'
  riskLevel?: (v: any) => 'critical' | 'warning' | 'caution' | 'ok'
}

const props = defineProps<{
  moduleTitle: string
  moduleKey: string
  columns: GridColumn[]
  fetchFn: (params: ListParams) => Promise<Paged>
  filterDefs?: { key: string; label: string; options?: string[]; placeholder?: string }[]
  searchPlaceholder?: string
  editSchema?: FieldDef[]
  cellRenderers?: CellRenderer[]
  endpoints?: {
    create?: (b: Record<string, any>) => Promise<any>
    update?: (id: string | number, b: Record<string, any>) => Promise<any>
    delete?: (id: string | number) => Promise<any>
  }
  createPerm?: string
  editPerm?: string
  deletePerm?: string
  rowKey?: string
  detailTitle?: (row: Record<string, any>) => string
}>()

const ui = useUiStore()
const pageSize = 20
const page = ref(1)
const search = ref('')
const filters = reactive<Record<string, string>>({})
const rows = ref<any[]>([])
const total = ref(0)
const loading = ref(false)
const error = ref('')

const selected = ref<any | null>(null)
const drawerOpen = ref(false)
const editing = ref(false)
const form = reactive<Record<string, any>>({})
const saving = ref(false)

const rk = computed(() => props.rowKey || 'id')
const hasCrud = computed(() => !!(props.endpoints?.create || props.endpoints?.update || props.endpoints?.delete))

async function load() {
  loading.value = true
  error.value = ''
  ui.clearError()
  const params: ListParams = {
    page: page.value,
    page_size: pageSize,
    search: search.value || undefined,
  }
  for (const f of props.filterDefs || []) {
    if (filters[f.key]) (params as any)[f.key] = filters[f.key]
  }
  try {
    const data = await props.fetchFn(params)
    rows.value = data.items || []
    total.value = data.total || 0
  } catch (e) {
    error.value = (e as Error).message
    ui.setError(error.value)
  } finally {
    loading.value = false
  }
}

function onSearch() {
  page.value = 1
  load()
}
function onReset() {
  search.value = ''
  for (const k of Object.keys(filters)) filters[k] = ''
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
  selected.value = row
  editing.value = false
  drawerOpen.value = true
}
function startCreate() {
  for (const k of Object.keys(form)) delete form[k]
  for (const f of props.editSchema || []) form[f.key] = f.type === 'number' ? 0 : ''
  selected.value = null
  editing.value = true
  drawerOpen.value = true
}
function startEdit(row: any) {
  for (const k of Object.keys(form)) delete form[k]
  for (const f of props.editSchema || []) form[f.key] = row?.[f.key] ?? (f.type === 'number' ? 0 : '')
  selected.value = row
  editing.value = true
}
function cancelEdit() {
  editing.value = false
}
async function save() {
  if (!props.endpoints) return
  saving.value = true
  try {
    const payload = { ...form }
    if (selected.value && selected.value[rk.value] != null && props.endpoints.update) {
      await props.endpoints.update(selected.value[rk.value], payload)
    } else if (props.endpoints.create) {
      await props.endpoints.create(payload)
    }
    editing.value = false
    drawerOpen.value = false
    load()
  } catch (e) {
    ui.setError((e as Error).message)
  } finally {
    saving.value = false
  }
}
async function remove(row: any) {
  if (!props.endpoints?.delete) return
  if (!window.confirm(`确认删除该${props.moduleTitle}记录？`)) return
  try {
    await props.endpoints.delete(row[rk.value])
    if (selected.value && selected.value[rk.value] === row[rk.value]) drawerOpen.value = false
    load()
  } catch (e) {
    ui.setError((e as Error).message)
  }
}

const drawerTitle = computed(() =>
  editing.value
    ? selected.value
      ? `编辑${props.moduleTitle}`
      : `新增${props.moduleTitle}`
    : props.detailTitle && selected.value
      ? props.detailTitle(selected.value)
      : `${props.moduleTitle}详情`,
)

const renderers = computed(() => props.cellRenderers || [])

onMounted(load)
</script>

<template>
  <section>
    <div class="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <nav class="mb-1 text-xs text-slate-400">资产运营 / {{ moduleTitle }}</nav>
        <h1 class="text-xl font-semibold text-slate-800">{{ moduleTitle }}</h1>
        <p class="mt-1 text-sm text-slate-500">统一列表 + 筛选 + 详情/编辑工作区；差异通过状态条、字段与主操作体现。</p>
      </div>
      <div class="flex items-center gap-2">
        <PermissionGate v-if="endpoints?.create" :perm="createPerm">
          <button class="c2-btn c2-btn-primary" type="button" @click="startCreate">
            <Plus :size="15" /> 新增
          </button>
        </PermissionGate>
        <button class="c2-btn c2-btn-ghost" type="button" :disabled="loading" @click="load">
          <RefreshCw :size="15" /> 刷新
        </button>
      </div>
    </div>

    <FilterBar v-model="search" :placeholder="searchPlaceholder || '搜索…'" :loading="loading" @submit="onSearch" @reset="onReset">
      <template #filters>
        <select
          v-for="f in filterDefs || []"
          :key="f.key"
          class="c2-input w-auto"
          :value="filters[f.key]"
          :aria-label="f.label"
          @change="(e: any) => { filters[f.key] = e.target.value; onSearch() }"
        >
          <option value="">{{ f.label }}</option>
          <option v-for="o in f.options || []" :key="o" :value="o">{{ o }}</option>
        </select>
      </template>
    </FilterBar>

    <div class="mt-3">
      <DataGrid :columns="columns" :rows="rows" :loading="loading" :row-key="rk">
        <template v-for="cr in renderers" :key="cr.key" #[`cell-${cr.key}`]="{ row }">
          <StageTag v-if="cr.kind === 'stage'" :stage="row[cr.key]" size="sm" />
          <RiskBadge
            v-else
            :level="cr.riskLevel ? cr.riskLevel(row[cr.key]) : 'ok'"
            :label="String(row[cr.key] ?? '')"
          />
        </template>
        <template #actions="{ row }">
          <button class="c2-link" type="button" @click="openDetail(row)">
            <Eye :size="14" /> 详情
          </button>
          <PermissionGate v-if="endpoints?.update && editPerm" :perm="editPerm">
            <button class="c2-link" type="button" @click="startEdit(row)">
              <Pencil :size="14" /> 编辑
            </button>
          </PermissionGate>
          <PermissionGate v-if="endpoints?.delete" :perm="deletePerm">
            <button class="c2-link c2-link-danger" type="button" @click="remove(row)">
              <Trash2 :size="14" /> 删除
            </button>
          </PermissionGate>
        </template>
        <template #footer>
          <span class="text-xs text-slate-500">共 {{ total }} 条</span>
          <div class="flex items-center gap-1">
            <button class="c2-btn c2-btn-ghost px-2 py-1 text-xs" type="button" :disabled="page <= 1" @click="prevPage">上一页</button>
            <span class="px-1 text-xs text-slate-500">第 {{ page }} 页</span>
            <button class="c2-btn c2-btn-ghost px-2 py-1 text-xs" type="button" :disabled="page * pageSize >= total" @click="nextPage">下一页</button>
          </div>
        </template>
      </DataGrid>
    </div>

    <DetailDrawer :open="drawerOpen" :title="drawerTitle" width="460px" @close="drawerOpen = false">
      <template v-if="!editing">
        <slot name="status" :row="selected" />
        <div class="mt-3">
          <LifecycleRecordWorkbench :schema="editSchema || []" :record="selected || {}" />
        </div>
        <slot name="detail" :row="selected" />
      </template>

      <template v-else>
        <div class="space-y-3">
          <div v-for="f in editSchema || []" :key="f.key" :class="f.col === 2 ? 'sm:col-span-2' : ''">
            <label class="mb-1 block text-xs text-slate-400">{{ f.label }}<span v-if="f.required" class="text-[var(--risk-critical)]"> *</span></label>
            <textarea
              v-if="f.type === 'textarea'"
              v-model="form[f.key]"
              rows="2"
              class="c2-input w-full"
              :disabled="f.readonly"
            ></textarea>
            <select
              v-else-if="f.type === 'select'"
              v-model="form[f.key]"
              class="c2-input w-full"
              :disabled="f.readonly"
            >
              <option value="">（未填）</option>
              <option v-for="o in f.options || []" :key="o" :value="o">{{ o }}</option>
            </select>
            <input
              v-else-if="f.type === 'date'"
              v-model="form[f.key]"
              type="date"
              class="c2-input w-full"
              :disabled="f.readonly"
            />
            <input
              v-else-if="f.type === 'number'"
              v-model="form[f.key]"
              type="number"
              class="c2-input w-full"
              :disabled="f.readonly"
            />
            <input
              v-else
              v-model="form[f.key]"
              type="text"
              class="c2-input w-full"
              :disabled="f.readonly"
            />
          </div>
        </div>
      </template>

      <template #footer>
        <slot name="actions" :row="selected" />
        <div v-if="editing" class="flex justify-end gap-2">
          <button class="c2-btn c2-btn-ghost" type="button" :disabled="saving" @click="cancelEdit">取消</button>
          <button class="c2-btn c2-btn-primary" type="button" :disabled="saving" @click="save">保存</button>
        </div>
      </template>
    </DetailDrawer>
  </section>
</template>
