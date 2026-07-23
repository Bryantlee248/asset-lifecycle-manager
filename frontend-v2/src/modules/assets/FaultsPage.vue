<script setup lang="ts">
import LifecycleListPage from '@/components/assets/LifecycleListPage.vue'
import type { GridColumn } from '@/components/common/DataGrid.vue'
import type { FieldDef } from '@/components/assets/field'
import RiskBadge from '@/components/common/RiskBadge.vue'
import LifecycleTimeline from '@/components/assets/LifecycleTimeline.vue'
import {
  getFaults, createFault, updateFault, deleteFault,
} from '@/services/faults'

const columns: GridColumn[] = [
  { key: 'fault_no', label: '故障单号', width: '130px' },
  { key: 'asset_code', label: '资产编号', width: '120px' },
  { key: 'fault_level', label: '故障级别', slot: true, width: '100px' },
  { key: 'fault_date', label: '故障日期', width: '110px' },
  { key: 'repair_person', label: '维修人', width: '100px' },
  { key: 'recovery_date', label: '恢复日期', width: '110px' },
]

const cellRenderers = [
  {
    key: 'fault_level',
    kind: 'risk' as const,
    // P1 / P2-严重 -> 严重(critical)；P2 -> 中警(warning)；P3 -> 注意(caution)；其余正常。
    riskLevel: (v: any) =>
      v === 'P1' || v === 'P2-严重' ? 'critical' : v === 'P2' ? 'warning' : v === 'P3' ? 'caution' : 'ok',
  },
]

const filterDefs = [{ key: 'asset_code', label: '按资产编号' }]

const editSchema: FieldDef[] = [
  { key: 'fault_no', label: '故障单号' },
  { key: 'asset_code', label: '资产编号', required: true },
  { key: 'fault_level', label: '故障级别', type: 'select', options: ['P1', 'P2', 'P2-严重', 'P3'], required: true },
  { key: 'fault_date', label: '故障日期', type: 'date' },
  { key: 'fault_description', label: '故障描述', type: 'textarea', col: 2 },
  { key: 'repair_person', label: '维修人' },
  { key: 'handle_method', label: '处理方式', type: 'select', options: ['现场维修', '返厂维修', '远程支持', '更换配件'] },
  { key: 'root_cause', label: '根因分类', type: 'select', options: ['硬件故障', '软件故障', '人为误操作', '环境因素', '未知'] },
  { key: 'parts_replaced', label: '更换配件' },
  { key: 'repair_cost', label: '维修费用', type: 'number' },
  { key: 'is_recurring', label: '是否复发', type: 'select', options: ['是', '否'] },
  { key: 'recovery_date', label: '恢复日期', type: 'date' },
  { key: 'downtime_hours', label: '停机时长(小时)', type: 'number' },
  { key: 'remarks', label: '备注', type: 'textarea', col: 2 },
]

const levelTone = (v: any) =>
  v === 'P1' || v === 'P2-严重' ? 'critical' : v === 'P2' ? 'warning' : v === 'P3' ? 'caution' : 'ok'
</script>

<template>
  <LifecycleListPage
    module-title="故障管理"
    module-key="faults"
    :columns="columns"
    :fetch-fn="getFaults"
    :filter-defs="filterDefs"
    search-placeholder="搜索故障单号 / 资产编号"
    :edit-schema="editSchema"
    :cell-renderers="cellRenderers"
    :endpoints="{ create: createFault, update: updateFault, delete: deleteFault }"
    create-perm="fault:create"
    edit-perm="fault:edit"
    delete-perm="fault:delete"
  >
    <template #status="{ row }">
      <div class="flex flex-wrap items-center gap-2">
        <RiskBadge :level="levelTone(row?.fault_level)" :label="`级别：${row?.fault_level || '—'}`" />
        <span class="text-xs text-slate-400">是否复发：{{ row?.is_recurring || '—' }}</span>
        <span class="text-xs text-slate-400">停机：{{ row?.downtime_hours ?? '—' }} 小时</span>
      </div>
    </template>
    <template #detail="{ row }">
      <div class="mt-3">
        <h4 class="mb-2 text-xs font-medium text-slate-400">故障时间线</h4>
        <LifecycleTimeline
          :events="[
            { time: row?.fault_date || '', title: '故障发生', desc: row?.fault_description || '', tone: 'critical' },
            { time: row?.recovery_date || '', title: '恢复', tone: 'ok' },
          ]"
        />
      </div>
    </template>
  </LifecycleListPage>
</template>
