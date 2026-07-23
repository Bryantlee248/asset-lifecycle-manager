import { beforeEach, vi } from 'vitest'

// Unit test environment setup (happy-dom).
beforeEach(() => {
  localStorage.clear()
  vi.stubGlobal('fetch', vi.fn())
})
