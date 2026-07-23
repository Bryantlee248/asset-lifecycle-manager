<script setup lang="ts">
import LifecycleListPage from '@/components/assets/LifecycleListPage.vue'
import type { GridColumn } from '@/components/common/DataGrid.vue'
import type { FieldDef } from '@/components/assets/field'
import RiskBadge from '@/components/common/RiskBadge.vue'
import {
  getOutbounds, createOutbound, updateOutbound, deleteOutbound,
} from '@/services/outbound'

const columns: GridColumn[] = [
  { key: 'outbound_no', label: '移出单号', width: '130px' },
  { key: 'asset_code', label: '资产编号', width: '120px' },
  { key: 'outbound_category', label: '移出类别', slot: true, width: '110px' },
  { key: 'outbound_date', label: '移出日期', width: '110px' },
  { key: 'destination', label: '去向', width: '120px' },
  { key: 'operator', label: '操作员', width: '100px' },
  { key: 'approver', label: '审批人', width: '100px' },
]

const cellRenderers = [
  {
    key: 'outbound_category',
    kind: 'risk' as const,
    // 报废移出 -> 严重(critical)；其余正常。
    riskLevel: (v: any) => (v === '报废' ? 'critical' : 'ok'),
  },
]

const filterDefs = [
  { key: 'outbound_category', label: '全部移出类别', options: ['调拨', '借用', '报废', '退还', '盘亏'] },
]

const editSchema: FieldDef[] = [
  { key: 'outbound_no', label: '移出单号' },
  { key: 'asset_code', label: '资产编号', required: true },
  { key: 'outbound_category', label: '移出类别', type: 'select', options: ['调拨', '借用', '报废', '退还', '盘亏'], required: true },
  { key: 'outbound_date', label: '移出日期', type: 'date' },
  { key: 'outbound_reason', label: '移出原因', type: 'textarea', col: 2 },
  { key: 'destination', label: '去向' },
  { key: 'receiver_contact', label: '接收人联系方式' },
  { key: 'receiver_phone', label: '接收人电话' },
  { key: 'operator', label: '操作员' },
  { key: 'approver', label: '审批人' },
  { key: 'remarks', label: '备注', type: 'textarea', col: 2 },
]

const categoryTone = (v: any) => (v === '报废' ? 'critical' : 'ok')
</script>

<template>
  <LifecycleListPage
    module-title="出库管理"
    module-key="outbound"
    :columns="columns"
    :fetch-fn="getOutbounds"
    :filter-defs="filterDefs"
    search-placeholder="搜索移出单号 / 资产编号 / 去向"
    :edit-schema="editSchema"
    :cell-renderers="cellRenderers"
    :endpoints="{ create: createOutbound, update: updateOutbound, delete: deleteOutbound }"
    create-perm="outbound:create"
    edit-perm="outbound:edit"
    delete-perm="outbound:delete"
  >
    <template #status="{ row }">
      <div class="flex flex-wrap items-center gap-2">
        <RiskBadge :level="categoryTone(row?.outbound_category)" :label="`类别：${row?.outbound_category || '—'}`" />
        <span class="text-xs text-slate-400">移出日期：{{ row?.outbound_date || '—' }}</span>
        <span class="text-xs text-slate-400">去向：{{ row?.destination || '—' }}</span>
      </div>
    </template>
  </LifecycleListPage>
</template>
