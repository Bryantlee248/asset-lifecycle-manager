import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import PermissionGate from '@/components/common/PermissionGate.vue'
import { useAuthStore } from '@/stores/auth'

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('PermissionGate', () => {
  it('shows slot content when user has the permission', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, permissions: ['asset.view'], roles: [] }
    const w = mount(PermissionGate, {
      props: { perm: 'asset.view' },
      slots: { default: '<span>secret</span>' },
    })
    expect(w.text()).toContain('secret')
  })

  it('hides slot content without the permission', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, permissions: ['asset.view'], roles: [] }
    const w = mount(PermissionGate, {
      props: { perm: 'asset.delete' },
      slots: { default: '<span>secret</span>' },
    })
    expect(w.text()).not.toContain('secret')
  })

  it('grants access to admin role regardless of explicit permission', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, permissions: [], roles: [{ code: 'admin' }] }
    const w = mount(PermissionGate, {
      props: { perm: 'asset.delete' },
      slots: { default: '<span>secret</span>' },
    })
    expect(w.text()).toContain('secret')
  })

  it('supports anyOf (show if any permission matches)', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, permissions: ['asset.edit'], roles: [] }
    const w = mount(PermissionGate, {
      props: { anyOf: ['asset.delete', 'asset.edit'] },
      slots: { default: '<span>secret</span>' },
    })
    expect(w.text()).toContain('secret')
  })
})
