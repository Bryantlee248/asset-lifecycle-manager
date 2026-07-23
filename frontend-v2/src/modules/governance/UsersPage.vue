<script setup lang="ts">
// User management — batch 3 governance page.
// List (search / status filter) + create / edit (modal with role_ids multi-
// select) + delete + reset password (high-risk, requires confirmation).
// Gate: users:view. No user-write permission literal exists in the allowed set,
// so write actions are gated by users:view (the only user-scoped permission).

import { ref, reactive, onMounted } from 'vue'
import { RefreshCw, Plus, Pencil, Trash2, KeyRound } from 'lucide-vue-next'
import DataGrid from '@/components/common/DataGrid.vue'
import type { GridColumn } from '@/components/common/DataGrid.vue'
import FilterBar from '@/components/common/FilterBar.vue'
import PermissionGate from '@/components/common/PermissionGate.vue'
import RiskBadge from '@/components/common/RiskBadge.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import { useUiStore } from '@/stores/ui'
import { getUsers, getAllRoles, createUser, updateUser, deleteUser, resetPassword } from '@/services/users'

const ui = useUiStore()
const pageSize = 20
const page = ref(1)
const search = ref('')
const statusFilter = ref('')
const rows = ref<any[]>([])
const total = ref(0)
const loading = ref(false)
const roles = ref<any[]>([])

const columns: GridColumn[] = [
  { key: 'id', label: 'ID', width: '60px' },
  { key: 'username', label: '用户名', width: '120px' },
  { key: 'real_name', label: '姓名', width: '100px' },
  { key: 'email', label: '邮箱', width: '180px' },
  { key: 'department', label: '部门', width: '120px' },
  { key: 'status', label: '状态', slot: true, width: '90px' },
  { key: 'roles', label: '角色', slot: true, width: '180px' },
]

const dialogOpen = ref(false)
const editing = ref(false)
const saving = ref(false)
const form = reactive<Record<string, any>>({
  id: null,
  username: '',
  real_name: '',
  email: '',
  phone: '',
  department: '',
  status: 'active',
  password: '',
  role_ids: [],
})

const resetTarget = ref<any | null>(null)
const deleteTarget = ref<any | null>(null)

function roleName(id: number | string): string {
  return roles.value.find((r) => r.id === id)?.name || String(id)
}

