<script setup lang="ts">
// ConfigWorkspace — governance workspace for the system-config page.
//  - Left: config-domain list (dictionaries / categories / validation-rules /
//    aggregate-fields / stage-transitions), driven by `domains` / `activeDomain`.
//  - Right: the list of items for the active domain + a create/edit form panel.
// High-risk operations (delete / reset / toggle) surface `riskNote` in a
// ConfirmDialog and require a second confirmation before the matching event is
// emitted; the host page performs the actual API call.

import { ref, reactive, computed } from 'vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import { Plus, Pencil, Power, Trash2, RotateCcw } from 'lucide-vue-next'

export interface ConfigDomain {
  key: string
  label: string
}
export interface ConfigFormField {
  key: string
  label: string
  type?: 'text' | 'number' | 'select' | 'textarea' | 'date'
  options?: string[]
  readonly?: boolean
}

const props = defineProps<{
  domains: ConfigDomain[]
  activeDomain: string
  items: any[]
  formSchema: ConfigFormField[]
  riskNote?: string
}>()

const emit = defineEmits<{
  (e: 'selectDomain', key: string): void
  (e: 'edit', item: any): void
  (e: 'save', payload: Record<string, any>): void
  (e: 'toggle', item: any): void
  (e: 'delete', item: any): void
  (e: 'reset'): void
}>()

const editingItem = ref<any | null>(null)
const panelOpen = ref(false)
const form = reactive<Record<string, any>>({})

function startCreate() {
  editingItem.value = null
  for (const k of Object.keys(form)) delete form[k]
  for (const f of props.formSchema) form[f.key] = f.type === 'number' ? 0 : ''
  panelOpen.value = true
}
function startEdit(item: any) {
  editingItem.value = item
  for (const k of Object.keys(form)) delete form[k]
  for (const f of props.formSchema) form[f.key] = item?.[f.key] ?? (f.type === 'number' ? 0 : '')
  panelOpen.value = true
  emit('edit', item)
}
function onSave() {
  const payload: Record<string, any> = { ...form }
  if (editingItem.value && editingItem.value.id != null) payload.id = editingItem.value.id
  emit('save', payload)
  panelOpen.value = false
  editingItem.value = null
}
function cancelPanel() {
  panelOpen.value = false
  editingItem.value = null
}

// ----- high-risk confirmation -----
const confirmOpen = ref(false)
const confirmAction = ref<null | 'toggle' | 'delete' | 'reset'>(null)
const confirmTarget = ref<any | null>(null)

function askToggle(item: any) {
  confirmAction.value = 'toggle'
  confirmTarget.value = item
  confirmOpen.value = true
}
function askDelete(item: any) {
  confirmAction.value = 'delete'
  confirmTarget.value = item
  confirmOpen.value = true
}
function askReset() {
  confirmAction.value = 'reset'
  confirmTarget.value = null
  confirmOpen.value = true
}
function onConfirm() {
  const a = confirmAction.value
  const t = confirmTarget.value
  confirmOpen.value = false
  if (a === 'toggle' && t) emit('toggle', t)
  else if (a === 'delete' && t) emit('delete', t)
  else if (a === 'reset') emit('reset')
  confirmAction.value = null
  confirmTarget.value = null
}
function onCancel() {
  confirmOpen.value = false
  confirmAction.value = null
  confirmTarget.value = null
}

const confirmMessage = computed(() => props.riskNote || '此操作影响系统级配置，请确认。')

function rowLabel(item: any): string {
  return (
    item.label ||
    item.name ||
    item.code ||
    item.field_key ||
    item.group_code ||
    item.category_name ||
    item.type_code ||
    String(item.id)
  )
}
function isEnabled(item: any): boolean {
  return item.enabled !== false
}
</script>

<template>
  <div class="grid grid-cols-1 gap-3 lg:grid-cols-[200px_1fr]">
    <!-- Left: domain list -->
    <div class="c2-panel p-2">
      <button
        v-for="d in domains"
        :key="d.key"
        type="button"
        class="mb-1 block w-full rounded px-3 py-2 text-left text-sm transition-colors"
        :class="d.key === activeDomain ? 'bg-[var(--brand)] text-white' : 'text-slate-600 hover:bg-[var(--canvas)]'"
        @click="emit('selectDomain', d.key)"
      >
        {{ d.label }}
      </button>
    </div>

    <!-- Right: list + edit panel -->
    <div class="space-y-3">
      <div class="flex items-center justify-end gap-2">
        <button class="c2-btn c2-btn-ghost" type="button" @click="askReset">
          <RotateCcw :size="14" /> 重置
        </button>
        <button class="c2-btn c2-btn-primary" type="button" @click="startCreate">
          <Plus :size="14" /> 新增
        </button>
      </div>

      <div class="c2-panel overflow-hidden">
        <div class="scroll-thin overflow-x-auto">
          <table class="w-full border-collapse text-sm">
            <tbody>
              <tr v-if="!items.length">
                <td class="px-3 py-10 text-center text-sm text-slate-400">该配置域暂无数据</td>
              </tr>
              <tr
                v-for="item in items"
                :key="item.id"
                class="border-b border-[var(--border)] last:border-0"
              >
                <td class="px-3 py-2.5 text-slate-700">{{ rowLabel(item) }}</td>
                <td class="px-3 py-2.5 text-right">
                  <button class="c2-link" type="button" @click="startEdit(item)"><Pencil :size="14" /> 编辑</button>
                  <button class="c2-link" type="button" @click="askToggle(item)">
                    <Power :size="14" /> {{ isEnabled(item) ? '停用' : '启用' }}
                  </button>
                  <button class="c2-link c2-link-danger" type="button" @click="askDelete(item)"><Trash2 :size="14" /> 删除</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Create / edit form panel -->
      <div v-if="panelOpen" class="c2-panel space-y-3 p-4">
        <h3 class="text-sm font-semibold text-slate-800">{{ editingItem ? '编辑配置' : '新增配置' }}</h3>
        <div v-for="f in formSchema" :key="f.key" :class="f.type === 'textarea' ? '' : 'sm:col-span-2'">
          <label class="mb-1 block text-xs text-slate-400">{{ f.label }}</label>
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
        <div class="flex justify-end gap-2">
          <button class="c2-btn c2-btn-ghost" type="button" @click="cancelPanel">取消</button>
          <button class="c2-btn c2-btn-primary" type="button" @click="onSave">保存</button>
        </div>
      </div>
    </div>

    <ConfirmDialog
      :open="confirmOpen"
      title="高风险操作确认"
      :message="confirmMessage"
      :danger="true"
      confirm-text="确认执行"
      @confirm="onConfirm"
      @cancel="onCancel"
    />
  </div>
</template>
