<script setup lang="ts">
import LifecycleListPage from '@/components/assets/LifecycleListPage.vue'
import type { GridColumn } from '@/components/common/DataGrid.vue'
import type { FieldDef } from '@/components/assets/field'
import RiskBadge from '@/components/common/RiskBadge.vue'
import {
  getInbounds, createInbound, updateInbound, deleteInbound,
} from '@/services/inbound'

const columns: GridColumn[] = [
  { key: 'inbound_no', label: '移入单号', width: '130px' },
  { key: 'receive_type', label: '接收类型', slot: true, width: '110px' },
  { key: 'asset_category', label: '资产分类', width: '110px' },
  { key: 'brand', label: '品牌', width: '110px' },
  { key: 'model', label: '型号', width: '120px' },
  { key: 'sn', label: 'SN', width: '140px' },
  { key: 'inspection_result', label: '验收结果', slot: true, width: '100px' },
  { key: 'inbound_date', label: '移入日期', width: '110px' },
]

const cellRenderers = [
  {
    key: 'receive_type',
    kind: 'risk' as const,
    // 报废 -> 严重(critical)；调拨类(如「调拨入库」) -> 中警(warning)；其余正常。
    riskLevel: (v: any) =>
      v === '报废' ? 'critical' : String(v || '').includes('调拨') ? 'warning' : 'ok',
  },
  {
    key: 'inspection_result',
    kind: 'risk' as const,
    riskLevel: (v: any) =>
      v === '合格' ? 'ok' : v === '不合格' ? 'critical' : v === '待验收' ? 'caution' : 'ok',
  },
]

const filterDefs = [
  { key: 'receive_type', label: '全部接收类型', options: ['采购到货', '调拨入库', '归还入库', '盘盈入库'] },
]

const editSchema: FieldDef[] = [
  { key: 'inbound_no', label: '移入单号' },
  { key: 'receive_type', label: '接收类型', type: 'select', options: ['采购到货', '调拨入库', '归还入库', '盘盈入库'] },
  { key: 'ownership', label: '产权归属', type: 'select', options: ['自有', '托管'] },
  { key: 'asset_category', label: '资产分类' },
  { key: 'brand', label: '品牌' },
  { key: 'model', label: '型号' },
  { key: 'sn', label: 'SN序列号' },
  { key: 'project_name', label: '项目名称' },
  { key: 'project_no', label: '项目编号' },
  { key: 'config_summary', label: '配置摘要', type: 'textarea', col: 2 },
  { key: 'purchase_contract_no', label: '采购合同号' },
  { key: 'purchase_total_price', label: '采购总价', type: 'number' },
  { key: 'inbound_date', label: '移入日期', type: 'date' },
  { key: 'receiver', label: '接收人' },
  { key: 'inspection_result', label: '验收结果', type: 'select', options: ['待验收', '合格', '不合格'] },
  { key: 'storage_location', label: '存放位置' },
  { key: 'owner_company', label: '所属公司' },
  { key: 'remarks', label: '备注', type: 'textarea', col: 2 },
]

const receiveTone = (v: any) =>
  v === '报废' ? 'critical' : String(v || '').includes('调拨') ? 'warning' : 'ok'
const inspectionTone = (v: any) =>
  v === '合格' ? 'ok' : v === '不合格' ? 'critical' : v === '待验收' ? 'caution' : 'ok'
</script>

<template>
  <LifecycleListPage
    module-title="入库管理"
    module-key="inbound"
    :columns="columns"
    :fetch-fn="getInbounds"
    :filter-defs="filterDefs"
    search-placeholder="搜索移入单号 / SN / 品牌"
    :edit-schema="editSchema"
    :cell-renderers="cellRenderers"
    :endpoints="{ create: createInbound, update: updateInbound, delete: deleteInbound }"
    create-perm="inbound:create"
    edit-perm="inbound:edit"
    delete-perm="inbound:delete"
  >
    <template #status="{ row }">
      <div class="flex flex-wrap items-center gap-2">
        <RiskBadge :level="inspectionTone(row?.inspection_result)" :label="`验收：${row?.inspection_result || '—'}`" />
        <span class="text-xs text-slate-400">接收类型：{{ row?.receive_type || '—' }}</span>
        <span class="text-xs text-slate-400">移入日期：{{ row?.inbound_date || '—' }}</span>
      </div>
      <p class="mt-1 text-xs text-slate-400">验收合格将自动建资产</p>
    </template>
  </LifecycleListPage>
</template>