async function load() {
  loading.value = true
  ui.clearError()
  try {
    const data = await getUsers({
      page: page.value,
      page_size: pageSize,
      search: search.value || undefined,
      status: statusFilter.value || undefined,
    })
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

async function openDialog(row?: any) {
  if (!roles.value.length) {
    try {
      const r = await getAllRoles()
      roles.value = r.items || []
    } catch {
      roles.value = []
    }
  }
  editing.value = !!row
  form.id = row ? row.id : null
  form.username = row?.username || ''
  form.real_name = row?.real_name || ''
  form.email = row?.email || ''
  form.phone = row?.phone || ''
  form.department = row?.department || ''
  form.status = row?.status || 'active'
  form.password = ''
  form.role_ids = (row?.roles || []).map((r: any) => r.id)
  dialogOpen.value = true
}

async function save() {
  saving.value = true
  ui.clearError()
  try {
    const payload: Record<string, any> = {
      username: form.username,
      real_name: form.real_name,
      email: form.email,
      phone: form.phone,
      department: form.department,
      status: form.status,
      role_ids: form.role_ids,
    }
    if (!editing.value) payload.password = form.password
    if (editing.value) await updateUser(form.id, payload)
    else await createUser(payload)
    dialogOpen.value = false
    load()
  } catch (e) {
    ui.setError((e as Error).message)
  } finally {
    saving.value = false
  }
}

function askDelete(row: any) {
  deleteTarget.value = row
}
async function confirmDelete() {
  if (!deleteTarget.value) return
  try {
    await deleteUser(deleteTarget.value.id)
    load()
  } catch (e) {
    ui.setError((e as Error).message)
  } finally {
    deleteTarget.value = null
  }
}

function askReset(row: any) {
  resetTarget.value = row
}
async function confirmReset() {
  if (!resetTarget.value) return
  try {
    await resetPassword(resetTarget.value.id)
  } catch (e) {
    ui.setError((e as Error).message)
  } finally {
    resetTarget.value = null
  }
}

onMounted(load)
</script>

<template>
  <section>
    <div class="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <nav class="mb-1 text-xs text-slate-400">系统治理 / 用户管理</nav>
        <h1 class="text-xl font-semibold text-slate-800">用户管理</h1>
        <p class="mt-1 text-sm text-slate-500">维护系统用户、角色绑定与密码重置；删除与重置为高风险操作。</p>
      </div>
      <div class="flex items-center gap-2">
        <PermissionGate perm="users:view">
          <button class="c2-btn c2-btn-primary" type="button" @click="openDialog()">
            <Plus :size="15" /> 新增用户
          </button>
        </PermissionGate>
        <button class="c2-btn c2-btn-ghost" type="button" :disabled="loading" @click="load">
          <RefreshCw :size="15" /> 刷新
        </button>
      </div>
    </div>

    <FilterBar v-model="search" placeholder="搜索用户名 / 姓名 / 邮箱" :loading="loading" @submit="applyFilter" @reset="applyFilter">
      <template #filters>
        <select v-model="statusFilter" class="c2-input w-auto" aria-label="状态筛选" @change="applyFilter">
          <option value="">全部状态</option>
          <option value="active">启用</option>
          <option value="disabled">禁用</option>
        </select>
      </template>
    </FilterBar>

    <div class="mt-3">
      <DataGrid :columns="columns" :rows="rows" :loading="loading" row-key="id">
        <template #cell-status="{ row }">
          <RiskBadge :level="row.status === 'active' ? 'ok' : 'critical'" :label="row.status === 'active' ? '启用' : '禁用'" />
        </template>
        <template #cell-roles="{ row }">
          <span class="text-xs text-slate-500">{{ (row.roles || []).map((r: any) => r.name).join('、') || '—' }}</span>
        </template>
        <template #actions="{ row }">
          <PermissionGate perm="users:view">
            <button class="c2-link" type="button" @click="openDialog(row)"><Pencil :size="14" /> 编辑</button>
          </PermissionGate>
          <PermissionGate perm="users:view">
            <button class="c2-link" type="button" @click="askReset(row)"><KeyRound :size="14" /> 重置密码</button>
          </PermissionGate>
          <PermissionGate perm="users:view">
            <button class="c2-link c2-link-danger" type="button" @click="askDelete(row)"><Trash2 :size="14" /> 删除</button>
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

    <!-- Create / edit dialog -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="dialogOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" @click.self="dialogOpen = false">
          <div class="c2-panel w-full max-w-md space-y-3 p-5 shadow-[var(--shadow)]">
            <h3 class="text-base font-semibold text-slate-800">{{ editing ? '编辑用户' : '新增用户' }}</h3>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="mb-1 block text-xs text-slate-400">用户名</label>
                <input v-model="form.username" class="c2-input w-full" :disabled="editing" />
              </div>
              <div>
                <label class="mb-1 block text-xs text-slate-400">姓名</label>
                <input v-model="form.real_name" class="c2-input w-full" />
              </div>
              <div>
                <label class="mb-1 block text-xs text-slate-400">邮箱</label>
                <input v-model="form.email" class="c2-input w-full" />
              </div>
              <div>
                <label class="mb-1 block text-xs text-slate-400">电话</label>
                <input v-model="form.phone" class="c2-input w-full" />
              </div>
              <div>
                <label class="mb-1 block text-xs text-slate-400">部门</label>
                <input v-model="form.department" class="c2-input w-full" />
              </div>
              <div>
                <label class="mb-1 block text-xs text-slate-400">状态</label>
                <select v-model="form.status" class="c2-input w-full">
                  <option value="active">启用</option>
                  <option value="disabled">禁用</option>
                </select>
              </div>
              <div class="col-span-2">
                <label class="mb-1 block text-xs text-slate-400">密码{{ editing ? '（留空则不修改）' : '' }}</label>
                <input v-model="form.password" type="password" class="c2-input w-full" :placeholder="editing ? '不修改请留空' : '必填'" />
              </div>
              <div class="col-span-2">
                <label class="mb-1 block text-xs text-slate-400">角色</label>
                <select v-model="form.role_ids" multiple class="c2-input h-24 w-full">
                  <option v-for="r in roles" :key="r.id" :value="r.id">{{ r.name }}</option>
                </select>
              </div>
            </div>
            <div class="flex justify-end gap-2">
              <button class="c2-btn c2-btn-ghost" type="button" :disabled="saving" @click="dialogOpen = false">取消</button>
              <button class="c2-btn c2-btn-primary" type="button" :disabled="saving" @click="save">保存</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <ConfirmDialog
      :open="!!deleteTarget"
      title="删除用户"
      :message="`确认删除用户 ${deleteTarget?.username}？此操作不可撤销。`"
      :danger="true"
      confirm-text="确认删除"
      @confirm="confirmDelete"
      @cancel="deleteTarget = null"
    />
    <ConfirmDialog
      :open="!!resetTarget"
      title="重置密码"
      :message="`确认重置用户 ${resetTarget?.username} 的密码？重置后将生成随机密码并通知用户。`"
      :danger="true"
      confirm-text="确认重置"
      @confirm="confirmReset"
      @cancel="resetTarget = null"
    />
  </section>
</template>
