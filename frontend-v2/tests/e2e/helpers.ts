import { test as base, expect } from '@playwright/test'

export type ConsoleFixtures = {
  consoleErrors: string[]
}

// Captures browser console errors and uncaught page errors so specs can assert
// the app loads and navigates without runtime errors (target: 0 acceptable).
export const test = base.extend<ConsoleFixtures>({
  consoleErrors: async ({ page }, use) => {
    const errors: string[] = []
    const onConsole = (msg: { type: () => string; text: () => string }) => {
      if (msg.type() === 'error') errors.push(msg.text())
    }
    const onPageError = (err: Error) => errors.push(`pageerror: ${err.message}`)
    page.on('console', onConsole)
    page.on('pageerror', onPageError)
    await use(errors)
  },
})

export { expect }
