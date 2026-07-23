<script setup lang="ts">
import LifecycleListPage from '@/components/assets/LifecycleListPage.vue'
import type { GridColumn } from '@/components/common/DataGrid.vue'
import type { FieldDef } from '@/components/assets/field'
import RiskBadge from '@/components/common/RiskBadge.vue'
import {
  getProcurements, createProcurement, updateProcurement, deleteProcurement,
} from '@/services/procurement'

const columns: GridColumn[] = [
  { key: 'asset_code', label: '资产编号', width: '120px' },
  { key: 'purchase_order', label: '采购单号', width: '130px' },
  { key: 'supplier', label: '供应商', width: '120px' },
  { key: 'device_name', label: '设备名称', width: '140px' },
  { key: 'approval_status', label: '审批状态', slot: true, width: '100px' },
  { key: 'inspection_result', label: '验收结果', slot: true, width: '100px' },
  { key: 'request_date', label: '申请日期', width: '110px' },
  { key: 'quantity', label: '数量', width: '70px', align: 'right' },
]

const cellRenderers = [
  { key: 'approval_status', kind: 'risk' as const, riskLevel: (v: any) =>
      v === '已批准' ? 'ok' : v === '已驳回' ? 'critical' : v === '待审批' ? 'warning' : 'ok' },
  { key: 'inspection_result', kind: 'risk' as const, riskLevel: (v: any) =>
      v === '合格' ? 'ok' : v === '不合格' ? 'critical' : v === '待验收' ? 'caution' : 'ok' },
]

const filterDefs = [{ key: 'asset_code', label: '按资产编号', placeholder: '输入资产编号' }]

const editSchema: FieldDef[] = [
  { key: 'asset_code', label: '资产编号' },
  { key: 'purchase_order', label: '采购单号' },
  { key: 'request_no', label: '采购申请号' },
  { key: 'supplier', label: '供应商' },
  { key: 'device_name', label: '设备名称' },
  { key: 'contract_no', label: '合同号' },
  { key: 'approval_status', label: '审批状态', type: 'select', options: ['待审批', '已批准', '已驳回'] },
  { key: 'request_date', label: '申请日期', type: 'date' },
  { key: 'quantity', label: '数量', type: 'number' },
  { key: 'unit_price', label: '单价', type: 'number' },
  { key: 'total_price', label: '总价', type: 'number' },
  { key: 'config_summary', label: '配置摘要', type: 'textarea', col: 2 },
  { key: 'arrival_date', label: '到货日期', type: 'date' },
  { key: 'inspector', label: '验收人' },
  { key: 'inspection_result', label: '验收结果', type: 'select', options: ['待验收', '合格', '不合格'] },
  { key: 'applicant', label: '申请人' },
  { key: 'install_date', label: '上架日期', type: 'date' },
  { key: 'remarks', label: '备注', type: 'textarea', col: 2 },
]

const approvalTone = (v: any) => (v === '已批准' ? 'ok' : v === '已驳回' ? 'critical' : v === '待审批' ? 'warning' : 'ok')
const inspectionTone = (v: any) => (v === '合格' ? 'ok' : v === '不合格' ? 'critical' : v === '待验收' ? 'caution' : 'ok')
</script>

<template>
  <LifecycleListPage
    module-title="采购管理"
    module-key="procurement"
    :columns="columns"
    :fetch-fn="getProcurements"
    :filter-defs="filterDefs"
    search-placeholder="搜索采购单号 / 供应商 / 设备"
    :edit-schema="editSchema"
    :cell-renderers="cellRenderers"
    :endpoints="{ create: createProcurement, update: updateProcurement, delete: deleteProcurement }"
    create-perm="procurement:create"
    edit-perm="procurement:edit"
    delete-perm="procurement:delete"
  >
    <template #status="{ row }">
      <div class="flex flex-wrap items-center gap-2">
        <RiskBadge :level="approvalTone(row?.approval_status)" :label="`审批：${row?.approval_status || '—'}`" />
        <RiskBadge :level="inspectionTone(row?.inspection_result)" :label="`验收：${row?.inspection_result || '—'}`" />
        <span class="text-xs text-slate-400">到货：{{ row?.arrival_date || '—' }}</span>
      </div>
    </template>
  </LifecycleListPage>
</template>
