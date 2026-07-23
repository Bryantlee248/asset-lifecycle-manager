import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { type Page } from '@playwright/test'
import { test, expect } from './helpers'

// ESM context (package.json "type": "module"): derive __dirname from the module URL.
const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const flagPath = path.resolve(__dirname, '.e2e-skip')
const skipReason = fs.existsSync(flagPath) ? fs.readFileSync(flagPath, 'utf8') : ''
test.skip(!!skipReason, `E2E skipped: ${skipReason}`)

// Three responsive breakpoints required by the acceptance criteria.
const VIEWPORTS = [
  { name: '1440', width: 1440, height: 900 },
  { name: '768', width: 768, height: 1024 },
  { name: '375', width: 375, height: 812 },
]

// Batch-3 output dir — kept separate from batch1/2 so we never overwrite those shots.
const OUT_DIR = path.resolve(
  __dirname,
  '../../../docs/handoff/ui-modernization-v2/screenshots/batch3',
)

async function shot(page: Page, dir: string, name: string) {
  fs.mkdirSync(path.join(OUT_DIR, dir), { recursive: true })
  await page.screenshot({ path: path.join(OUT_DIR, dir, `${name}.png`), fullPage: false })
}

// Collaboration / insights / governance routes wired by the engineer (batch 3).
// Paths are the real hash-route paths from src/app/nav.ts; the `title` is the
// expected page heading (moduleTitle) so the test fails loudly if a route or
// its heading is missing.
const BATCH3_ROUTES: { route: string; title: string }[] = [
  { route: '/collaboration/approval', title: '审批中心' },
  { route: '/collaboration/notifications', title: '审批通知' },
  { route: '/collaboration/import-export', title: '导入导出' },
  { route: '/insights/reports', title: '报表中心' },
  { route: '/insights/stats', title: '统计分析' },
  { route: '/governance/users', title: '用户管理' },
  { route: '/governance/roles', title: '角色管理' },
  { route: '/governance/config', title: '系统配置' },
]

function routeDir(route: string): string {
  return route.replace(/^\//, '').replace(/\//g, '-')
}

test.describe('responsive screenshots (batch 3 — 协同/洞察/治理)', () => {
  for (const vp of VIEWPORTS) {
    test(`8 批三路由 @ ${vp.name}`, async ({ page, consoleErrors }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height })

      // 1) Login (credentials come from the environment, never hardcoded)
      await page.goto('/')
      await page.getByLabel('用户名').fill(process.env.E2E_USER!)
      await page.getByLabel('密码').fill(process.env.E2E_PASSWORD!)
      await page.getByRole('button', { name: /登\s*录/ }).click()
      await expect(page).toHaveURL(/#\/command-center\/dashboard/)

      // 2) Visit each batch-3 route and capture a screenshot once the heading is visible
      for (const { route, title } of BATCH3_ROUTES) {
        await page.goto('/#' + route)
        await expect(page.getByRole('heading', { name: title })).toBeVisible()
        await shot(page, routeDir(route), vp.name)
      }

      // No unexpected console errors across the navigated pages.
      expect(consoleErrors, `unexpected console errors @ ${vp.name}px`).toEqual([])
    })
  }
})
