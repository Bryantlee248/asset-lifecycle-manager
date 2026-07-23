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

const OUT_DIR = path.resolve(
  __dirname,
  '../../../docs/handoff/ui-modernization-v2/screenshots/batch1',
)

async function shot(page: Page, dir: string, name: string) {
  fs.mkdirSync(path.join(OUT_DIR, dir), { recursive: true })
  await page.screenshot({ path: path.join(OUT_DIR, dir, `${name}.png`), fullPage: false })
}

test.describe('responsive screenshots (batch 1)', () => {
  for (const vp of VIEWPORTS) {
    test(`login + dashboard + validation + nav drawer @ ${vp.name}px`, async ({ page, consoleErrors }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height })

      // 1) Login page (logged out)
      await page.goto('/')
      await expect(page.getByText('统一登录')).toBeVisible()
      await shot(page, 'login', vp.name)

      // 2) Login and land on the dashboard
      await page.getByLabel('用户名').fill(process.env.E2E_USER!)
      await page.getByLabel('密码').fill(process.env.E2E_PASSWORD!)
      await page.getByRole('button', { name: /登\s*录/ }).click()
      await expect(page).toHaveURL(/#\/command-center\/dashboard/)
      await shot(page, 'dashboard', vp.name)

      // 3) Mobile off-canvas navigation drawer (only meaningful on narrow widths)
      if (vp.width <= 900) {
        await page.getByRole('button', { name: '打开导航' }).click()
        await expect(page.getByText('资产运营')).toBeVisible()
        await shot(page, 'nav-drawer', vp.name)
      }

      // 4) Validation page
      await page.goto('/#/command-center/validation')
      await expect(page.getByRole('heading', { name: /数据校验/ })).toBeVisible()
      await shot(page, 'validation', vp.name)

      // No unexpected console errors across the navigated pages.
      expect(consoleErrors, `unexpected console errors @ ${vp.name}px`).toEqual([])
    })
  }
})
