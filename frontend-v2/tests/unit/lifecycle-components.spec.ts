import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import DataGrid from '@/components/common/DataGrid.vue'
import FilterBar from '@/components/common/FilterBar.vue'
import StageGateBadge from '@/components/assets/StageGateBadge.vue'
import AssetDetailWorkbench from '@/modules/assets/AssetDetailWorkbench.vue'

// AssetDetailWorkbench calls getAssetTimeline / stageGate from @/services/assets.
// Mock the services module so the mount never hits a real network call.
vi.mock('@/services/assets', () => ({
  getAssetTimeline: vi.fn().mockResolvedValue({ timeline: [] }),
  stageGate: vi.fn().mockResolvedValue({ allowed: true }),
}))

describe('DataGrid', () => {
  const twoCols = [
    { key: 'a', label: 'A', slot: true },
    { key: 'b', label: 'B' },
  ]

  it('renders one header per column and renders the #cell-<key> slot', () => {
    const rows = [{ a: '1', b: 'Bval' }]
    const wrapper = mount(DataGrid, {
      props: { columns: twoCols, rows },
      slots: { 'cell-a': '<span class="cell-a">X</span>' },
    })
    // header count tracks the columns prop
    expect(wrapper.findAll('thead th').length).toBe(twoCols.length)
    // the custom slot content is rendered
    expect(wrapper.find('.cell-a').text()).toContain('X')
    // a non-slot column falls back to the raw row value
    expect(wrapper.text()).toContain('Bval')
  })

  it('column visibility is driven by the columns prop (4 vs 2)', () => {
    const fourCols = [
      { key: 'a', label: 'A' },
      { key: 'b', label: 'B' },
      { key: 'c', label: 'C' },
      { key: 'd', label: 'D' },
    ]
    const four = mount(DataGrid, { props: { columns: fourCols, rows: [] } })
    const two = mount(DataGrid, { props: { columns: twoCols, rows: [] } })
    expect(four.findAll('thead th').length).toBe(4)
    expect(two.findAll('thead th').length).toBe(2)
    // proves the header count is driven by the columns prop, not hardcoded
    expect(four.findAll('thead th').length).not.toBe(two.findAll('thead th').length)
  })

  it('shows the empty state text when there are no rows', () => {
    const wrapper = mount(DataGrid, { props: { columns: twoCols, rows: [] } })
    expect(wrapper.text()).toContain('暂无数据')
  })
})

describe('FilterBar', () => {
  it('emits update:modelValue with the typed text on input', async () => {
    const wrapper = mount(FilterBar, { props: { modelValue: '' } })
    const input = wrapper.find('input')
    await input.setValue('router')
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')![0]).toEqual(['router'])
  })

  it('emits submit when Enter is pressed', async () => {
    const wrapper = mount(FilterBar, { props: { modelValue: 'abc' } })
    await wrapper.find('input').trigger('keyup', { key: 'Enter' })
    expect(wrapper.emitted('submit')).toBeTruthy()
  })

  it('clearing via 重置 emits update:modelValue("") and reset', async () => {
    const wrapper = mount(FilterBar, { props: { modelValue: '' } })
    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([['']])
    expect(wrapper.emitted('reset')).toBeTruthy()
  })
})

describe('StageGateBadge', () => {
  it('shows 门禁通过 when the transition is allowed', () => {
    const wrapper = mount(StageGateBadge, { props: { allowed: true } })
    expect(wrapper.text()).toContain('门禁通过')
  })

  it('shows 门禁拦截 and the message when blocked', () => {
    const wrapper = mount(StageGateBadge, {
      props: { allowed: false, message: '需审批' },
    })
    expect(wrapper.text()).toContain('门禁拦截')
    expect(wrapper.text()).toContain('需审批')
  })
})

describe('AssetDetailWorkbench', () => {
  it('renders the asset code, 基础信息 tab, field labels, and stage tag', async () => {
    const asset = {
      asset_code: 'A1',
      lifecycle_stage: '运行',
      device_name: 'x',
      warranty_status: '在保',
    }
    const wrapper = mount(AssetDetailWorkbench, { props: { asset } })
    await wrapper.vm.$nextTick()

    const text = wrapper.text()
    expect(text).toContain('A1')
    expect(text).toContain('基础信息')
    expect(text).toContain('资产编号')
    expect(text).toContain('设备名称')
    // StageTag (from common/) renders the stage label
    expect(text).toContain('运行')
  })
})
