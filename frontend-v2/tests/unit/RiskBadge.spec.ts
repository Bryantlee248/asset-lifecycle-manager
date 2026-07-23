import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import RiskBadge from '@/components/common/RiskBadge.vue'

describe('RiskBadge', () => {
  it('renders 严重 with critical background token by default', () => {
    const w = mount(RiskBadge, { props: { level: 'critical' } })
    expect(w.text()).toContain('严重')
    expect(w.element.getAttribute('style')).toContain('#fde8e8')
  })

  it('renders 中等 with warning background token by default', () => {
    const w = mount(RiskBadge, { props: { level: 'warning' } })
    expect(w.text()).toContain('中等')
    expect(w.element.getAttribute('style')).toContain('#fff7e8')
  })

  it('renders 正常 for ok level by default', () => {
    const w = mount(RiskBadge, { props: { level: 'ok' } })
    expect(w.text()).toContain('正常')
  })

  it('honours a custom label', () => {
    const w = mount(RiskBadge, { props: { level: 'critical', label: '紧急' } })
    expect(w.text()).toContain('紧急')
  })
})
