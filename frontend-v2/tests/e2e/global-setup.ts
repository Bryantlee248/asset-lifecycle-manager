import { chromium } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// ESM context (package.json "type": "module"): __dirname is not defined, so we
// derive it from the module URL. This must run before any __dirname usage.
const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// Global setup: detect whether the E2E environment is actually runnable.
// We write a tiny flag file that each spec reads to skip *cleanly* (no crash)
// when there is no browser installed or no E2E credentials supplied.
//
// Credentials are ALWAYS read from the environment (E2E_USER / E2E_PASSWORD);
// nothing is hardcoded here.
export default async function globalSetup() {
  const reasons: string[] = []

  if (!process.env.E2E_USER || !process.env.E2E_PASSWORD) {
    reasons.push('no-credentials')
  }

  try {
    if (!fs.existsSync(chromium.executablePath())) {
      reasons.push('browser-missing')
    }
  } catch {
    reasons.push('browser-missing')
  }

  // Always write the flag (empty string means "run"). We never delete files
  // here to stay compatible with restrictive sandbox file policies.
  const flag = path.resolve(__dirname, '.e2e-skip')
  fs.writeFileSync(flag, reasons.join(','))
}
