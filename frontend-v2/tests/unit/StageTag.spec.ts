import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StageTag from '@/components/common/StageTag.vue'

describe('StageTag', () => {
  it('renders the stage label', () => {
    const w = mount(StageTag, { props: { stage: '运行' } })
    expect(w.text()).toContain('运行')
  })

  it('applies the 运行 semantic background token', () => {
    const w = mount(StageTag, { props: { stage: '运行' } })
    expect(w.element.getAttribute('style')).toContain('var(--stage-运行-bg)')
  })

  it('falls back to a neutral style for unknown stages', () => {
    const w = mount(StageTag, { props: { stage: '未知阶段' } })
    expect(w.text()).toContain('未知阶段')
    expect(w.element.getAttribute('style')).toContain('var(--canvas)')
  })

  it('supports the small size', () => {
    const w = mount(StageTag, { props: { stage: '规划', size: 'sm' } })
    expect(w.classes().join(' ')).toContain('text-[11px]')
  })
})
