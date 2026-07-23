import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { test, expect } from './helpers'

// ESM context (package.json "type": "module"): derive __dirname from the module URL.
const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const flagPath = path.resolve(__dirname, '.e2e-skip')
const skipReason = fs.existsSync(flagPath) ? fs.readFileSync(flagPath, 'utf8') : ''
test.skip(!!skipReason, `E2E skipped: ${skipReason}`)

test('login and land on command-center dashboard', async ({ page, consoleErrors }) => {
  // E2E credentials MUST come from the environment — never hardcode accounts,
  // passwords, or backend addresses here.
  await page.goto('/')

  // Should redirect unauthenticated users to the login screen.
  await expect(page.getByText('统一登录')).toBeVisible()

  await page.getByLabel('用户名').fill(process.env.E2E_USER!)
  await page.getByLabel('密码').fill(process.env.E2E_PASSWORD!)
  await page.getByRole('button', { name: /登\s*录/ }).click()

  // After login, hash router lands on the dashboard.
  await expect(page).toHaveURL(/#\/command-center\/dashboard/)
  await expect(page.getByRole('heading', { name: /指挥台 · 仪表盘/ })).toBeVisible()

  // The five-domain navigation must be visible and clickable.
  await expect(page.getByText('资产运营')).toBeVisible()
  await expect(page.getByText('协同中心')).toBeVisible()
  await expect(page.getByText('洞察报告')).toBeVisible()
  await expect(page.getByText('系统治理')).toBeVisible()

  // No unexpected console errors on the dashboard.
  expect(consoleErrors, 'unexpected console errors on dashboard').toEqual([])
})
