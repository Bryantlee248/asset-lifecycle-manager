<script setup lang="ts">
import LifecycleListPage from '@/components/assets/LifecycleListPage.vue'
import type { GridColumn } from '@/components/common/DataGrid.vue'
import type { FieldDef } from '@/components/assets/field'
import RiskBadge from '@/components/common/RiskBadge.vue'
import {
  getWarranties, createWarranty, updateWarranty, deleteWarranty,
} from '@/services/warranties'

const columns: GridColumn[] = [
  { key: 'warranty_no', label: '维保单号', width: '130px' },
  { key: 'asset_code', label: '资产编号', width: '120px' },
  { key: 'warranty_type', label: '维保类型', width: '120px' },
  { key: 'start_date', label: '生效日期', width: '110px' },
  { key: 'end_date', label: '到期日期', width: '110px' },
  { key: 'renewal_decision', label: '续保决策', slot: true, width: '100px' },
]

const cellRenderers = [
  {
    key: 'renewal_decision',
    kind: 'risk' as const,
    riskLevel: (v: any) =>
      v === '续保' ? 'ok' : v === '不续保' ? 'warning' : v === '待定' ? 'caution' : 'ok',
  },
]

const filterDefs = [{ key: 'asset_code', label: '按资产编号' }]

const editSchema: FieldDef[] = [
  { key: 'warranty_no', label: '维保单号' },
  { key: 'asset_code', label: '资产编号', required: true },
  { key: 'warranty_type', label: '维保类型', type: 'select', options: ['原厂维保', '集成商维保', '第三方维保'] },
  { key: 'warranty_vendor', label: '维保厂商' },
  { key: 'contract_no', label: '合同号' },
  { key: 'coverage', label: '覆盖范围', type: 'textarea', col: 2 },
  { key: 'start_date', label: '生效日期', type: 'date' },
  { key: 'end_date', label: '到期日期', type: 'date' },
  { key: 'renewal_decision', label: '续保决策', type: 'select', options: ['续保', '不续保', '待定'] },
  { key: 'decision_person', label: '决策人' },
  { key: 'renewal_contract_no', label: '续保合同号' },
  { key: 'cost', label: '费用', type: 'number' },
  { key: 'renewal_start_date', label: '续保生效', type: 'date' },
  { key: 'renewal_end_date', label: '续保到期', type: 'date' },
  { key: 'remarks', label: '备注', type: 'textarea', col: 2 },
]

const decisionTone = (v: any) =>
  v === '续保' ? 'ok' : v === '不续保' ? 'warning' : v === '待定' ? 'caution' : 'ok'
</script>

<template>
  <LifecycleListPage
    module-title="质保管理"
    module-key="warranties"
    :columns="columns"
    :fetch-fn="getWarranties"
    :filter-defs="filterDefs"
    search-placeholder="搜索维保单号 / 资产编号"
    :edit-schema="editSchema"
    :cell-renderers="cellRenderers"
    :endpoints="{ create: createWarranty, update: updateWarranty, delete: deleteWarranty }"
    create-perm="warranty:create"
    edit-perm="warranty:edit"
    delete-perm="warranty:delete"
  >
    <template #status="{ row }">
      <div class="flex flex-wrap items-center gap-2">
        <RiskBadge :level="decisionTone(row?.renewal_decision)" :label="`续保：${row?.renewal_decision || '—'}`" />
        <span class="text-xs text-slate-400">维保类型：{{ row?.warranty_type || '—' }}</span>
        <span class="text-xs text-slate-400">有效期：{{ row?.start_date || '—' }} ~ {{ row?.end_date || '—' }}</span>
      </div>
    </template>
    <template #detail="{ row }">
      <div class="mt-3 space-y-3">
        <div>
          <h4 class="mb-1 text-xs font-medium text-slate-400">覆盖范围</h4>
          <p class="whitespace-pre-wrap rounded border border-[var(--border)] bg-[var(--canvas)] p-3 text-sm text-slate-700">{{ row?.coverage || '—' }}</p>
        </div>
        <div>
          <h4 class="mb-1 text-xs font-medium text-slate-400">续保信息</h4>
          <dl class="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
            <div><dt class="text-xs text-slate-400">续保决策</dt><dd class="text-slate-700">{{ row?.renewal_decision || '—' }}</dd></div>
            <div><dt class="text-xs text-slate-400">续保合同号</dt><dd class="text-slate-700">{{ row?.renewal_contract_no || '—' }}</dd></div>
            <div><dt class="text-xs text-slate-400">续保生效</dt><dd class="text-slate-700">{{ row?.renewal_start_date || '—' }}</dd></div>
            <div><dt class="text-xs text-slate-400">续保到期</dt><dd class="text-slate-700">{{ row?.renewal_end_date || '—' }}</dd></div>
          </dl>
        </div>
      </div>
    </template>
  </LifecycleListPage>
</template>
