import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { nextTick } from 'vue'

// EChart is canvas-based; mock it so ChartCard's "ready" state renders a
// deterministic stub instead of initialising a real canvas in happy-dom.
vi.mock('@/components/common/EChart.vue', () => ({
  default: { name: 'EChartStub', template: '<div class="echart-mock"></div>' },
}))

import ApprovalQueue from '@/components/collaboration/ApprovalQueue.vue'
import NotifyList from '@/components/collaboration/NotifyList.vue'
import TaskCenter from '@/components/collaboration/TaskCenter.vue'
import ChartCard from '@/components/insights/ChartCard.vue'
import ConfigWorkspace from '@/components/governance/ConfigWorkspace.vue'
import LifecycleListPage from '@/components/assets/LifecycleListPage.vue'
import { useAuthStore } from '@/stores/auth'

beforeEach(() => {
  setActivePinia(createPinia())
})

function findButton(wrapper: any, text: string) {
  return wrapper.findAll('button').find((b: any) => (b.text() || '').includes(text))
}

// ---------------------------------------------------------------------------
// ApprovalQueue
// ---------------------------------------------------------------------------
describe('ApprovalQueue', () => {
  const items = [
    { id: 1, asset_code: 'A1', approval_type: '采购', status: 'pending', reason: '需要审批' },
    { id: 2, asset_code: 'A2', approval_type: '入库', status: 'approved', reason: 'ok' },
  ]

  it('renders a dual-column layout (left list + right detail)', () => {
    const w = mount(ApprovalQueue, { props: { items } })
    // left list panel + right detail panel => at least two .c2-panel blocks
    expect(w.findAll('.c2-panel').length).toBeGreaterThanOrEqual(2)
    // left list shows each item's asset_code / approval_type
    expect(w.text()).toContain('A1')
    expect(w.text()).toContain('采购')
  })

  it('clicking an item emits select with its id; selecting shows detail', async () => {
    const w = mount(ApprovalQueue, { props: { items } })
    const itemBtn = findButton(w, 'A1')
    expect(itemBtn).toBeTruthy()
    await itemBtn!.trigger('click')
    expect(w.emitted('select')).toBeTruthy()
    expect(w.emitted('select')![0]).toEqual([1])

    // simulate parent wiring selectedId back
    await w.setProps({ selectedId: 1 })
    await nextTick()
    // right detail shows the selected asset_code + reason
    expect(w.text()).toContain('A1')
    expect(w.text()).toContain('需要审批')
  })

  it('approve emits approve(id); reject flow emits reject(id, comment)', async () => {
    const w = mount(ApprovalQueue, { props: { items, selectedId: 1 } })
    await nextTick()

    const approve = findButton(w, '同意')
    expect(approve).toBeTruthy()
    await approve!.trigger('click')
    expect(w.emitted('approve')).toBeTruthy()
    expect(w.emitted('approve')![0]).toEqual([1])

    const reject = findButton(w, '驳回')
    expect(reject).toBeTruthy()
    await reject!.trigger('click')
    await nextTick()
    // reject reason textarea now present
    const ta = w.find('textarea')
    expect(ta.exists()).toBe(true)
    await ta.setValue('不符合规范')
    const confirm = findButton(w, '确认驳回')
    await confirm!.trigger('click')
    expect(w.emitted('reject')).toBeTruthy()
    expect(w.emitted('reject')![0]).toEqual([1, '不符合规范'])
  })
})

// ---------------------------------------------------------------------------
// NotifyList
// ---------------------------------------------------------------------------
describe('NotifyList', () => {
  const items = [
    { id: 1, title: '待你审批', is_read: false },
    { id: 2, title: '已完成', is_read: true },
  ]

  it('shows an unread marker for unread items', () => {
    const w = mount(NotifyList, { props: { items } })
    // default tab is "unread" -> only unread items visible, with the dot marker
    const marker = w.find('[aria-label="未读"]')
    expect(marker.exists()).toBe(true)
  })

  it('clicking an unread item emits markRead with id (and click)', async () => {
    const w = mount(NotifyList, { props: { items } })
    const item = findButton(w, '待你审批')
    expect(item).toBeTruthy()
    await item!.trigger('click')
    expect(w.emitted('markRead')).toBeTruthy()
    expect(w.emitted('markRead')![0]).toEqual([1])
    expect(w.emitted('click')).toBeTruthy()
  })

  it('"全部已读" emits markAllRead', async () => {
    const w = mount(NotifyList, { props: { items } })
    const all = findButton(w, '全部已读')
    expect(all).toBeTruthy()
    await all!.trigger('click')
    expect(w.emitted('markAllRead')).toBeTruthy()
  })
})

// ---------------------------------------------------------------------------
// TaskCenter
// ---------------------------------------------------------------------------
describe('TaskCenter', () => {
  const tasks = [
    { id: 1, name: '导入中', status: 'running' as const },
    { id: 2, name: '导出完成', status: 'success' as const },
    { id: 3, name: '校验失败', status: 'failed' as const, errorLines: ['第 3 行格式错误'] },
  ]

  it('renders task list with per-status badges; running shows progress state', () => {
    const w = mount(TaskCenter, { props: { tasks } })
    expect(w.text()).toContain('导入中')
    expect(w.text()).toContain('导出完成')
    // running task carries data-status="running" (progress element proxy)
    expect(w.find('[data-status="running"]').exists()).toBe(true)
  })

  it('failed task surfaces its error line', () => {
    const w = mount(TaskCenter, { props: { tasks } })
    expect(w.text()).toContain('第 3 行格式错误')
  })

  it('emits download / retry / remove on their respective buttons', async () => {
    const w = mount(TaskCenter, { props: { tasks } })
    const dl = findButton(w, '下载')
    await dl!.trigger('click')
    expect(w.emitted('download')).toBeTruthy()
    expect(w.emitted('download')![0]).toEqual([2])

    const retry = findButton(w, '重试')
    await retry!.trigger('click')
    expect(w.emitted('retry')).toBeTruthy()
    expect(w.emitted('retry')![0]).toEqual([3])

    const remove = findButton(w, '移除')
    await remove!.trigger('click')
    expect(w.emitted('remove')).toBeTruthy()
    expect(w.emitted('remove')![0]).toEqual([1])
  })
})

