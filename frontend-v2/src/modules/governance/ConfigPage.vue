<script setup lang="ts">
// System config — batch 3 governance page.
// A governance workspace (ConfigWorkspace) over five config domains:
// 字典 / 分类 / 校验规则 / 聚合字段 / 阶段流转. Write operations route to the
// config service; high-risk ops (delete / reset / toggle) surface riskNote via
// ConfigWorkspace's second confirmation. Gate: config:manage.
//
// Note: the config service exposes CRUD for 字典 / 校验规则(限 toggle·update·reset) /
// 聚合字段 / 阶段流转. 分类 only exposes a read endpoint in the contract, so it
// is presented read-only (mutations show a friendly notice rather than inventing
// endpoints).

import { ref, computed, onMounted } from 'vue'
import { RefreshCw } from 'lucide-vue-next'
import ConfigWorkspace from '@/components/governance/ConfigWorkspace.vue'
import type { ConfigDomain, ConfigFormField } from '@/components/governance/ConfigWorkspace.vue'
import { useUiStore } from '@/stores/ui'
import {
  getDictionaryGroups,
  getCategories,
  getValidationRules,
  getAggregateFields,
  getStageTransitions,
  createDictionary,
  updateDictionary,
  toggleDictionary,
  deleteDictionary,
  updateValidationRule,
  toggleValidationRule,
  resetValidationRules,
  createAggregateField,
  updateAggregateField,
  toggleAggregateField,
  deleteAggregateField,
  resetAggregateFields,
  createStageTransition,
  updateStageTransition,
  toggleStageTransition,
  deleteStageTransition,
} from '@/services/config'

const ui = useUiStore()

const DOMAINS: ConfigDomain[] = [
  { key: 'dictionaries', label: '数据字典' },
  { key: 'categories', label: '分类管理' },
  { key: 'validation', label: '校验规则' },
  { key: 'aggregate', label: '聚合字段' },
  { key: 'stage', label: '阶段流转' },
]

const activeDomain = ref('validation')
const items = ref<any[]>([])
const loading = ref(false)

const FORM_SCHEMA: Record<string, ConfigFormField[]> = {
  dictionaries: [
    { key: 'group_code', label: '组代码' },
    { key: 'group_name', label: '组名称' },
    { key: 'description', label: '描述', type: 'textarea' },
  ],
  categories: [
    { key: 'category_name', label: '分类名称' },
    { key: 'description', label: '描述' },
  ],
  validation: [{ key: 'remark', label: '备注', type: 'textarea' }],
  aggregate: [
    { key: 'field_key', label: '字段键' },
    { key: 'field_label', label: '字段标签' },
    { key: 'metric_support', label: '支持指标' },
    { key: 'remark', label: '备注' },
  ],
  stage: [
    { key: 'from_stage', label: '起始阶段' },
    { key: 'to_stage', label: '目标阶段' },
    { key: 'description', label: '描述' },
  ],
}

const RISK_NOTE: Record<string, string> = {
  dictionaries: '删除或停用字典项会影响引用该字典的资产字段展示与数据校验，操作不可撤销。',
  categories: '分类为系统基础数据，当前版本仅支持查看。',
  validation: '修改或重置校验规则会影响全量资产的校验判定，请确认影响范围。',
  aggregate: '修改或删除聚合字段会影响统计看板的维度配置，请确认。',
  stage: '修改或删除阶段流转规则会影响资产生命周期门禁，请确认。',
}

const formSchema = computed(() => FORM_SCHEMA[activeDomain.value] || [])
const riskNote = computed(() => RISK_NOTE[activeDomain.value] || '此操作影响系统级配置，请确认。')

