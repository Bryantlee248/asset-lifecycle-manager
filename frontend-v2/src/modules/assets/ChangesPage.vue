<script setup lang="ts">
import LifecycleListPage from '@/components/assets/LifecycleListPage.vue'
import type { GridColumn } from '@/components/common/DataGrid.vue'
import type { FieldDef } from '@/components/assets/field'
import RiskBadge from '@/components/common/RiskBadge.vue'
import {
  getChanges, createChange, updateChange, deleteChange,
} from '@/services/changes'

const columns: GridColumn[] = [
  { key: 'asset_code', label: '资产编号', width: '120px' },
  { key: 'work_order_no', label: '工单号', width: '130px' },
  { key: 'change_type', label: '变更类型', width: '120px' },
  { key: 'completion_status', label: '完成状态', slot: true, width: '100px' },
  { key: 'execute_date', label: '执行日期', width: '110px' },
  { key: 'executor', label: '执行人', width: '100px' },
]

const cellRenderers = [
  {
    key: 'completion_status',
    kind: 'risk' as const,
    riskLevel: (v: any) =>
      v === '已完成' ? 'ok' : v === '进行中' ? 'caution' : v === '已取消' ? 'warning' : 'ok',
  },
]

const filterDefs = [{ key: 'asset_code', label: '按资产编号' }]

const editSchema: FieldDef[] = [
  { key: 'asset_code', label: '资产编号', required: true },
  { key: 'work_order_no', label: '工单号' },
  { key: 'change_type', label: '变更类型', type: 'select', options: ['配置变更', '位置变更', '责任人变更', '扩容', '缩容'] },
  { key: 'completion_status', label: '完成状态', type: 'select', options: ['进行中', '已完成', '已取消'] },
  { key: 'change_content', label: '变更内容', type: 'textarea', col: 2 },
  { key: 'old_config', label: '原配置', type: 'textarea' },
  { key: 'new_config', label: '新配置', type: 'textarea' },
  { key: 'change_reason', label: '变更原因', type: 'textarea', col: 2 },
  { key: 'approver', label: '审批人' },
  { key: 'executor', label: '执行人' },
  { key: 'execute_date', label: '执行日期', type: 'date' },
  { key: 'remarks', label: '备注', type: 'textarea', col: 2 },
]

const statusTone = (v: any) =>
  v === '已完成' ? 'ok' : v === '进行中' ? 'caution' : v === '已取消' ? 'warning' : 'ok'
</script>

<template>
  <LifecycleListPage
    module-title="变更管理"
    module-key="changes"
    :columns="columns"
    :fetch-fn="getChanges"
    :filter-defs="filterDefs"
    search-placeholder="搜索工单号 / 资产编号"
    :edit-schema="editSchema"
    :cell-renderers="cellRenderers"
    :endpoints="{ create: createChange, update: updateChange, delete: deleteChange }"
    create-perm="change:create"
    edit-perm="change:edit"
    delete-perm="change:delete"
  >
    <template #status="{ row }">
      <div class="flex flex-wrap items-center gap-2">
        <RiskBadge :level="statusTone(row?.completion_status)" :label="`状态：${row?.completion_status || '—'}`" />
        <span class="text-xs text-slate-400">变更类型：{{ row?.change_type || '—' }}</span>
        <span class="text-xs text-slate-400">执行日期：{{ row?.execute_date || '—' }}</span>
      </div>
    </template>
    <template #detail="{ row }">
      <div class="mt-3">
        <h4 class="mb-2 text-xs font-medium text-slate-400">配置差异对比</h4>
        <div class="grid grid-cols-2 gap-3">
          <div class="rounded border border-[var(--border)] bg-[var(--canvas)] p-3">
            <div class="mb-1 text-xs text-slate-400">原配置</div>
            <p class="whitespace-pre-wrap text-sm text-slate-700">{{ row?.old_config || '—' }}</p>
          </div>
          <div class="rounded border border-[var(--border)] bg-[var(--canvas)] p-3">
            <div class="mb-1 text-xs text-slate-400">新配置</div>
            <p class="whitespace-pre-wrap text-sm text-slate-700">{{ row?.new_config || '—' }}</p>
          </div>
        </div>
      </div>
    </template>
  </LifecycleListPage>
</template>