// ---------------------------------------------------------------------------
// ChartCard
// ---------------------------------------------------------------------------
describe('ChartCard', () => {
  it('empty option -> data-state="empty" and 暂无数据', () => {
    const w = mount(ChartCard, { props: { title: 'T', option: null } })
    expect(w.attributes('data-state')).toBe('empty')
    expect(w.text()).toContain('暂无数据')
  })

  it('error string -> data-state="error"', () => {
    const w = mount(ChartCard, { props: { title: 'T', option: { series: [] }, error: '加载失败' } })
    expect(w.attributes('data-state')).toBe('error')
    expect(w.text()).toContain('加载失败')
  })

  it('valid option -> data-state="ready" and renders chart container', () => {
    const w = mount(ChartCard, {
      props: { title: 'T', option: { series: [{ type: 'bar', data: [1, 2] }] } },
    })
    expect(w.attributes('data-state')).toBe('ready')
    expect(w.find('.echart-mock').exists()).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// ConfigWorkspace — must surface a high-risk warning.
// ---------------------------------------------------------------------------
describe('ConfigWorkspace', () => {
  const props = {
    domains: [{ key: 'dict', label: '字典管理' }],
    activeDomain: 'dict',
    items: [{ id: 1, label: 'X' }],
    formSchema: [{ key: 'name', label: '名称' }],
    riskNote: '本操作属于高风险，请谨慎处理，可能影响生产环境。',
  }

  it('renders left domain list and right detail panel', () => {
    const w = mount(ConfigWorkspace, { props })
    // left column contains the domain button
    expect(w.text()).toContain('字典管理')
    // right panel exists
    expect(w.findAll('.c2-panel').length).toBeGreaterThanOrEqual(2)
  })

  it('surfaces a high-risk warning (高风险 / 谨慎 / 可能影响生产)', async () => {
    const w = mount(ConfigWorkspace, { props })
    // open the reset confirm dialog (teleported to body) to reveal the warning
    const reset = findButton(w, '重置')
    await reset!.trigger('click')
    await nextTick()
    const bodyText = document.body.textContent || ''
    expect(bodyText).toContain('高风险')
    expect(bodyText).toContain('谨慎')
  })
})

// ---------------------------------------------------------------------------
// LifecycleListPage — editPerm fix verification.
//
// The bug: the edit (铅笔) button previously reused `createPerm`. It now gates
// on the dedicated `editPerm` prop. We verify the edit action is driven by
// editPerm, independent of createPerm.
// ---------------------------------------------------------------------------
describe('LifecycleListPage editPerm', () => {
  function makeFetch() {
    return vi.fn().mockResolvedValue({ items: [{ id: 1, asset_code: 'A1' }], total: 1 })
  }

  async function mountPage(perms: string[], extra: Record<string, any> = {}) {
    const auth = useAuthStore()
    auth.user = { id: 1, permissions: perms, roles: [] } as any
    const w = mount(LifecycleListPage, {
      props: {
        moduleTitle: '采购管理',
        moduleKey: 'procurement',
        columns: [{ key: 'asset_code', label: '编号' }],
        fetchFn: makeFetch(),
        endpoints: { create: vi.fn(), update: vi.fn(), delete: vi.fn() },
        createPerm: 'procurement:create',
        editPerm: 'procurement:edit',
        ...extra,
      },
    })
    await flushPromises()
    await w.vm.$nextTick()
    return w
  }

  it('① user has only *:create (not *:edit) -> 编辑 button hidden', async () => {
    const w = await mountPage(['procurement:create'])
    const editBtn = w.findAll('button').find((b) => (b.text() || '').includes('编辑'))
    expect(editBtn, '编辑 button should be hidden when user lacks edit perm').toBeFalsy()
  })

  it('② user has *:edit -> 编辑 button visible', async () => {
    const w = await mountPage(['procurement:edit'])
    const editBtn = w.findAll('button').find((b) => (b.text() || '').includes('编辑'))
    expect(editBtn, '编辑 button should show when user has edit perm').toBeTruthy()
  })

  it('LATENT FINDING — editPerm omitted: 编辑 button must stay hidden after hardening', async () => {
    // LifecycleListPage now guards the edit button with
    // v-if="endpoints?.update && editPerm", so omitting editPerm must NOT expose
    // the button to everyone (previously PermissionGate's falsy-perm default-allow
    // leaked it). This asserts the hardened, intended behaviour.
    const w = await mountPage(['procurement:create'], { editPerm: undefined })
    const editBtn = w.findAll('button').find((b) => (b.text() || '').includes('编辑'))
    expect(editBtn, '编辑 button must be hidden when editPerm is omitted').toBeFalsy()
  })
})
