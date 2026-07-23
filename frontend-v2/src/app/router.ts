import { createRouter, createWebHashHistory } from 'vue-router'
import { NAV_GROUPS } from './nav'
import { useAuthStore } from '@/stores/auth'

// Route-level lazy loading (batch 3). Every page component is now a dynamic
// import() so the main entry chunk stays small and per-module code is only
// fetched when navigated to. The 18 nav keys/paths from nav.ts are preserved;
// known keys map to their lazy component, unknown keys fall back to the lazy
// ComingSoon placeholder. Hash routing, login guard and redirect logic are
// unchanged.

const routes: any[] = [
  { path: '/login', name: 'login', component: () => import('@/modules/auth/LoginPage.vue'), meta: { public: true } },
  { path: '/command-center/dashboard', name: 'dashboard', component: () => import('@/modules/command-center/DashboardPage.vue') },
  { path: '/command-center/validation', name: 'validation', component: () => import('@/modules/command-center/ValidationPage.vue') },
]

// Known page loaders. dashboard/validation are handled explicitly above.
const pageLoaders: Record<string, () => Promise<any>> = {
  assets: () => import('@/modules/assets/AssetsPage.vue'),
  procurement: () => import('@/modules/assets/ProcurementPage.vue'),
  inbound: () => import('@/modules/assets/InboundPage.vue'),
  outbound: () => import('@/modules/assets/OutboundPage.vue'),
  changes: () => import('@/modules/assets/ChangesPage.vue'),
  faults: () => import('@/modules/assets/FaultsPage.vue'),
  warranties: () => import('@/modules/assets/WarrantiesPage.vue'),
  retirements: () => import('@/modules/assets/RetirementsPage.vue'),
  // collaboration
  approval: () => import('@/modules/collaboration/ApprovalPage.vue'),
  approvalNotify: () => import('@/modules/collaboration/ApprovalNotifyPage.vue'),
  importExport: () => import('@/modules/collaboration/ImportExportPage.vue'),
  // insights
  reports: () => import('@/modules/insights/ReportsPage.vue'),
  stats: () => import('@/modules/insights/StatsPage.vue'),
  // governance
  users: () => import('@/modules/governance/UsersPage.vue'),
  roles: () => import('@/modules/governance/RolesPage.vue'),
  config: () => import('@/modules/governance/ConfigPage.vue'),
}

const comingSoon = () => import('@/components/common/ComingSoon.vue')

for (const group of NAV_GROUPS) {
  for (const item of group.items) {
    if (item.key === 'dashboard' || item.key === 'validation') continue
    const loader = pageLoaders[item.key] || comingSoon
    routes.push({
      path: item.path,
      name: item.key,
      component: loader,
      props: pageLoaders[item.key] ? undefined : { module: item.label },
    })
  }
}

routes.push({ path: '/', redirect: '/command-center/dashboard' })
routes.push({ path: '/:pathMatch(.*)*', redirect: '/command-center/dashboard' })

export const router = createRouter({
  history: createWebHashHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

// Route guard: unauthenticated users are sent to /login.
router.beforeEach((to) => {
  const auth = useAuthStore()
  if ((to.meta as any).public) return true
  if (!auth.loggedIn) return { path: '/login', query: to.path !== '/' ? { redirect: to.fullPath } : undefined }
  return true
})