async function loadItems(key: string = activeDomain.value) {
  loading.value = true
  ui.clearError()
  try {
    let data: any
    if (key === 'dictionaries') data = await getDictionaryGroups()
    else if (key === 'categories') data = await getCategories()
    else if (key === 'validation') data = await getValidationRules()
    else if (key === 'aggregate') data = await getAggregateFields()
    else data = await getStageTransitions()
    items.value = Array.isArray(data) ? data : data.items || []
  } catch (e) {
    ui.setError((e as Error).message)
  } finally {
    loading.value = false
  }
}

function onSelectDomain(key: string) {
  activeDomain.value = key
  loadItems(key)
}

async function onSave(payload: Record<string, any>) {
  const key = activeDomain.value
  try {
    if (key === 'dictionaries') {
      if (payload.id != null) await updateDictionary(payload.id, payload)
      else await createDictionary(payload)
    } else if (key === 'validation') {
      if (payload.id != null) await updateValidationRule(payload.id, payload.remark || '')
      else ui.setError('校验规则不支持新增')
    } else if (key === 'aggregate') {
      if (payload.id != null)
        await updateAggregateField(payload.id, { field_label: payload.field_label, remark: payload.remark })
      else
        await createAggregateField({
          field_key: payload.field_key,
          field_label: payload.field_label,
          metric_support: payload.metric_support,
          remark: payload.remark,
        })
    } else if (key === 'stage') {
      if (payload.id != null) await updateStageTransition(payload.id, payload)
      else await createStageTransition(payload)
    } else {
      ui.setError('该配置域当前仅支持查看')
      return
    }
    await loadItems(key)
  } catch (e) {
    ui.setError((e as Error).message)
  }
}

async function onToggle(item: any) {
  const key = activeDomain.value
  try {
    if (key === 'dictionaries') await toggleDictionary(item.id)
    else if (key === 'validation') await toggleValidationRule(item.id)
    else if (key === 'aggregate') await toggleAggregateField(item.id)
    else if (key === 'stage') await toggleStageTransition(item.id)
    else {
      ui.setError('该配置域当前仅支持查看')
      return
    }
    await loadItems(key)
  } catch (e) {
    ui.setError((e as Error).message)
  }
}

async function onDelete(item: any) {
  const key = activeDomain.value
  try {
    if (key === 'dictionaries') await deleteDictionary(item.id)
    else if (key === 'aggregate') await deleteAggregateField(item.id)
    else if (key === 'stage') await deleteStageTransition(item.id)
    else {
      ui.setError('该配置域不支持删除')
      return
    }
    await loadItems(key)
  } catch (e) {
    ui.setError((e as Error).message)
  }
}

async function onReset() {
  const key = activeDomain.value
  try {
    if (key === 'validation') await resetValidationRules()
    else if (key === 'aggregate') await resetAggregateFields()
    else {
      ui.setError('该配置域不支持重置')
      return
    }
    await loadItems(key)
  } catch (e) {
    ui.setError((e as Error).message)
  }
}

function onEdit(_item: any) {
  /* ConfigWorkspace manages its own edit form; nothing extra required here */
}

onMounted(() => loadItems('validation'))
</script>

<template>
  <section>
    <div class="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <nav class="mb-1 text-xs text-slate-400">系统治理 / 系统配置</nav>
        <h1 class="text-xl font-semibold text-slate-800">系统配置</h1>
        <p class="mt-1 text-sm text-slate-500">配置中心：数据字典、分类、校验规则、聚合字段与阶段流转；写操作含高风险二次确认。</p>
      </div>
      <button class="c2-btn c2-btn-ghost" type="button" :disabled="loading" @click="loadItems()">
        <RefreshCw :size="15" /> 刷新
      </button>
    </div>

    <ConfigWorkspace
      :domains="DOMAINS"
      :active-domain="activeDomain"
      :items="items"
      :form-schema="formSchema"
      :risk-note="riskNote"
      @select-domain="onSelectDomain"
      @edit="onEdit"
      @save="onSave"
      @toggle="onToggle"
      @delete="onDelete"
      @reset="onReset"
    />
  </section>
</template>
