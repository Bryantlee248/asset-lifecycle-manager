<script setup lang="ts">
// Role management — batch 3 governance page.
// List + create / edit (permission tree from getPermissionConfig) + delete
// (high-risk confirmation). Gate: roles:view.

import { ref, reactive, onMounted } from 'vue'
import { RefreshCw, Plus, Pencil, Trash2 } from 'lucide-vue-next'
import DataGrid from '@/components/common/DataGrid.vue'
import type { GridColumn } from '@/components/common/DataGrid.vue'
import PermissionGate from '@/components/common/PermissionGate.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import { useUiStore } from '@/stores/ui'
import { getRoles, getPermissionConfig, createRole, updateRole, deleteRole } from '@/services/roles'

const ui = useUiStore()
const rows = ref<any[]>([])
const loading = ref(false)
const permConfig = ref<{ groups: Array<{ name?: string; group?: string; permissions: string[] }> }>({ groups: [] })

const columns: GridColumn[] = [
  { key: 'id', label: 'ID', width: '60px' },
  { key: 'name', label: '角色名称', width: '160px' },
  { key: 'code', label: '代码', width: '140px' },
  { key: 'description', label: '描述', width: '200px' },
  { key: 'permissions', label: '权限数', slot: true, width: '90px' },
]

const dialogOpen = ref(false)
const editing = ref(false)
const saving = ref(false)
const form = reactive<Record<string, any>>({ id: null, name: '', code: '', description: '', permissions: [] as string[] })

const deleteTarget = ref<any | null>(null)

async function load() {
  loading.value = true
  ui.clearError()
  try {
    const data = await getRoles()
    rows.value = data.items || []
  } catch (e) {
    ui.setError((e as Error).message)
  } finally {
    loading.value = false
  }
}

async function ensurePermConfig() {
  if (permConfig.value.groups.length) return
  try {
    permConfig.value = await getPermissionConfig()
  } catch {
    permConfig.value = { groups: [] }
  }
}

async function openDialog(row?: any) {
  await ensurePermConfig()
  editing.value = !!row
  form.id = row ? row.id : null
  form.name = row?.name || ''
  form.code = row?.code || ''
  form.description = row?.description || ''
  form.permissions = row ? [...(row.permissions || [])] : []
  dialogOpen.value = true
}

async function save() {
  saving.value = true
  ui.clearError()
  try {
    const payload = {
      name: form.name,
      code: form.code,
      description: form.description,
      permissions: form.permissions,
    }
    if (editing.value) await updateRole(form.id, payload)
    else await createRole(payload)
    dialogOpen.value = false
    load()
  } catch (e) {
    ui.setError((e as Error).message)
  } finally {
    saving.value = false
  }
}

function isChecked(p: string): boolean {
  return form.permissions.includes(p)
}
function togglePerm(p: string, e: Event) {
  const checked = (e.target as HTMLInputElement).checked
  if (checked) {
    if (!form.permissions.includes(p)) form.permissions.push(p)
  } else {
    form.permissions = form.permissions.filter((x: string) => x !== p)
  }
}

function askDelete(row: any) {
  deleteTarget.value = row
}
async function confirmDelete() {
  if (!deleteTarget.value) return
  try {
    await deleteRole(deleteTarget.value.id)
    load()
  } catch (e) {
    ui.setError((e as Error).message)
  } finally {
    deleteTarget.value = null
  }
}

onMounted(load)
</script>

<template>
  <section>
    <div class="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <nav class="mb-1 text-xs text-slate-400">系统治理 / 角色管理</nav>
        <h1 class="text-xl font-semibold text-slate-800">角色管理</h1>
        <p class="mt-1 text-sm text-slate-500">维护角色及其权限集合；删除为高风险操作，需二次确认。</p>
      </div>
      <div class="flex items-center gap-2">
        <PermissionGate perm="roles:view">
          <button class="c2-btn c2-btn-primary" type="button" @click="openDialog()">
            <Plus :size="15" /> 新增角色
          </button>
        </PermissionGate>
        <button class="c2-btn c2-btn-ghost" type="button" :disabled="loading" @click="load">
          <RefreshCw :size="15" /> 刷新
        </button>
      </div>
    </div>

    <DataGrid :columns="columns" :rows="rows" :loading="loading" row-key="id">
      <template #cell-permissions="{ row }">
        <span class="text-xs text-slate-500">{{ (row.permissions || []).length }} 项</span>
      </template>
      <template #actions="{ row }">
        <PermissionGate perm="roles:view">
          <button class="c2-link" type="button" @click="openDialog(row)"><Pencil :size="14" /> 编辑</button>
        </PermissionGate>
        <PermissionGate perm="roles:view">
          <button class="c2-link c2-link-danger" type="button" @click="askDelete(row)"><Trash2 :size="14" /> 删除</button>
        </PermissionGate>
      </template>
    </DataGrid>

    <!-- Create / edit dialog -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="dialogOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" @click.self="dialogOpen = false">
          <div class="c2-panel flex max-h-[85vh] w-full max-w-lg flex-col p-5 shadow-[var(--shadow)]">
            <h3 class="mb-3 text-base font-semibold text-slate-800">{{ editing ? '编辑角色' : '新增角色' }}</h3>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="mb-1 block text-xs text-slate-400">角色名称</label>
                <input v-model="form.name" class="c2-input w-full" />
              </div>
              <div>
                <label class="mb-1 block text-xs text-slate-400">代码</label>
                <input v-model="form.code" class="c2-input w-full" :disabled="editing" />
              </div>
              <div class="col-span-2">
                <label class="mb-1 block text-xs text-slate-400">描述</label>
                <input v-model="form.description" class="c2-input w-full" />
              </div>
            </div>
            <div class="mt-3 flex-1 overflow-y-auto">
              <p class="mb-1 text-xs text-slate-400">权限分配</p>
              <div
                v-for="(g, gi) in permConfig.groups"
                :key="gi"
                class="mb-2 rounded border border-[var(--border)] p-2"
              >
                <p class="mb-1 text-xs font-medium text-slate-600">{{ g.name || g.group || ('分组' + (gi + 1)) }}</p>
                <div class="flex flex-wrap gap-x-3 gap-y-1">
                  <label v-for="p in g.permissions" :key="p" class="flex items-center gap-1 text-xs text-slate-600">
                    <input type="checkbox" :checked="isChecked(p)" @change="togglePerm(p, $event)" />
                    {{ p }}
                  </label>
                </div>
              </div>
            </div>
            <div class="mt-3 flex justify-end gap-2">
              <button class="c2-btn c2-btn-ghost" type="button" :disabled="saving" @click="dialogOpen = false">取消</button>
              <button class="c2-btn c2-btn-primary" type="button" :disabled="saving" @click="save">保存</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <ConfirmDialog
      :open="!!deleteTarget"
      title="删除角色"
      :message="`确认删除角色 ${deleteTarget?.name}？该角色下的用户将失去对应权限。`"
      :danger="true"
      confirm-text="确认删除"
      @confirm="confirmDelete"
      @cancel="deleteTarget = null"
    />
  </section>
</template>
