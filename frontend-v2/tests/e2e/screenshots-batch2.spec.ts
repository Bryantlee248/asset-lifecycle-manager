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

// Batch-2 output dir — kept separate from batch1 so we never overwrite those shots.
const OUT_DIR = path.resolve(
  __dirname,
  '../../../docs/handoff/ui-modernization-v2/screenshots/batch2',
)

async function shot(page: Page, dir: string, name: string) {
  fs.mkdirSync(path.join(OUT_DIR, dir), { recursive: true })
  await page.screenshot({ path: path.join(OUT_DIR, dir, `${name}.png`), fullPage: false })
}

// Asset-operations routes wired by the engineer (batch 2). Each maps to a page
// heading so the test fails loudly if a route/heading is missing.
const ASSET_ROUTES: { route: string; title: string }[] = [
  { route: '/assets', title: '资产台账' },
  { route: '/assets/procurement', title: '采购管理' },
  { route: '/assets/inbound', title: '入库管理' },
  { route: '/assets/outbound', title: '出库管理' },
  { route: '/assets/changes', title: '变更管理' },
  { route: '/assets/faults', title: '故障管理' },
  { route: '/assets/warranties', title: '质保管理' },
  { route: '/assets/retirements', title: '退役管理' },
]

function routeDir(route: string): string {
  return route.replace(/^\//, '').replace(/\//g, '-')
}

test.describe('responsive screenshots (batch 2 — 资产运营)', () => {
  for (const vp of VIEWPORTS) {
    test(`8 资产路由 @ ${vp.name}`, async ({ page, consoleErrors }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height })

      // 1) Login (credentials come from the environment, never hardcoded)
      await page.goto('/')
      await page.getByLabel('用户名').fill(process.env.E2E_USER!)
      await page.getByLabel('密码').fill(process.env.E2E_PASSWORD!)
      await page.getByRole('button', { name: /登\s*录/ }).click()
      await expect(page).toHaveURL(/#\/command-center\/dashboard/)

      // 2) Visit each asset route and capture a screenshot once the heading is visible
      for (const { route, title } of ASSET_ROUTES) {
        await page.goto('/#' + route)
        await expect(page.getByRole('heading', { name: title })).toBeVisible()
        await shot(page, routeDir(route), vp.name)
      }

      // No unexpected console errors across the navigated pages.
      expect(consoleErrors, `unexpected console errors @ ${vp.name}px`).toEqual([])
    })
  }
})
