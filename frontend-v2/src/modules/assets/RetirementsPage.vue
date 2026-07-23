<script setup lang="ts">
import LifecycleListPage from '@/components/assets/LifecycleListPage.vue'
import type { GridColumn } from '@/components/common/DataGrid.vue'
import type { FieldDef } from '@/components/assets/field'
import RiskBadge from '@/components/common/RiskBadge.vue'
import {
  getRetirements, createRetirement, updateRetirement, deleteRetirement,
} from '@/services/retirements'

const columns: GridColumn[] = [
  { key: 'asset_code', label: '资产编号', width: '120px' },
  { key: 'retire_category', label: '退役类别', slot: true, width: '110px' },
  { key: 'application_no', label: '申请单号', width: '130px' },
  { key: 'approver', label: '审批人', width: '100px' },
  { key: 'uninstall_date', label: '下架日期', width: '110px' },
  { key: 'disposal_method', label: '处置方式', width: '110px' },
  { key: 'residual_value', label: '残值', width: '90px', align: 'right' },
]

const cellRenderers = [
  {
    key: 'retire_category',
    kind: 'risk' as const,
    // 报废 -> 严重(critical)；置换 -> 注意(caution)；捐赠 -> 正常(ok)；其余正常。
    riskLevel: (v: any) =>
      v === '报废' ? 'critical' : v === '置换' ? 'caution' : v === '捐赠' ? 'ok' : 'ok',
  },
]

const filterDefs = [{ key: 'asset_code', label: '按资产编号' }]

const editSchema: FieldDef[] = [
  { key: 'asset_code', label: '资产编号', required: true },
  { key: 'retire_category', label: '退役类别', type: 'select', options: ['报废', '置换', '捐赠', '转售'] },
  { key: 'retire_reason', label: '退役原因', type: 'textarea', col: 2 },
  { key: 'application_no', label: '申请单号' },
  { key: 'approver', label: '审批人' },
  { key: 'approval_date', label: '审批日期', type: 'date' },
  { key: 'uninstall_date', label: '下架日期', type: 'date' },
  { key: 'uninstall_person', label: '下架人' },
  { key: 'data_cleared', label: '数据清除', type: 'select', options: ['已清除', '未清除'], required: true },
  { key: 'data_clear_person', label: '数据清除人' },
  { key: 'disposal_method', label: '处置方式', type: 'select', options: ['销毁', '回收', '转售', '捐赠'] },
  { key: 'residual_value', label: '残值', type: 'number' },
  { key: 'remarks', label: '备注', type: 'textarea', col: 2 },
]

const retireTone = (v: any) =>
  v === '报废' ? 'critical' : v === '置换' ? 'caution' : v === '捐赠' ? 'ok' : 'ok'
const dataClearedTone = (v: any) => (v === '已清除' ? 'ok' : 'critical')
</script>

<template>
  <LifecycleListPage
    module-title="退役管理"
    module-key="retirements"
    :columns="columns"
    :fetch-fn="getRetirements"
    :filter-defs="filterDefs"
    search-placeholder="搜索资产编号 / 申请单号"
    :edit-schema="editSchema"
    :cell-renderers="cellRenderers"
    :endpoints="{ create: createRetirement, update: updateRetirement, delete: deleteRetirement }"
    create-perm="retirement:create"
    edit-perm="retirement:edit"
    delete-perm="retirement:delete"
  >
    <template #status="{ row }">
      <div class="flex flex-wrap items-center gap-2">
        <RiskBadge :level="retireTone(row?.retire_category)" :label="`类别：${row?.retire_category || '—'}`" />
        <RiskBadge :level="dataClearedTone(row?.data_cleared)" :label="`数据：${row?.data_cleared || '—'}`" />
        <span class="text-xs text-slate-400">处置方式：{{ row?.disposal_method || '—' }}</span>
      </div>
    </template>
    <template #detail="{ row }">
      <div class="mt-3 space-y-3">
        <div>
          <h4 class="mb-1 text-xs font-medium text-slate-400">退役原因</h4>
          <p class="whitespace-pre-wrap rounded border border-[var(--border)] bg-[var(--canvas)] p-3 text-sm text-slate-700">{{ row?.retire_reason || '—' }}</p>
        </div>
        <div>
          <h4 class="mb-1 text-xs font-medium text-slate-400">残值</h4>
          <p class="text-sm text-slate-700">{{ row?.residual_value ?? '—' }}</p>
        </div>
      </div>
    </template>
  </LifecycleListPage>
</template>
