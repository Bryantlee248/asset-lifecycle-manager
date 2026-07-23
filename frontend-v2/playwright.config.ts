import { defineConfig, devices } from '@playwright/test'

// E2E base URL is taken from the environment so QA can point at any deployed
// preview. We never hardcode the backend (8000) as the E2E target.
// globalSetup writes a flag file so specs skip cleanly when the browser or
// credentials are unavailable (no hard crash on missing environment).
export default defineConfig({
  testDir: 'tests/e2e',
  globalSetup: './tests/e2e/global-setup.ts',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:5173',
    headless: true,
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
